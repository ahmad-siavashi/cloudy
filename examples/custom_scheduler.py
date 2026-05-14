"""Write your own scheduler — a worked example.

A first-come-first-served (FCFS) scheduler in five lines: the process
at the head of the queue gets every available cycle until it finishes,
then the next one starts. Compare with
:class:`cloudy.policies.TimeShared`, which runs all processes in turn
(round-robin).

The framework handles per-process start/stop events, thread-to-core
mapping, and terminate bookkeeping. We only override
:meth:`Scheduler.share` to declare the cycle distribution.

Run with::

    python examples/custom_scheduler.py
"""

from cloudy import App, DataCenter, PM, Request, Simulation, VM
from cloudy.policies import FirstFit, Scheduler, SpaceShared


class FCFSScheduler(Scheduler):
    """First-come, first-served — the head-of-queue process gets every cycle."""

    def share(self, processes, cores_cycles):
        return [list(cores_cycles)] + [[0] * len(cores_cycles) for _ in processes[1:]]


sim = Simulation(name='FCFSDemo')

vm = sim.create(VM, name='vm', cpu=1, ram=512, scheduler=FCFSScheduler())
# Three processes run strictly in submission order.
vm.run([sim.create(App, name=n, length=(2,)) for n in ('first', 'second', 'third')])

pm = sim.create(PM, name='pm', cpu=(2,), ram=1024, hypervisor=SpaceShared())

sim.datacenter = sim.create(DataCenter, name='dc', hosts=[pm], placement=FirstFit())
sim.requests = [sim.create(Request, arrival=0, vm=vm)]

sim.run().report()
