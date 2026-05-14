"""Scheduler — pluggable guest "operating system" inside a VM.

The :class:`Scheduler` is the brain of every VM: it admits the
processes that run on the VM (allocating each one's RAM from the VM's
pool — see :attr:`cloudy.models.Daemon.ram`) and decides which
process's threads get CPU time, and for how long. Subclass it when your
research question is about scheduling policies (time-share, priority,
fair-share, gang scheduling, ...) or in-guest admission.

A scheduler is constructed without a VM — the user passes an instance::

    vm = sim.create(VM, name='Web', cpu=1, ram=1024, scheduler=TimeShared())

The VM's ``__post_init__`` then calls ``attach`` to bind the scheduler
to it. After that, ``self.vm`` / ``self.clock`` / ``self.event_queue``
are available (the mechanics are in :class:`cloudy.core.Bound`).
Override ``attach`` only if your scheduler needs setup at bind time
that reads ``vm``.

To add your own scheduler — minimal version
-----------------------------------------------
For most research questions you only need to decide *how cycles are
divided among running processes*. Override :meth:`Scheduler.share` and
the base class handles everything else (per-process start/stop events,
thread-to-core mapping, and termination bookkeeping)::

    class FCFSScheduler(Scheduler):
        def share(self, processes, cores_cycles):
            # The first process gets every cycle; the rest wait.
            if not processes:
                return []
            return [list(cores_cycles)] + [[0] * len(cores_cycles)
                                           for _ in processes[1:]]

The reference implementation :class:`TimeShared` is itself a
:meth:`share`-only override. For full control of the resume loop (e.g.
inserting your own pre/post hooks), override :meth:`resume` directly —
the contract is documented on that method.

For copy-pasteable starters, see ``examples/custom_scheduler.py``.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Iterator

from cloudy import models
from cloudy.core import Bound


@dataclass(kw_only=True, eq=False)
class Scheduler(Bound['models.VM'], ABC):
    """Base class for VM-internal CPU schedulers.

    A :class:`Scheduler` owns the processes running inside a single VM
    and decides which thread of which process gets which core's cycles
    each simulation step.

    Custom schedulers normally override :meth:`share` only — the
    framework handles event publishing, thread-to-core drain, and
    terminate bookkeeping in :meth:`resume`. The VM this scheduler runs
    in is :attr:`vm` (set by the framework when :class:`cloudy.models.VM`
    calls :meth:`attach` — see :class:`cloudy.core.Bound`); ``self.clock``
    and ``self.event_queue`` come from there too.
    """

    @property
    def vm(self) -> models.VM:
        """The VM this scheduler is bound to (alias for :attr:`Bound.owner`)."""
        return self.owner

    def __post_init__(self) -> None:
        # Processes currently scheduled and running.
        self._running_processes: list[models.Daemon] = []
        # Processes already resumed at least once; used to fire per-process
        # ``<class>.start`` events on first dispatch.
        self._started_processes: set[models.Daemon] = set()

    def attach(self, vm: models.VM) -> None:
        super().attach(vm)
        # RAM the guest OS has left to hand out to processes. Starts at
        # the VM's full pool; :meth:`schedule` draws it down, :meth:`terminate`
        # and :meth:`reset` give it back.
        self._free_ram: int = vm.ram

    @property
    def free_ram(self) -> int:
        """RAM the guest OS has not yet allocated to processes, in
        :attr:`cloudy.models.VM.ram` units. Read it from a custom
        :meth:`schedule` override."""
        return self._free_ram

    def __iter__(self) -> Iterator[models.Daemon]:
        """Iterate over the running processes."""
        return iter(self._running_processes)

    def __len__(self) -> int:
        """Number of running processes."""
        return len(self._running_processes)

    def __contains__(self, process: models.Daemon) -> bool:
        """``True`` if the given process is currently scheduled."""
        return process in self._running_processes

    def schedule(self, processes: list[models.Daemon]) -> list[bool]:
        """Admit the given processes onto this VM.

        A process is admitted only if its
        :attr:`~cloudy.models.Daemon.ram` fits in the VM's remaining
        RAM — the guest OS allocates RAM out of the VM's pool. The RAM
        is reclaimed when the process stops (see :meth:`terminate`) or
        the VM is deactivated (see :meth:`reset`). Override to add other
        admission rules — a process cap, per-tenant limits, … — calling
        ``super().schedule(...)`` for the RAM check.

        Parameters
        ----------
        processes : list[Daemon]
            Processes to schedule.

        Returns
        -------
        list[bool]
            One element per input process: ``True`` if it was admitted
            (and is now running), ``False`` if it was turned away (and
            not scheduled).
        """
        results: list[bool] = []
        for process in processes:
            if process.ram > self._free_ram:
                results.append(False)
                continue
            self._free_ram -= process.ram
            self._running_processes.append(process)
            results.append(True)
        return results

    def terminate(self, processes: list[models.Daemon]) -> Scheduler:
        """Remove the given processes from the running set, freeing their RAM.

        Returns the scheduler for chaining. The framework calls this
        for processes that finish on their own (see :meth:`resume`);
        call it yourself only if your scheduler can cancel a process.
        """
        for process in processes:
            self._running_processes.remove(process)
            self._free_ram += process.ram
        return self

    def reset(self) -> Scheduler:
        """Reset to the empty initial state — drop every process, the
        per-process start bookkeeping, and reclaim all allocated RAM.
        Called by :meth:`cloudy.models.VM.deactivate` when the VM is
        deallocated. Returns the scheduler for chaining."""
        self._running_processes.clear()
        self._started_processes.clear()
        self._free_ram = self.vm.ram
        return self

    def share(self, processes: list[models.Daemon], cores_cycles: list[int]) -> list[list[int]]:
        """Decide how the available cycles are divided among the running processes.

        This is the *one* hook a custom scheduler usually overrides. The
        framework calls it once per simulation step and uses the returned
        per-process per-core budget to drive each process's threads.

        Parameters
        ----------
        processes : list[Daemon]
            The running processes in iteration order. Inspect them if
            your policy depends on per-process state (priority,
            deadline, ...).
        cores_cycles : list[int]
            Total cycles available on each core for this step.

        Returns
        -------
        list[list[int]]
            Per-process per-core cycle allocation. The outer list is
            parallel to ``processes``; each inner list is parallel to
            ``cores_cycles``. Shares need not sum to the totals —
            leftover cycles are simply unused.
        """
        raise NotImplementedError('Subclasses must override share() (preferred) or resume().')

    def resume(self, cpu: tuple[int, ...], duration: int | float) -> list[int]:
        """Run the scheduler for one simulation step.

        Among the three policies' ``resume`` methods this is the leaf:
        it runs *inside* a VM, so the hypervisor passes the per-core
        cycle rates that VM was granted, and it returns the cycles
        actually consumed on each of those cores.

        Default implementation: ask :meth:`share` for the per-process
        cycle budget, then drain each process's share into its threads
        round-robin. Per-class start/stop events fire automatically as
        processes appear and finish.

        Override this directly if you need to bypass the default loop —
        e.g. to insert pre/post hooks, or implement multi-pass
        scheduling. Most schedulers should override :meth:`share` instead.

        Parameters
        ----------
        cpu : tuple[int, ...]
            Cycles per simulation time unit per core, for the cores this
            VM was allocated.
        duration : int | float
            How many simulation time units may run uninterrupted.

        Returns
        -------
        list[int]
            Cycles actually consumed on each core, parallel to ``cpu``.
        """
        processes: list[models.Daemon] = list(self._running_processes)
        if not processes:
            return [0 for _ in cpu]

        cores_cycles: list[int] = [int(core * duration) for core in cpu]
        per_process_shares: list[list[int]] = self.share(processes, cores_cycles)

        consumed_cycles: list[int] = [0 for _ in cpu]
        stopped_processes: list[models.Daemon] = []

        for process, share in zip(processes, per_process_shares):
            # A process stays unstarted until it actually receives cycles.
            # This makes FCFS-style schedulers work without surgery:
            # processes whose share is all zeros (queued, not yet running)
            # don't tick and don't fire ``start`` events.
            if process not in self._started_processes and not any(share):
                continue

            if process not in self._started_processes:
                self._started_processes.add(process)
                self.event_queue.publish(f'{type(process).__name__.lower()}.start', self.clock.now, self.vm, process)

            process.tick()

            # Drain this process's share into its threads round-robin. The
            # thread-to-core mapping is the framework's decision; the
            # process only exposes per-thread consume primitives.
            available_cycles: list[int] = list(share)
            num_threads: int = process.num_threads
            thread_idx: int = 0
            for core_idx in range(min(len(cpu), num_threads)):
                while available_cycles[core_idx] > 0 and not process.is_stopped():
                    consumed: int = process.consume(thread_idx, available_cycles[core_idx])
                    available_cycles[core_idx] -= consumed
                    consumed_cycles[core_idx] += consumed
                    thread_idx = (thread_idx + 1) % num_threads

            if process.is_stopped():
                stopped_processes.append(process)

        # Terminate finished processes and emit ``<class>.stop`` events.
        for stopped_process in stopped_processes:
            self.terminate([stopped_process])
            self.event_queue.publish(f'{type(stopped_process).__name__.lower()}.stop', self.clock.now, self.vm, stopped_process)

        return consumed_cycles

    def is_empty(self) -> bool:
        """``True`` when no processes are currently running."""
        return not self._running_processes

    def has_finite_process(self) -> bool:
        """``True`` when at least one running process is finite — i.e.
        has a bounded cycle budget (an :class:`~cloudy.models.App`).
        ``False`` when the scheduler is idle or runs only infinite
        :class:`~cloudy.models.Daemon` s.

        The framework's ``Simulation`` engine uses this to tell whether
        a no-``duration`` run can still make progress, without having to
        enumerate processes or know the App/Daemon distinction itself —
        that distinction lives in the scheduler, which is the layer that
        manages processes.
        """
        return any(isinstance(p, models.App) for p in self._running_processes)


@dataclass(kw_only=True, eq=False)
class TimeShared(Scheduler):
    """A round-robin time-sharing CPU scheduler.

    Divides every core's cycle budget evenly across the running
    processes; when the total does not divide cleanly, the residue
    cycles go to the processes at the head of a rotation that advances
    by one slot every step, so over time every process receives the
    same average share.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        # Head of the residue rotation. Advances one slot per step so
        # the bonus cycle does not always go to the same process.
        self._rotation: int = 0

    def share(self, processes: list[models.Daemon], cores_cycles: list[int]) -> list[list[int]]:
        """Equal floor share; the remainder is distributed using the rotation."""
        n: int = len(processes)
        base: list[int] = [c // n for c in cores_cycles]
        residue: list[int] = [c - b * n for c, b in zip(cores_cycles, base)]

        shares: list[list[int]] = [list(base) for _ in range(n)]
        for c_idx, r in enumerate(residue):
            for offset in range(r):
                shares[(offset + self._rotation) % n][c_idx] += 1

        self._rotation = (self._rotation - 1) % n
        return shares
