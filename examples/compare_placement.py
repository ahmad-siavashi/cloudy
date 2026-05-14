"""Compare two placement policies — same workload, different metrics.

Demonstrates :func:`cloudy.compare`. Five VMs arrive in a sequence
designed to show a real algorithmic difference between bin-packing
(``FirstFit``) and spreading (a custom ``RoundRobinPlacement``).
Spreading fragments host capacity, so the last (large) VM no longer
fits anywhere. Bin-packing leaves one host completely empty and accepts
every VM.

Run with::

    python examples/compare_placement.py
"""

from cloudy import App, DataCenter, PM, Request, VM, compare
from cloudy.policies import FirstFit, Placement, SpaceShared, TimeShared


class RoundRobinPlacement(Placement):
    """A placement that distributes VMs round-robin across hosts."""

    def __post_init__(self):
        super().__post_init__()
        self._next = 0

    def allocate(self, vms):
        results = []
        hosts = self.datacenter.hosts
        for vm in vms:
            placed = False
            for offset in range(len(hosts)):
                host = hosts[(self._next + offset) % len(hosts)]
                if all(host.hypervisor.has_capacity(vm)):
                    host.hypervisor.allocate([vm])
                    self[vm] = host
                    self.event_queue.publish('vm.allocate', self.clock.now, host, vm)
                    self._next = (self._next + offset + 1) % len(hosts)
                    placed = True
                    break
            results.append(placed)
        return results

    def deallocate(self, vms):
        results = []
        for vm in vms:
            host = self[vm]
            host.hypervisor.deallocate([vm])
            del self[vm]
            self.event_queue.publish('vm.deallocate', self.clock.now, host, vm)
            results.append(True)
        return results


def build(sim, placement_class):
    """Two hosts, four small VMs followed by one 4-core VM."""
    hosts = [sim.create(PM, name=f'pm-{i}', cpu=(2, 2, 2, 2), ram=4096, hypervisor=SpaceShared()) for i in range(2)]
    sim.datacenter = sim.create(DataCenter, name='dc', hosts=hosts, placement=placement_class())

    small_vms = [sim.create(VM, name=f'small-{i}', cpu=1, ram=512, scheduler=TimeShared()) for i in range(4)]
    large_vm = sim.create(VM, name='large', cpu=4, ram=2048, scheduler=TimeShared())
    for vm in (*small_vms, large_vm):
        vm.run(sim.create(App, name=f'app-{vm.name}', length=(1,)))

    sim.requests = [sim.create(Request, arrival=0, vm=vm) for vm in (*small_vms, large_vm)]


# Run the comparison.
results = compare(build, placement_class=[FirstFit, RoundRobinPlacement])

# Print a small table. Researchers wanting more analysis can hand
# ``results`` to ``pandas.DataFrame(...)``.
print(f'{"placement":<22} {"accepted":<10} {"rejected":<10} {"acceptance":<10}')
for row in results:
    accepted: int = int(row["request.accepted"])
    arrived: int = int(row["request.arrived"])
    acceptance: float = round(accepted / arrived, 2) if arrived else 0.0
    print(f'{row["placement_class"]:<22} {accepted:<10} {int(row["request.rejected"]):<10} {acceptance:<10}')
