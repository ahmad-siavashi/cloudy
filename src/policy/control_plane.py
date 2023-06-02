from dataclasses import dataclass, asdict
from typing import Optional

import cloca
import evque

import model
import policy
from model import Container


@dataclass
class ControlPlaneRoundRobin(policy.ControlPlane):
    """
    Implements a round-robin resource allocation policy for Control Plane.

    Notes
    -----
    - Does not support partial scheduling.
    - Supports degraded deployments.
    - Assumes restart policy is 'never'.
    """

    def __post_init__(self):
        super().__post_init__()
        # Initializing resource dictionaries for each node.
        self._node_cpu: dict[model.Vm, float] = dict()
        self._node_ram: dict[model.Vm, int] = dict()
        self._node_gpu: dict[model.Vm, Optional[tuple[int, int] | float]] = dict()
        for node in self.CLUSTER_CONTROLLER.NODES:
            self._node_cpu[node] = node.CPU
            self._node_ram[node] = node.RAM
            self._node_gpu[node] = node.GPU

        # Initializing container and deployment related dictionaries.
        self._deployment_replicas: dict[model.Deployment, list[list[model.Container, ...], ...]] = {}
        self._container_deployment: dict[model.Container, model.Deployment] = {}
        self._container_node: dict[model.Container, model.Vm] = {}

        # List of deployments that haven't reached their desired replica count.
        # Each entry is a tuple containing the deployment and the number of replicas yet to be deployed.
        self._degraded_deployments: list[tuple[model.Deployment, int], ...] = []

        evque.subscribe('container.stop', self._delete_container)

    def _deploy_deployment(self, deployment: model.Deployment, num_replicas: int = None) -> int:
        """
        Deploy the given deployment.

        Parameters
        ----------
        deployment : model.Deployment
            Deployment to be deployed.

        Returns
        -------
        int
            Number of replicas successfully deployed.
        """
        if not num_replicas:
            num_replicas = deployment.replicas

        num_deployed_replicas = 0
        prev_num_deployed_replicas = num_deployed_replicas

        if not self._deployment_replicas.get(deployment):
            self._deployment_replicas[deployment] = []

        # Loop to continuously deploy replicas until no more can be deployed.
        while True:
            for worker in filter(lambda n: n.is_on(), self.CLUSTER_CONTROLLER.NODES):
                if num_replicas == num_deployed_replicas:
                    return num_deployed_replicas
                elif self._deploy_replica(deployment, worker):
                    num_deployed_replicas += 1

            # Terminate the loop if no new replicas were executed in this iteration.
            if prev_num_deployed_replicas == num_deployed_replicas:
                break
            prev_num_deployed_replicas = num_deployed_replicas

        return num_deployed_replicas

    def _deploy_replica(self, deployment: model.Deployment, node: model.Vm) -> bool:
        """
        Deploy a replica on the given node.

        Parameters
        ----------
        deployment : model.Deployment
            Deployment to be deployed.
        node : model.Vm
            Node (VM) on which to deploy the replica.

        Returns
        -------
        bool
            True if deployment was successful, False otherwise.
        """
        if not self._has_sufficient_resources_for_deployment(deployment, node):
            return False

        replica_containers = [Container(**container_spec) for container_spec in deployment.CONTAINER_SPECS]
        for container in replica_containers:
            self._deploy_container(container, node)
            self._container_node[container] = node
            self._container_deployment[container] = deployment

        self._deployment_replicas[deployment].append(replica_containers)
        return True

    def delete(self, deployment: model.Deployment, num_replicas: int = None) -> policy.ControlPlane:
        """
        Delete the specified number of replicas of the given deployment.

        Parameters
        ----------
        deployment : model.Deployment
            Deployment to be deleted
        num_replicas : int, optional
            Number of replicas to be deleted, or remove all if none is specified

        Returns
        -------
        policy.ControlPlane
            Current instance of the control plane.
        """
        if not num_replicas:
            num_replicas = len(self._deployment_replicas[deployment])

        while self._deployment_replicas[deployment] and num_replicas:
            replica_containers = self._deployment_replicas[deployment].pop()
            while replica_containers:
                container = replica_containers.pop()
                self._delete_container(None, container)
            num_replicas -= 1

        if not self._deployment_replicas[deployment]:
            del self._deployment_replicas[deployment]

        return self

    def _deploy_container(self, container: model.Container, node: model.Vm) -> bool:
        """
        Deploy a container on the specified node.

        Parameters
        ----------
        container : model.Container
            The container to be deployed.
        node : model.Vm
            The node (VM) on which to deploy the container.

        Returns
        -------
        bool
            True if the container was successfully deployed, False otherwise.
        """
        if not self._has_sufficient_resources_for_container(asdict(container), node):
            return False

        # Retrieve the resources required by the container.
        requested_cpu, requested_ram, requested_gpu = self._get_container_requested_resources(asdict(container))

        # Update the node's resources.
        self._node_cpu[node] -= requested_cpu
        self._node_ram[node] -= requested_ram
        self._node_gpu[node] = ()  # Assuming GPU resources are fully utilized and set to empty tuple

        # Schedule the container on the node.
        node.OS.schedule([container])

        return True

    def _delete_container(self, node: Optional[model.Vm], container: model.Container) -> bool:
        """
        Delete a container.

        Parameters
        ----------
        container : model.Container
            The container to be deleted.
        node : model.Vm
            The node on of the container

        Returns
        -------
        bool
            True if the container was successfully deleted, False otherwise.
        """
        if not node:
            node = self._container_node[container]
        elif self._container_node[container] != node:
            raise ValueError("Container not found on the specified node.")

        # Retrieve the resources utilized by the container.
        requested_cpu, requested_ram, requested_gpu = self._get_container_requested_resources(asdict(container))

        # Release the resources.
        self._node_cpu[node] += requested_cpu
        self._node_ram[node] += requested_ram
        self._node_gpu[node] = requested_gpu

        self._remove_container_references(container)

        return True

    def _remove_container_references(self, container: model.Container):
        """
        Removes references to the given container from internal storage.

        This function performs the following:
        1. Deletes the container from the node-container mapping.
        2. Deletes the container from deployment replicas and performs cleanup if necessary.

        Parameters
        ----------
        container : model.Container
            the container to be removed from references
        """
        deployment = self._container_deployment[container]
        del self._container_deployment[container]

        # Remove the container from node-container mapping.
        del self._container_node[container]

        # Remove the container from deployment replicas and clean up if needed.
        replicas = self._deployment_replicas.get(deployment, [])
        for i, replica in enumerate(replicas):
            if container in replica:
                replica.remove(container)

                # If the replica list is empty after removal, delete it.
                if not replica:
                    del self._deployment_replicas[deployment][i]

                    # If there are no replicas left for the deployment, delete the deployment entry.
                    if not self._deployment_replicas[deployment]:
                        del self._deployment_replicas[deployment]
                        evque.publish('deployment.stop', cloca.now(), self.CLUSTER_CONTROLLER, deployment)
                break

    def _has_sufficient_resources_for_deployment(self, deployment: model.Deployment, node: model.Vm) -> bool:
        """
        Check if a node has sufficient resources to deploy a given deployment.

        Parameters
        ----------
        deployment : model.Deployment
            The deployment to check resources for.
        node : model.Vm
            The node to check resources against.

        Returns
        -------
        bool
            True if there are sufficient resources, False otherwise.
        """
        requested_cpu, requested_ram, requested_gpu = self._get_deployment_requested_resources(deployment)
        return self._has_sufficient_resources(requested_cpu, requested_ram, requested_gpu, node)

    def _has_sufficient_resources_for_container(self, container_spec: dict, node: model.Vm) -> bool:
        """
        Check if a node has sufficient resources to deploy a given container.

        Parameters
        ----------
        container_spec : dict
            The container spec to check resources for.
        node : model.Vm
            The node to check resources against.

        Returns
        -------
        bool
            True if there are sufficient resources, False otherwise.
        """
        requested_cpu, requested_ram, requested_gpu = self._get_container_requested_resources(container_spec)
        return self._has_sufficient_resources(requested_cpu, requested_ram, [requested_gpu], node)

    def _has_sufficient_resources(self, requested_cpu: float, requested_ram: int,
                                  requested_gpu: list[tuple[int, int], ...], node: model.Vm) -> bool:
        """
        General method to check if a node has sufficient resources.

        Parameters
        ----------
        requested_cpu : float
            The required CPU.
        requested_ram : int
            The required RAM.
        requested_gpu : list[tuple[int, int], ...]
            The required GPUs.
        node : model.Vm
            The node to check resources against.

        Returns
        -------
        bool
            True if there are sufficient resources, False otherwise.
        """
        has_cpu: bool = self._node_cpu[node] >= requested_cpu
        has_ram: bool = self._node_ram[node] >= requested_ram
        has_gpu: bool = not requested_gpu or self._node_gpu[node] in requested_gpu
        return has_cpu and has_ram and has_gpu

    def _get_deployment_requested_resources(self, deployment: model.Deployment) -> tuple[float, int, list[tuple[int, int], ...]]:
        """
        Retrieve the total requested resources by a deployment.

        Parameters
        ----------
        deployment : model.Deployment
            The deployment for which resources are being computed.

        Returns
        -------
        tuple
            A tuple containing total requested CPU, RAM, and GPU resources.
        """
        total_requested_cpu, total_requested_ram, total_requested_gpu = 0, 0, []
        for container_spec in deployment.CONTAINER_SPECS:
            requested_cpu, requested_ram, requested_gpu = self._get_container_requested_resources(container_spec)
            total_requested_cpu += requested_cpu
            total_requested_ram += requested_ram
            total_requested_gpu.append(requested_gpu)
        return total_requested_cpu, total_requested_ram, total_requested_gpu

    @staticmethod
    def _get_container_requested_resources(container_spec: dict) -> tuple[float, int, tuple[int, int]]:
        """
        Extract the requested resources of a container from its spec.

        Parameters
        ----------
        container_spec : model.Container
            The spec of the container whose requested resources are to be extracted.

        Returns
        -------
        tuple[float, int, tuple[int, int]]
            A tuple containing requested CPU, RAM, and GPU requirements by the container.
        """
        return container_spec['CPU'][0], container_spec['RAM'][0], container_spec['GPU']

    def _deploy_degraded_deployments(self):
        """
        Execute degraded deployments.

        This method attempts to handle the deployments which have not been fully executed.
        It calculates the remaining number of replicas for each deployment and tries to execute them.

        Notes
        -----
        - If a deployment remains degraded after an attempt, it's added back to the `_degraded_deployments` list.
        - Utilizes `_deploy_deployment()` to execute the replicas.
        """
        num_degraded_deployments = len(self._degraded_deployments)

        # Loop through all degraded deployments
        while num_degraded_deployments:
            deployment, num_remained_replicas = self._degraded_deployments.pop(0)
            num_remained_replicas -= self._deploy_deployment(deployment, num_remained_replicas)

            # If all required replicas were not executed, re-append to degraded deployments
            if num_remained_replicas:
                self._degraded_deployments.append((deployment, num_remained_replicas))
                evque.publish('deployment.degrade', cloca.now(), self.CLUSTER_CONTROLLER, deployment, num_remained_replicas)
            else:
                evque.publish('deployment.run', cloca.now(), self.CLUSTER_CONTROLLER, deployment)

            num_degraded_deployments -= 1

    def _deploy_pending_deployments(self):
        """
        Execute pending deployments.

        This method tries to execute deployments from the pending list. If a deployment can't be fully executed,
        it's moved to the degraded list. If none of its replicas are executed, it remains in the pending list.

        Notes
        -----
        - Uses `_deploy_replicas()` to execute the replicas.
        """
        num_pending_deployments = len(self._pending_deployments)

        # Loop through all pending deployments
        while num_pending_deployments:
            deployment = self._pending_deployments.pop(0)
            num_deployed_replicas = self._deploy_deployment(deployment)

            # Determine the status of deployment execution
            if not num_deployed_replicas:
                self._pending_deployments.append(deployment)
                evque.publish('deployment.pend', cloca.now(), self.CLUSTER_CONTROLLER, deployment)
            elif num_deployed_replicas < deployment.replicas:
                num_remained_replicas = deployment.replicas - num_deployed_replicas
                self._degraded_deployments.append((deployment, num_remained_replicas))
                evque.publish('deployment.degrade', cloca.now(), self.CLUSTER_CONTROLLER, deployment, num_remained_replicas)
            else:
                evque.publish('deployment.run', cloca.now(), self.CLUSTER_CONTROLLER, deployment)

            num_pending_deployments -= 1

    def _deploy_scaled_deployments(self):
        """
        Adjust running replicas based on scaling instructions.

        If the desired count of replicas is higher, this method moves deployments to the degraded list
        (indicating a need for more replicas). If the desired count is lower, it terminates the extra replicas.

        Remarks
        -------
        - This method should be called prior to `_deploy_degraded_deployments()` to ensure consistency.
        """
        num_scaled_deployments = len(self._scaled_deployments)

        # Loop through all scaled deployments
        while num_scaled_deployments:
            deployment = self._scaled_deployments.pop(0)

            current_replicas = len(self._deployment_replicas[deployment])
            required_replicas = deployment.replicas - current_replicas

            # Scale up or down based on the difference
            if required_replicas < 0:
                to_delete_replicas = abs(required_replicas)
                self.delete(deployment, to_delete_replicas)
                evque.publish('deployment.scale', cloca.now(), self.CLUSTER_CONTROLLER, deployment, required_replicas)
            elif required_replicas > 0:
                self._degraded_deployments.append((deployment, required_replicas))
                evque.publish('deployment.scale', cloca.now(), self.CLUSTER_CONTROLLER, deployment, required_replicas)
            else:
                evque.publish('deployment.run', cloca.now(), self.CLUSTER_CONTROLLER, deployment)

            num_scaled_deployments -= 1

    def manage(self):
        """
        Monitor the state of deployments and execute necessary actions.
        """
        self._deploy_scaled_deployments()
        self._deploy_degraded_deployments()
        self._deploy_pending_deployments()

    def is_stopped(self) -> bool:
        """
        Check if the control plane service is stopped.

        Returns
        -------
        bool
            Always returns False, assuming the control plane runs continuously.
        """
        return False


