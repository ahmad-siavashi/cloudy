from dataclasses import dataclass
from typing import Optional

import model
import policy


@dataclass
class VmmSpaceShared(policy.Vmm):
    """
    A space-shared VM scheduler in which each VM receives dedicated blocks of resources.
    """

    def __post_init__(self):
        """
        The __post_init__ function is called after the object has been initialized.
        This function is used to set up any additional attributes that are not part of
        the initialization process. In this case, we want to keep track of available CPU,
        RAM, and GPU of the host.
        """
        super().__post_init__()
        self._free_cpu: set[model.Vm, ...] = {core for core in range(len(self.HOST.CPU))}
        self._vm_cpu: dict[int, set[int, ...]] = {}
        self._free_ram: int = self.HOST.RAM
        self._free_gpu: tuple[set[int], ...] = tuple({block for block in range(blocks)} for _, blocks in self.HOST.GPU)
        self._vm_gpu: dict[model.Vm, tuple[int, set[int, ...]]] = {}

    def has_capacity(self, vm: model.Vm) -> bool:
        """
        Check if the host has enough resources to allocate the given virtual machine.

        Parameters
        ----------
        vm : Vm
            Virtual machine for which resource allocation check is performed.

        Returns
        -------
        bool
            `True` if the virtual machine can be allocated, otherwise `False`.
        """
        if len(self._free_cpu) >= vm.CPU and self._free_ram >= vm.RAM and (not vm.GPU or self._get_free_gpu(vm.GPU)):
            return True
        return False

    def allocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        The allocate function takes a list of VMs and attempts to allocate them on the host.
        It returns a list of booleans indicating whether each VM was successfully allocated or not.

        Parameters
        ----------
        vms : list[Vm, ...]
            pass in a list of vms to the allocate function

        Returns
        -------
            a list of booleans, where each boolean indicates whether the corresponding vm
            was successfully allocated
        """
        results = []
        for vm in vms:
            if self.has_capacity(vm):
                self._vm_cpu[vm] = {self._free_cpu.pop() for core in range(vm.CPU)}
                self._free_ram -= vm.RAM
                if vm.GPU:
                    free_gpu = self._get_free_gpu(vm.GPU)
                    free_gpu, free_block = self._vm_gpu[vm] = free_gpu
                    self._free_gpu[free_gpu].difference_update(free_block)
                self._guests += [vm]
                vm.turn_on()
                results.append(True)
            else:
                results.append(False)
        return results

    def deallocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        The deallocate function takes a list of VMs and removes them from the host.
        It returns a list of booleans indicating whether each VM was successfully removed.

        Parameters
        ----------
        vms : list[Vm, ...]
            pass in a list of vms that we want to deallocate

        Returns
        -------
            a list of booleans
        """
        results = []
        for vm in vms:
            if vm in self:
                self._free_cpu.update(self._vm_cpu[vm])
                del self._vm_cpu[vm]
                self._free_ram += vm.RAM
                if vm.GPU:
                    gpu, block = self._vm_gpu[vm]
                    self._free_gpu[gpu].update(block)
                    del self._vm_gpu[vm]
                self._guests.remove(vm)
                vm.turn_off()

                results.append(True)
            else:
                results.append(False)
        return results

    def resume(self, duration: int) -> policy.Vmm:
        """
        The process function is the main function of the scheduler. It takes a duration
        parameter and processes all VMs for that amount of time.

        Parameters
        ----------
        duration : int
            determine how long the cpu should be processing for
        """
        for vm in self:
            vm_cpu = [self.HOST.CPU[core] for core in self._vm_cpu[vm]]
            vm.OS.resume(vm_cpu, duration)
        return self

    def _can_allocate_gpu(self, vm: model.Vm, gpu: int, block: int) -> bool:
        """
        This function checks if a given virtual machine can be allocated on a specific GPU and block.

        Parameters
        ----------
        vm : Vm 
            represents a virtual machine
        gpu : int 
            the index of the GPU in the machine which needs to be allocated
        block : int 
            an integer representing the starting block in the GPU memory

        Returns
        -------
            a boolean value indicating whether the given GPU and memory block can be allocated for the given virtual machine (vm) or not
        """
        if not vm.GPU:
            raise ValueError
        free_gpu, free_block = gpu, {block + i for i in range(vm.GPU[1])}
        return free_block.issubset(self._free_gpu[free_gpu])

    def _get_free_gpu(self, gpu: tuple[int, int]) -> Optional[tuple[int, set[int, ...]]]:
        """
        The _get_free_gpu function is used to find a physical GPU with a contiguous set of memory blocks that
        can be allocated to a given virtual GPU. The function takes in the number of compute engines and memory blocks
        required by a given virtual GPU, and returns the index of the first free GPU (if one exists) along with a tuple
        containing indices of free memory blocks on that GPU which can be allocated for the virtual GPU.
        If no such contiguous set exists, None is returned.

        Parameters
        ----------
        gpu : tuple[int, int]
            represents the virtual GPU

        Returns
        -------
            index of first free physical GPU and free memory blocks
        """

        _PROFILE_BLOCK = {
            (1, 1): {0, 1, 2, 3, 4, 5, 6},
            (1, 2): {0, 2, 4, 6},
            (2, 2): {0, 2, 4},
            (3, 4): {0, 4},
            (4, 4): {0},
            (7, 8): {0}
        }

        _, num_memory_blocks = gpu
        placements = tuple(range(p, p + num_memory_blocks)
                           for p in _PROFILE_BLOCK.get(gpu, ()))

        for free_gpu_index, free_gpu_blocks in enumerate(self._free_gpu):
            for placement in map(set, placements):
                if placement.issubset(free_gpu_blocks):
                    return free_gpu_index, placement
        return ()
