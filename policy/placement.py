from dataclasses import dataclass

import model
import policy
from model import Pm


class PlacementFirstFit(policy.Placement):
    """
    A class that inherits from the Placement class. It is a placement algorithm that attempts to allocate VMs to
    the first server that has enough resources to allocate the VM.
    """

    def allocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        The allocate function takes a list of VMs and attempts to allocate them on the servers in the data center.
        It returns a list of booleans, where each boolean corresponds to whether or not that VM was successfully allocated.

        :param self: Refer to the object itself
        :param vms: list[Vm, ...]: Pass in the list of vms that need to be allocated
        :return: A list of booleans
        """
        results = []
        for vm in vms:
            for server in self._DATACENTER.SERVERS:
                if True in server.VMM.allocate([vm]):
                    results += [True]
                    break
            else:
                results += [False]
        return results


@dataclass
class PlacementMaxProfile(policy.Placement):
    """
    A class that inherits from the Placement class. It is a placement algorithm that attempts to allocate VMs to
    the first server that has enough resources to allocate the VM.
    """

    placements = {
        (1, 1): {0, 1, 2, 3, 4, 5, 6},
        (2, 2): {0, 2, 4},
        (3, 4): {0, 4},
        (4, 4): {0},
        (7, 8): {0}
    }

    profiles = [
        (1, 1),
        (2, 2),
        (3, 4),
        (4, 4),
        (7, 8)
    ]

    def __post_init__(self):
        """
        The __post_init__ function is called after the object has been initialized.
        This function can be used to perform additional initialization steps, such as
        adding attributes that are derived from other attributes or adding methods to
        the class.

        :param self: Represent the instance of the class
        :return: A dictionary of gpu objects and the server they are in
        """
        self.gpus = []
        self.gpu_pm = {}
        gpu_index = 0
        for server in self._DATACENTER.SERVERS:
            for gpu in server.VMM._free_gpu:
                self.gpus += [gpu]
                self.gpu_pm[gpu_index] = server
            gpu_index += 1

    def _profile_loc(self, profile: tuple[int, int], gpu: set[int, ...]) -> set[int, ...]:
        """
        The _profile_loc function takes a profile and a set of gpu slices, and returns the locations
        on which the profile can reside. For example: self._profile_loc((2, 2), {0, 1}) -> {0}

        :param profile: tuple[int, ...]: Specify the profile of the virtual gpu
        :param gpu: set[int, ...]: Indicate which physical gpu slices are available for the profile
        :return: The set of locations where the profile can be placed
        """
        _, memory_slices = profile
        placement = self.placements[profile]
        locs = []
        for loc in placement:
            slices = set(slice for slice in range(loc, loc + memory_slices))
            if all(slice in gpu for slice in slices):
                locs += [loc]
        return locs

    def _count_profile_loc(self, profile: tuple[int, int], gpu: set[int, ...]) -> int:
        """
        The _count_profile_loc function takes in a profile and a gpu, and returns the number of locations
        in that profile. The function is used to determine which profiles are valid for the given GPU.

        :param profile: tuple[int, ...]: Specify the profile of the virtual gpu
        :param gpu: set[int, ...]: Specify the slices of the physical gpu to use
        :return: The number of locations that the profile can be placed in
        """
        num_loc = len(self._profile_loc(profile, gpu))
        return num_loc

    def _count_profiles_loc(self, profiles: list[tuple[int, int], ...], gpu: set[int, ...]) -> int:
        """
        The _count_profiles_loc function takes a list of profiles and a physical gpu.
        It then sums the number of available locations for all profiles on the gpu.


        :param profiles: list[tuple[int, int], ...]: Store the list of profiles, i.e. virtual gpus
        :param gpu: set[int, ...]: Specify the gpu to be used
        :return: The number of locations that all profiles can be placed in the gpu
        """
        count = 0
        for profile in profiles:
            count += self._count_profile_loc(profile, gpu)
        return count

    def count_all_loc(self, profiles: list[tuple[int, int], ...], gpus: list[set[int, ...], ...]) -> list[tuple[int, int], ...]:
        """
        The count_all_loc function takes in a list of profiles and a list of gpus.
        It then returns the sum of all locations for all profiles on each gpu.


        :param profiles: list[tuple[int, int], ...]: List of all profiles, i.e. virtual gpus
        :param gpus: list[set[int, ...], ...]: Specify the list of physical gpus
        :return: Sum of all locations for all profiles on each gpu
        """
        count = []
        for i, gpu in enumerate(gpus):
            count += [(i, self._count_profiles_loc(profiles, gpu))]
        return count

    def solve(self, request: tuple[int, int], gpus: list[set[int, ...], ...]) -> tuple[()] | tuple[int, int]:
        counts = []
        for i, gpu in enumerate(gpus):
            for loc in self._profile_loc(request, gpu):
                if loc in self.placements[request]:
                    gpu.remove(loc)
                    count = sum(map(lambda x: x[1], self.count_all_loc(self.profiles, gpus)))
                    counts += [(i, loc, count)]
                    gpu.add(loc)
        if not counts:
            return ()
        gpu, loc, _ = max(counts, key=lambda c: c[2])
        return gpu, loc

    def allocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        The allocate function takes a list of VMs and attempts to allocate them on the servers in the data center.
        It returns a list of booleans, where each boolean corresponds to whether or not that VM was successfully allocated.

        :param self: Refer to the object itself
        :param vms: list[Vm, ...]: Pass in the list of vms that need to be allocated
        :return: A list of booleans
        """
        results = []
        for vm in vms:
            self.__post_init__()
            solution = self.solve(vm.GPU, self.gpus)
            if not solution:
                results += [False]
            else:
                gpu, slice = solution
                server = self.gpu_pm[gpu]
                gpu = gpu % len(server.GPU)
                if server.VMM.allocate_ex(vm, gpu, slice):
                    results += [True]
                else:
                    results += [False]
        return results
