""" The algorithms within the simulated environment. """

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import model


@dataclass
class Os(ABC):
    """
    This class is an abstract base class for operating systems.

    Attributes
    ----------
    VM : Vm
        the vm in which the operating system is installed
    """
    VM: model.Vm

    def __post_init__(self):
        # list of applications assigned to the operating system for execution
        self._running_apps: list[model.App, ...] = []
        # list of terminated apps
        self._stopped_apps: list[model.App, ...] = []

    def __contains__(self, app: model.App) -> bool:
        """
        Check if an app is present in the operating system.

        Parameters
        ----------
        app : App
            An instance of class `model.App` to check for existence.

        Returns
        -------
        bool
            True if the app is present in the operating system, False otherwise.
        """
        return app in self._running_apps

    def __iter__(self):
        """
        Return an iterator over all the running apps in the operating system.

        Returns
        -------
            An iterator over all the running apps in the operating system.
        """
        return iter(self._running_apps)

    def __len__(self) -> int:
        """
        Return the number of applications scheduled by the OS.
        This method returns the number of applications scheduled by the scheduler. It counts
        the total number of applications present in the `_apps` attribute of the scheduler.

        Returns

            The number of applications scheduled by the scheduler.
        """
        return len(self._running_apps)

    def __contains__(self, app: model.App) -> bool:
        """
        Check if the given app is currently managed or scheduled by the OS.

        Parameters
        ----------
        app : App
            The app instance to check for.

        Returns
        -------
        bool
            True if the app is managed by the OS, False otherwise.
        """
        return app in self._running_apps or app in self._stopped_apps

    def schedule(self, apps: list[model.App, ...]) -> list[bool, ...]:
        """
        The schedule function takes a list of apps and schedules them on the
            scheduler. It returns a list of booleans indicating whether each app was
            scheduled successfully or not.

        Parameters
        ----------
        apps : list[App, ...]
            pass in a list of apps to the schedule function
        
        Returns
        -------
            a list of booleans
        """
        self._running_apps.extend(apps)
        return [True] * len(apps)

    def terminate(self, apps: list[model.App, ...]) -> Os:
        """
        This method terminates an app within the operating system.

        Parameters
        ----------
        apps : list[App, ...]
            list of instance of class `model.App` that needs to be terminated
        """
        for app in apps:
            self._running_apps.remove(app)
            self._stopped_apps.append(app)
        return self

    def restart(self) -> Os:
        """
        The function restarts the operating system.
        It discards any app running.
        """
        self._running_apps.clear()
        self._stopped_apps.clear()
        return self

    @abstractmethod
    def resume(self, cpu: tuple[int, ...], duration: int) -> list[int, ...]:
        """
        The resume function is the main function of the scheduler. It takes in a list of processors and an amount
        of time that they can run uninterrupted, and returns list of consumed cycles.

        Parameters
        ----------
        cpu : tuple[int, ...]
            indicate the processors that are available
        duration : int
            determine how long the cpu can run uninterrupted

        Returns
        -------
            list of consumed cycles
        """
        pass

    def stopped(self) -> list[model.App, ...]:
        """
        This function returns applications stopped running since last call to it.

        Returns
        -------
            list of stopped applications since last call
        """
        finished_apps = self._stopped_apps
        self._stopped_apps = []
        return finished_apps

    def is_idle(self) -> bool:
        """
        Checks whether there are any running applications.

        Returns
        -------
            A Boolean flag that is True when there is no running application
        """
        return not bool(self._running_apps)


