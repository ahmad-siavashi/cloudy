from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, ClassVar


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

    _events: ClassVar[List[Tuple[int, Event]]] = field(init=False, default=[])

    def put(self, tick: int, event: Event) -> None:
        """
        The put function is used to register an event with the EventQueue class.
        The function takes two arguments: a tick and an event. The tick argument is
        the number of ticks that must pass before the event will be executed, and the
        event argument will be consumed when it's time for the event to execute.
        The register function then inserts the tuple containing these two arguments
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

    def get(self) -> Tuple[int, Event]:
        """
        The get function returns the first event in the list of events.

        :return: A single event
        """
        return self._events.pop(0)
