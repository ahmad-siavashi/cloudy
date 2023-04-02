from module import User, DataCenter, Vm
from simulation.clock import Clock
from simulation.event import Event
from simulation.log import Logger

_user: User = None
_datacenter: DataCenter = None
_clock_resolution: int = None


def init(user: User, datacenter: DataCenter, clock_resolution: int = 1) -> None:
    """
    The init function initializes the simulation. The clock_resolution sets the minimum interval between event processing.
    The default value is one time unit. A higher value reduces simulation time at the cost of simulation accuracy. The caller
    should provide a proper value based on its requirements.

    :param user: User: Access the user's requests
    :param datacenter: DataCenter: Pass the data center object to the init function
    :param clock_resolution: int: Set the clock resolution of simulation
    :return: None
    """
    global _user, _datacenter, _clock_resolution
    _user, _datacenter, _clock_resolution = user, datacenter, clock_resolution

    Clock.reset()

    for request in _user.REQUESTS:
        new_event = Event(Event.Type.VM_ARRIVAL, request.VM)
        Event.register(request.ARRIVAL, new_event)

    _handler_dc_process.num_requests: int = 0
    _handler_dc_process.finished_vms: list[tuple[int, Vm], ...] = []

    new_event = Event(Event.Type.DC_PROCESS, (Clock.now(), _datacenter))
    Event.register(Clock.now(), new_event)


def _handler_vm_arrival(event: Event) -> None:
    """
    The _handler_vm_arrival function is a handler for the VM_ARRIVAL event.
    It takes an Event object as input and returns nothing.
    The function first checks if the vm can be allocated in the data enter,
    and prints a message to stdout depending on whether or not it was successful.

    :param event: Event: Pass the event to the function
    :return: None
    """
    global _datacenter
    vm: Vm = event.DATA
    sign, type = ('-', 'rejected')
    if True in _datacenter.PLACEMENT.allocate([vm]):
        _handler_dc_process.num_requests += 1
        sign, type = ('+', 'allocated')
    Logger.log(Clock.now(), sign, 'vm ' + type, vm.NAME)


def _handler_dc_process(event: Event) -> None:
    """
    The _handler_dc_process function is responsible for processing the virtual machines in a data center.
    It takes in an event and then calculates the duration of time that has passed since the last tick.
    Then it loops through all of the servers in a data center, and then loops through all of the guests
    on each server to process them. It also keeps track of finished requests to conclude the simulation.

    :param event: Event: Pass the event object to the function
    :return: None
    """
    previous_tick, datacenter = event.DATA
    duration = Clock.now() - previous_tick

    for server in datacenter.SERVERS:
        finished_vms = server.VMM.process(duration)
        server.VMM.deallocate(finished_vms)
        _handler_dc_process.finished_vms += [(Clock.now(), finished_vm) for finished_vm in finished_vms]
        _handler_dc_process.num_requests -= len(finished_vms)

    if _handler_dc_process.num_requests:
        next_event = Event(Event.Type.DC_PROCESS, (Clock.now(), datacenter))
        Event.register(Clock.now() + _clock_resolution, next_event)
    else:
        for clock, finished_vm in _handler_dc_process.finished_vms:
            Logger.log(clock, '+', 'vm finished', finished_vm.NAME)


def start() -> None:
    """
    The start function is the main function of this simulation.
    It will run until there are no more events in the event queue.
    Each time it runs, it will get an event from the queue and call a handler for that type of event.
    The handlers are responsible for creating new events to be added to the queue.

    :return: None
    """
    Logger.begin()
    Logger.log(Clock.now(), '!', 'simulation', 'begin')
    while not Event.empty():
        tick, event = Event.get()
        if event.TYPE == Event.Type.VM_ARRIVAL:
            _handler_vm_arrival(event)
        elif event.TYPE == Event.Type.DC_PROCESS:
            _handler_dc_process(event)
        else:
            raise ValueError('unknown event ' + event.TYPE.value)
        Clock.increment()
    Logger.log(Clock.now(), '!', 'simulation', 'end')
    Logger.end()
