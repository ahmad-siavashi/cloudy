""" This is a simple example to demonstrate the use of the simulator. In this example, a data center with one
physical machine (PM) receives one request (a virtual machine) from a user. The virtual machine (VM) which contains
one application to run, arrives at time zero, i.e. the beginning of the simulation. The VM uses a
time-sharing scheduling policy to execute its processes. The PM uses a space-shared policy to
allocate resources for the virtual machine. Furthermore, the data center uses a first-fit (FF) policy to find a
suitable host for the request. """

from model import App, DataCenter, Pm, Request, User, Vm
from module import Simulation
from policy.os import OsTimeShared
from policy.vmp import VmpFirstFit
from policy.vmm import VmmSpaceShared

# Creating an application object called 'nginx' with 3 threads, each 1 cycles length.
app = App(NAME='nginx', LENGTH=(1, 1, 1), EXPIRATION=None)

# Creating a virtual machine called 'webserver' with 1 core, 1 GB of RAM, (2, 2) GPU profile, and OsTimeShared
# operating system.
vm = Vm(NAME='webserver', CPU=1, RAM=1024, GPU=(2, 2), OS=OsTimeShared)
# The application is scheduled for execution in the virtual machine.
vm.OS.schedule([app])

# Creating a request for a VM and a user that will request that VM.
# The request arrives at clock 0 and the user represents the portal of the cloud provider.
request = Request(ARRIVAL=0, VM=vm)
user = User(NAME='portal', REQUESTS=[request])

# Creating a physical machine with 2 cores (each 2 cycles per simulation time unit)
# and 2 GB of RAM, and using the VmmSpaceShared virtual machine manager.
pm = Pm(NAME='hpe gen10', CPU=(2, 2), RAM=2048, GPU=((7, 8),), VMM=VmmSpaceShared)

# Creating a data center with a single physical machine which uses the PlacementFirstFit placement algorithm.
datacenter = DataCenter(NAME='boston region', HOSTS=[pm], VMP=VmpFirstFit)

# Initializing the simulation with the user and data center and then starting the simulation.
Simulation(NAME='simple', USER=user, DATACENTER=datacenter).run().report()
