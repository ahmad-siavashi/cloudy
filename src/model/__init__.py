""" The models of the simulated environment. """

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Type, Optional, Callable

import cloca

import policy


class BaseMeta(type):
    """
        Metaclass for the Base class.

        This metaclass is responsible for modifying the behavior of the generated data class. If the data class
        doesn't provide a custom __hash__ method, it sets the __hash__ method to the one from the Base class.

        Attributes
        ----------
        name : str
            The name of the class.
        bases : tuple
            A tuple of the base classes.
        class_dict : dict
            The dictionary containing the attributes and methods of the class.
        """

    def __init__(cls, name, bases, class_dict):
        if "__hash__" not in class_dict:
            # If the class doesn't provide a custom __hash__ method, use the one from the Base class
            cls.__hash__ = Base.__hash__


@dataclass(kw_only=True)
class Base(metaclass=BaseMeta):
    """
    Base class providing common functionality for data classes. This class includes
    custom __eq__ and __hash__ methods based on object ids.
    """

    def __eq__(self, other):
        """
        Compare the equality of two instances based on their object ids.
        """
        if isinstance(other, self.__class__):
            return id(self) == id(other)
        return False

    def __hash__(self):
        """
        Calculate the hash value of the instance based on its object id.
        """
        return hash(id(self))


@dataclass(kw_only=True)
class App(Base):
    """
    The App class represent a single application instance in cloud.

    Attributes
    ----------
    NAME : str
        name of the application
    LENGTH : tuple[int, ...]
        length of application threads, in cycles
    EXPIRATION : Optional[int]
        time at which the application expires
    """
    NAME: str
    LENGTH: tuple[int, ...]
    EXPIRATION: Optional[int] = field(default=None)

    def __post_init__(self):
        """
        The __post_init__ function is called after the object has been initialized.
        It allows post-initialization processing, such as setting up a list of remaining values.
        """
        # denotes initialization of app instances
        self.__has_resumed_once: bool = False
        # remained length of application threads
        self._remained: list[int, ...] = list(self.LENGTH)

    def has_resumed_once(self) -> bool:
        """
        Property to check if the app has resumed at least once.
        """
        return self.__has_resumed_once

    def restart(self) -> App:
        """
        Resets the remained list to its original length.

        Returns
        -------
        App
            Returns the current instance of the App.
        """
        self._remained = list(self.LENGTH)
        return self

    def resume(self, cpu: tuple[int, ...]) -> list[int, ...]:
        """
        Simulates the resumption of the app on the given CPU cores.

        Parameters
        ----------
        cpu : tuple[int, ...]
            Tuple representing the CPU cores.

        Returns
        -------
        list[int, ...]
            List of consumed cycles for each core.
        """
        num_cores = len(cpu)
        num_threads = len(self._remained)
        remaining_cycles = list(cpu)
        consumed_cycles = [0] * num_cores

        if not self.__has_resumed_once:
            self.__has_resumed_once = True

        thread_idx = 0
        for core_idx in range(num_cores):
            while remaining_cycles[core_idx] > 0 and not self.is_stopped():
                cycles_to_spend = min(remaining_cycles[core_idx], self._remained[thread_idx])
                self._remained[thread_idx] -= cycles_to_spend
                remaining_cycles[core_idx] -= cycles_to_spend
                consumed_cycles[core_idx] += cycles_to_spend
                thread_idx = (thread_idx + 1) % num_threads

        return consumed_cycles

    def is_stopped(self) -> bool:
        """
        Checks if the app is stopped.

        Returns
        -------
        bool
            True if the app is stopped, False otherwise.
        """
        # Check if the current time has surpassed the expiration time
        if self.EXPIRATION is not None and cloca.now() >= self.EXPIRATION:
            return True
        return not any(self._remained)


@dataclass(kw_only=True)
class Container(App):
    """
    A container is a lightweight and isolated runtime environment that encapsulates an application.

    Attributes
    ----------
    CPU : tuple[float, float]
        required and limit of CPU for the container
    RAM : tuple[int, int]
        required and limit of RAM for the container
    GPU : Optional[tuple[int, int] | float]
        required GPU profile (or fraction) for the container
    """
    CPU: tuple[float, float]
    RAM: tuple[int, int]
    GPU: Optional[tuple[int, int] | float]


