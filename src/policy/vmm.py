from dataclasses import dataclass

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
        has_cpu_capacity = len(self._free_cpu) >= vm.CPU
        has_ram_capacity = self._free_ram >= vm.RAM
        has_gpu_capacity = not vm.GPU or any(self.find_gpu_blocks(vm.GPU, gpu) for gpu in self._free_gpu)

        return has_cpu_capacity, has_ram_capacity, has_gpu_capacity

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
            # Check if there is enough overall capacity (CPU, RAM, GPU) for the VM
            if not all(self.has_capacity(vm)):
                results.append(False)
                continue
            self._vm_cpu[vm] = {self._free_cpu.pop() for core in range(vm.CPU)}
            self._free_ram -= vm.RAM
            if vm.GPU:
                for gpu_idx, free_gpu in enumerate(self._free_gpu):
                    if all_gpu_blocks := self.find_gpu_blocks(vm.GPU, free_gpu):
                        gpu_blocks = all_gpu_blocks.pop(0)
                        free_gpu.difference_update(gpu_blocks)
                        self._vm_gpu[vm] = gpu_idx, gpu_blocks
                        break
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
            if vm.is_on():
                vm_cpu = [self.HOST.CPU[core] for core in self._vm_cpu[vm]]
                vm.OS.resume(vm_cpu, duration)
        return self

    def find_gpu_blocks(self, profile: tuple[int, int], gpu: set[int, ...]) -> list[set[int], ...]:
        """
        Find available GPU block sets that match a given profile on a specific GPU.

        This method iterates through the available GPU blocks, checking them against the profile requirements.
        It identifies sets of contiguous blocks on a GPU that match the profile's needs and collects these sets.

        Parameters
        ----------
        profile : tuple[int, int]
            A tuple representing the profile of the virtual GPU. The first element is the number of compute engines
            needed, and the second element is the number of memory blocks needed.
        gpu : set[int, ...]
            A set representing available memory blocks on a specific GPU.

        Returns
        -------
        list[set[int, ...], ...]
            A list of sets, where each set contains contiguous memory blocks on the GPU where the profile can be placed.
        """
        result = []
        _, num_memory_blocks = profile
        for start in gpu:
            blocks = set(range(start, start + num_memory_blocks))
            if blocks.issubset(gpu):
                result.append(blocks)
        return result
