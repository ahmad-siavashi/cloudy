import random

from model import App, Vm, Request, User, Pm, DataCenter
from module import Simulation
from policy.os import OsFcfs
from policy.placement import PlacementFirstFit, PlacementMaxProfile
from policy.vmm import VmmSpaceShared

NUM_REQUESTS = 1000
# POISSON_RATE = 1

NUM_SERVERS = 100

random.seed(1)

requests = []
gpus = {
    (1, 1): 0.1,
    (2, 2): 0.2,
    (3, 4): 0.3,
    (4, 4): 0.3,
    (7, 8): 0.1
}
vms = []
for gpu, prob in gpus.items():
    for i in range(int(NUM_REQUESTS * prob)):
        app = App('app', (random.randint(1, 100),))
        vm = Vm('vm ' + str(i), 1, 1024, gpu, OsFcfs)
        vms += [vm]
        vm.OS.schedule([app])
        requests += [Request(0, vm)]

# print(requests)
random.shuffle(requests)
# print(requests)

# arrival_time = 0.0
# for req in requests:
    # arrival_time += round(random.expovariate(POISSON_RATE), 3) if POISSON_RATE > 0 else 0
    # req.ARRIVAL = arrival_time

user = User('user', requests)

servers = []
for j in range(NUM_SERVERS):
    pm = Pm('pm ' + str(j), tuple([1 for _ in range(128)]), 128 * 1024, ((7, 8),), VmmSpaceShared)
    servers += [pm]

# print('-----------NVIDIA Driver------------')
# datacenter = DataCenter('boston region', servers, PlacementFirstFit)
# Simulation(user, datacenter).start().report()

# print('-----------Revised Driver------------')
datacenter = DataCenter('boston region', servers, PlacementMaxProfile)
Simulation(user, datacenter).start().report()