@dataclass(kw_only=True)
class Controller(App):
    """
    The Controller class serves as the central controller for a cluster.
    It acts as the brain behind the cluster's control plane, overseeing the cluster's resources,
    applications, and services. The Controller ensures that desired configurations and policies
    are enforced across the cluster. It monitors the state of the cluster, handles events,
    and takes actions to reconcile the observed state with the desired state.

    Attributes
    ----------
    CONTROL_PLANE : Type[policy.ControlPlane]
        the control plane of the cluster
    NODES : list[Vm, ...]
        list of cluster nodes
    """
    NODES: list[Vm, ...]
    CONTROL_PLANE: Type[policy.ControlPlane]

    def __post_init__(self):
        """
        Perform post-initialization steps for the object.

        This method is automatically called after the object is initialized. It schedules
        worker applications on the nodes defined in `self.NODES` and initializes the
        `self.CONTROL_PLANE` attribute with an instance of the control plane class.
        """
        super().__post_init__()
        # A worker service is scheduled on the worker nodes
        for node in self.NODES:
            node.OS.schedule([App(NAME='worker', LENGTH=self.LENGTH)])
        self.CONTROL_PLANE = self.CONTROL_PLANE(self)

    def resume(self, cpu: tuple[int, ...]) -> list[int, ...]:
        """
        Process the object on the given CPU.

        This method manages the control plane, calls the parent class's `resume` method to
        execute the object on the specified CPU, and checks if the object has finished
        execution. If the object has finished, the control plane is terminated.

        Parameters
        ----------
            cpu (tuple[int, ...]): The CPU on which the object is to be processed.

        Returns
        -------
            consumed cycles by the application
        """
        self.CONTROL_PLANE.manage()
        consumed_cycles = super().resume(cpu)
        return consumed_cycles

    def is_stopped(self) -> bool:
        """
        Check if the object has finished processing.

        This method checks if the object has completed its processing by calling the parent
        class's `has_stopped` method and also considering the status of the control plane.

        Returns
        -------
            bool: True if the object has finished processing, False otherwise.
        """
        return super().is_stopped() or self.CONTROL_PLANE.is_stopped()


@dataclass(kw_only=True)
class Deployment(Base):
    """
    Represents a Deployment.

    Attributes
    ----------
    NAME : str
        The name of the deployment.
    CONTAINER_SPECS : list[Dict, ...]
        A list of container blueprints or specifications that make up the deployment.
    replicas : int
        The desired number of replicas (instances) of the application.

    Example
    -------
    To create a deployment:

    container_spec_1 = {
        "NAME": "WebServer",
        "LENGTH": (1000, 1500),
        "CPU": (1.0, 2.0),
        "RAM": (512, 1024),
        "GPU": None
    }

    container_spec_2 = {
        "NAME": "Database",
        "LENGTH": (2000, 2500),
        "CPU": (0.5, 1.5),
        "RAM": (256, 512),
        "GPU": (1, 2)
    }

    container_specs = [container_spec_1, container_spec_2]

    deployment = Deployment(NAME="MyDeployment", replicas=3, CONTAINER_SPECS=container_specs)
    """

    NAME: str
    CONTAINER_SPECS: list[dict, ...]
    replicas: int

    def __iter__(self):
        """
        Returns an iterator over the 'CONTAINER_SPECS' list.

        Returns
        -------
        Iterator[Container]
            An iterator yielding the Container specs in the 'CONTAINER_SPECS' list.
        """
        return iter(self.CONTAINER_SPECS)


@dataclass(kw_only=True)
class Vm(Base):
    """
    The Vm class represent a virtual machine instance in cloud.

    Attributes
    ----------
    NAME : str
        name of the virtual machine
    CPU : int
        number of cores; core speed depends on the host machine
    RAM : int
        amount of RAM
    GPU : Optional[tuple[int, int]]
        no. of compute engines, no. of memory blocks
    OS : Type[Os]
        operating system which determines creation and execution of applications
    state : Literal['ON', 'OFF']
        denotes the state of the virtual machine
    """
    NAME: str
    CPU: int
    RAM: int
    GPU: Optional[tuple[int, int]]
    OS: Type[policy.Os]

    STATE_ON = 'ON'
    STATE_OFF = 'OFF'

    state: Literal[STATE_ON, STATE_OFF] = field(init=False, default=STATE_OFF)

    def __post_init__(self):
        """
        The __post_init__ function is a special function that runs after the object has been initialized. It allows
        us to do some additional setup on our objects, like setting up attributes that depend on other attributes.
        """
        self.OS = self.OS(self)

    def turn_on(self) -> Vm:
        """
        Turns the virtual machine on.
        """
        self.state = Vm.STATE_ON
        return self

    def turn_off(self) -> Vm:
        """
        Turns the virtual machine off.
        """
        self.state = Vm.STATE_OFF
        self.OS.restart()
        return self

    def is_on(self) -> bool:
        """
        Returns True if the virtual machine is on, False otherwise.

        Returns
        -------
            True if the virtual machine is on, False otherwise.
        """
        return self.state == Vm.STATE_ON

    def is_off(self) -> bool:
        """Returns True if the virtual machine is off, False otherwise.

        Returns
        -------
            True if the virtual machine is off, False otherwise.
        """
        return not self.is_on()


