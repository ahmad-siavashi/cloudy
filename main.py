import simulation
from components import App, Vm, Pm, User, Request, DataCenter
from management.os.fcfs import OsFcfs
from management.placement.firstfit import PlacementFirstFit
from management.vmm.spaceshared import VmmSpaceShared

# Creating an application called 'nginx' with 2 threads each 2 cycles length.
app = App('nginx', (4, 4, 4))

# Creating a virtual machine called 'web server' with 2 cores and 1024 MB of RAM, using the OsFcfs operating system,
# and scheduling the application 'nginx' on it.
vm = Vm('webserver', 2, 1024, OsFcfs)
vm.OS.schedule([app])

# Creating a request for a VM and a user that will request that VM.
# The request arrives at clock 0 and the user represents the web portal of the cloud provider.
req = Request(0, vm)
user = User('portal', [req])

# Creating a physical machine with the name 'hpe gen10', with 2 cores (each 2 cycles per simulation time unit, i.e. tick)
# and 2 GB of RAM, and using the VmmSpaceShared virtual machine manager.
pm = Pm('hpe gen10', (2, 2), 2048, VmmSpaceShared)

# Creating a data center called 'boston region' with a single physical machine called 'hpe gen10' which uses the
# PlacementFirstFit placement algorithm.
datacenter = DataCenter('boston region', [pm], PlacementFirstFit)

# Initializing the simulation with the user and data center and then starting the simulation.
simulation.init(user, datacenter)
simulation.start()
