"""Pluggable decision policies — Cloudy's extension points.

Three policies, each an abstract base plus at least one reference
implementation:

- :class:`Scheduler` (CPU scheduling within a VM) — :class:`TimeShared`
- :class:`Hypervisor` (VM management on a host) — :class:`SpaceShared`
- :class:`Placement` (mapping VMs to hosts) — :class:`FirstFit`

To experiment with a new algorithm, subclass the relevant abstract base
and implement the marked methods. See the module-level docstring of
:mod:`cloudy.policies.scheduler`, :mod:`cloudy.policies.hypervisor`, and
:mod:`cloudy.policies.placement` for each contract.

To observe a run rather than control it, subclass
:class:`cloudy.Tracker` (see :mod:`cloudy.tracker`) — the ready-made
trackers in :mod:`cloudy.metrics` are examples.
"""

from __future__ import annotations

from cloudy.policies.hypervisor import Hypervisor, SpaceShared
from cloudy.policies.placement import FirstFit, Placement
from cloudy.policies.scheduler import Scheduler, TimeShared

__all__ = [
    "FirstFit",
    "Hypervisor",
    "Placement",
    "Scheduler",
    "SpaceShared",
    "TimeShared",
]
