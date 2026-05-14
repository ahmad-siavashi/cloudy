"""The simulation driver: :class:`Simulation`.

A :class:`Simulation` owns the clock, event queue, and tracker for a
single run. The recommended usage pattern is::

    sim = Simulation(name='Demo')
    app = sim.create(App, name='Nginx', length=(1,))
    vm = sim.create(VM, name='Web', cpu=1, ram=1024, scheduler=TimeShared())
    vm.run(app)
    pm = sim.create(PM, name='HPE', cpu=(2,), ram=2048, hypervisor=SpaceShared())
    sim.datacenter = sim.create(DataCenter, name='dc', hosts=[pm], placement=FirstFit())
    sim.requests = [sim.create(Request, arrival=0, vm=vm)]
    sim.run().report()

:meth:`Simulation.create` passes the simulation's :class:`Clock` and
:class:`EventQueue` into each component automatically, so user code
never sees a ``None`` clock or event_queue attribute.

Simulation log output uses the standard library :mod:`logging`
package, on the logger ``cloudy.<name>``. When ``log=True`` (the
default), a stdout handler prints each event as
``<name>@<time> <topic> key=value …``. The line-formatting code is in
:mod:`cloudy.core.log`. To silence
Cloudy's logging, pass ``log=False`` or call::

    logging.getLogger('cloudy').setLevel(logging.WARNING)
"""

from __future__ import annotations

import csv
import json
import logging
import random
from dataclasses import dataclass, field
from itertools import groupby
from typing import Any, Final, Type, TypeVar

from cloudy import models
from cloudy.core import Clock, EventQueue, on, log
from cloudy.topics import Topic
from cloudy.tracker import Tracker


T = TypeVar('T')


