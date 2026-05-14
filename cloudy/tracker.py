"""Pluggable metric collector for a :class:`Simulation`.

The default :class:`Tracker` counts arrived, accepted, and rejected
requests. Researchers subclass it to track utilisation, latency,
concurrency, or any other metric their study needs, then pass an
instance to :class:`cloudy.Simulation`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cloudy import models
from cloudy.core import Bound

# Imported only for type hints. A plain ``from cloudy.simulation import
# Simulation`` would be a circular import — ``cloudy.simulation`` imports
# this module for the default tracker. ``TYPE_CHECKING`` is ``True`` for
# type checkers and IDEs, ``False`` at runtime, so this import is skipped
# when the program actually runs.
if TYPE_CHECKING:
    from cloudy.simulation import Simulation


@dataclass(eq=False)
class Tracker(Bound['Simulation']):
    """Records request outcomes; subclass to track custom metrics.

    The default tracker counts arrived, accepted, and rejected requests.
    Subclass to track utilisation, latency, concurrency, anything else.
    Two extension points:

    - **The :func:`cloudy.on` decorator** — mark any method as
      an event subscriber. Attaching the tracker (which the simulation
      does for you) subscribes every decorated method automatically, so
      you don't need to override ``attach`` for the common case. (You
      still can, e.g. for dynamic topic names; remember to call
      ``super().attach``.)
    - :meth:`report` — return a dict of custom metrics; the simulation's
      :meth:`Simulation.report` merges them with its own counts
      (``request.arrived`` / ``request.accepted`` / ``request.rejected``
      / ``request.pending``). Keep your keys dot-namespaced too
      (``util.<host>.cpu``-style), so the merged line reads uniformly.

    The simulation this tracker is attached to is :attr:`simulation`
    (and ``self.clock`` / ``self.event_queue`` come from it) — see
    :class:`cloudy.core.Bound`.

    Example
    -------
    ::

        from cloudy import Topic
        from cloudy import on

        @dataclass(eq=False)
        class UtilizationTracker(Tracker):
            allocations: dict[str, int] = field(default_factory=dict)

            @on(Topic.VM_ALLOCATE)
            def _on_allocate(self, host, vm):
                self.allocations[host.name] = self.allocations.get(host.name, 0) + vm.cpu

            def report(self):
                return {f'alloc.{host}.cpu': cpu for host, cpu in self.allocations.items()}

        sim = Simulation(name='Demo', tracker=UtilizationTracker())
    """

    arrived: list[models.Request] = field(default_factory=list)
    accepted: list[models.Request] = field(default_factory=list)
    rejected: list[models.Request] = field(default_factory=list)

    @property
    def simulation(self) -> Simulation:
        """The simulation this tracker is attached to (alias for :attr:`Bound.owner`)."""
        return self.owner

    def on_arrive(self, requests: list[models.Request]) -> None:
        """Record arriving requests."""
        self.arrived.extend(requests)

    def on_accept(self, requests: list[models.Request]) -> None:
        """Record accepted requests."""
        self.accepted.extend(requests)

    def on_reject(self, requests: list[models.Request]) -> None:
        """Record rejected requests."""
        self.rejected.extend(requests)

    @property
    def pending(self) -> int:
        """Number of arrived requests not yet accepted or rejected.

        With the built-in lifecycle this is essentially always 0 —
        :class:`Simulation` accepts or rejects each request the instant
        it arrives, so a request is "pending" only inside that one
        handler. The concept (and :meth:`Simulation.is_completed`'s check
        on it) is here for subclasses that add a richer admission flow.
        """
        return len(self.arrived) - len(self.accepted) - len(self.rejected)

    def report(self) -> dict[str, float]:
        """Custom metrics merged into :meth:`Simulation.report`. Default: empty."""
        return {}
