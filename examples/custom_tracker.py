"""Write your own metrics tracker — a worked example.

A :class:`cloudy.Tracker` extends the default per-request bookkeeping
with custom metrics. Two extension points:

1. **The :func:`cloudy.on` decorator** — mark any method with
   ``@on(topic)`` and the framework subscribes it automatically. You
   do not need to override ``attach()`` in the common case.
2. :meth:`Tracker.report` returns a dict of fields that are merged into
   the :meth:`Simulation.report` result and printed on the same
   ``sim.report`` line as the built-in ``request.arrived`` /
   ``request.accepted`` / … counters.

Here we count the cumulative CPU cores allocated per host. Under
first-fit placement the early hosts are filled more than the later
ones, so the report shows a clear asymmetry.

Run with::

    python examples/custom_tracker.py
"""

from dataclasses import dataclass, field

from cloudy import App, DataCenter, PM, Request, Simulation, Topic, Tracker, VM, on
from cloudy.policies import FirstFit, SpaceShared, TimeShared


@dataclass
class UtilizationTracker(Tracker):
    """Tally cumulative CPU cores allocated to each host."""

    cpu_per_host: dict[str, int] = field(default_factory=dict)

    @on(Topic.VM_ALLOCATE)
    def _on_allocate(self, host, vm):
        self.cpu_per_host[host.name] = self.cpu_per_host.get(host.name, 0) + vm.cpu

    def report(self):
        return {f'alloc.{host}.cpu': cpu for host, cpu in self.cpu_per_host.items()}


# Three 2-core VMs, two 4-core hosts. FirstFit packs vm-1 and vm-2 onto
# pm-1 (4 of 4 cores), spills vm-3 onto pm-2 (2 of 4). The tracker reports
# alloc.pm-1.cpu=4, alloc.pm-2.cpu=2.
sim = Simulation(name='UtilDemo', tracker=UtilizationTracker())

vms = [sim.create(VM, name=f'vm-{i+1}', cpu=2, ram=512, scheduler=TimeShared()) for i in range(3)]
for vm in vms:
    vm.run(sim.create(App, name=f'{vm.name}-job', length=(1,)))

hosts = [sim.create(PM, name=f'pm-{i+1}', cpu=(1, 1, 1, 1), ram=2048, hypervisor=SpaceShared()) for i in range(2)]
sim.datacenter = sim.create(DataCenter, name='dc', hosts=hosts, placement=FirstFit())
sim.requests = [sim.create(Request, arrival=0, vm=vm) for vm in vms]

result = sim.run().report()

# The custom fields are merged into the result dict.
print(f'pm-1 packed: {result["alloc.pm-1.cpu"]} cores')
print(f'pm-2 packed: {result["alloc.pm-2.cpu"]} cores')
