"""
This example demonstrates the use of containers.
A three-node cluster is created to deploy containers.
"""

from model import Controller, DataCenter, Deployment, Pm, Request, User, Vm, Action
from module import Simulation
from policy.control_plane import ControlPlaneRoundRobin
from policy.os import OsTimeShared
from policy.vmm import VmmSpaceShared
from policy.vmp import VmpFirstFit

# Creating a user who will send requests to the cloud provider.
user = User(NAME='Portal')

# Creating a container spec that requires 0.5-1 CPU and 256-512MB RAM.
container_spec = {'NAME': 'Nginx', 'LENGTH': (2,), 'CPU': (0.5, 1), 'RAM': (256, 512), 'GPU': ()}
# A deployment of the container consists of six replicas.
deployment = Deployment(NAME='WebServer', replicas=6, CONTAINER_SPECS=[container_spec])

# Creating a cluster of three nodes.
nodes = [Vm(NAME=f'Node {i + 1}', CPU=1, RAM=1024, OS=OsTimeShared, GPU=()) for i in range(3)]

# Sending node requests for placement at the data center.
for node in nodes:
    user.REQUESTS += [Request(ARRIVAL=0, VM=node)]

# Creating a controller to manage the cluster for 50 cycles.
# The control plane runs on the first node (default).
controller = Controller(NAME='Controller', LENGTH=(10,), NODES=nodes[1:], CONTROL_PLANE=ControlPlaneRoundRobin)

# Running the deployment on the cluster.
user.REQUESTS += [
    Action(ARRIVAL=0, EXECUTE=lambda: nodes[0].OS.schedule([controller])),
    Action(ARRIVAL=0, EXECUTE=lambda: controller.CONTROL_PLANE.apply(deployment))
]

# Creating a data center with three physical machines (PMs).
datacenter = DataCenter(NAME='Shiraz', VMP=VmpFirstFit)

# Creating PMs with 1 core (1 cycle per time unit each), 1 GB RAM, and VmmSpaceShared manager.
datacenter.HOSTS += [
    Pm(NAME='PM 1', CPU=(1, 1, 1), RAM=1024, GPU=(), VMM=VmmSpaceShared),
    Pm(NAME='PM 2', CPU=(1, 1, 1), RAM=1024, GPU=(), VMM=VmmSpaceShared),
    Pm(NAME='PM 3', CPU=(1, 1, 1), RAM=1024, GPU=(), VMM=VmmSpaceShared)
]

# Initializing the simulation with the user and data center, and then starting the simulation.
Simulation(NAME='ContainerSim', USER=user, DATACENTER=datacenter).run().report()
