from dataclasses import dataclass

import cloca
import evque

import model
import policy


@dataclass
class VmpFirstFit(policy.Vmp):
    """
    The VmpFirstFit class inherits from the abstract Vmp class and implements
    a first-fit VM placement algorithm. This algorithm attempts to allocate
    VMs to the first host that has enough resources to accommodate them.
    """

    def allocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        The allocate function takes a list of VMs and attempts to allocate them
        on the hosts in the data center. It returns a list of booleans, where each
        boolean corresponds to whether or not that VM was successfully allocated.

        Parameters
        ----------
        vms : list[Vm, ...]
            pass in the list of vms or apps that need to be allocated

        Returns
        -------
            a list of booleans
        """
        results = []
        for vm in vms:
            for host in self.DATACENTER.HOSTS:
                if all(host.VMM.has_capacity(vm)):
                    results.extend(host.VMM.allocate([vm]))
                    self[vm] = host
                    evque.publish('vm.allocate', cloca.now(), host, vm)
                    break
            else:
                results.append(False)
        return results

    def deallocate(self, vms: list[model.Vm, ...]) -> list[bool, ...]:
        """
        Deallocates the specified instances.

        Parameters
        ----------
        vms : list of Vm
            List of virtual machine instances to be deallocated.

        Returns
        -------
        list of bool
            List of deallocation success statuses corresponding to each vm.
        """
        results = []
        for vm in vms:
            host = self[vm]
            results.extend(host.VMM.deallocate([vm]))
            del self[vm]
            evque.publish('vm.deallocate', cloca.now(), host, vm)
        return results

    def stopped(self) -> list[model.Vm, ...]:
        """
        Retrieves a list of stopped virtual machines or apps.

        Returns
        -------
        list of Vm or App
            List of virtual machine instances that are currently in a stopped state.

        Notes
        -----
        This method is used to retrieve a list of virtual machine instances that
        are currently in a stopped state. It iterates through the available virtual
        machine instances and identifies those that are not actively running.
        """
        stopped_vms = []
        for host in self.DATACENTER.HOSTS:
            # VMs in an idle state are treated as stopped, but other criteria can also be considered.
            stopped_vms.extend(host.VMM.idles())
        return stopped_vms

    def migrate(self) -> int:
        """
        Raises NotImplementedError as this method is not implemented.

        Returns
        -------
        int
            The number of successful migrations (not applicable).

        Raises
        ------
        NotImplementedError
            Always raised as this method is not implemented.
        """
        raise NotImplementedError()