@dataclass(eq=False)
class Simulation:
    """A single simulation run.

    Construct an empty simulation, attach a :class:`DataCenter` and a
    list of :class:`Request` s (build them with :meth:`create`), then
    call :meth:`run`.

    Attributes
    ----------
    name : str
        Name of the simulation (used in log prefixes and the logger name).
    clock_resolution : int | float
        Simulation time units between consecutive scheduler/housekeeping
        rounds — i.e. how often :meth:`_advance_once` crosses a tick
        boundary and drives every host's hypervisor. Usually an integer;
        ``int | float`` for consistency with the rest of the time API
        (see :mod:`cloudy.core.clock`).
    log : bool
        When ``True``, attach a stdout handler so simulation events are
        printed. When ``False``, the logger is silent unless the caller
        has configured handlers themselves.
    seed : int, optional
        If given, seeds Python's global RNG so policies that call
        :mod:`random` produce deterministic sequences. ``None`` (default)
        leaves the RNG state alone.
    requests : list[Request]
        The arriving workload. Each :class:`Request` fires at its
        ``arrival`` time. Empty by default; populate before :meth:`run`.
    datacenter : DataCenter, optional
        The data center under management. Required before :meth:`run`.
    tracker : Tracker
        Records request outcomes; subclass and pass an instance to
        track custom metrics. Defaults to a base :class:`Tracker`.
    """

    name: Final[str]
    clock_resolution: Final[int | float] = field(default=1)
    log: Final[bool] = True
    seed: Final[int | None] = None
    requests: list[models.Request] = field(default_factory=list)
    datacenter: models.DataCenter | None = None
    tracker: Tracker = field(default_factory=Tracker)

    def __post_init__(self) -> None:
        # Per-simulation clock and event queue. Each Simulation owns its
        # own pair so independent runs (and tests) do not share state.
        self.clock: Clock = Clock()
        self.event_queue: EventQueue = EventQueue()
        self._setup_done: bool = False
        # Last simulation time at which ``placement.resume`` was run.
        # Updated only on tick boundaries; ``_advance_once`` may jump
        # the clock past intermediate event-only steps.
        self._last_resume: int | float = 0
        # Seed Python's global RNG so any policy that calls ``random``
        # produces deterministic sequences. NumPy users seed
        # ``numpy.random`` themselves; Cloudy doesn't depend on NumPy.
        if self.seed is not None:
            random.seed(self.seed)

        # Per-simulation logger; callers just write ``self._logger.info(msg)``
        # and the ``<name>@<time>`` prefix is added at format time (see
        # :mod:`cloudy.core.log`).
        self._logger: logging.Logger = log.get_logger(self.name, to_stdout=self.log, clock=self.clock)

        # Bind the tracker to this simulation (this also subscribes its handlers).
        self.tracker.attach(self)

    def create(self, cls: Type[T], **kwargs: Any) -> T:
        """Construct an instance of ``cls`` bound to this simulation.

        If ``cls`` is a :class:`cloudy.models.SimObject` subclass, this
        simulation's ``clock`` and ``event_queue`` are threaded in
        automatically. Pure-data classes (e.g. :class:`Request`) that
        don't inherit ``SimObject`` pass through unchanged.

        Parameters
        ----------
        cls : type
            Class to instantiate.
        **kwargs
            Keyword arguments forwarded to ``cls``.

        Returns
        -------
        T
            A live instance of ``cls``.
        """
        if issubclass(cls, models.SimObject):
            kwargs.setdefault('clock', self.clock)
            kwargs.setdefault('event_queue', self.event_queue)
        return cls(**kwargs)

    def _setup(self) -> None:
        """Subscribe handlers and publish initial request.arrive events.

        Idempotent — safe to call multiple times. Called once at the
        start of :meth:`run`.
        """
        if self._setup_done:
            return
        if self.datacenter is None:
            raise ValueError('Simulation requires a datacenter to be set before run().')

        # Auto-subscribe every ``@on``-decorated method (request handlers,
        # lifecycle markers, the report renderer).
        self.event_queue.subscribe_all(self)

        # Default per-topic log subscribers (see :mod:`cloudy.core.log`).
        for topic, template in log.LOG_TEMPLATES.items():
            self.event_queue.subscribe(topic, log.topic_logger(self._logger, template))

        # Group incoming requests by arrival time and publish them.
        # Sort first so requests with the same arrival but submitted out
        # of order land in a single batch.
        by_arrival = lambda r: r.arrival
        for arrival, requests in groupby(sorted(self.requests, key=by_arrival), key=by_arrival):
            self.event_queue.publish(Topic.REQUEST_ARRIVE, arrival, list(requests))

        self._setup_done = True

    def report(self, to_stdout: bool = True, to_csv: str | None = None, to_json: str | None = None) -> dict[str, Any]:
        """Compute and broadcast a result summary.

        The result is a flat dict of raw counts plus whatever fields
        the attached :class:`Tracker` chooses to merge in. Ratios are
        not included — they are trivial to derive from the counts.

        Parameters
        ----------
        to_stdout : bool
            When true, broadcast :data:`Topic.SIM_REPORT`; the default
            subscriber writes a single ``sim.report key=value …`` line.
        to_csv : str, optional
            Path to write the result as a single-row CSV via stdlib
            :mod:`csv`. Headers are the dict keys.
        to_json : str, optional
            Path to write the result as JSON via stdlib :mod:`json`.

        Returns
        -------
        dict
            The result dict (always returned regardless of ``to_*``).
        """
        result: dict[str, Any] = {
            'request.arrived':  len(self.tracker.arrived),
            'request.accepted': len(self.tracker.accepted),
            'request.rejected': len(self.tracker.rejected),
            'request.pending':  self.tracker.pending,
            **self.tracker.report(),
        }

        if to_stdout:
            self.event_queue.broadcast(Topic.SIM_REPORT, self, result)

        if to_csv is not None:
            with open(to_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=list(result.keys()))
                writer.writeheader()
                writer.writerow(result)

        if to_json is not None:
            with open(to_json, 'w') as f:
                json.dump(result, f, indent=2)

        return result

    @on(Topic.SIM_REPORT)
    def _render_sim_report(self, _sim: Simulation, result: dict[str, Any]) -> None:
        """Default :data:`Topic.SIM_REPORT` subscriber — one KV-formatted line."""
        kv: str = ' '.join(f'{k}={v}' for k, v in result.items())
        self._logger.info(f'sim.report {kv}')

    def run(self, duration: int | float | None = None) -> Simulation:
        """Drive the simulation forward.

        Parameters
        ----------
        duration : int | float, optional
            If given, run for exactly that many time units. Otherwise
            run until :meth:`is_completed` returns ``True`` — which it
            never will if the only work left is a non-terminating
            :class:`cloudy.models.Daemon`, so in that case ``run()``
            raises :class:`RuntimeError`; pass ``duration=`` for
            infinite workloads.
        """
        self._setup()
        self.event_queue.broadcast(Topic.SIM_START, self)

        if duration is None:
            while not self.is_completed():
                self._advance_once()
                self._guard_against_infinite_stall()
            self.event_queue.broadcast(Topic.SIM_STOP, self)
        else:
            end_time: int | float = self.clock.now + duration
            while self.clock.now < end_time:
                self._advance_once(deadline=end_time)
            self.event_queue.broadcast(Topic.SIM_PAUSE, self)
        return self

    def _guard_against_infinite_stall(self) -> None:
        """Raise if a no-``duration`` :meth:`run` can no longer progress.

        The run stalls when the event queue is empty and every placed VM
        is running only infinite work — no idle VMs (which would be
        reclaimed on the next tick) and no VMs running an :class:`App`
        (which would eventually finish). Both predicates are documented
        methods on :class:`~cloudy.policies.Scheduler`, so the engine
        never has to know about :class:`~cloudy.models.App` vs
        :class:`~cloudy.models.Daemon` directly.
        """
        assert self.datacenter is not None  # ensured by _setup
        if not self.event_queue.is_empty() or self.tracker.pending != 0:
            return  # more events / decisions are coming
        placement = self.datacenter.placement
        if placement.is_empty():
            return  # is_completed() will be True next iteration

        if any(vm.scheduler.is_empty() or vm.scheduler.has_finite_process() for vm in placement):
            return  # some VM will be reclaimed or finish its App
        raise RuntimeError(
            f'Simulation {self.name!r} has only infinite work left '
            f'(a Daemon never finishes), so run() with no duration would '
            f'never return. Call run(duration=...) to give it a time horizon.'
        )

    def _advance_once(self, deadline: int | float | None = None) -> None:
        """Advance the simulation by one step.

        The clock target is the minimum of (a) the next queued event's
        scheduled time, (b) the next periodic tick at
        ``_last_resume + clock_resolution``, and (c) the optional
        ``deadline`` passed by :meth:`run`. ``placement.resume`` runs
        only on tick boundaries — when the queue is briefly busy with
        events between two ticks the simulator drains them at the
        intermediate time without forcing the schedulers through a
        zero-duration cycle.
        """
        assert self.datacenter is not None  # ensured by _setup

        now: int | float = self.clock.now
        next_event: int | float | None = self.event_queue.next_time
        next_tick: int | float = self._last_resume + self.clock_resolution

        target: int | float = next_tick
        if next_event is not None and next_event < target:
            target = next_event
        if deadline is not None and deadline < target:
            target = deadline

        dt: int | float = max(0, target - now)
        self.clock.now = target

        if target >= next_tick:
            # Reached a tick boundary — run schedulers + housekeeping
            # BEFORE firing events scheduled at this exact moment, so
            # arrivals landing on a tick boundary don't get retroactively
            # credited with work for the closing interval [_last_resume, T]
            # they did not exist in. Their first tick runs in the next
            # iteration's resume.
            resume_dt: int | float = target - self._last_resume
            self.datacenter.placement.resume(resume_dt)
            stopped_vms: list[models.VM] = self.datacenter.placement.pop_stopped()
            if stopped_vms:
                self.datacenter.placement.deallocate(stopped_vms)
            # Commit any in-flight timed migration whose transfer just
            # finished, then let the policy start new ones (the latter is
            # a no-op unless the placement overrides migrate()).
            self.datacenter.placement.advance_migrations()
            self.datacenter.placement.migrate()
            self._last_resume = target

        self.event_queue.run_until(target)
        self.event_queue.broadcast(Topic.SIM_TICK, self, dt)

    def is_completed(self) -> bool:
        """``True`` when nothing remains to do."""
        assert self.datacenter is not None  # ensured by _setup
        return self.event_queue.is_empty() and self.tracker.pending == 0 and self.datacenter.placement.is_empty()

    @on(Topic.REQUEST_ARRIVE)
    def _handle_request_arrive(self, requests: list[models.Request]) -> None:
        """Place a batch of arriving requests on the data center."""
        self.tracker.on_arrive(requests)
        self._log_requests('arrive', requests)

        assert self.datacenter is not None  # ensured by _setup
        allocations: list[bool] = self.datacenter.placement.allocate([r.vm for r in requests])

        accepted: list[models.Request] = [r for r, ok in zip(requests, allocations) if ok]
        rejected: list[models.Request] = [r for r, ok in zip(requests, allocations) if not ok]

        now: int | float = self.clock.now
        self.event_queue.publish(Topic.REQUEST_ACCEPT, now, accepted)
        self.event_queue.publish(Topic.REQUEST_REJECT, now, rejected)

    @on(Topic.REQUEST_ACCEPT)
    def _handle_request_accept(self, requests: list[models.Request]) -> None:
        """Record accepted requests and emit per-request log lines."""
        self.tracker.on_accept(requests)
        self._log_requests('accept', requests)

    @on(Topic.REQUEST_REJECT)
    def _handle_request_reject(self, requests: list[models.Request]) -> None:
        """Record rejected requests and emit per-request log lines."""
        self.tracker.on_reject(requests)
        self._log_requests('reject', requests)

    def _log_requests(self, verb: str, requests: list[models.Request]) -> None:
        """Emit one ``request.{verb} vm={name}`` line per request."""
        for r in requests:
            self._logger.info(f'request.{verb} vm={r.vm.name}')
