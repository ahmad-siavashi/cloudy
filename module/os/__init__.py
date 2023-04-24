from module import Os, App


class OsFcfs(Os):
    """
    This class is a subclass of the Os class and it implements the first-come-first-served algorithm for
    application, i.e. process, scheduling.
    """

    def schedule(self, apps: list[App, ...]) -> list[bool, ...]:
        """
        The schedule function takes a list of apps and schedules them on the
            scheduler. It returns a list of booleans indicating whether each app was
            scheduled successfully or not.

        :param self: Represent the instance of the class
        :param apps: list[App, ...]: Pass in a list of apps to the schedule function
        :return: A list of booleans
        """
        results = []
        for app in apps:
            self._apps += [app]
            results += [True]
        return results

    def process(self, cpu: tuple[int, ...], duration: int) -> tuple[int, ...]:
        """
        The process function takes a list of integers representing the number of
        cores available on each CPU and an integer representing the duration for which
        the process should run. It then runs all apps in parallel, using as many cores
        as necessary to complete them within that time. If any app is not completed by
        the end of this period, it will be left with some remaining work.

        :param self: Represent the instance of the class
        :param cpu: list[int, ...]: Represent the number of cores in each cpu
        :param duration: int: Determine how long the process should run for
        :return: The remaining cycles of processors
        """
        cycles = [core * duration for core in cpu]
        for app in self._apps:
            if any(cycles) and not app.finished():
                cycles = app.process(cycles)
            elif not any(cycles):
                break
        return tuple(cycles)
