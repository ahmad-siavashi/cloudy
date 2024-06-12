""" The components of the simulator. """

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import groupby
from typing import Callable

import cloca
import evque

import model
from model import Request


@dataclass
class Tracker:
    """Tracks request labels: arrived, accepted, and rejected."""

    _requests: dict[str, list[Request]] = field(default_factory=lambda: {
        'arrived': [],
        'accepted': [],
        'rejected': []
    })

    def reset(self) -> Tracker:
        """Reset the request lists."""
        for key in self._requests:
            self._requests[key].clear()
        return self

    def record(self, label: str, requests: list[Request]) -> Tracker:
        """
        Add a list of requests to the specified label list.

        Parameters
        ----------
        label : str
            Label type ('arrived', 'accepted', 'rejected').
        requests : List[Request]
            The list of request instances to be recorded.

        Returns
        -------
        Tracker
            Updated tracker instance.
        """
        if label in self._requests:
            self._requests[label].extend(requests)
        return self

    def has_pending(self) -> bool:
        """Check if there are any pending requests."""
        return len(self._requests['arrived']) > (len(self._requests['accepted']) + len(self._requests['rejected']))

    def stats(self) -> dict[str, dict[str, float]]:
        """Retrieve counts and ratios of requests."""
        arrived_requests = len(self._requests['arrived'])
        accepted_count = len(self._requests['accepted'])
        rejected_count = len(self._requests['rejected'])
        pending_count = arrived_requests - accepted_count - rejected_count

        if arrived_requests == 0:
            accepted_ratio = rejected_ratio = pending_ratio = 0.0
        else:
            accepted_ratio = accepted_count / arrived_requests
            rejected_ratio = rejected_count / arrived_requests
            pending_ratio = pending_count / arrived_requests

        return {
            'counts': {
                'arrived': arrived_requests,
                'accepted': accepted_count,
                'rejected': rejected_count,
                'pending': pending_count
            },
            'ratios': {
                'accepted_ratio': accepted_ratio,
                'rejected_ratio': rejected_ratio,
                'pending_ratio': pending_ratio
            }
        }

    def get_requests(self, label: str) -> list[Request]:
        """
        Retrieve the list of requests for the specified label.

        Parameters
        ----------
        label : str
            Label type ('arrived', 'accepted', 'rejected').

        Returns
        -------
        List[Request]
            List of request instances for the specified label.
        """
        return self._requests.get(label, [])


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
    LOG : bool
        print simulation logs to stdout (default: True)
    """
    NAME: str
    USER: model.User
    DATACENTER: model.DataCenter
    CLOCK_RESOLUTION: int = field(default=1)
    LOG: bool = True

    def __post_init__(self):
        """
        The __post_init__ function is a special function that is called after the __init__ function.
        It allows us to initialize variables that are not passed as arguments to the constructor, but rather
        are initialized based on other attributes of the class. In this case, we want to initialize our EventQueue,
        Logger and Clock objects.
        """
        # This object will be used to record events during the simulation.
        self.tracker: Tracker = Tracker()
        # Reset global simulation clock.
        cloca.reset()

        # Subscribe to event topics
        for topic, handler in [
            ('request.arrive', self._handle_request_arrive),
            ('request.accept', self._handle_request_accept),
            ('request.reject', self._handle_request_reject),
            ('action.execute', self._handle_action_execute),
            ('sim.log', self._handle_simulation_log),
        ]:
            evque.subscribe(topic, handler)

        for topic, message_suffix in [
            ('app.start', 'start {1.NAME}'),
            ('app.stop', 'stop {1.NAME}'),
            ('container.start', 'start {1.NAME}'),
            ('container.stop', 'stop {1.NAME}'),
            ('controller.start', 'start {1.NAME}'),
            ('controller.stop', 'stop {1.NAME}'),
            ('deployment.run', '{1.NAME} is RUNNING'),
            ('deployment.pend', '{1.NAME} is PENDING'),
            ('deployment.degrade', '{1.NAME} is DEGRADED ({2} replica(s) remained)'),
            ('deployment.scale', '{1.NAME} is SCALED (± {2} replica(s))'),
            ('deployment.stop', '{1.NAME} is STOPPED'),
            ('vm.allocate', 'allocate {1.NAME}'),
            ('vm.deallocate', 'deallocate {1.NAME}')
        ]:
            evque.subscribe(topic, self._create_log_formatter(message_suffix))

        # Group incoming requests by their arrival time
        for arrival, requests in groupby(self.USER.REQUESTS, key=lambda r: r.ARRIVAL):
            # Publish an event to signal the arrival of requests with the same arrival time.
            evque.publish('request.arrive', arrival, list(requests))

    def report(self, to_stdout=True) -> dict[str, float]:
        """
        The function reports the acceptance and rejection ratios of requests and returns a dictionary of values.

        Parameters
        ----------
        to_stdout : bool, default=True
            Determines whether the report should be printed to the console (stdout) or not. If set to True,
            the report will be printed to the console. If set to False, the report will not be printed to the console,
            defaults to True.

        Returns
        -------
            A dictionary with the following keys and their corresponding values:
                - 'arrived': number of arrived requests
                - 'accepted': number of accepted requests
                - 'rejected': number of rejected requests
                - 'pending': number of pending requests
                - 'acceptance_ratio': ratio of accepted requests to arrived requests
                - 'rejection_ratio': ratio of rejected requests to arrived requests.
                - 'pending_ratio': ratio of pending requests to arrived requests.
        """
        stats = self.tracker.stats()
        counts, ratios = stats['counts'], stats['ratios']

        result = {
            'arrived': counts['arrived'],
            'accepted': counts['accepted'],
            'rejected': counts['rejected'],
            'pending': counts['pending'],
            'acceptance_ratio': round(ratios['accepted_ratio'], 2),
            'rejection_ratio': round(ratios['rejected_ratio'], 2),
            'pending_ratio': round(ratios['pending_ratio'], 2)
        }

        if to_stdout:
            current_time = cloca.now()
            print(f'{self.NAME}@{current_time}> Accept[{result["accepted"]} / {result["arrived"]}] = {result["acceptance_ratio"]}')
            print(f'{self.NAME}@{current_time}> Reject[{result["rejected"]} / {result["arrived"]}] = {result["rejection_ratio"]}')
            print(f'{self.NAME}@{current_time}> Pending[{result["pending"]} / {result["arrived"]}] = {result["pending_ratio"]}')

        return result

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
        has_duration_elapsed = lambda start_time=cloca.now(): cloca.now() >= start_time + duration if duration else False
        should_exit = has_duration_elapsed if duration else self.completed

        while not should_exit():
            self._simulate_step()

        if has_duration_elapsed():
            print(f'{self.NAME}@{cloca.now()}> -------- PAUSE --------')
        else:
            print(f'{self.NAME}@{cloca.now()}> ======== STOP ========')
        return self

    def _simulate_step(self):
        """
        Simulates a single step of the simulation.

        Performs the following actions:
            1. Runs events from the queue until the current simulation time.
            2. Resumes VMs in the data center.
            3. Deallocates any stopped VMs.
            4. Advances the simulation clock.
        """

        # Execute events for the current simulation time
        evque.run_until(cloca.now())

        # Resume VMs in the data center
        self.DATACENTER.VMP.resume(self.CLOCK_RESOLUTION)

        # Collect and deallocate stopped VMs
        stopped_vms = self.DATACENTER.VMP.stopped()
        if stopped_vms:
            self.DATACENTER.VMP.deallocate(stopped_vms)

        # Advance the simulation clock
        cloca.increase(self.CLOCK_RESOLUTION)

    def completed(self) -> bool:
        """
        Determine if the simulation has completed all tasks.

        This includes verifying that there are no more events in the queue,
        no ongoing requests, and all virtual machines have been processed.

        Returns
        -------
        bool
            True if the simulation is complete, False otherwise.
        """
        return evque.empty() and not self.tracker.has_pending() and self.DATACENTER.VMP.empty()

    def _handle_request_arrive(self, requests: list[model.Request, ...]) -> Simulation:
        """
        Handles the arrival of requests and allocates them to the datacenter.

        Parameters
        ----------
        requests : list[model.Request, ...]
            List of incoming requests.
        """

        requests = [r for r in requests if isinstance(r, model.Request)]
        self.tracker.record('arrived', [r for r in requests if not r.IGNORED])
        for request in requests:
            required_tag = ' [REQUIRED]' if request.REQUIRED else ''
            ignored_tag = ' [IGNORED]' if request.IGNORED else ''
            evque.publish('sim.log', cloca.now(), f'arrive {request.VM.NAME}' + required_tag + ignored_tag)

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
                    raise AssertionError(f'The allocation of initialization requests must not result in failure: {request.VM.NAME}')
                if request.ON_FAILURE:
                    request.ON_FAILURE()

        # Publish allocation results
        evque.publish('request.accept', cloca.now(), accepted_requests)
        evque.publish('request.reject', cloca.now(), rejected_requests)

        evque.publish('action.execute', cloca.now(), requests)

        return self

    def _handle_request_accept(self, requests):
        """
        Handle the acceptance of requests by recording the event and publishing a log.

        This method iterates over each request, records it as 'accepted' if it's not ignored,
        and publishes an acceptance log with the request's virtual machine name and any
        required or ignored flags.

        Parameters
        ----------
        requests : list
            A list of request objects to be processed.

        See Also
        --------
        _tracker.record : Method used to record the number of accepted requests.
        evque.publish : Method used to publish an event to the event queue.
        """
        requests = [r for r in requests if isinstance(r, model.Request)]
        self.tracker.record('accepted', [r for r in requests if not r.IGNORED])
        for request in requests:
            required_tag = ' [REQUIRED]' if request.REQUIRED else ''
            ignored_tag = ' [IGNORED]' if request.IGNORED else ''
            evque.publish('sim.log', cloca.now(), f'accept {request.VM.NAME}' + required_tag + ignored_tag)

    def _handle_request_reject(self, requests):
        """
            Handle the rejection of requests by recording the event and publishing a log.

            This method iterates over each request, records it as 'rejected' if it's not ignored,
            and publishes a rejection log with the request's virtual machine name and any
            required or ignored flags.

            Parameters
            ----------
            requests : list
                A list of request objects to be processed.

            See Also
            --------
            _tracker.record : Method used to record the number of rejected requests.
            evque.publish : Method used to publish an event to the event queue.
        """
        requests = [r for r in requests if isinstance(r, model.Request)]
        self.tracker.record('rejected', [r for r in requests if not r.IGNORED])
        for request in requests:
            required_tag = ' [REQUIRED]' if request.REQUIRED else ''
            ignored_tag = ' [IGNORED]' if request.IGNORED else ''
            evque.publish('sim.log', cloca.now(), f'reject {request.VM.NAME}' + required_tag + ignored_tag)

    def _handle_action_execute(self, actions: list[model.Action, ...]) -> Simulation:
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
        if self.LOG:
            print(f'{self.NAME}@{cloca.now()}> {message}')

    @staticmethod
    def _create_log_formatter(template_suffix) -> Callable:
        """
        Returns a logger function that prefixes messages with the standard format
        and appends a given message template.

        Parameters
        ----------
        template_suffix : str
            The template string to append to the standard log message prefix.

        Returns
        -------
        Callable
            A function that logs messages with a standard prefix followed by the formatted template_suffix.
        """
        template = '[{0.NAME}]: ' + template_suffix
        return lambda *args: evque.publish('sim.log', cloca.now(), template.format(*args))


