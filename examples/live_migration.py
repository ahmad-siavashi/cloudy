"""Live VM migration — a worked example.

:meth:`cloudy.policies.Placement.migrate` runs once per tick (after the
schedulers). Override it to detect fragmentation and start migrations
with :meth:`~cloudy.policies.Placement.migrate_vm`. A migration changes
only the host: the guest's scheduler, processes, and their progress
move with the VM unchanged, so it is a true no-downtime migration. Pass
a ``duration`` and the framework models the memory copy: it emits
``vm.migrate.start`` now, keeps the VM running on its source host, and
commits the move (``vm.migrate.done``) ``duration`` ticks later. Here we
put a dynamic-consolidation policy on top of first-fit:

  * three single-core VMs arrive at t=0 onto two 2-core hosts: first-fit
    places the batch job and svc-1 on pm-1, and svc-2 on pm-2;
  * the batch job finishes (``app.stop … @5``), the simulator reclaims
    its VM (``vm.deallocate … batch @6``), and the cluster is now
    fragmented: one service on each host;
  * the policy migrates svc-1 to pm-2, sizing the copy from ``vm.ram``
    via a :class:`cloudy.network.Link`'s ``transmission_time``
    (``latency + bytes / bandwidth``): svc-1's 1 GB at 512 MB/tick takes
    2 ticks, so ``vm.migrate.start … @6`` (move begins) →
    ``vm.migrate.done … @8`` (move commits), with the VM running on pm-1
    in between;
  * pm-1 is now empty and ready to power down.

A small :class:`~cloudy.Tracker` counts migrations and each host's
final VM count, so the result appears on the standard ``sim.report``
line (``migrate.count=1``, ``host.pm-1.vms=0 host.pm-2.vms=2``).

``vm.ram`` is enough here, and storage is not involved, because only
*memory* moves between hosts: the VM's disk is on shared storage
(SAN/NFS), so it does not move. Memory bytes / bandwidth is the correct
first-order cost. The pre-copy refinements (re-sending pages dirtied
during the copy, and a brief stop-and-copy at the end) only multiply
this by a workload-dependent factor; for the rule "a bigger VM costs
more to move", ``vm.ram`` alone is enough.

Run with::

    python examples/live_migration.py
"""

import math
from dataclasses import dataclass

from cloudy import App, Daemon, DataCenter, PM, Request, Simulation, Topic, Tracker, VM, on
from cloudy.network import Link
from cloudy.policies import FirstFit, SpaceShared, TimeShared

# The migration link: 512 "MB" of memory copied per tick, zero setup
# latency. We only use transmission_time() — LINK_DELIVER models app
# traffic between VMs, not infrastructure transfers.
MIGRATION_NET = Link(name='migration-net', bandwidth=512, latency=0)


@dataclass
class Consolidation(Tracker):
    """Count migrations → ``migrate.count``, and each host's final VM count → ``host.<name>.vms``."""

    migrations: int = 0

    @on(Topic.VM_MIGRATE_DONE)
    def _on_migrate(self, _src, _dst, _vm):
        self.migrations += 1

    def report(self):
        counts = {f'host.{h.name}.vms': len(h.hypervisor) for h in self.simulation.datacenter.hosts}
        return {'migrate.count': self.migrations, **counts}


class ConsolidatingPlacement(FirstFit):
    """First-fit on arrival; each tick, fold a lonely VM onto a fuller host."""

    def migrate(self) -> int:
        if any(self.is_migrating(vm) for vm in self):       # one migration at a time keeps the demo tidy
            return 0
        for src in self.datacenter.hosts:
            guests = [vm for vm in self if self[vm] is src]
            if len(guests) != 1:
                continue
            vm = guests[0]
            for dst in self.datacenter.hosts:
                if dst is not src and all(dst.hypervisor.has_capacity(vm)):
                    # vm.ram ≈ the memory to copy (see the module docstring); at least 1 tick.
                    ticks = max(1, math.ceil(MIGRATION_NET.transmission_time(vm.ram)))
                    self.migrate_vm(vm, dst, duration=ticks)
                    return 1
        return 0


sim = Simulation(name='MigrateDemo', seed=42, tracker=Consolidation())

# A finite batch job + a service share pm-1; a second service spills onto
# pm-2 (pm-1's two cores are full).
batch = sim.create(VM, name='batch', cpu=1, ram=512, scheduler=TimeShared())
batch.run(sim.create(App, name='job', length=(10,)))                  # 10 cycles / 2 per tick → finishes at t=5
svc1 = sim.create(VM, name='svc-1', cpu=1, ram=1024, scheduler=TimeShared())   # 1 GB → 2-tick migration
svc1.run(Daemon(name='svc-1-daemon'))
svc2 = sim.create(VM, name='svc-2', cpu=1, ram=512, scheduler=TimeShared())
svc2.run(Daemon(name='svc-2-daemon'))

pm1 = sim.create(PM, name='pm-1', cpu=(2, 2), ram=2048, hypervisor=SpaceShared())
pm2 = sim.create(PM, name='pm-2', cpu=(2, 2), ram=2048, hypervisor=SpaceShared())
sim.datacenter = sim.create(DataCenter, name='dc', hosts=[pm1, pm2], placement=ConsolidatingPlacement())
sim.requests = [sim.create(Request, arrival=0, vm=vm) for vm in (batch, svc1, svc2)]

# Daemons never finish, so bound the run with a horizon.
sim.run(duration=12).report()
