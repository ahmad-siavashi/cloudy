from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Type


@dataclass
class App:
    """
    The App class represent a single application instance in cloud.

    Attributes
    ==========
    - NAME (str): name of the application
    - LENGTH (tuple[int, ...]): length of application threads, in cycles
    - _remained (list[int, ...], private): remained length of application threads, in cycles
    """
    NAME: str
    LENGTH: tuple[int, ...]
    _remained: list[int, ...] = field(init=False)

    def __post_init__(self):
        """
        The __post_init__ function is called after the object has been initialized.
        It allows us to do some post-initialization processing, such as setting up a list of remaining values.

        :param self: Refer to the instance of the class
        """
        self._remained = list(self.LENGTH)

    def remained(self) -> tuple[int, ...]:
        """
        The remained function returns a tuple of the remaining number of cycles required by each thread in
        this application to complete its execution.

        :param self: Refer to the instance of the class
        :return: A tuple of the remained cycles of application threads
        """
        return tuple(self._remained)

    def process(self, cycles: tuple[int, ...]) -> tuple[int, ...]:
        """
        The process function takes a tuple of integers as input, and returns a tuple of integers.
        The input is the number of cycles available to each processor in the system. The output is
        the remaining number of processor cycles after execution.

        :param self: Refer to the current object
        :param cycles: tuple[int, ...]: Pass in the available cycles of each processor
        :return: The remained cycles of processors
        """
        c = 0
        t = 0
        cycles = list(cycles)
        threads = self._remained
        num_cores = len(cycles)
        num_threads = len(threads)
        while any(cycles) and not self.finished():
            while cycles[c] and t < num_threads:
                spent_cycles = cycles[c] if threads[t] >= cycles[c] else threads[t]
                self._remained[t] -= spent_cycles
                cycles[c] -= spent_cycles
                t = (t + 1) % num_threads
            c = (c + 1) % num_cores
        return tuple(cycles)

    def finished(self) -> bool:
        """
        The finished function checks if the application is finished.
        It returns True if all the threads in the application have been finished, and False otherwise.

        :param self: Access the attributes of the class
        :return: True if the application is finished, and False otherwise
        """
        return not any(self.remained())


@dataclass
class Vm:
    """
    The Vm class represent a virtual machine instance in cloud.

    Attributes
    ==========
    - NAME (str): name of the virtual machine
    - CPU (int): number of cores; core speed depends on the host machine
    - RAM (int): amount of RAM, in megabytes
    - OS (Type[Os]): operating system which determines creation and execution of applications
    """
    NAME: str
    CPU: int
    RAM: int
    OS: Type[Os]

    def __post_init__(self):
        """
        The __post_init__ function is a special function that runs after the object has been initialized.
        It allows us to do some additional setup on our objects, like setting up attributes that depend on other attributes.

        :param self: Represent the instance of the class
        """
        self.OS = self.OS(self)


@dataclass
class Pm:
    """
    The Pm class represent a physical machine in the data center.

    Attributes
    ==========
    - NAME (str): name of the physical machine
    - CPU (tuple[int, ...]): cycles of cores per simulation time unit
    - RAM (int): amount of RAM in megabytes
    - VMM (Type[Vmm]): hypervisor which determines creation and execution of virtual machines
    """
    NAME: str
    CPU: tuple[int, ...]
    RAM: int
    VMM: Type[Vmm]

    def __post_init__(self):
        """
        The __post_init__ function is called after the object has been initialized.
        This allows you to do some post-initialization processing, without having to
        call a separate function (which would require you to pass in all of the arguments).

        :param self: Represent the instance of the class
        """
        self.VMM = self.VMM(self)


@dataclass
class DataCenter:
    """
    The DataCenter class represent a data center in cloud.

    Attributes
    ==========
    - NAME (str): name of the data center
    - SERVERS (list[Pm, ...]): physical machines of data center
    - PLACEMENT (Type[Placement]): management utility which determines assignment of virtual machines to physical machines
    """
    NAME: str
    SERVERS: list[Pm, ...]
    PLACEMENT: Type[Placement]

    def __post_init__(self):
        """
        The __post_init__ function is called after the object has been initialized.
        This allows you to do some additional initialization steps that require access to the instance, e.g.:
            def __post_init__(self):
                self.PLACEMENT = self.PLACEMENT(self)

        :param self: Represent the instance of the class
        """
        self.PLACEMENT = self.PLACEMENT(self)


