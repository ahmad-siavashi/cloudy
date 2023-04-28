""" The components of the simulator. """

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from typing import List, Tuple

import model


class Clock:
    """
    The simulator uses a clock to keep track of time. One tick equals one time unit. To make things easy, assume
    one tick equals one second.

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
        The increment function is used to increment the clock by a given number of ticks where each tick represents one simulation time unit.
        The default value for ticks is 1, so if no argument is passed in, the clock will be incremented by 1 tick.

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
            {'Clock': 5, 'Event': 15, 'Description': 25}
        """
        self.COLUMNS = {'Clock': 5, 'Event': 15, 'Description': 25} if not kwargs else kwargs
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


class EventType(Enum):
    """
    The Type class is an enum class that defines the available types af Events in the simulation.

    Attributes
    ==========
    - VM_ARRIVAL (str): types of events that denote the arrival of a new IaaS request to the cloud provider
    - DC_PROCESS (str): types of events that enforce execution of guest virtual machines in a data center
    """
    VM_ARRIVAL: str = 'vm_arrival'
    DC_PROCESS: str = 'dc_process'


@dataclass
class Event:
    """
    It is a class that represents an event that can occur in the simulation.

    Attributes
    ==========
    - TYPE (Event.Type): the event of the event which helps in the interpretation and processing of the event
    - DATA (object): the data that is associated with the event
    """
    TYPE: EventType
    DATA: object


@dataclass
class EventQueue:
    """
    This class represents an event queue to hold registered events during simulation
    """

    _events: List[Tuple[int, Event]] = field(init=False, default_factory=list)

    def put(self, tick: int, event: Event) -> None:
        """
        The put function is used to register an event with the EventQueue class.
        The function takes two arguments: a tick and an event. The tick argument is
        the number of ticks that must pass before the event will be executed, and the
        event argument will be consumed when it's time for the event to execute.
        The put function then inserts the tuple containing these two arguments
        into Event's list attribute at an index such that all events in this list are
        sorted by their respective ticks, with earlier events appearing first.

        :param tick: int: Tell the register function when to run the event
        :param event: Event: Specify the event that is to be registered
        :return: None
        """
        index = 0
        for t, e in self._events:
            if t > tick:
                break
            index += 1
        self._events.insert(index, (tick, event))

    def empty(self) -> bool:
        """
        The empty function checks if the Event list is empty.

        :return: True if the event list is empty, otherwise it returns false
        """
        return len(self._events) == 0

    def get(self, current_tick: int) -> list[[]] | list[tuple[int, Event], ...]:
        """
        The get function returns the list of events that their time precedes the current time.

        :param current_tick: int: the current time
        :return: list of events or nothing if no event precedes the current time
        """
        events = []
        while not self.empty():
            tick, _ = self._events[0]
            if tick <= current_tick:
                events += [self._events.pop(0)]
            else:
                break
        return events


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
        # event queue. It is also initializing `_num_requests` variable, which will be used to
        # keep track of the number of processed requests during the simulation.
        for request in self._user.REQUESTS:
            new_event = Event(EventType.VM_ARRIVAL, request.VM)
            self._queue.put(request.ARRIVAL, new_event)

        self._num_requests: int = len(self._user.REQUESTS)

        new_event = Event(EventType.DC_PROCESS, (self._clock.now(), self._datacenter))
        self._queue.put(self._clock.now(), new_event)

    def _handler_vm_arrival(self, event: Event) -> None:
        """
        The _handler_vm_arrival function is a handler for the VM_ARRIVAL event.
        It takes an Event object as input and returns nothing.
        The function first checks if the vm can be allocated in the data enter,
        and prints a message to stdout depending on whether or not it was successful.

        :param event: Event: Pass the event to the function
        :return: None
        """
        vm: model.Vm = event.DATA
        if True in self._datacenter.PLACEMENT.allocate([vm]):
            event = 'allocated'
        else:
            self._num_requests -= 1
            event = 'rejected'

        self._logger.log(self._clock.now(), 'vm ' + event, vm.NAME)

    def _handler_dc_process(self, event: Event) -> None:
        """
        The _handler_dc_process function is responsible for processing the virtual machines in a data center.
        It takes in an event and then calculates the duration of time that has passed since the last tick.
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
            self._num_requests -= len(finished_vms)
            for finished_vm in finished_vms:
                self._logger.log(self._clock.now(), 'vm finished', finished_vm.NAME)

        if self._num_requests:
            next_event = Event(EventType.DC_PROCESS, (self._clock.now(), datacenter))
            self._queue.put(self._clock.now() + self._clock_resolution, next_event)

    def start(self) -> None:
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
            for tick, event in self._queue.get(self._clock.now()):
                if event.TYPE == EventType.VM_ARRIVAL:
                    self._handler_vm_arrival(event)
                elif event.TYPE == EventType.DC_PROCESS:
                    self._handler_dc_process(event)
                else:
                    raise ValueError('unknown event ' + event.TYPE.value)
            self._clock.increment()
        self._logger.log(self._clock.now(), 'simulation', 'end')
        self._logger.end()
