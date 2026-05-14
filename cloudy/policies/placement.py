"""Placement — pluggable algorithm for placing VMs on hosts.

Given a batch of incoming VMs and the hosts available in the data
center, the :class:`Placement` decides which host each VM is placed on
(or that no host fits, so the VM is rejected). Each tick, it may also
move already-placed VMs (consolidation, load-balancing). Subclass it
when your research is about VM placement (first-fit, best-fit,
worst-fit, energy-aware, locality-aware, dynamic consolidation, ...).

To add your own placement — minimal version
-----------------------------------------------
For most research questions you only need to decide *which host a VM
should go to*. Override :meth:`Placement.select_host` and the base
class handles everything else (the host's hypervisor allocation, the
``vm.allocate`` / ``vm.deallocate`` events, and the ``vm → host`` map)::

    class RoundRobinPlacement(Placement):
        def __post_init__(self):
            super().__post_init__()
            self._next = 0

        def select_host(self, vm):
            hosts = self.datacenter.hosts
            for i in range(len(hosts)):
                host = hosts[(self._next + i) % len(hosts)]
                if all(host.hypervisor.has_capacity(vm)):
                    self._next = (self._next + i + 1) % len(hosts)
                    return host
            return None

The reference :class:`FirstFit` is a 3-line
:meth:`select_host` override. For full control of the allocate loop
(e.g. batching, two-phase commit), override :meth:`allocate` directly —
the contract is documented on that method.

For copy-pasteable starters, see ``examples/custom_placement.py``.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Iterator

from cloudy import models
from cloudy.core import Bound
from cloudy.topics import Topic


@dataclass(kw_only=True, eq=False)
class Placement(Bound['models.DataCenter'], ABC):
    """Base class for VM placement policies.

    Custom placements normally override :meth:`select_host` only — the
    framework's :meth:`allocate` and :meth:`deallocate` handle the
    hypervisor calls, the ``vm → host`` map, and the
    ``vm.allocate`` / ``vm.deallocate`` events. To also relocate running
    VMs, override :meth:`migrate` (the per-tick policy hook) and call
    :meth:`migrate_vm` (the mechanism).

    Constructed without a data center; the data center is set when
    :class:`cloudy.models.DataCenter`'s ``__post_init__`` calls
    :meth:`attach` (see :class:`cloudy.core.Bound`) — which also
    subscribes any ``@on``-decorated handlers the subclass defines.
    After that, ``self.datacenter`` / ``self.clock`` / ``self.event_queue``
    are available. Override ``attach`` for setup that reads the data
    center's hosts; call ``super().attach(datacenter)`` first.
    """

    @property
    def datacenter(self) -> models.DataCenter:
        """The data center this placement is bound to (alias for :attr:`Bound.owner`)."""
        return self.owner

    def __post_init__(self) -> None:
        # Mapping of placed VMs to their hosts.
        self._vm_pm: dict[models.VM, models.PM] = {}
        # In-flight timed migrations: vm → (target host, ticks of transfer
        # left). :meth:`advance_migrations` ticks these down each step and
        # commits each move when its timer hits zero.
        self._migrations: dict[models.VM, tuple[models.PM, int]] = {}

    def __getitem__(self, vm: models.VM) -> models.PM:
        """Host on which the given VM is placed."""
        return self._vm_pm[vm]

    def __setitem__(self, vm: models.VM, pm: models.PM) -> None:
        """Record that ``vm`` is placed on ``pm``."""
        self._vm_pm[vm] = pm

    def __delitem__(self, vm: models.VM) -> None:
        """Forget the placement record for ``vm``."""
        del self._vm_pm[vm]

    def __contains__(self, vm: models.VM) -> bool:
        """``True`` if the VM is currently placed."""
        return vm in self._vm_pm

    def __iter__(self) -> Iterator[models.VM]:
        """Iterate over the currently placed VMs."""
        return iter(self._vm_pm)

    def __len__(self) -> int:
        """Number of currently placed VMs."""
        return len(self._vm_pm)

    def is_empty(self) -> bool:
        """``True`` when no VMs are placed."""
        return len(self) == 0

    def select_host(self, vm: models.VM) -> models.PM | None:
        """Pick the host this VM should go to, or ``None`` to reject it.

        This is the *one* hook a custom placement usually overrides. The
        framework calls it once per arriving VM and uses the returned
        host to drive the hypervisor allocation and event emission.

        Parameters
        ----------
        vm : VM
            The VM to place.

        Returns
        -------
        PM or None
            A host with capacity for ``vm``, or ``None`` to reject the
            request. Re-checking ``host.hypervisor.has_capacity(vm)`` is
            the implementer's responsibility — the framework trusts the
            returned host.
        """
        raise NotImplementedError('Subclasses must override select_host() (preferred) or allocate().')

    def allocate(self, vms: list[models.VM]) -> list[bool]:
        """Place a batch of VMs on hosts.

        Default implementation: for each VM, ask :meth:`select_host`,
        delegate to that host's hypervisor, record the placement, and
        publish :data:`cloudy.Topic.VM_ALLOCATE`.

        Override directly only if you need batch behavior (two-phase
        commit, gang scheduling). Most placements should override
        :meth:`select_host` instead.

        Parameters
        ----------
        vms : list[VM]
            VMs to place.

        Returns
        -------
        list[bool]
            One element per input VM, indicating whether it was placed.
        """
        results: list[bool] = []
        for vm in vms:
            host: models.PM | None = self.select_host(vm)
            if host is None:
                results.append(False)
                continue
            placed: list[bool] = host.hypervisor.allocate([vm])
            results.extend(placed)
            if placed[0]:
                self[vm] = host
                vm.activate()                  # the VM "boots" — first placement only
                self.event_queue.publish(Topic.VM_ALLOCATE, self.clock.now, host, vm)
        return results

    def deallocate(self, vms: list[models.VM]) -> list[bool]:
        """Release a batch of VMs from their hosts.

        Pure framework code: looks up each VM's host, releases the
        hypervisor reservation, runs the VM's :meth:`~cloudy.models.VM.deactivate`
        teardown hook, drops the placement record, and publishes
        :data:`cloudy.Topic.VM_DEALLOCATE`. There is no per-policy
        decision to make here — custom placements rarely need to
        override this. (Relocating a *running* VM is :meth:`migrate_vm`,
        which does *not* deactivate it.)
        """
        results: list[bool] = []
        for vm in vms:
            host: models.PM = self[vm]
            results.extend(host.hypervisor.deallocate([vm]))
            vm.deactivate()                    # the VM "shuts down" — its work is done
            del self[vm]
            self._migrations.pop(vm, None)     # cancel any in-flight migration for it
            self.event_queue.publish(Topic.VM_DEALLOCATE, self.clock.now, host, vm)
        return results

    def resume(self, duration: int | float) -> None:
        """Drive every host's hypervisor for ``duration`` time units.

        Parameters
        ----------
        duration : int | float
            Simulation time units to run.
        """
        for host in self.datacenter.hosts:
            host.hypervisor.resume(duration)

    def pop_stopped(self) -> list[models.VM]:
        """Return placed VMs whose schedulers are now idle, for reclamation.

        Schedulers run inside :meth:`resume` (called by the engine
        immediately before this method on each tick boundary), and the
        scheduler's :meth:`is_empty` flips to ``True`` synchronously when
        its last process stops — *before* the engine has had a chance to
        dispatch any queued events. So scanning the placement directly
        here yields the right answer in the same tick the VM finishes,
        independent of clock resolution.

        Cloudy's convention: a VM whose work just finished frees its host
        at the same instant. CloudSim (and other broker-based simulators)
        model a small teardown latency instead — that is a separate
        modelling choice you can layer on with a custom :class:`Placement`.
        """
        return [vm for vm in self._vm_pm if vm.scheduler.is_empty()]

    def is_migrating(self, vm: models.VM) -> bool:
        """``True`` if a timed migration of ``vm`` is currently in flight
        (started, not yet committed)."""
        return vm in self._migrations

    def advance_migrations(self) -> int:
        """Step every in-flight timed migration by one tick; commit those
        whose transfer is done. Called by the engine each tick boundary,
        just before :meth:`migrate` — you don't call this yourself.

        Returns
        -------
        int
            The number of migrations committed this call.
        """
        committed: int = 0
        for vm, (target, left) in list(self._migrations.items()):
            if left > 1:
                self._migrations[vm] = (target, left - 1)
                continue
            del self._migrations[vm]
            if vm in self._vm_pm:                          # still placed (not reaped mid-transfer)
                committed += self._commit_migration(vm, target)
        return committed

    def migrate(self) -> int:
        """Re-balance / consolidate placed VMs — the migration *policy* hook.

        Called once per tick boundary by the engine, right after the
        schedulers run and after :meth:`advance_migrations` has completed
        any transfer that finished this tick (so utilisation and the
        placement map are current). The default does nothing; override it
        to inspect the data center and start moves with :meth:`migrate_vm`
        — passing a ``duration`` to model the memory-image transfer time.
        See ``examples/live_migration.py``.

        Returns
        -------
        int
            The number of migrations *started* this call (0 by default).
        """
        return 0

    def migrate_vm(self, vm: models.VM, target: models.PM, duration: int = 0) -> bool:
        """Move an already-placed VM to ``target`` — the migration *mechanism*.

        Host-side bookkeeping only: the source host releases the VM's
        reservation, ``target`` claims a new one, and the placement record
        is updated. The guest is **not** torn down — its scheduler,
        running processes, and their progress travel with the VM untouched
        (no :meth:`~cloudy.models.VM.activate` / :meth:`~cloudy.models.VM.deactivate`)
        — so this is a true live, no-downtime move; only the host changes.

        With ``duration <= 0`` (default) the move is immediate and
        publishes :data:`cloudy.Topic.VM_MIGRATE_DONE`. With ``duration > 0``
        it models a memory-image copy that takes that many ticks: a
        :data:`cloudy.Topic.VM_MIGRATE_START` fires now, the VM keeps
        running on its source host, and :meth:`advance_migrations` (called
        by the engine each tick) commits the move — publishing
        :data:`~cloudy.Topic.VM_MIGRATE_DONE` — when the timer runs out.

        Deciding *which* VM goes *where*, and how long the copy takes, is
        up to :meth:`migrate` — see ``examples/live_migration.py``.

        Parameters
        ----------
        vm : VM
            A currently-placed VM, not already migrating.
        target : PM
            The host to move it to.
        duration : int, optional
            Ticks the transfer takes. ``<= 0`` (default) means immediate.

        Returns
        -------
        bool
            ``True`` if the move was done (immediate) or started (timed);
            ``False`` if ``vm`` isn't placed, is already on ``target``, is
            already migrating, or ``target`` has no room for it.
        """
        if vm not in self._vm_pm or vm in self._migrations:
            return False
        source: models.PM = self._vm_pm[vm]
        if source is target or not all(target.hypervisor.has_capacity(vm)):
            return False
        if duration > 0:
            self._migrations[vm] = (target, duration)
            self.event_queue.publish(Topic.VM_MIGRATE_START, self.clock.now, source, target, vm)
            return True
        return bool(self._commit_migration(vm, target))

    def _commit_migration(self, vm: models.VM, target: models.PM) -> int:
        """Perform the actual host-to-host move now and publish
        :data:`cloudy.Topic.VM_MIGRATE_DONE`. Returns ``1`` on success,
        ``0`` if ``target`` no longer has room (the VM does not move)."""
        if not all(target.hypervisor.has_capacity(vm)):
            return 0
        source: models.PM = self._vm_pm[vm]
        source.hypervisor.deallocate([vm])                # release the source's cores/RAM
        placed: list[bool] = target.hypervisor.allocate([vm])   # reserve them on the target
        assert placed[0]                                  # capacity was just checked
        self[vm] = target
        self.event_queue.publish(Topic.VM_MIGRATE_DONE, self.clock.now, source, target, vm)
        return 1


@dataclass(kw_only=True, eq=False)
class FirstFit(Placement):
    """First-fit: each VM is placed on the first host that fits."""

    def select_host(self, vm: models.VM) -> models.PM | None:
        """Return the first host with capacity for ``vm``."""
        for host in self.datacenter.hosts:
            if all(host.hypervisor.has_capacity(vm)):
                return host
        return None