@dataclass
class Request:
    """
    The Request class represents a request that arrives at the data center.

    Attributes
    ==========
    - ARRIVAL (int): arrival time of the request, in simulation time unit
    - VM (Vm): virtual machine instance
    """
    ARRIVAL: int
    VM: Vm


@dataclass
class User:
    """
    The User class represents a cloud user.

    Attributes
    ==========
    - NAME (str): name of the user
    - REQUESTS (list[Request, ...]): list of user requrests (e.g., vm provisioning)
    """
    NAME: str
    REQUESTS: list[Request, ...]


@dataclass
class Os(ABC):
    _VM: Vm
    _apps: list[App, ...] = field(init=False, default_factory=list)

    @abstractmethod
    def schedule(self, apps: list[App, ...]) -> list[bool, ...]:
        """
        The schedule function is responsible for scheduling the applications to run on the virtual machine.
        It takes a list of App objects as input and returns a list of booleans indicating whether each app was successfully scheduled or not.

        :param self: Represent the instance of a class
        :param apps: list[App, ...]: Pass in the list of apps that need to be scheduled
        :return: A list of booleans
        """
        pass

    @abstractmethod
    def process(self, cpu: tuple[int, ...], duration: int) -> tuple[int, ...]:
        """
        The process function is the main function of the scheduler. It takes in a list of processors and an amount
        of time that they can run uninterrupted, and returns an integer representing how much time it will take to finish
        all processes.

        :param self: Represent the instance of the class
        :param cpu: tuple[int, ...]: Indicate the processors that are available
        :param duration: int: Determine how long the cpu can run uninterrupted
        :return: The remaining cycles of processors
        """
        pass

    def finished(self) -> bool:
        """
        The finished function checks to see if all of the apps in the list are finished.
        If they are, it returns True. If not, it returns False.

        :param self: Refer to the object itself
        :return: A boolean value
        """
        return all(app.finished() for app in self._apps)


@dataclass
class Vmm(ABC):
    """
    This class provides a template for implementing virtual machine managers that can allocate and deallocate VMs on a host and process.

    Attributes
    ==========
    _HOST(Pm, private): the physical machine on which the virtual machines managed by the Vmm instance are running
    guests (list[Vm, ...]): the list of allocated VMs
    """
    _HOST: Pm
    guests: list[Vm, ...] = field(init=False, default_factory=list)

    @abstractmethod
    def allocate(self, vms: list[Vm, ...]) -> list[bool, ...]:
        """
        The allocate function is responsible for allocating a new VM on the host.
        It takes as input a list of VMs and returns a list of booleans, one per VM, indicating whether or not it was successfully allocated.

        :param self: Represent the instance of the class
        :param vms: list[Vm, ...]: Pass in the list of vms that need to be allocated
        :return: A list of boolean values
        """
        pass

    @abstractmethod
    def deallocate(self, vms: list[Vm, ...]) -> list[bool, ...]:
        """
        The deallocate function is used to deallocate a list of VMs from the host.
        It returns a list of booleans, where each boolean indicates whether the VM was successfully deallocated or not.

        :param self: Represent the instance of the class
        :param vms: list[Vm, ...]: Specify the vms that are to be deallocated
        :return: A list of booleans
        """
        pass

    @abstractmethod
    def process(self, duration: int) -> tuple[Vm, ...]:
        """
        The process function is the main function of the Host class. It takes a duration as an argument, and processes
        the guest vms OS for that amount of time. Then it checks if any VMs have finished running, and returns them in a list.

        :param self: Represent the instance of a class
        :param duration: int: Specify the amount of time that the vms will run for
        :return: A list of finished vms
        """
        pass

    def idle(self) -> bool:
        """
        The idle function returns True if all of the guests have no running load.

        :param self: Refer to the object itself
        :return: True if all the guests have finished executing, and False otherwise.
        """
        return all(guest.OS.finished() for guest in self.guests)


@dataclass
class Placement(ABC):
    _DATACENTER: DataCenter

    @abstractmethod
    def allocate(self, vms: list[Vm, ...]) -> list[bool, ...]:
        """
        The allocate function is responsible for allocating the given VMs in the data center.
        It should return a list of booleans, where each boolean indicates whether or not a VM was successfully allocated.
        The order of these booleans should correspond to the order of VMs in the input list.

        :param self: Represent the instance of the class
        :param vms: list[Vm, ...]: Pass the list of vms to be allocated
        :return: A list of booleans
        """
        pass
