"""Write your own hypervisor — a worked example.

Add a RAM safety buffer to :class:`SpaceShared`: the host
refuses to admit a VM if doing so would lower free RAM below 10 % of
the host's total. The CPU check is inherited unchanged.

This is a typical research scenario for host-level admission control
under memory pressure. We override :meth:`Hypervisor.has_capacity` and
read free state through the public :attr:`SpaceShared.free_ram`
property; there is no need to access the private ``_free_*`` fields.

Run with::

    python examples/custom_hypervisor.py
"""

from cloudy import App, DataCenter, PM, Request, Simulation, VM
from cloudy.policies import FirstFit, SpaceShared, TimeShared


class StrictRamHypervisor(SpaceShared):
    """Like :class:`SpaceShared`, but reserves 10 % of RAM."""

    RAM_SAFETY_RATIO = 0.10

    def has_capacity(self, vm):
        cpu_ok, ram_ok = super().has_capacity(vm)
        if ram_ok and (self.free_ram - vm.ram) < self.host.ram * self.RAM_SAFETY_RATIO:
            ram_ok = False
        return cpu_ok, ram_ok


# One host, two VMs; the second is rejected by the safety buffer. The host
# has 1024 MB. VM 1 takes 500 MB, leaving 524. VM 2 also wants 500 MB,
# which would leave 24 — below the 102.4 MB (10 %) threshold — so
# StrictRamHypervisor rejects it; plain SpaceShared would admit both.
sim = Simulation(name='StrictRamDemo')

vms = [sim.create(VM, name=f'vm-{i}', cpu=1, ram=500, scheduler=TimeShared()) for i in (1, 2)]
for vm in vms:
    vm.run(sim.create(App, name=f'{vm.name}-app', length=(1,)))

pm = sim.create(PM, name='pm', cpu=(2, 2), ram=1024, hypervisor=StrictRamHypervisor())

sim.datacenter = sim.create(DataCenter, name='dc', hosts=[pm], placement=FirstFit())
sim.requests = [sim.create(Request, arrival=0, vm=vm) for vm in vms]

sim.run().report()
