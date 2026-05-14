"""Ready-made trackers — CPU utilisation, completion time, concurrency, energy.

Each is a :class:`cloudy.Tracker` subclass that subscribes to the event
topics it needs. Run several at once via :class:`Composite`::

    from cloudy.metrics import Composite, Utilisation, CompletionTime, Energy

    sim = Simulation(name='Demo', tracker=Composite([Utilisation(), CompletionTime(), Energy()]))

Each metric's :meth:`report` keys are namespaced by metric
(``util.pm-1.cpu``, ``complete.p99``, ``energy.pm-1.kwh``), so merging
them into one flat result dict causes no key collisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cloudy.core import on
from cloudy.models import PM, VM
from cloudy.simulation import Simulation
from cloudy.topics import Topic
from cloudy.tracker import Tracker


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


class Composite(Tracker):
    """Wraps multiple trackers so a single :class:`Simulation` can use
    several at once.

    Each sub-tracker is attached to the simulation and its
    :meth:`Tracker.report` is merged into the composite's report.
    Sub-tracker key namespaces (``util.``, ``energy.``, …) prevent
    collisions.

    Unlike the metric trackers in this module, :class:`Composite` is a
    combinator: it takes the trackers it wraps as a positional argument,
    so it carries a hand-written ``__init__`` rather than being a
    dataclass.
    """

    def __init__(self, trackers: list[Tracker]) -> None:
        super().__init__()
        self.trackers: list[Tracker] = list(trackers)

    def attach(self, simulation: Simulation) -> None:
        super().attach(simulation)
        for t in self.trackers:
            t.attach(simulation)

    def report(self) -> dict[str, float]:
        merged: dict[str, float] = {}
        for t in self.trackers:
            merged.update(t.report())
        return merged


# ---------------------------------------------------------------------------
# Utilisation
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class Utilisation(Tracker):
    """Average per-host CPU *allocation* over the run.

    Sums ``vm.cpu`` (cores reserved) while a VM is allocated, divides by
    the run length and the host's ``sum(host.cpu)`` core count at report
    time → ``util.<host>.cpu``. This is allocation, not consumed work —
    for the latter see :attr:`cloudy.policies.Hypervisor.cpu_utilisation`
    (which :class:`Energy` uses).
    """

    _hosts: dict[str, PM] = field(default_factory=dict)
    _used: dict[str, int] = field(default_factory=dict)
    _last_t: dict[str, float] = field(default_factory=dict)
    _accum: dict[str, float] = field(default_factory=dict)

    @on(Topic.VM_ALLOCATE)
    def _on_alloc(self, host: PM, vm: VM) -> None:
        self._integrate(host)
        self._hosts.setdefault(host.name, host)
        self._used[host.name] = self._used.get(host.name, 0) + vm.cpu

    @on(Topic.VM_DEALLOCATE)
    def _on_dealloc(self, host: PM, vm: VM) -> None:
        self._integrate(host)
        self._used[host.name] = max(0, self._used.get(host.name, 0) - vm.cpu)

    def _integrate(self, host: PM) -> None:
        now: float = self.clock.now
        last: float = self._last_t.get(host.name, 0.0)
        used: int = self._used.get(host.name, 0)
        total: int = sum(host.cpu)
        if total > 0:
            dt: float = max(0.0, now - last)
            self._accum[host.name] = (self._accum.get(host.name, 0.0) + dt * used / total)
        self._last_t[host.name] = now

    def report(self) -> dict[str, float]:
        # Final integration up to "now".
        for host in list(self._hosts.values()):
            self._integrate(host)
        run_length: float = max(1e-12, self.clock.now)
        return {f'util.{name}.cpu': accum / run_length for name, accum in self._accum.items()}


# ---------------------------------------------------------------------------
# CompletionTime
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class CompletionTime(Tracker):
    """Mean / median / p99 of per-app wall-time, in simulation units."""

    _start: dict[int, float] = field(default_factory=dict)
    _durations: list[float] = field(default_factory=list)

    @on(Topic.APP_START)
    def _on_start(self, _vm, app) -> None:
        self._start[id(app)] = self.clock.now

    @on(Topic.APP_STOP)
    def _on_stop(self, _vm, app) -> None:
        start = self._start.pop(id(app), None)
        if start is not None:
            self._durations.append(self.clock.now - start)

    def report(self) -> dict[str, float]:
        if not self._durations:
            return {}
        sorted_d: list[float] = sorted(self._durations)
        n: int = len(sorted_d)

        def percentile(p: float) -> float:
            idx: int = max(0, min(n - 1, int(n * p)))
            return sorted_d[idx]

        return {
            'complete.mean': sum(sorted_d) / n,
            'complete.median': percentile(0.50),
            'complete.p99': percentile(0.99),
            'complete.count': n
            }


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class Concurrency(Tracker):
    """Time-averaged number of running apps per VM."""

    _count: dict[str, int] = field(default_factory=dict)
    _last_t: dict[str, float] = field(default_factory=dict)
    _accum: dict[str, float] = field(default_factory=dict)

    @on(Topic.APP_START)
    def _on_start(self, vm, _app) -> None:
        self._integrate(vm.name)
        self._count[vm.name] = self._count.get(vm.name, 0) + 1

    @on(Topic.APP_STOP)
    def _on_stop(self, vm, _app) -> None:
        self._integrate(vm.name)
        self._count[vm.name] = max(0, self._count.get(vm.name, 0) - 1)

    def _integrate(self, name: str) -> None:
        now: float = self.clock.now
        last: float = self._last_t.get(name, 0.0)
        n: int = self._count.get(name, 0)
        dt: float = max(0.0, now - last)
        self._accum[name] = self._accum.get(name, 0.0) + dt * n
        self._last_t[name] = now

    def report(self) -> dict[str, float]:
        for name in list(self._count.keys()):
            self._integrate(name)
        run_length: float = max(1e-12, self.clock.now)
        return {f'concurrency.{name}': accum / run_length for name, accum in self._accum.items()}


# ---------------------------------------------------------------------------
# Energy
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class Energy(Tracker):
    """Per-host energy consumed over the run, in kilowatt-hours.

    On every :data:`Topic.SIM_TICK`, integrates ``power × dt`` for **all**
    hosts in the data center — an idle but powered-on host still draws
    its model's ``idle`` watts — where ``power`` is
    ``host.power.power(host, host.hypervisor.cpu_utilisation)``. So energy
    tracks *actual CPU work* (via :attr:`Hypervisor.cpu_utilisation`),
    not just how many cores were reserved.

    Reported in kWh — i.e. watts × *seconds* / 3.6e6 — so it assumes one
    simulation time unit is one second. With a different unit, scale the
    :attr:`report` values accordingly.
    """

    _joules: dict[str, float] = field(default_factory=dict)

    @on(Topic.SIM_TICK)
    def _on_tick(self, _simulation, dt: float) -> None:
        for host in self.simulation.datacenter.hosts:
            watts: float = host.power.power(host, host.hypervisor.cpu_utilisation)
            self._joules[host.name] = self._joules.get(host.name, 0.0) + watts * dt

    def report(self) -> dict[str, float]:
        return {f'energy.{name}.kwh': joules / 3.6e6 for name, joules in self._joules.items()}