@dataclass
class Vmm(ABC):
    """
    This class provides a template for implementing virtual machine managers that can allocate and deallocate VMs on
    a host and process.

    Attributes
    ----------
    HOST : Pm
        the physical machine on which the virtual machines managed by the Vmm instance are running
    """

    HOST: model.Pm

    def __post_init__(self):
        # the list of allocated VMs
        self._guests: list[model.Vm, ...] = []

    def __contain__(self, vm: model.Vm) -> bool:
        """
        Check if a Vm instance is present in the list of allocated VMs.

        Parameters
        ----------
        vm : Vm
            A virtual machine instance.

        Returns
        -------
        bool
            True if the VM instance is present in the allocated VMs list, False otherwise.
        """
        return vm in self._guests

    def __iter__(self):
        """
        Return an iterator for iterating over each Vm instance in the list of allocated VMs.

        Returns
        -------
            An iterator object for the allocated VMs list.
        """
        return iter(self._guests)

    def __len__(self) -> int:
        """
        Return the number of guests managed by the host.

        This method returns the number of guests managed by the host.

        Returns

            The number of guests managed by the host.
        """
        return len(self._guests)

    @abstractmethod
    def has_capacity(self, vm: model.Vm) -> tuple[bool, bool, bool]:
        """
        Check if the host has enough CPU, RAM, and GPU resources to allocate the given virtual machine.

        Parameters
        ----------
        vm : Vm
            Virtual machine for which resource allocation check is performed.

        Returns
        -------
        tuple[bool, bool, bool]
            A tuple where the first element indicates if there is enough CPU,
            the second if there is enough RAM,
            and the third if there is enough GPU capacity.
            Each element is `True` if there is enough capacity, otherwise `False`.
        """
        pass

    @abstractmethod
    def allocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        The allocate function is responsible for allocating a new VM on the host. It takes as input a list of VMs and
        returns a list of booleans, one per VM, indicating whether it was successfully allocated.

        Parameters
        ----------
        vms : list[Vm, ...]
            pass in the list of vms that need to be allocated
        Returns
        -------
            a list of boolean values
        """
        pass

    @abstractmethod
    def deallocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        The deallocate function is used to deallocate a list of VMs from the host.
        It returns a list of booleans, where each boolean indicates whether the VM was successfully deallocated or not.

        Parameters
        ----------
        vms : list[Vm, ...]
            the vms that are to be deallocated

        Returns
        -------
            a list of booleans
        """
        pass

    @abstractmethod
    def resume(self, duration: int) -> Vmm:
        """
        The resume function processes the guest VMs OS for the specified duration.

        Parameters
        ----------
        duration : int
            the amount of time that the vms will run for
        """
        pass

    def idles(self) -> list[model.Vm, ...]:
        """
        The idles function returns list of guests that have no running load.

        Returns
        -------
            list of guest virtual machines with no running application
        """
        return [guest for guest in self._guests if guest.OS.is_idle()]


