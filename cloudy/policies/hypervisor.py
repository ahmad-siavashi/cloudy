"""Hypervisor — pluggable algorithm for VM management on a host.

The :class:`Hypervisor` is the brain of every PM: it decides whether a
new VM fits, reserves the cores/RAM it needs, and runs each guest VM's
scheduler at every simulation step. Subclass it when your research is
about resource management on a host (space-share, oversubscription,
NUMA-aware allocation, ...).

Resource note: ``vm.cpu`` / ``vm.ram`` are only numbers on the model; a
hypervisor decides what they mean. With the default :class:`SpaceShared`,
CPU is the one resource it actively shares (the
:class:`cloudy.policies.Scheduler` divides the cycle rate among
processes, so CPU contention and oversubscription are expressible). RAM
is an admission capacity: it is reserved at placement and held for the
VM's lifetime, and the guest's own :class:`cloudy.policies.Scheduler`
then sub-allocates it to its processes. A custom :class:`Hypervisor`
may model overcommit, OOM, and similar effects. See :mod:`cloudy.models`
for the full picture.

To add your own hypervisor
------------------------------
1. Subclass :class:`Hypervisor`.
2. Implement :meth:`Hypervisor.has_capacity`, :meth:`Hypervisor.allocate`,
   :meth:`Hypervisor.deallocate`, and :meth:`Hypervisor.resume`.
3. Pass your class as the ``hypervisor=`` argument when constructing a
   :class:`cloudy.models.PM`.

The reference implementation :class:`SpaceShared` is the simplest
example in the tree. Subclass *it* to change only admission control
(:meth:`~SpaceShared.has_capacity`) or core selection
(:meth:`~SpaceShared.select_cores`). For a starter you can copy and
paste, see ``examples/custom_hypervisor.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator

from cloudy import models
from cloudy.core import Bound


@dataclass(kw_only=True, eq=False)
class Hypervisor(Bound['models.PM'], ABC):
    """Abstract base class for host-level VM managers.

    Constructed without a host; the host is set when
    :class:`cloudy.models.PM`'s ``__post_init__`` calls :meth:`attach`
    (see :class:`cloudy.core.Bound`), after which ``self.host`` /
    ``self.clock`` / ``self.event_queue`` are available. Override
    :meth:`attach` if your subclass needs binding-time setup that reads
    ``host.cpu`` / ``host.ram``; call ``super().attach(host)`` first.
    """

    @property
    def host(self) -> models.PM:
        """The PM this hypervisor is bound to (alias for :attr:`Bound.owner`)."""
        return self.owner

    def __post_init__(self) -> None:
        # Allocated VMs.
        self._guests: list[models.VM] = []

    def __contains__(self, vm: models.VM) -> bool:
        """``True`` if the VM is currently allocated on this host."""
        return vm in self._guests

    def __iter__(self) -> Iterator[models.VM]:
        """Iterate over allocated VMs."""
        return iter(self._guests)

    def __len__(self) -> int:
        """Number of currently allocated VMs."""
        return len(self._guests)

    def is_empty(self) -> bool:
        """``True`` when no VMs are allocated on this host."""
        return not self._guests

    @property
    def cpu_utilisation(self) -> float:
        """Fraction of this host's CPU capacity in use, in ``[0, 1]``.

        Sampled each :data:`cloudy.Topic.SIM_TICK` by the
        :class:`cloudy.metrics.Energy` tracker and fed to the host's
        :class:`cloudy.power.PowerModel`. The base implementation reports
        the *allocated*-core fraction (``Σ vm.cpu / num_cores``, clamped
        to 1); :class:`SpaceShared` overrides it with the *consumed*-cycle
        fraction from the last :meth:`resume`, which is what you usually
        want for energy work.
        """
        num_cores: int = len(self.host.cpu)
        if num_cores == 0:
            return 0.0
        return min(1.0, sum(vm.cpu for vm in self._guests) / num_cores)

    @abstractmethod
    def has_capacity(self, vm: models.VM) -> tuple[bool, bool]:
        """Whether the host has enough free CPU and RAM for this VM.

        Returns one boolean *per resource* rather than a single verdict,
        so a placement policy can react to *which* resource is short.
        For the common "does it fit at all?" check, call ``all(...)`` on
        the result.

        Parameters
        ----------
        vm : VM
            VM to check against the host's free resources.

        Returns
        -------
        tuple[bool, bool]
            ``(has_cpu, has_ram)`` — each ``True`` if there is enough of
            that resource for the VM, otherwise ``False``.
        """

    @abstractmethod
    def allocate(self, vms: list[models.VM]) -> list[bool]:
        """Reserve host resources for a batch of VMs (claim cores/RAM, add
        to the guest list).

        Host-side bookkeeping only — the VM *lifecycle* hooks
        (:meth:`cloudy.models.VM.activate` / :meth:`~cloudy.models.VM.deactivate`)
        are fired by the :class:`cloudy.policies.Placement` around this
        call, **not** here, so this method is equally usable for a fresh
        placement and for the receiving side of a migration.

        Parameters
        ----------
        vms : list[VM]
            VMs to allocate.

        Returns
        -------
        list[bool]
            One element per input VM, indicating whether it was placed.
        """

    @abstractmethod
    def deallocate(self, vms: list[models.VM]) -> list[bool]:
        """Release host resources held by a batch of VMs (free cores/RAM,
        drop from the guest list).

        Host-side bookkeeping only — like :meth:`allocate`, it does not
        touch the guest itself (no :meth:`cloudy.models.VM.deactivate`),
        so :meth:`cloudy.policies.Placement.migrate_vm` can reuse it to
        release a VM from its source host without tearing the guest down.

        Parameters
        ----------
        vms : list[VM]
            VMs to deallocate.

        Returns
        -------
        list[bool]
            One element per input VM, indicating whether it was released.
        """

    @abstractmethod
    def resume(self, duration: int | float) -> None:
        """Drive each guest VM's scheduler for ``duration`` time units.

        Parameters
        ----------
        duration : int | float
            Simulation time units to run.
        """


@dataclass(kw_only=True, eq=False)
class SpaceShared(Hypervisor):
    """A space-shared hypervisor: each VM gets dedicated cores and RAM."""

    def attach(self, host: models.PM) -> None:
        super().attach(host)
        self._free_cores: set[int] = set(range(len(host.cpu)))
        self._vm_cores: dict[models.VM, set[int]] = {}
        self._free_ram: int = host.ram
        # CPU work done in the most recent resume(), and the cycles that
        # were available — their ratio is :attr:`cpu_utilisation`.
        self._consumed_cycles: int = 0
        self._capacity_cycles: int | float = 0

    # -- Public accessors / hooks for subclasses -----------------------------
    #
    # These let custom hypervisors (admission control, oversubscription
    # checks, NUMA-aware pinning, …) inspect free capacity or steer core
    # selection without touching the private ``_free_*`` state. See
    # ``examples/custom_hypervisor.py`` for usage.

    @property
    def free_cores(self) -> int:
        """Number of currently unallocated cores."""
        return len(self._free_cores)

    @property
    def free_ram(self) -> int:
        """Currently unallocated RAM, in the same units as ``host.ram``."""
        return self._free_ram

    @property
    def cpu_utilisation(self) -> float:
        """See :attr:`Hypervisor.cpu_utilisation` — here, the fraction of the
        host's cycle capacity actually consumed in the last :meth:`resume`."""
        if not self._capacity_cycles:
            return 0.0
        return self._consumed_cycles / self._capacity_cycles

    def select_cores(self, vm: models.VM) -> set[int]:
        """Pick which of the host's free cores to give ``vm``.

        The hook for heterogeneous hosts: ``host.cpu`` may list different
        per-core rates, and this method decides which ``vm.cpu`` of the
        free cores the VM gets (and hence how fast it runs). The default
        takes the lowest-numbered free cores. Override for NUMA-aware or
        performance-aware pinning. (If your override can fail even when
        :meth:`has_capacity` reports ``True``, override
        :meth:`has_capacity` to match.)
        """
        return set(sorted(self._free_cores)[:vm.cpu])

    def has_capacity(self, vm: models.VM) -> tuple[bool, bool]:
        """See :meth:`Hypervisor.has_capacity`."""
        return self.free_cores >= vm.cpu, self.free_ram >= vm.ram

    def allocate(self, vms: list[models.VM]) -> list[bool]:
        """See :meth:`Hypervisor.allocate`."""
        results: list[bool] = []
        for vm in vms:
            if not all(self.has_capacity(vm)):
                results.append(False)
                continue
            cores: set[int] = self.select_cores(vm)
            self._free_cores -= cores
            self._vm_cores[vm] = cores
            self._free_ram -= vm.ram
            self._guests.append(vm)
            results.append(True)
        return results

    def deallocate(self, vms: list[models.VM]) -> list[bool]:
        """See :meth:`Hypervisor.deallocate`."""
        results: list[bool] = []
        for vm in vms:
            if vm not in self:
                results.append(False)
                continue
            self._free_cores.update(self._vm_cores.pop(vm))
            self._free_ram += vm.ram
            self._guests.remove(vm)
            results.append(True)
        return results

    def resume(self, duration: int | float) -> None:
        """See :meth:`Hypervisor.resume`. Also records, for :attr:`cpu_utilisation`,
        how many of the host's cycles were actually consumed this round."""
        # Every VM in self._guests was placed via allocate(), so it is
        # still allocated — no need to re-check.
        consumed: int = 0
        for vm in self:
            core_speeds: list[int] = [self.host.cpu[core] for core in self._vm_cores[vm]]
            consumed += sum(vm.scheduler.resume(core_speeds, duration))
        self._consumed_cycles = consumed
        self._capacity_cycles = sum(self.host.cpu) * duration
