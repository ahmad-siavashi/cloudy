"""
A minimal Cloudy simulation. A data center with one physical machine
receives one VM request from a user. Time-share scheduling inside the
VM, space-shared hypervisor on the host, first-fit placement at the
data center.
"""

from cloudy import App, DataCenter, PM, Request, Simulation, VM
from cloudy.policies import FirstFit, SpaceShared, TimeShared

sim = Simulation(name='BasicSim')

# Build the workload. Policies are passed as instances.
app = sim.create(App, name='Nginx', length=(1, 1, 1))
vm = sim.create(VM, name='WebServer', cpu=1, ram=1024, scheduler=TimeShared())
vm.run(app)

# Build the host.
pm = sim.create(PM, name='HPE', cpu=(2, 2), ram=2048, hypervisor=SpaceShared())

# Attach the data center and arriving requests, then run.
sim.datacenter = sim.create(DataCenter, name='Tehran', hosts=[pm], placement=FirstFit())
sim.requests = [sim.create(Request, arrival=0, vm=vm)]

sim.run().report()
