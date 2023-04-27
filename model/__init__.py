""" The models of the simulated environment. """

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Type

import policy


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
            spent_cycles = min(cycles[c], threads[t])
            threads[t] -= spent_cycles
            cycles[c] -= spent_cycles
            if not threads[t]:
                t = (t + 1) % num_threads
            if not cycles[c]:
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
    - RAM (int): amount of RAM
    - GPU (tuple[()]|tuple[int, int]): (no. of compute engines, no. of memory slices)
    - OS (Type[Os]): operating system which determines creation and execution of applications
    """
    NAME: str
    CPU: int
    RAM: int
    GPU: tuple[()] | tuple[int, int]
    OS: Type[policy.Os]

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
    - RAM (int): amount of RAM
    - GPU (tuple[()]|tuple[tuple(int, int), ...]): list of GPUs in the form of [(no. of compute engines, no. of memory slices), ...]
    - VMM (Type[Vmm]): hypervisor which determines creation and execution of virtual machines
    """
    NAME: str
    CPU: tuple[int, ...]
    RAM: int
    GPU: tuple[()] | tuple[tuple[int, int], ...]
    VMM: Type[policy.Vmm]

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
    PLACEMENT: Type[policy.Placement]

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
