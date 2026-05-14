"""Minimal network model — a point-to-point link with bandwidth and latency.

This module is a **standalone, optional building block**: the core
simulator never creates or uses a :class:`Link`. VMs and PMs have no
NIC and no bandwidth attribute, the workload (``Daemon`` / ``App``)
produces no traffic, and placement is not network-aware. If you want
network effects, build :class:`Link` s yourself and call
:meth:`Link.send` from your own event handlers (e.g. on
:data:`cloudy.Topic.APP_START`).

It models the common case — "how long does a payload take to travel
from A to B" — and does not try to be a full network simulator.
:meth:`~Link.transmission_time` is the cost formula
(``latency + bytes / bandwidth``, also useful for estimating costs such
as a migration's memory copy — see ``examples/live_migration.py``).
:meth:`~Link.send` schedules the delivery event. For congestion control,
switching, or topology routing, subclass :class:`Link` (or write your
own model that publishes :data:`cloudy.Topic.LINK_DELIVER`).
"""

from __future__ import annotations

from dataclasses import dataclass

from cloudy.models import VM
from cloudy.simulation import Simulation
from cloudy.topics import Topic


@dataclass(eq=False)
class Link:
    """A point-to-point link between two endpoints.

    Bandwidth and latency are in the simulation's own units (bytes per
    *time unit*, and *time units*) — same convention as the rest of the
    clock-driven model. Construction rejects a non-positive ``bandwidth``
    or a negative ``latency``, so a typo fails immediately instead of
    silently making the link instantaneous.

    Attributes
    ----------
    name : str
        Identifier shown in events and logs.
    bandwidth : float
        Bytes carried per simulation time unit (must be > 0).
        ``payload_bytes / bandwidth`` is the transmission-time component.
    latency : float
        Constant per-hop latency (must be >= 0), in simulation time
        units. Added to every transmission.
    """

    name: str
    bandwidth: float
    latency: float

    def __post_init__(self) -> None:
        if self.bandwidth <= 0:
            raise ValueError(f'Link {self.name!r}: bandwidth must be > 0, got {self.bandwidth!r}')
        if self.latency < 0:
            raise ValueError(f'Link {self.name!r}: latency must be >= 0, got {self.latency!r}')

    def transmission_time(self, payload_bytes: int | float) -> float:
        """Time for ``payload_bytes`` to traverse the link —
        ``latency + payload_bytes / bandwidth``."""
        return self.latency + payload_bytes / self.bandwidth

    def send(self, simulation: Simulation, src: VM, dst: VM, payload_bytes: int | float, tag: object | None = None) -> None:
        """Schedule a :data:`Topic.LINK_DELIVER` event at the delivery time.

        Pure event scheduling — no in-flight bookkeeping, no congestion.
        Subclass to add either.

        Parameters
        ----------
        simulation : Simulation
            The running simulation — used for its clock and event queue.
        src, dst : VM
            Sender and receiver; carried in the delivery event's payload.
        payload_bytes : int | float
            Payload size, fed to :meth:`transmission_time`.
        tag : object, optional
            Opaque value echoed back in the delivery event so a handler
            can tell *which* transfer arrived (a request id, the VM being
            migrated, …). Defaults to ``None``.
        """
        delivery: float = simulation.clock.now + self.transmission_time(payload_bytes)
        simulation.event_queue.publish(Topic.LINK_DELIVER, delivery, src, dst, payload_bytes, tag)
