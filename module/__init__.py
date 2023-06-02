""" The components of the simulator. """

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

import model


class Clock:
    """
    The simulator uses a clock to keep track of time. One event_tick equals one time unit. To make things easy, assume
    one event_tick equals one second.

    Attributes
    ==========
    - _tick (int, private): a private class variable to keep the current time
    """
    _tick: int = 0

    def reset(self) -> int:
        """
        The reset function resets the clock to 0.

        :return: The new current time
        """
        self._tick = 0
        return self.now()

    def increment(self, ticks: int = 1) -> int:
        """
        The increment function is used to increment the clock by a given number of ticks where each event_tick represents one simulation time unit.
        The default value for ticks is 1, so if no argument is passed in, the clock will be incremented by 1 event_tick.

        :param ticks: int: Increment the clock by a certain number of ticks
        :return: The new current time
        """
        self._tick += ticks
        return self.now()

    def now(self) -> int:
        """
        The now function returns the current time, which is stored in a private variable called _tick.

        :return: The value of the _tick attribute
        """
        return self._tick


class Logger:
    """
    A class that logs messages to stdout.
    """

    def __init__(self, **kwargs: dict[str, int]):
        """
        The __init__ function initializes the class with a dictionary of column names and their widths.
        If no arguments are passed, it defaults to the following:
            {'Tick': 5, 'Event': 15, 'Description': 25}
        """
        self.COLUMNS = {'Tick': 5, 'Event': 15, 'Description': 25} if not kwargs else kwargs
        self.SEPARATOR = '+ ' + ' + '.join('-' * col_width for col_width in self.COLUMNS.values()) + ' +'
        self.ROW = '| ' + ' | '.join('{:<%d}' % col_width for col_width in self.COLUMNS.values()) + ' |'

    def begin(self) -> None:
        """
        The begin function prints the header for the table of events.

        :return: None
        """
        print(self.SEPARATOR)
        print(self.ROW.format(*self.COLUMNS.keys()))
        print(self.SEPARATOR)

    def end(self) -> None:
        """
        The end function prints the bottom of the table of events.

        :return: None
        """
        print(self.SEPARATOR)

    def log(self, *args: Any) -> None:
        """
        The log function is used to print out the event log.
        It takes the values to print in a log.

        :param *args: Any: Values to be logged
        :return: None
        """
        print(self.ROW.format(*args))


@dataclass
class Event:
    """
    This class represents an event in the simulation.

    Attributes
    ==========
    TICK: int: the occurrence time attributed to the event
    TYPE: str: type of the event
    DATA: object: data associated with the event
    """
    TICK: int
    TYPE: str
    DATA: object

    # types of events that denote the arrival of a new IaaS request to the cloud provider
    TYPE_VM_ARRIVAL: str = 'vm_arrival'
    # types of events that enforce execution of guest virtual machines in a data center
    TYPE_DC_PROCESS: str = 'dc_process'


@dataclass
class EventQueue:
    """
    This class represents an event queue to hold registered events during simulation

    Attributes
    ==========
    _events: (list[Event], private): the list of events within the queue
    """

    _events: list[Event] = field(init=False, default_factory=list)

    def put(self, event: Event) -> None:
        """
        The put function is used to insert an event into the queue.
        The function iterates through the list of events and compares each event's tick value with that of the new event.
        If it finds a tick value greater than that of the new event, it inserts it at this index in order to maintain sorted order.

        :param self: Refer to the object itself
        :param event: Event: Pass in the event object to be inserted into the queue
        :return: None, because it is a void function
        """
        index = 0
        for e in self._events:
            if e.TICK > event.TICK:
                break
            index += 1
        self._events.insert(index, event)

    def empty(self) -> bool:
        """
        The empty function checks if the Event list is empty.

        :return: True if the event list is empty, otherwise it returns false
        """
        return not bool(self._events)

    def get(self, current_tick: int) -> list[[]] | list[Event, ...]:
        """
        The get function returns the list of events that their time precedes the current time.

        :param current_tick: int: the current time
        :return: list of events or nothing if no event precedes the current time
        """
        events = []
        while not self.empty():
            if self._events[0].TICK <= current_tick:
                events += [self._events.pop(0)]
            else:
                break
        return events


@dataclass
class Report:
    _num_requests: int = 0
    _num_accepted_requests: int = 0
    _num_finished_requests: int = 0
    _num_rejected_requests: int = 0

    def reset(self):
        self._num_requests = 0
        self._num_accepted_requests = 0
        self._num_finished_requests = 0
        self._num_rejected_requests = 0

    def count_request_arrival(self, count: int = 1) -> None:
        self._num_requests += count

    def count_request_acceptance(self, count: int = 1) -> None:
        self._num_accepted_requests += count

    def count_request_finish(self, count: int = 1) -> None:
        self._num_finished_requests += count

    def count_request_rejection(self, count: int = 1) -> None:
        self._num_rejected_requests += count

    def has_request_running(self) -> bool:
        return bool(self._num_requests - self._num_finished_requests - self._num_rejected_requests)

    def get(self):
        return {
            'requests': self._num_requests,
            'accepted': self._num_accepted_requests,
            'rejected': self._num_rejected_requests,
            'finished': self._num_finished_requests
        }