class FractionalGPUControlPlaneRoundRobin(ControlPlaneRoundRobin):
    """
    A control plane that uses a round-robin scheduling algorithm with fractional GPU support.

    This class extends the ControlPlaneRoundRobin class to support fractional GPU utilization.
    It allows containers to request a fraction of a GPU, rather than an entire GPU.
    """

    def __post_init__(self):
        super().__post_init__()
        # Initialize GPU resources for each node in the cluster.
        for node in self.CLUSTER_CONTROLLER.NODES:
            # Set GPU availability to 1.0 (100%) if the node has a GPU, otherwise set it to 0.0.
            self._node_gpu[node] = 1.0 if node.GPU else 0.0

    def _deploy_container(self, container: model.Container, node: model.Vm) -> bool:
        """
        Deploy a container to a node if the node has sufficient resources.

        Parameters
        ----------
        container : model.Container
            The container to be deployed.
        node : model.Vm
            The node where the container should be deployed.

        Returns
        -------
        bool
            True if the container was successfully deployed, False otherwise.
        """
        # Check if the node has sufficient resources for the container.
        if not self._has_sufficient_resources_for_container(asdict(container), node):
            return False

        # Extract the resources required by the container.
        requested_cpu, requested_ram, requested_gpu = self._get_container_requested_resources(asdict(container))

        # Deduct the resources used by the container from the node's available resources.
        self._node_cpu[node] -= requested_cpu
        self._node_ram[node] -= requested_ram
        self._node_gpu[node] -= requested_gpu

        # Schedule the container on the node.
        node.OS.schedule([container])

        return True

    def _delete_container(self, node: Optional[model.Vm], container: model.Container) -> bool:
        """
        Delete a container.

        Parameters
        ----------
        container : model.Container
            The container to be deleted.
        node : model.Vm
            The node on of the container

        Returns
        -------
        bool
            True if the container was successfully deleted, False otherwise.
        """
        if not node:
            node = self._container_node[container]
        elif self._container_node[container] != node:
            raise ValueError("Container not found on the specified node.")

        # Extract the resources utilized by the container.
        requested_cpu, requested_ram, requested_gpu = self._get_container_requested_resources(asdict(container))

        # Release the resources back to the node.
        self._node_cpu[node] += requested_cpu
        self._node_ram[node] += requested_ram
        self._node_gpu[node] += requested_gpu

        # Remove references to the container from internal data structures.
        self._remove_container_references(container)

        return True

    @staticmethod
    def _get_container_requested_resources(container_spec: dict) -> tuple[float, int, float]:
        """
        Extract the requested resources of a container from its spec.

        Parameters
        ----------
        container_spec : model.Container
            The spec of the container whose requested resources are to be extracted.

        Returns
        -------
        tuple[float, int, float]
            A tuple containing requested CPU, RAM, and GPU requirements by the container.
        """
        return container_spec['CPU'][0], container_spec['RAM'][0], container_spec['GPU']

    def _has_sufficient_resources(self, requested_cpu: float, requested_ram: int, requested_gpu: float, node: model.Vm) -> bool:
        """
        General method to check if a node has sufficient resources.

        Parameters
        ----------
        requested_cpu : float
            The required CPU.
        requested_ram : int
            The required RAM.
        requested_gpu : float
            The required GPU utilization [0, 1].
        node : model.Vm
            The node to check resources against.

        Returns
        -------
        bool
            True if there are sufficient resources, False otherwise.
        """
        has_cpu: bool = self._node_cpu[node] >= requested_cpu
        has_ram: bool = self._node_ram[node] >= requested_ram
        has_gpu: bool = self._node_gpu[node] >= requested_gpu
        return has_cpu and has_ram and has_gpu

    def _get_deployment_requested_resources(self, deployment: model.Deployment) -> tuple[float, int, float]:
        """
        Retrieve the total requested resources by a deployment.

        Parameters
        ----------
        deployment : model.Deployment
            The deployment for which resources are being computed.

        Returns
        -------
        tuple
            A tuple containing total requested CPU, RAM, and GPU resources.
        """
        total_requested_cpu, total_requested_ram, total_requested_gpu = 0.0, 0, 0.0
        for container_spec in deployment.CONTAINER_SPECS:
            requested_cpu, requested_ram, requested_gpu = self._get_container_requested_resources(container_spec)
            total_requested_cpu += requested_cpu
            total_requested_ram += requested_ram
            total_requested_gpu += requested_gpu  # Summing up the GPU requirements for each container

        # Ensure that the total GPU requirement does not exceed 1.0 (100%)
        if total_requested_gpu > 1.0:
            AssertionError('GPU requirement must not exceed 1.0')

        return total_requested_cpu, total_requested_ram, total_requested_gpu

    def _has_sufficient_resources_for_container(self, container_spec: dict, node: model.Vm) -> bool:
        """
        Check if a node has sufficient resources to deploy a given container.

        Parameters
        ----------
        container_spec : dict
            The container spec to check resources for.
        node : model.Vm
            The node to check resources against.

        Returns
        -------
        bool
            True if there are sufficient resources, False otherwise.
        """
        requested_cpu, requested_ram, requested_gpu = self._get_container_requested_resources(container_spec)
        return self._has_sufficient_resources(requested_cpu, requested_ram, requested_gpu, node)