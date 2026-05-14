"""Per-host power models.

A :class:`PowerModel` predicts the instantaneous power draw of a
:class:`cloudy.models.PM` given its current CPU utilisation. The default
:class:`LinearPower` is the standard reference model used in most
cloud-power-related papers — power scales linearly between the host's
idle and peak draw with utilisation.

The :class:`cloudy.metrics.Energy` tracker samples every host's model on
each :data:`Topic.SIM_TICK`, using ``host.hypervisor.cpu_utilisation``,
and integrates the result over time into per-host energy figures (kWh)
at the end of a run. (``Energy`` reports kWh, so it assumes one
simulation time unit is one second — see :mod:`cloudy.core.clock`.)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

# Imported only for type hints. A plain ``from cloudy.models import PM``
# would be a circular import — ``cloudy.models`` imports this module to
# give every ``PM`` a default power model. ``TYPE_CHECKING`` is ``True``
# for type checkers and IDEs, ``False`` at runtime, so this import is
# skipped when the program actually runs.
if TYPE_CHECKING:
    from cloudy.models import PM


class PowerModel(ABC):
    """Predicts a host's instantaneous power draw, in watts.

    Attached per :class:`PM` and queried by the :class:`cloudy.metrics.Energy`
    tracker on every :data:`Topic.SIM_TICK`. Override :meth:`power` for
    non-linear curves (cubic, table-driven, DVFS, …) — most subclasses
    are one method. ``host`` is passed in case the curve depends on the
    hardware (CPU generation, core count); :class:`LinearPower` ignores it.
    """

    @abstractmethod
    def power(self, host: PM, utilisation: float) -> float:
        """Return power draw in watts for ``host`` at CPU ``utilisation``
        (a fraction in ``[0, 1]``)."""


@dataclass
class LinearPower(PowerModel):
    """Linear interpolation between idle and peak power.

    The classic SPECpower-style model: ``P(u) = idle + (peak - idle) · u``,
    where ``u`` is the host's CPU utilisation in ``[0, 1]``. Any memory
    contribution is absorbed into the linear term — researchers needing
    more granularity subclass with the same signature.
    """

    idle: float
    """Watts drawn when the host is idle (``u = 0``) — including when it
    is powered on but hosts no VMs."""

    peak: float
    """Watts drawn when the host's CPU is fully utilised (``u = 1``)."""

    def power(self, host: PM, utilisation: float) -> float:
        u: float = max(0.0, min(1.0, utilisation))
        return self.idle + (self.peak - self.idle) * u


@dataclass
class ZeroPower(PowerModel):
    """A power model that always reports zero. The default for hosts that
    don't care about energy; lets the :class:`Energy` tracker run
    harmlessly across the whole simulation."""

    def power(self, host: PM, utilisation: float) -> float:
        return 0.0
