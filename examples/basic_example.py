"""
This example demonstrates the ease of use of the cloud simulator. A data center with one physical machine (PM)
receives one request for a virtual machine (VM) from a user. The VM arrives at time zero, uses a time-sharing policy
for processes, and the PM uses a space-shared policy for resource allocation. The data center uses a first-fit policy
to host the request.
"""

from model import App, DataCenter, Pm, Request, User, Vm
from module import Simulation
from policy.os import OsTimeShared
from policy.vmp import VmpFirstFit
from policy.vmm import VmmSpaceShared

# Step 1: Create an application with 3 threads, each 1 cycle long.
app = App(NAME='Nginx', LENGTH=(1, 1, 1))

# Step 2: Create a VM with 1 core, 1 GB RAM, (2, 2) GPU profile, and OsTimeShared OS.
vm = Vm(NAME='WebServer', CPU=1, RAM=1024, GPU=(2, 2), OS=OsTimeShared)
vm.OS.schedule([app])  # Schedule the app in the VM.

# Step 3: Create a request for the VM at time 0 and a user to make the request.
request = Request(ARRIVAL=0, VM=vm)
user = User(NAME='Portal', REQUESTS=[request])

# Step 4: Create a PM with 2 cores (2 cycles per time unit each), 2 GB RAM, and VmmSpaceShared manager.
pm = Pm(NAME='HPE', CPU=(2, 2), RAM=2048, GPU=((7, 8),), VMM=VmmSpaceShared)

# Step 5: Create a data center with the PM and VmpFirstFit placement policy.
datacenter = DataCenter(NAME='Tehran', HOSTS=[pm], VMP=VmpFirstFit)

# Step 6: Initialize and run the simulation with the user and data center.
Simulation(NAME='BasicSim', USER=user, DATACENTER=datacenter).run().report()
