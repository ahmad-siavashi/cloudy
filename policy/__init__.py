""" The algorithms within the simulated environment. """

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import model


@dataclass
class Os(ABC):
    _VM: model.Vm
    _apps: list[model.App, ...] = field(init=False, default_factory=list)

    @abstractmethod
    def schedule(self, apps: list[model.App, ...]) -> list[bool, ...]:
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
    _HOST: model.Pm
    guests: list[model.Vm, ...] = field(init=False, default_factory=list)

    @abstractmethod
    def allocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        The allocate function is responsible for allocating a new VM on the host.
        It takes as input a list of VMs and returns a list of booleans, one per VM, indicating whether or not it was successfully allocated.

        :param self: Represent the instance of the class
        :param vms: list[Vm, ...]: Pass in the list of vms that need to be allocated
        :return: A list of boolean values
        """
        pass

    @abstractmethod
    def deallocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        The deallocate function is used to deallocate a list of VMs from the host.
        It returns a list of booleans, where each boolean indicates whether the VM was successfully deallocated or not.

        :param self: Represent the instance of the class
        :param vms: list[Vm, ...]: Specify the vms that are to be deallocated
        :return: A list of booleans
        """
        pass

    @abstractmethod
    def process(self, duration: int) -> list[model.Vm, ...]:
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
    _DATACENTER: model.DataCenter

    @abstractmethod
    def allocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        The allocate function is responsible for allocating the given VMs in the data center.
        It should return a list of booleans, where each boolean indicates whether or not a VM was successfully allocated.
        The order of these booleans should correspond to the order of VMs in the input list.

        :param self: Represent the instance of the class
        :param vms: list[Vm, ...]: Pass the list of vms to be allocated
        :return: A list of booleans
        """
        pass
