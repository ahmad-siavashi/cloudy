"""The models of the simulated environment.

Most users create these via :meth:`cloudy.Simulation.create`, which
passes the simulation's :class:`Clock` and :class:`EventQueue` into
each :class:`SimObject` (``VM``, ``PM``, ``DataCenter``) automatically.
Direct construction also works, as long as you pass ``clock=`` and
``event_queue=`` to those classes yourself.

Cloudy models one cluster level: a :class:`DataCenter` holds a list of
:class:`PM` hosts and a :class:`Placement` policy that maps incoming
:class:`VM` requests onto those hosts. Each :class:`VM` runs a
:class:`Scheduler` that divides the host's cycles among the processes
(:class:`Daemon` / :class:`App` instances) running on it.

Resource model
--------------
The model classes only *carry* :attr:`VM.cpu` / :attr:`VM.ram` (and
:attr:`PM.cpu` / ``ram``) as plain data. What those numbers *mean* is
decided by the policies: a custom :class:`Scheduler` /
:class:`Hypervisor` / :class:`Placement` interprets them however a
study needs. With the default policies:

- **CPU is the dynamic resource.** Work is measured in *cycles*
  (:attr:`App.length`). A host's cores supply cycles per time unit
  (:attr:`PM.cpu`). The :class:`Scheduler` shares the cycle rate among
  processes, and a process *finishes* when its budget is spent. This
  makes CPU contention and oversubscription expressible.
- **RAM is allocated in two layers.** The default
  :class:`~cloudy.policies.SpaceShared` hypervisor reserves :attr:`VM.ram`
  on the host at placement and holds it for the VM's lifetime. *Inside*
  the VM, the :class:`Scheduler` — the guest "operating system" — gives
  that RAM to the processes it runs (:attr:`Daemon.ram`) and rejects
  one that does not fit. A process's footprint is the constant it
  declares; there is no time-varying RAM "load".

CPU quantities are *host-relative*: a "vCPU" (:attr:`VM.cpu`) is simply
one of the host's cores at the host's speed, not a normalised unit.
:attr:`App.length` is in cycles, not seconds. GPUs / accelerators are
not modelled. :mod:`cloudy.network` is a separate, unintegrated add-on:
it is not a VM/PM attribute, and the workload generates no traffic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Iterator

from cloudy.core import Clock, EventQueue
from cloudy.policies import Hypervisor, Placement, Scheduler
from cloudy.power import PowerModel, ZeroPower


@dataclass(kw_only=True, eq=False)
class SimObject:
    """Base for models that live inside a running simulation.

    A :class:`SimObject` carries the simulation's :class:`Clock` and
    :class:`EventQueue`, so it can read the current time and publish
    events. :meth:`Simulation.create` checks ``issubclass(cls, SimObject)``
    and injects those two automatically. Plain data classes that don't
    need them (e.g. ``Request``) don't inherit from :class:`SimObject`
    and are constructed directly.
    """

    clock: Final[Clock]
    event_queue: Final[EventQueue]


# Every model class declares ``eq=False`` so the dataclass decorator
# leaves ``__eq__`` and ``__hash__`` alone. The defaults inherited from
# ``object`` give us identity-based equality and identity-based hashing,
# which is what model instances want — two different VMs with the same
# fields are *not* the same VM.


@dataclass(kw_only=True, eq=False)
class Daemon:
    """A schedulable process with no inherent lifetime.

    A :class:`Daemon` is the base of every entity the VM-level
    :class:`Scheduler` operates on. By default it has one thread,
    absorbs whatever cycles the scheduler grants, runs forever, and
    does nothing each :meth:`tick`. Subclasses override the relevant
    methods — :class:`App` adds a finite cycle budget.

    A bare :class:`Daemon` never finishes, so a run in which only
    ``Daemon`` s remain (and the event queue is empty) has nothing left
    that will ever change. :meth:`Simulation.run` with no ``duration``
    detects that and raises a clear error — use ``run(duration=...)``
    when you model an infinite workload (a web server, a background
    service, …).

    Attributes
    ----------
    name : str
        Name of the process.
    ram : int
        RAM this process needs while it runs, in the same units as
        :attr:`VM.ram`. When the process is scheduled, the VM's
        in-guest :class:`Scheduler` (its "operating system") allocates
        this out of the VM's RAM pool and reclaims it when the process
        stops or the VM is deactivated; a process that does not fit in
        the VM's free RAM is turned away (see
        :meth:`cloudy.policies.Scheduler.schedule`). Defaults to ``0`` —
        "RAM-free", always admitted.
    """

    name: Final[str]
    ram: Final[int] = 0

    @property
    def num_threads(self) -> int:
        """Number of threads this process exposes to the scheduler."""
        return 1

    def tick(self) -> None:
        """Hook called by the scheduler once per resume round, before
        any cycles are consumed. The default is a no-op.
        """
        return

    def consume(self, thread_idx: int, max_cycles: int) -> int:
        """Absorb up to ``max_cycles`` of work on the given thread.

        Daemons absorb every cycle they are offered without depleting a
        budget. :class:`App` overrides this to track per-thread cycles.
        """
        return max_cycles

    def restart(self) -> Daemon:
        """Reset internal state. The default daemon has no state."""
        return self

    def is_stopped(self) -> bool:
        """``True`` when this process has no more work to do.

        The default daemon runs forever. Subclasses override.
        """
        return False


@dataclass(kw_only=True, eq=False)
class App(Daemon):
    """A finite process with a per-thread cycle budget.

    Stops once every thread has consumed its full ``length``. Inherits
    the optional :attr:`Daemon.ram` footprint.

    Attributes
    ----------
    length : tuple[int, ...]
        Length of each thread, in *cycles* — a hardware-relative unit. A
        thread of ``length=20`` finishes in 10 time units on a core that
        runs 2 cycles/unit, in 5 on a core that runs 4. To express "a
        10-time-unit job" you must know the core rate it'll run on.
    """

    length: Final[tuple[int, ...]]

    def __post_init__(self) -> None:
        # Remaining cycles per thread.
        self._remained: list[int] = list(self.length)

    @property
    def num_threads(self) -> int:
        return len(self._remained)

    def restart(self) -> App:
        """Reset the remaining cycles to the original ``length``."""
        self._remained = list(self.length)
        return self

    def consume(self, thread_idx: int, max_cycles: int) -> int:
        """Consume up to ``max_cycles`` from the given thread.

        Parameters
        ----------
        thread_idx : int
            Index of the thread to advance.
        max_cycles : int
            Upper bound on cycles to deduct.

        Returns
        -------
        int
            Cycles actually consumed (0 if the thread is already done).
        """
        cycles: int = min(max_cycles, self._remained[thread_idx])
        self._remained[thread_idx] -= cycles
        return cycles

    def is_stopped(self) -> bool:
        return not any(self._remained)


@dataclass(kw_only=True, eq=False)
class VM(SimObject):
    """A virtual machine.

    Whether a VM is currently allocated, and where, is recorded by the
    placement (``vm in datacenter.placement``, ``datacenter.placement[vm]``)
    and the host's hypervisor (``vm in pm.hypervisor``) — those are the
    authoritative sources; the VM itself doesn't track it.

    Attributes
    ----------
    name : str
        Name of the virtual machine.
    cpu : int
        Number of cores requested — a *count*, not a speed. The VM's
        compute capacity is this count times the host's per-core rate,
        so it is not a portable performance figure: the same VM runs
        faster on a faster host.
    ram : int
        Amount of RAM the VM requests. The default
        :class:`~cloudy.policies.SpaceShared` hypervisor reserves it on
        the host for the VM's lifetime and uses it for admission.
        *Inside* the VM, the :class:`Scheduler` (the guest OS) gives that
        RAM to the processes running on it (see :attr:`Daemon.ram`). A
        custom
        :class:`~cloudy.policies.Hypervisor` may interpret ``ram``
        however it likes (overcommit, …).
    scheduler : Scheduler
        The scheduling policy instance. Bound via
        :meth:`Scheduler.attach` in :meth:`__post_init__`.
    tenant : str, optional
        Identifier of the tenant this VM belongs to, for multi-tenant
        studies. Purely a *label*: a custom :class:`Placement` /
        :class:`Scheduler` / :class:`Hypervisor` or :class:`Tracker` can
        read ``vm.tenant`` to make tenant-aware decisions or break stats
        down per tenant, but the framework enforces no quotas, fairness,
        or isolation. ``None`` (default) means "unset / single-tenant".
    """

    name: Final[str]
    cpu: Final[int]
    ram: Final[int]
    scheduler: Scheduler
    tenant: Final[str | None] = None

    def __post_init__(self) -> None:
        self.scheduler.attach(self)

    def run(self, process: Daemon | list[Daemon]) -> VM:
        """Schedule one or more processes on this VM.

        The single user-facing entry point for adding work to a VM:
        ``vm.run(my_app)`` or ``vm.run([app1, app2])``. A convenience
        wrapper around :meth:`Scheduler.schedule`; it ignores that
        method's per-process accept result and returns the VM for fluent
        chaining. Use ``vm.scheduler.schedule([...])`` directly if you
        need to know whether the scheduler accepted each process.

        May be called before the VM is placed (the usual case — you
        build the VM, attach its work, then wrap it in a :class:`Request`)
        *or* later from an event handler, to add work to a running VM.
        """
        processes: list[Daemon] = [process] if isinstance(process, Daemon) else list(process)
        self.scheduler.schedule(processes)
        return self

    def activate(self) -> VM:
        """Lifecycle hook the placement fires when this VM is *first*
        placed on a host — its "boot". Not fired on migration: a migrated
        VM keeps running and only changes host (see
        :meth:`cloudy.policies.Placement.migrate_vm`). The default does
        nothing; override to model boot behaviour. Returns the VM for
        chaining."""
        return self

    def deactivate(self) -> VM:
        """Lifecycle hook the placement fires when this VM is reclaimed
        (its work is done) — its "shutdown". Not fired on migration. The
        default resets the VM's scheduler (drops any running processes);
        override to model teardown behaviour, calling
        ``super().deactivate()``. Returns the VM for chaining."""
        self.scheduler.reset()
        return self


@dataclass(kw_only=True, eq=False)
class PM(SimObject):
    """A physical machine (host).

    Attributes
    ----------
    name : str
        Name of the physical machine.
    cpu : tuple[int, ...]
        Per-core cycle rates: ``cpu[i]`` is how many cycles core *i*
        runs each simulation time unit. The tuple's length is the core
        count; entries may differ (heterogeneous cores) — see
        :meth:`cloudy.policies.SpaceShared.select_cores`.
    ram : int
        Amount of RAM available for VM reservations.
    hypervisor : Hypervisor
        The host-management policy instance. Bound via
        :meth:`Hypervisor.attach` in :meth:`__post_init__`.
    power : PowerModel
        Per-host power model. Defaults to :class:`cloudy.power.ZeroPower`
        so runs that don't care about energy pay nothing extra. The
        :class:`cloudy.metrics.Energy` tracker integrates this over
        the run.
    """

    name: Final[str]
    cpu: Final[tuple[int, ...]]
    ram: Final[int]
    hypervisor: Hypervisor
    power: PowerModel = field(default_factory=ZeroPower)

    def __post_init__(self) -> None:
        self.hypervisor.attach(self)


@dataclass(kw_only=True, eq=False)
class DataCenter(SimObject):
    """A data center: a placement policy plus a list of hosts.

    A simulation has exactly one (``Simulation.datacenter``), and it is a
    *flat* list of hosts — there's no notion of zones, racks, regions,
    or internal topology.

    Attributes
    ----------
    name : str
        Name of the data center.
    hosts : list[PM]
        Physical machines under management.
    placement : Placement
        The placement policy instance. Bound via :meth:`Placement.attach`
        in :meth:`__post_init__`.
    """

    name: Final[str]
    placement: Placement
    hosts: Final[list[PM]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.placement.attach(self)

    # A data center reads as its collection of hosts: ``for pm in dc``,
    # ``pm in dc``, ``len(dc)`` — mirroring the list-like hypervisor /
    # scheduler and the dict-like placement. ``dc.hosts`` is still there
    # when you want the list itself.

    def __iter__(self) -> Iterator[PM]:
        """Iterate over the hosts in this data center."""
        return iter(self.hosts)

    def __contains__(self, host: PM) -> bool:
        """``True`` if the given host belongs to this data center."""
        return host in self.hosts

    def __len__(self) -> int:
        """Number of hosts in this data center."""
        return len(self.hosts)


@dataclass(kw_only=True, eq=False)
class Request:
    """A VM-allocation request that arrives at the data center.

    A request carries a fully-built :class:`VM` — with its
    :class:`Scheduler` and any work already attached via
    :meth:`VM.run` — and asks the placement to find it a host at time
    ``arrival``. Placement is instantaneous (no provisioning latency),
    and the verdict is final: a request that doesn't fit is *rejected*,
    not queued or retried.

    To react to acceptance or rejection, subscribe to
    :data:`cloudy.topics.REQUEST_ACCEPT` / ``REQUEST_REJECT`` on the
    simulation's event queue.

    Attributes
    ----------
    arrival : int | float
        Simulation time at which this request arrives.
    vm : VM
        Virtual machine to place.
    """

    arrival: Final[int | float]
    vm: Final[VM]
