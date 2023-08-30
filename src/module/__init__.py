""" The components of the simulator. """

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import groupby
from typing import Callable

import cloca
import evque

import model


@dataclass
class Tracker:
    """Tracks request labels: total, accepted, and rejected."""

    _counts: dict[str, int] = field(default_factory=lambda: {
        'requests': 0,
        'accepted': 0,
        'rejected': 0
    })

    def reset(self) -> Tracker:
        """Reset the label counters."""
        for key in self._counts:
            self._counts[key] = 0
        return self

    def record(self, label: str, count: int = 1) -> Tracker:
        """
        Increment the specified label's counter.

        Parameters
        ----------
        label : str
            Label type ('requests', 'accepted', 'rejected').
        count : int, optional
            Number of labels, default is 1.

        Returns
        -------
        Tracker
            Updated tracker instance.
        """
        if label in self._counts:
            self._counts[label] += count
        return self

    def has_pending(self) -> bool:
        """Check if there are any pending requests."""
        return self._counts['requests'] - self._counts['accepted'] - self._counts['rejected'] > 0

    def stats(self) -> dict[str, int]:
        """Retrieve all request label counts."""
        return self._counts.copy()


@dataclass
class Simulation:
    """
    This class represents a simulation.

    Attributes
    ----------
    NAME : str
        name of the simulation
    USER : User
        the user and its requests
    DATACENTER : DataCenter
        the data center associated with the simulation
    CLOCK_RESOLUTION : int
        the resolution of the simulation clock
    """
    NAME: str
    USER: model.User
    DATACENTER: model.DataCenter
    CLOCK_RESOLUTION: int = field(default=1)

    def __post_init__(self):
        """
        The __post_init__ function is a special function that is called after the __init__ function.
        It allows us to initialize variables that are not passed as arguments to the constructor, but rather
        are initialized based on other attributes of the class. In this case, we want to initialize our EventQueue,
        Logger and Clock objects.
        """
        # This object will be used to record events during the simulation.
        self._tracker: Tracker = Tracker()
        # Reset global simulation clock.
        cloca.reset()

        # Subscribe to event topics
        for topic, handler in [
            ('request.arrival', self._handle_request_arrival),
            ('request.arrival', lambda xs: self._tracker.record('requests', sum(isinstance(x, model.Request) for x in xs))),
            ('request.arrival', lambda xs: [evque.publish('sim.log', cloca.now(), f'arrive {x.VM.NAME}') for x in xs]),
            ('request.accept', lambda xs: self._tracker.record('accepted', len(xs))),
            ('request.accept', lambda xs: [evque.publish('sim.log', cloca.now(), f'accept {x.VM.NAME}') for x in xs]),
            ('request.reject', lambda xs: self._tracker.record('rejected', len(xs))),
            ('request.reject', lambda xs: [evque.publish('sim.log', cloca.now(), f'reject {x.VM.NAME}') for x in xs]),
            ('action.execute', self._handle_action_execution),
            ('sim.log', self._handle_simulation_log)
        ]:
            evque.subscribe(topic, handler)

        for topic, log_msg in [
            ('app.start', '[{0.NAME}]: start {1.NAME}'),
            ('app.stop', '[{0.NAME}]: stop {1.NAME}'),
            ('container.start', '[{0.NAME}]: start {1.NAME}'),
            ('container.stop', '[{0.NAME}]: stop {1.NAME}'),
            ('controller.start', '[{0.NAME}]: start {1.NAME}'),
            ('controller.stop', '[{0.NAME}]: stop {1.NAME}'),
            ('deployment.run', '[{0.NAME}]: {1.NAME} is RUNNING'),
            ('deployment.pend', '[{0.NAME}]: {1.NAME} is PENDING (awaiting resources)'),
            ('deployment.degrade', '[{0.NAME}]: {1.NAME} is DEGRADED ({2} replica(s) remained)'),
            ('deployment.scale', '[{0.NAME}]: {1.NAME} is SCALED ({2} replica(s) {"added" if z > 0 else "deleted"})'),
            ('deployment.stop', '[{0.NAME}]: {1.NAME} is STOPPED'),
            ('vm.allocate', '[{0.NAME}]: allocate {1.NAME}'),
            ('vm.deallocate', '[{0.NAME}]: deallocate {1.NAME}')
        ]:
            evque.subscribe(topic, self.__make_log_handler(log_msg))

        # Group incoming requests by their arrival time
        for arrival, requests in groupby(self.USER.REQUESTS, key=lambda r: r.ARRIVAL):
            # Publish an event to signal the arrival of requests with the same arrival time.
            evque.publish('request.arrival', arrival, list(requests))

    def report(self, to_stdout=True) -> dict[str, float]:
        """
        The function reports the acceptance and rejection ratios of requests and returns a dictionary of
        values.

        Parameters
        ----------
        to_stdout : bool, default=True
            determines whether the report should be printed to the console (stdout) or not. If set to True, 
            the report will be printed to the console. If set to False, the report will not be printed to the console,
            defaults to True

        Returns
        -------
            a dictionary with the following keys and their corresponding values:
                - 'requests': total number of requests
                - 'accepted': number of accepted requests
                - 'rejected': number of rejected requests
                - 'acceptance_ratio': ratio of accepted requests to total requests
                - 'rejection_ratio': ratio of rejected requests to total requests.
        """
        stats = self._tracker.stats()
        requests = stats.get('requests', 0)

        # Compute ratios with safe division
        stats['accept_rate'] = round(stats.get('accepted', 0) / requests, 2) if requests else 0
        stats['reject_rate'] = round(1 - stats['accept_rate'], 2) if requests else 0

        # Print results if needed
        if to_stdout:
            current_time = cloca.now()
            print(f'{self.NAME}@{current_time}> Accept[{stats["accepted"]} / {requests}] = {stats["accept_rate"]}')
            print(f'{self.NAME}@{current_time}> Reject[{stats["rejected"]} / {requests}] = {stats["reject_rate"]}')

        return stats

    def run(self, duration: int = None) -> Simulation:
        """
        The run function is the main function of this simulation.
        It will run until there are no more events in the event queue or until the specified duration is reached.
        Each time it runs, it will get an event from the queue and call a handler for that event.
        The handlers are responsible for creating new events to be added to the queue.

        Parameters
        ----------
        duration : int, optional
            the duration for which simulation keeps running,
            if None, run till the end.
        """
        print(f'{self.NAME}@{cloca.now()}> ======== START ========')

        # Define the exit condition based on whether a duration is provided
        exit_condition = (lambda start_time=cloca.now(): cloca.now() >= start_time + duration) if duration else self._no_pending_events_or_requests

        while not exit_condition():
            self._simulate_step()

        print(f'{self.NAME}@{cloca.now()}> ======== STOP ========')
        return self

    def resume(self, duration: int) -> Simulation:
        """
        Process events related to resuming a simulation and deallocate finished instances.

        Parameters
        ----------
        duration : int
            The amount of time to resume the simulation
        """
        self.DATACENTER.VMP.resume(duration)

        if stopped_vms := self.DATACENTER.VMP.stopped():
            self.DATACENTER.VMP.deallocate(stopped_vms)

        return self

    def _simulate_step(self):
        """
        Simulate a single step of the simulation.
        """
        evque.run_until(cloca.now())
        self.resume(self.CLOCK_RESOLUTION)
        cloca.increase(self.CLOCK_RESOLUTION)

    def _no_pending_events_or_requests(self) -> bool:
        """
        Determine if there are no more events in the queue and no ongoing requests.
        """
        return evque.empty() and not self._tracker.has_pending()

    def _handle_request_arrival(self, requests: list[model.Request, ...]) -> Simulation:
        """
        Handles the arrival of requests and allocates them to the datacenter.

        Parameters
        ----------
        requests : list[model.Request, ...]
            List of incoming requests.
        """

        allocations = self.DATACENTER.VMP.allocate([r.VM for r in requests if isinstance(r, model.Request)])

        # Initialize lists for publishing results
        accepted_requests = []
        rejected_requests = []

        # Check allocation results, handle callbacks, and update counters
        for request, allocated in zip(filter(lambda r: isinstance(r, model.Request), requests), allocations):
            if allocated:
                accepted_requests.append(request)
                if request.ON_SUCCESS:
                    request.ON_SUCCESS()
            else:
                rejected_requests.append(request)
                if request.REQUIRED:
                    raise AssertionError('The allocation of initialization requests must not result in failure.')
                if request.ON_FAILURE:
                    request.ON_FAILURE()

        # Publish allocation results
        evque.publish('request.accept', cloca.now(), accepted_requests)
        evque.publish('request.reject', cloca.now(), rejected_requests)

        evque.publish('action.execute', cloca.now(), requests)

        return self

    def _handle_action_execution(self, actions: list[model.Action, ...]) -> Simulation:
        """
        Handles the execution of a list of actions.

        Parameters
        ----------
        actions : list of model.Action
            List of actions to be executed.

        Returns
        -------
        Simulation
            Returns the current instance of the simulation.

        Notes
        -----
        Only actions with a defined EXECUTE callable will be executed.
        """
        for action in actions:
            if action.EXECUTE:
                action.EXECUTE()
        return self

    def _handle_simulation_log(self, message: str) -> None:
        """
        Logs input message to the console.

        Parameters
        ----------
        message : str
            input message

        Returns
        -------
        None
            This method does not return any value, it simply prints the message to the console.
        """
        print(f'{self.NAME}@{cloca.now()}> {message}')

    @staticmethod
    def __make_log_handler(log_msg) -> Callable:
        """
        Generate a logging handler using a specified log message format.

        Parameters
        ----------
        log_msg : str
            Format string for the log message.

        Returns
        -------
        function
            Lambda function that logs using the specified format.
        """
        return lambda *args: evque.publish('sim.log', cloca.now(), log_msg.format(*args))

