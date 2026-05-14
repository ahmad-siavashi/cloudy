"""Write your own placement policy — a worked example.

A round-robin placement in seven lines: move a cursor forward through
the host list, wrapping around to the start, until a host with capacity
is found. Compare with :class:`cloudy.policies.FirstFit`, which always
places the VM on the first host that fits.

The framework handles the hypervisor allocation, the
``vm.allocate`` / ``vm.deallocate`` events, and the ``vm → host`` map.
We only override :meth:`Placement.select_host` to choose the host.

Run with::

    python examples/custom_placement.py
"""

from cloudy import App, DataCenter, PM, Request, Simulation, VM
from cloudy.policies import Placement, SpaceShared, TimeShared


class RoundRobinPlacement(Placement):
    """Distribute VMs round-robin across hosts."""

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


# Three small VMs, three roomy hosts. FirstFit would pack all three onto
# pm1; round-robin gives one to each: vm-1 → pm1, vm-2 → pm2, vm-3 → pm3.
sim = Simulation(name='RoundRobinDemo')

vms = [sim.create(VM, name=f'vm-{i+1}', cpu=1, ram=512, scheduler=TimeShared()) for i in range(3)]
for vm in vms:
    vm.run(sim.create(App, name=f'{vm.name}-app', length=(1,)))

hosts = [sim.create(PM, name=f'pm{i+1}', cpu=(2, 2, 2, 2), ram=4096, hypervisor=SpaceShared()) for i in range(3)]
sim.datacenter = sim.create(DataCenter, name='dc', hosts=hosts, placement=RoundRobinPlacement())
sim.requests = [sim.create(Request, arrival=0, vm=vm) for vm in vms]

sim.run().report()
