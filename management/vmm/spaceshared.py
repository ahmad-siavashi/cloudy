from dataclasses import dataclass

from components import Vm
from management import Vmm


@dataclass
class VmmSpaceShared(Vmm):
    """
    A space-shared VM scheduler in which each VM receives dedicated slices of resources.
    """

    def __post_init__(self):
        """
        The __post_init__ function is called after the object has been initialized.
        This function is used to set up any additional attributes that are not part of the initialization process.
        In this case, we want to keep track of available CPUs and RAM on each host.

        :param self: Represent the instance of the class
        :return: None
        """
        self._free_cpu: list[int, ...] = list(range(len(self._HOST.CPU)))
        self._vm_cpu: dict[int, tuple[int, ...]] = dict()
        self._free_ram: int = self._HOST.RAM

    def allocate(self, vms: list[Vm, ...]) -> list[bool, ...]:
        """
        The allocate function takes a list of VMs and attempts to allocate them on the host.
        It returns a list of booleans indicating whether each VM was successfully allocated or not.

        :param self: Represent the instance of the class
        :param vms: list[Vm, ...]: Pass in a list of vms to the allocate function
        :return: A list of booleans, where each boolean indicates whether the corresponding vm was successfully allocated
        """
        results = []
        for vm in vms:
            if len(self._free_cpu) >= vm.CPU and self._free_ram >= vm.RAM:
                self._vm_cpu[id(vm)] = self._free_cpu[:vm.CPU]
                del self._free_cpu[:vm.CPU]
                self._free_ram -= vm.RAM
                self.guests += [vm]
                results += [True]
            else:
                results += [False]
        return results

    def deallocate(self, vms: list[Vm, ...]) -> list[bool, ...]:
        """
        The deallocate function takes a list of VMs and removes them from the host.
        It returns a list of booleans indicating whether each VM was successfully removed.

        :param self: Represent the instance of the class
        :param vms: list[Vm, ...]: Pass in a list of vms that we want to deallocate
        :return: A list of booleans
        """
        results = []
        for vm in vms:
            if vm in self.guests:
                self._free_cpu += self._vm_cpu[id(vm)]
                del self._vm_cpu[id(vm)]
                self._free_ram += vm.RAM
                self.guests.remove(vm)
                results += [True]
            else:
                results += [False]
        return results

    def process(self, duration: int) -> tuple[Vm, ...]:
        finished = []
        for vm in self.guests:
            vm_cpu = list(self._HOST.CPU[index] for index in self._vm_cpu[id(vm)])
            vm.OS.process(vm_cpu, duration)
            if vm.OS.finished():
                finished += [vm]
        return finished
