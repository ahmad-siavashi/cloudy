""" This is a simple example to demonstrate the use of containers.
In this example, a three-node cluster is created to deploy containers."""

from model import Controller, DataCenter, Deployment, Pm, Request, Vm, User, Action
from module import Simulation
from policy.control_plane import ControlPlaneRoundRobin
from policy.os import OsTimeShared
from policy.vmm import VmmSpaceShared
from policy.vmp import VmpFirstFit

# Creating a user which will send requests to the cloud provider
user = User(NAME='portal')

# Creating a container spec that requires a minimum of 0.5 CPU, and 256MB of RAM.
container_spec = {'NAME': 'nginx', 'LENGTH': (2,), 'EXPIRATION': None, 'CPU': (0.5, 1), 'RAM': (256, 512), 'GPU': ()}
# A deployment of the container consists of six replicas.
deployment = Deployment(NAME='server', replicas=6, CONTAINER_SPECS=[container_spec])

# A cluster of three nodes is created
nodes = []
for i in range(3):
    nodes += [Vm(NAME=f'node {i + 1}', CPU=1, RAM=1024, OS=OsTimeShared, GPU=())]

# The nodes are sent as requests for placement at datacenter.
# The three nodes will be placed on the three hosts.
for node in nodes:
    user.REQUESTS += [Request(ARRIVAL=0, VM=node)]

# The controller is asked to run a cluster of three nodes for 50 cycles.
# The control plane runs on the first node (default).
controller = Controller(NAME='controller', LENGTH=(10,), EXPIRATION=None, NODES=nodes[1:], CONTROL_PLANE=ControlPlaneRoundRobin)

# The cluster is asked to run the deployment.
user.REQUESTS += [
    Action(ARRIVAL=0, EXECUTE=lambda: nodes[0].OS.schedule([controller])),
    Action(ARRIVAL=0, EXECUTE=lambda: controller.CONTROL_PLANE.apply(deployment))
]

# Let's create a data center with three nodes
datacenter = DataCenter(NAME='boston region', VMP=VmpFirstFit)

# The master host is given more CPU to simultaneously run the control plane.
datacenter.HOSTS += [Pm(NAME='pm 1', CPU=(1, 1, 1), RAM=1024, GPU=(), VMM=VmmSpaceShared)]
datacenter.HOSTS += [Pm(NAME='pm 2', CPU=(1, 1, 1), RAM=1024, GPU=(), VMM=VmmSpaceShared)]
datacenter.HOSTS += [Pm(NAME='pm 3', CPU=(1, 1, 1), RAM=1024, GPU=(), VMM=VmmSpaceShared)]

# Initializing the simulation with the user and data center and then starting the simulation.
Simulation(NAME='container', USER=user, DATACENTER=datacenter).run().report()
