""" This is a simple example to demonestrate the use of the simulator. In this example, a data center with one
physical machine (PM) receives one request (a virtual machine) from a user. The virtual machine (VM) which contains
one application to run, arrives at time zero, i.e. the beginning of the simulation. The VM uses a
first-come-first-served (FCFS) scheduling policy to execute its processes. The PM uses a space-shared policy to
allocate resources for the virtual machine. Furthermore, the data center uses a first-fit (FF) policy to find a
suitable host for the request. """

from model import App, Vm, Request, User, Pm, DataCenter
from module import Simulation
from policy.os import OsFcfs
from policy.placement import PlacementFirstFit
from policy.vmm import VmmSpaceShared

# Creating an application object called 'nginx' with 3 threads, each 4 cycles length.
app = App('nginx', (4, 4, 4))

# Creating a virtual machine called 'webserver' with 2 cores and 1 GB of RAM, using the OsFcfs operating system,
# and scheduling the application 'nginx' on it.
vm = Vm('webserver', 2, 1024, None, OsFcfs)
vm.OS.schedule([app])

# Creating a request for a VM and a user that will request that VM.
# The request arrives at clock 0 and the user represents the portal of the cloud provider.
req = Request(0, vm)
user = User('portal', [req])

# Creating a physical machine with the name 'hpe gen10', with 2 cores (each 2 cycles per simulation time unit)
# and 2 GB of RAM, and using the VmmSpaceShared virtual machine manager.
pm = Pm('hpe gen10', (2, 2), 2048, None, VmmSpaceShared)

# Creating a data center called 'boston region' with a single physical machine called 'hpe gen10' which uses the
# PlacementFirstFit placement algorithm.
datacenter = DataCenter('boston region', [pm], PlacementFirstFit)

# Initializing the simulation with the user and data center and then starting the simulation.
Simulation(user, datacenter).start()
