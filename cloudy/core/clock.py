"""Simulation clock — the monotonic time source each :class:`Simulation` owns.

A :class:`Clock` is a tiny wrapper around one numeric counter holding the
current simulated time, in user-defined units. Each :class:`cloudy.Simulation`
owns its own clock — there is no process-wide singleton.

Time is ``int | float``, not int-only: integers are the natural case
(``arrival=0``, ``length=(10,)``), but floats are kept so trace replay,
jittered or fractional arrivals, and :class:`cloudy.network.Link`
delivery times (``latency + bytes / bandwidth``) work without rounding.
The periodic scheduler still steps on integer-spaced
``Simulation.clock_resolution`` ticks; only event-driven dispatch lands
at the in-between times. (CPU work is unit-agnostic — *cycles* and
*cycles per time unit* — but :class:`cloudy.metrics.Energy` reports kWh,
so it assumes one tick is one second.)
"""

from __future__ import annotations

Time = int | float
"""A point in simulated time, or a duration — ``int`` or ``float``."""


class Clock:
    """A monotonic discrete-time simulation clock.

    Holds a single non-negative numeric counter. Read the current time
    with :attr:`now`; the simulator advances the clock by assigning to
    :attr:`now`. The clock never moves backwards on its own.
    """

    def __init__(self) -> None:
        self._now: Time = 0

    @property
    def now(self) -> Time:
        """The current simulated time, in simulation time units."""
        return self._now

    @now.setter
    def now(self, time: Time) -> None:
        self._now = time
