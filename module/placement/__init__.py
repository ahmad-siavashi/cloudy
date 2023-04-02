from module import Placement, Vm


class PlacementFirstFit(Placement):
    """
    A class that inherits from the Placement class. It is a placement algorithm that attempts to allocate VMs to
    the first server that has enough resources to allocate the VM.
    """

    def allocate(self, vms: list[Vm, ...]) -> list[bool, ...]:
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