@dataclass
class Simulation:
    """
    This class represents a simulation.
    """
    _user: model.User
    _datacenter: model.DataCenter
    _clock_resolution: int = field(default=1)

    def __post_init__(self):
        """
        The __post_init__ function is a special function that is called after the __init__ function.
        It allows us to initialize variables that are not passed as arguments to the constructor, but rather
        are initialized based on other attributes of the class. In this case, we want to initialize our EventQueue, Logger and Clock objects.

        :param self: Refer to the object itself
        """
        # This creates an empty queue that will be used to store events in the simulation.
        self._queue: EventQueue = EventQueue()
        # This logger will be used to record events and messages during the simulation.
        self._logger: Logger = Logger()
        # This creates a clock object that can be used to keep track of time during the simulation.
        self._clock: Clock = Clock()

        # It is resetting the clock object to its initial state. This is done to ensure that the clock
        # starts at 0 when the simulation begins.
        self._clock.reset()

        # This code block is initializing the simulation by creating events for each VM arrival and adding them to the
        # event queue.
        for request in self._user.REQUESTS:
            new_event = Event(request.ARRIVAL, Event.TYPE_VM_ARRIVAL, request.VM)
            self._queue.put(new_event)

        self._report: Report = Report()

        new_event = Event(self._clock.now(), Event.TYPE_DC_PROCESS, (self._clock.now(), self._datacenter))
        self._queue.put(new_event)

    def report(self) -> None:
        report = self._report.get()
        acceptance_ratio = round(report["accepted"] / report["requests"], 2)
        rejection_ratio = round(1 - acceptance_ratio, 2)
        print('============== Report ==============')
        print(f'Accepted: {report["accepted"]} / {report["requests"]} = {acceptance_ratio}')
        print(f'Rejected: {report["rejected"]} / {report["requests"]} = {rejection_ratio}')
        print(f'Total: {report["requests"]}')
        print('====================================')

    def _handler_vm_arrival(self, events: Iterator[Event]) -> None:
        """
        The _handler_vm_arrival function is called when a VM arrives.
        It calls the PLACEMENT algorithm to allocate the VMs on hosts.
        If allocation fails, it logs that the VM was rejected and decrements _num_requests.

        :param self: Refer to the current object
        :param events: Iterator[Event]: Pass in a list of events
        :return: None
        """
        vms = [event.DATA for event in events]
        self._report.count_request_arrival(len(vms))
        results = self._datacenter.PLACEMENT.allocate(vms)
        for i, result in enumerate(results):
            if result:
                self._logger.log(self._clock.now(), 'vm accepted', vms[i].NAME)
                self._report.count_request_acceptance()
            else:
                self._logger.log(self._clock.now(), 'vm rejected', vms[i].NAME)
                self._report.count_request_rejection()

    def _handler_dc_process(self, event: Event) -> None:
        """
        The _handler_dc_process function is responsible for processing the virtual machines in a data center.
        It takes in an event and then calculates the duration of time that has passed since the last event_tick.
        Then it loops through all of the servers in a data center, and then loops through all of the guests
        on each server to process them. It also keeps track of finished requests to conclude the simulation.

        :param event: Event: Pass the event object to the function
        :return: None
        """
        previous_tick, datacenter = event.DATA
        duration = self._clock.now() - previous_tick

        for server in datacenter.SERVERS:
            finished_vms = server.VMM.process(duration)
            server.VMM.deallocate(finished_vms)
            self._report.count_request_finish(len(finished_vms))
            for finished_vm in finished_vms:
                self._logger.log(self._clock.now(), 'vm finished', finished_vm.NAME)

        if self._report.has_request_running():
            next_event = Event(self._clock.now() + self._clock_resolution, Event.TYPE_DC_PROCESS,
                               (self._clock.now(), datacenter))
            self._queue.put(next_event)

    def start(self) -> Simulation:
        """
        The start function is the main function of this simulation.
        It will run until there are no more events in the event queue.
        Each time it runs, it will get an event from the queue and call a handler for that event of event.
        The handlers are responsible for creating new events to be added to the queue.

        :return: None
        """
        self._logger.begin()
        self._logger.log(self._clock.now(), 'simulation', 'begin')
        while not self._queue.empty():
            events_so_far = self._queue.get(self._clock.now())
            self._handler_vm_arrival(filter(lambda e: e.TYPE == Event.TYPE_VM_ARRIVAL, events_so_far))
            for event_dc_process in filter(lambda e: e.TYPE == Event.TYPE_DC_PROCESS, events_so_far):
                self._handler_dc_process(event_dc_process)
            self._clock.increment()
        self._logger.log(self._clock.now(), 'simulation', 'end')
        self._logger.end()
        return self