@dataclass
class Vmp(ABC):
    """
    The Placement class is an abstract base class for VM placement policies in the data center.

    Attributes
    ----------
    DATACENTER : model.DataCenter
        A data center instance whose resources are used for placement.
    """
    DATACENTER: model.DataCenter

    def __post_init__(self):
        # An internal mapping from VM instances to their respective nodes (PM).
        self._vm_pm: dict[model.Vm, model.Pm] = {}

    def __getitem__(self, vm: model.Vm) -> model.Pm:
        """
        Retrieve the node for a given VM instance using the instance as a key.

        Parameters
        ----------
        vm : model.Vm
            The VM instance whose node is to be retrieved.

        Returns
        -------
        model.Pm
            The corresponding node for the provided VM instance.

        Raises
        ------
        KeyError
            If the VM instance is not found in the placement.
        """
        return self._vm_pm[vm]

    def __setitem__(self, vm: model.Vm, pm: model.Pm):
        """
        Set the node (PM) for a given VM instance.

        Parameters
        ----------
        vm : model.Vm
            The VM instance to be placed.
        pm : model.Pm
            The PM instance where the VM is to be placed.
        """
        self._vm_pm[vm] = pm

    def __delitem__(self, vm: model.Vm):
        """
        Remove the VM instance from the placement.

        Parameters
        ----------
        vm : model.Vm
            The VM instance to be removed.
        """
        del self._vm_pm[vm]

    def __len__(self) -> int:
        """
        Returns the number of VMs currently placed.

        Returns
        -------
        int
            The number of VM instances in the placement.
        """
        return len(self._vm_pm)

    def empty(self) -> bool:
        """
        Check if there are any virtual machines placed.

        Returns
        -------
        bool
            True if there are no VMs placed, False otherwise.
        """
        return len(self) == 0

    @abstractmethod
    def allocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        Allocate the given VMs in the data center. The function returns a list
        of booleans, where each boolean indicates the success of allocation for each VM.
        The order of the booleans corresponds to the order of VMs in the input list.

        Parameters
        ----------
        vms : list[Vm, ...]
            List of VM instances to be allocated.

        Returns
        -------
        list of bool
            List indicating the success of each allocation.
        """
        pass

    def resume(self, duration: int) -> Vmp:
        """
        Resumes the execution of virtual machines after a suspension.

        Parameters
        ----------
        duration : int
            The duration for which the execution is resumed, in simulation time units.

        Returns
        -------
        Placement
            The placement instance itself.
        """
        for host in self.DATACENTER.HOSTS:
            host.VMM.resume(duration)
        return self

    @abstractmethod
    def deallocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        Deallocates the specified VM instances.

        Parameters
        ----------
        vms : list of Vm
            List of virtual machine instances to be deallocated.

        Returns
        -------
        list of bool
            List of deallocation success statuses corresponding to each VM instance.

        Notes
        -----
        This method is responsible for deallocating the given virtual machine instances.
        The method should iterate through the provided list of instances and perform
        the necessary deallocation steps for each instance. The deallocation status for
        each instance is recorded in the returned list of boolean values.
        """
        pass

    @abstractmethod
    def stopped(self) -> list[model.Vm, ...]:
        """
        Retrieves a list of stopped virtual machines.

        Returns
        -------
        list of Vm
            List of virtual machine instances that are currently in a stopped state.

        Notes
        -----
        This method is used to retrieve a list of virtual machine instances that are
        currently in a stopped state. It iterates through the available virtual machine
        instances and identifies those that are not actively running.

        The returned list contains the virtual machine instances that are currently
        in a stopped state.
        """
        pass

    def migrate(self) -> int:
        """
        Migrates selected VMs to suitable target physical machines.

        Returns
        -------
        int
            The number of successful migrations.
        """


@dataclass
class ControlPlane(ABC):
    """
    The ControlPlane class is an abstract base class that represents the policy included in a cluster controller.

    Attributes
    ----------
    CLUSTER_CONTROLLER : model.Controller
        the cluster controller of the control plane
    """

    CLUSTER_CONTROLLER: model.Controller

    def __post_init__(self):
        # Deployments submitted for execution
        self._pending_deployments: list[model.Deployment] = []
        # Deployments with a scaling request
        self._scaled_deployments: list[model.Deployment] = []

    def apply(self, deployment: model.Deployment) -> ControlPlane:
        """
        The function `apply` adds a deployment to the pending deployments queue and
        returns a boolean value to denote the result of creation.

        Parameters
        ----------
        deployment : model.Deployment
            The "deployment" parameter is a model.Deployment object.

        Returns
        -------
            the control plane itself

        """
        self._pending_deployments.append(deployment)
        return self

    def scale(self, deployment: model.Deployment, replicas: int) -> ControlPlane:
        """
        Scales the deployment with the given name to the given number of replicas.

        Parameters
        ---------
            deployment : model.Deployment
                the deployment that you want to delete
            replicas : int
                The number of replicas to scale the deployment to.

        Returns
        -------
            the control plane itself
        """
        deployment.replicas = replicas
        self._scaled_deployments.append(deployment)
        return self

    @abstractmethod
    def delete(self, deployment: model.Deployment, num_replicas: int = None) -> ControlPlane:
        """
        This function deletes deployment replicas and their containers.

        Parameters
        ----------
        deployment : model.Deployment
            The deployment that you want to delete
        num_replicas : int, optional
            Delete the specified number of replicas, or remove all if none is specified
        """
        pass

    @abstractmethod
    def is_stopped(self) -> bool:
        """
        The function checks if all finish criteria is met.

        Returns
        -------
            a boolean value.

        """
        pass

    @abstractmethod
    def manage(self):
        """
        The "manage" method monitors  the state of deployments and takes required actions.
        """
        pass
