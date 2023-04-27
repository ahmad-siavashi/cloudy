from dataclasses import dataclass

import model
import policy


@dataclass
class VmmSpaceShared(policy.Vmm):
    """
    A space-shared VM scheduler in which each VM receives dedicated slices of resources.
    """

    def __post_init__(self):
        """
        The __post_init__ function is called after the object has been initialized.
        This function is used to set up any additional attributes that are not part of the initialization process.
        In this case, we want to keep track of available CPU, RAM, and GPU of the host.

        :param self: Represent the instance of the class
        :return: None
        """
        self._free_cpu: set[int, ...] = {core for core in range(len(self._HOST.CPU))}
        self._vm_cpu: dict[int, set[int, ...]] = dict()
        self._free_ram: int = self._HOST.RAM
        self._free_gpu: tuple[set[int], ...] = tuple({slice for slice in range(slices)} for _, slices in self._HOST.GPU)
        self._vm_gpu: dict[int, tuple[int, set[int, ...]]] = dict()

    def allocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        The allocate function takes a list of VMs and attempts to allocate them on the host.
        It returns a list of booleans indicating whether each VM was successfully allocated or not.

        :param self: Represent the instance of the class
        :param vms: list[Vm, ...]: Pass in a list of vms to the allocate function
        :return: A list of booleans, where each boolean indicates whether the corresponding vm was successfully allocated
        """
        results = []
        for vm in vms:
            if len(self._free_cpu) >= vm.CPU and self._free_ram >= vm.RAM and (not vm.GPU or (free_gpu := self._get_free_gpu(vm.GPU))):
                self._vm_cpu[id(vm)] = {self._free_cpu.pop() for core in range(vm.CPU)}
                self._free_ram -= vm.RAM
                if vm.GPU:
                    free_gpu, free_slice = self._vm_gpu[id(vm)] = free_gpu
                    self._free_gpu[free_gpu].difference_update(free_slice)
                self.guests += [vm]
                results += [True]
            else:
                results += [False]
        return results

    def deallocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
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
                self._free_cpu.update(self._vm_cpu[id(vm)])
                del self._vm_cpu[id(vm)]
                self._free_ram += vm.RAM
                if vm.GPU:
                    gpu, slice = self._vm_gpu[id(vm)]
                    self._free_gpu[gpu].update(slice)
                    del self._vm_gpu[id(vm)]
                self.guests.remove(vm)
                results += [True]
            else:
                results += [False]
        return results

    def process(self, duration: int) -> list[model.Vm, ...]:
        """
        The process function is the main function of the scheduler. It takes a duration
        parameter and processes all VMs for that amount of time. The return value is a list
        of finished VMs, which are removed from the scheduler.

        :param self: Refer to the object itself
        :param duration: int: Determine how long the cpu should be processing for
        :return: A list of vms that have finished their execution
        """
        finished = []
        for vm in self.guests:
            vm_cpu = list(self._HOST.CPU[index] for index in self._vm_cpu[id(vm)])
            vm.OS.process(vm_cpu, duration)
            if vm.OS.finished():
                finished += [vm]
        return finished

    def _get_free_gpu(self, gpu: tuple[int, int]) -> tuple[int, set[int, ...]] | tuple[()]:
        """
        The _get_free_gpu function is used to find a physical GPU with a contiguous set of memory slices that
        can be allocated to a given virtual GPU. The function takes in the number of compute engines and memory slices
        required by a given virtual GPU, and returns the index of the first free GPU (if one exists) along with a tuple
        containing indices of free memory slices on that GPU which can be allocated for the virtual GPU.
        If no such contiguous set exists, None is returned.

        :param gpu: tuple[int, int]: represents the virtual GPU
        :return: index of first free physical GPU and free memory slices
        """
        placements = self._get_gpu_placement(gpu)
        for free_gpu_idx, free_gpu_slices in enumerate(self._free_gpu):
            for placement in map(set, placements):
                if placement.issubset(free_gpu_slices):
                    return free_gpu_idx, placement
        return ()

    @staticmethod
    def _get_gpu_placement(gpu: tuple[int, int]) -> tuple[range, ...] | tuple[()]:
        """
        This function is used to determine the order of placements for a given virtual GPU in the physical GPU memory.
        The function takes in a tuple of integers, which represents a virtual GPU where the first integer in the tuple
        represents the number of compute engines, and the second integer represents the number of memory slices.
        For example, (2, 2) means that we have a virtual GPU with 2 compute engines and 2 memory slices.
        The function returns an ordered list containing physical GPU memory slice placements for the virtual GPU.

        Remarks
        =======
        The sequences of placement returned by this function are obtained from NVIDIA driver version 495.29.05

        :param gpu: tuple[int, int]: represents the virtual GPU
        :return: ordered list of physical GPU memory slices to place the virtual GPU
        """
        if gpu == (1, 1):
            placement = (6, 4, 5, 0, 1, 2, 3)
        elif gpu == (2, 2):
            placement = (4, 0, 2)
        elif gpu == (3, 4):
            placement = (4, 0)
        elif gpu == (4, 4):
            placement = (0,)
        elif gpu == (7, 8):
            placement = (0,)
        else:
            return ()

        num_compute_engines, num_memory_slices = gpu
        placements = tuple(range(p, p + num_memory_slices) for p in placement)
        return placements