@dataclass(kw_only=True)
class Pm(Base):
    """
    The Pm class represent a physical machine, i.e. host, in the data center.

    Attributes
    ----------
    NAME : str
        name of the physical machine
    CPU : tuple[int, ...]
        cycles of cores per simulation time unit
    RAM : int
        amount of RAM
    GPU : Optional[tuple[tuple[int, int], ...]]
        list of GPUs in the form of [(no. of compute engines, no. of memory blocks), ...]
    VMM : Type[Vmm])
        hypervisor which determines creation and execution of virtual machines
    """
    NAME: str
    CPU: tuple[int, ...]
    RAM: int
    GPU: Optional[tuple[tuple[int, int], ...]]
    VMM: Type[policy.Vmm]

    def __post_init__(self):
        """
        The __post_init__ function is called after the object has been initialized.
        This allows you to do some post-initialization processing, without having to
        call a separate function (which would require you to pass in all the arguments).
        """
        self.VMM = self.VMM(self)


@dataclass(kw_only=True)
class DataCenter(Base):
    """
    The DataCenter class represent a data center in cloud.

    Attributes
    ----------
    NAME : str
        name of the data center
    HOSTS : list[Pm, ...]
        physical machines of data center
    VMP : Type[Placement]
        management utility which determines assignment of virtual machines to physical machines
    """
    NAME: str
    VMP: Type[policy.Vmp]
    HOSTS: list[Pm, ...] = field(default_factory=list)

    def __post_init__(self):
        """
        The __post_init__ function is called after the object has been initialized.
        It allows additional initialization steps that require access to the instance, e.g.:
            def __post_init__(self):
                self.VMP = self.VMP(self)
        """
        self.VMP = self.VMP(self)

    def __iter__(self):
        """
        Return an iterator for the object.

        This method allows the object to be iterable, and it returns an iterator over the
        hosts in the data center.

        Returns
        -------
            An iterator over the hosts in the data center.
        """
        return iter(self.HOSTS)


@dataclass(kw_only=True)
class User(Base):
    """
    The User class represents a cloud user.

    Attributes
    ----------
    NAME : str
        name of the user
    REQUESTS : list[Action, ...]
        list of user requests
    """
    NAME: str
    REQUESTS: list[Action, ...] = field(default_factory=list)

    def __iter__(self):
        """
        Return an iterator for the object.

        This method allows the object to be iterable, and it returns an iterator over the
        requests of the user.

        Returns
        -------
            An iterator over the requests of the user.
        """
        return iter(self.REQUESTS)


@dataclass(kw_only=True)
class Action(Base):
    """
    The Action class represents a callable action to be executed. Actions can be
    associated with a user or exist independently as a simulation element.

    Attributes
    ----------
    EXECUTE : Callable[[], None]
        The callable function to be executed.
    ARRIVAL : int
        Arrival time of the action, in simulation time unit.
    """
    ARRIVAL: int
    EXECUTE: Callable[[], Any]


@dataclass(kw_only=True)
class Request(Action):
    """
    The Request class represents a request that arrives at the data center.
    Requests are usually associated with a User.

    Attributes
    ----------
    VM : Vm
        A virtual machine.
    REQUIRED : bool
        True if this action is required for initialization, False otherwise.
    IGNORED : bool
        When set to True, this request won't be counted in stats.
        Usually used for requests that are part of simulation initialization.
    EXECUTE : Callable[[], None], optional
        The callable function to be executed. Defaults to None.
    ON_SUCCESS : Callable[[], None], optional
        A function to be called upon successful execution of the request.
    ON_FAILURE : Callable[[], None], optional
        A function to be called upon failure in executing the request.
    """
    VM: Vm
    REQUIRED: bool = field(default=False)
    IGNORED: bool = field(default=False)
    EXECUTE: Optional[Callable[[], Any]] = None
    ON_SUCCESS: Optional[Callable[[], Any]] = None
    ON_FAILURE: Optional[Callable[[], Any]] = None
