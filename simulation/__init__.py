from dataclasses import dataclass, field

from module import User, DataCenter, Vm
from simulation.clock import Clock
from simulation.event import Event, EventQueue
from simulation.log import Logger


@dataclass
class Simulation:
    """
    This class represents a simulation.
    """
    _user: User
    _datacenter: DataCenter
    _clock_resolution: int = field(default=1)

    def __post_init__(self):
        """
        The __post_init__ function is a special function that is called after the __init__ function.
        It allows us to initialize variables that are not passed as arguments to the constructor, but rather
        are initialized based on other attributes of the class. In this case, we want to initialize our EventQueue, Logger and Clock objects.

        :param self: Refer to the object itself
        """
        # This creates an empty queue that will be used to store events in the simulation.
        self._events: EventQueue = EventQueue()
        # This logger will be used to record events and messages during the simulation.
        self._logger: Logger = Logger()
        # This creates a clock object that can be used to keep track of time during the simulation.
        self._clock: Clock = Clock()

        # It is resetting the clock object to its initial state. This is done to ensure that the clock
        # starts at 0 when the simulation begins.
        self._clock.reset()

        # This code block is initializing the simulation by creating events for each VM arrival and adding them to the
        # event queue. It is also initializing two variables, `_num_requests` and `_finished_vms`, which will be used to
        # keep track of the number of requests and finished VMs during the simulation.
        for request in self._user.REQUESTS:
            new_event = Event(Event.Type.VM_ARRIVAL, request.VM)
            self._events.put(request.ARRIVAL, new_event)

        self._num_requests: int = 0
        self._finished_vms: list[tuple[int, Vm], ...] = []

        new_event = Event(Event.Type.DC_PROCESS, (self._clock.now(), self._datacenter))
        self._events.put(self._clock.now(), new_event)

    def _handler_vm_arrival(self, event: Event) -> None:
        """
        The _handler_vm_arrival function is a handler for the VM_ARRIVAL event.
        It takes an Event object as input and returns nothing.
        The function first checks if the vm can be allocated in the data enter,
        and prints a message to stdout depending on whether or not it was successful.

        :param event: Event: Pass the event to the function
        :return: None
        """
        vm: Vm = event.DATA
        if True in self._datacenter.PLACEMENT.allocate([vm]):
            self._num_requests += 1
            event = 'allocated'
        else:
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
            self._finished_vms += [(self._clock.now(), finished_vm) for finished_vm in finished_vms]

        if self._num_requests:
            next_event = Event(Event.Type.DC_PROCESS, (self._clock.now(), datacenter))
            self._events.put(self._clock.now() + self._clock_resolution, next_event)
        else:
            for clock, finished_vm in self._finished_vms:
                self._logger.log(clock, 'vm finished', finished_vm.NAME)

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
        while not self._events.empty():
            tick, event = self._events.get()
            if event.TYPE == Event.Type.VM_ARRIVAL:
                self._handler_vm_arrival(event)
            elif event.TYPE == Event.Type.DC_PROCESS:
                self._handler_dc_process(event)
            else:
                raise ValueError('unknown event ' + event.TYPE.value)
            self._clock.increment()
        self._logger.log(self._clock.now(), 'simulation', 'end')
        self._logger.end()
