from dataclasses import dataclass
from typing import Generator

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
        self._vm_cpu: dict[model.Vm, set[int, ...]] = {}
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
        if len(self._free_cpu) >= vm.CPU and self._free_ram >= vm.RAM:
            if not vm.GPU or any(self.find_gpu_blocks(vm.GPU)):
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
            if not self.has_capacity(vm):
                results.append(False)
                continue
            self._vm_cpu[vm] = {self._free_cpu.pop() for core in range(vm.CPU)}
            self._free_ram -= vm.RAM
            if vm.GPU:
                gpu_idx, gpu_blocks = next(self.find_gpu_blocks(vm.GPU))
                self._vm_gpu[vm] = gpu_idx, gpu_blocks
                self._free_gpu[gpu_idx].difference_update(gpu_blocks)
            self._guests.append(vm)
            results.append(True)
            vm.turn_on()
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
            if vm not in self:
                results.append(False)
                continue
            self._free_cpu.update(self._vm_cpu[vm])
            del self._vm_cpu[vm]
            self._free_ram += vm.RAM
            if vm.GPU:
                gpu, blocks = self._vm_gpu[vm]
                self._free_gpu[gpu].update(blocks)
                del self._vm_gpu[vm]
            self._guests.remove(vm)
            results.append(True)
            vm.turn_off()
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

    def find_gpu_blocks(self, profile: tuple[int, int]) -> Generator[tuple[int, set[int, ...]], None, None]:
        """
        Yield GPU indices and available block sets for a given profile.

        This method iterates through the available GPU blocks of each GPU, checking against the profile requirements.
        When a matching set of contiguous blocks is found on a GPU, it yields a tuple containing the GPU index and
        the set of blocks where the profile can be placed.

        For example, invoking `find_gpu_blocks((2, 2))` will yield `(gpu_idx, {0, 1})` for a suitable `gpu_idx`.
        This indicates that the profile can occupy starting at the 0th location and extend across 2 blocks on the
        GPU with index `gpu_idx`.

        Parameters
        ----------
        profile : tuple[int, int]
            Represents the profile of the virtual GPU, including the number of compute engines and memory blocks needed.

        Yields
        ------
        tuple[int, set[int, ...]]
            Yields tuples where the first element is the index of a GPU and the second element is a set of blocks
            on that GPU where the profile can be placed.
        """
        _, num_memory_blocks = profile
        for gpu_idx, free_gpu_blocks in enumerate(self._free_gpu):
            for start in free_gpu_blocks:
                blocks = set(range(start, start + num_memory_blocks))
                if blocks.issubset(free_gpu_blocks):
                    yield gpu_idx, blocks
