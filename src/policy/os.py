from dataclasses import dataclass

import cloca
import evque

import policy


@dataclass
class OsTimeShared(policy.Os):
    """
    This class is a subclass of the Os class and implements time-sharing scheduling.
    """

    def resume(self, cpu: tuple[int, ...], duration: int) -> list[int, ...]:
        """
        The resume function takes a tuple of integers representing the number of
        cycles available on each CPU core and an integer representing the duration for which
        the process may run uninterrupted. It then runs the apps in a time-sharing scheduling,
        then returns the consumed cycles.

        Parameters
        ----------
        cpu : tuple[int, ...]
            Represent the number of cycles for each CPU core.
        duration : int
            Determine how long the process should run for.

        Returns
        -------
        list[int, ...]
            Consumed cycles for each CPU core.
        """
        stopped_apps = []

        # Compute the initial cycles available for all cores
        remained_cycles = [core * duration for core in cpu]

        num_apps = len(self)
        for app in self:
            if not app.has_resumed_once():
                evque.publish(f'{type(app).__name__.lower()}.start', cloca.now(), self.VM, app)

            available_cycles = [core * duration // num_apps for core in remained_cycles]
            consumed_cycles = app.resume(available_cycles)

            # Calculate the remaining cycles after the app has consumed some
            for i in range(len(remained_cycles)):
                remained_cycles[i] -= consumed_cycles[i]

            if app.is_stopped():
                stopped_apps.append(app)

            num_apps -= 1
            if not num_apps:
                break

        # Terminate finished apps
        for stopped_app in stopped_apps:
            self.terminate([stopped_app])
            evque.publish(f'{type(app).__name__.lower()}.stop', cloca.now(), self.VM, stopped_app)

        # Return the cycles consumed on each core
        return [core * duration - rc for core, rc in zip(cpu, remained_cycles)]
