"""Publish/subscribe event queue that drives the simulation.

This module provides:

- :class:`EventQueue` — a time-ordered topic-based event queue. Each
  :class:`cloudy.Simulation` instance owns its own; there is no
  process-wide singleton.
- :func:`on` — a method decorator that marks event handlers for
  auto-subscription. Combined with :meth:`EventQueue.subscribe_all`, it
  removes the boilerplate of calling :meth:`EventQueue.subscribe` from
  every ``__post_init__``::

      class MyTracker(Tracker):
          @on(Topic.VM_ALLOCATE)
          def _record_allocation(self, host, vm):
              ...

  When the object is registered (via :meth:`EventQueue.subscribe_all` —
  the framework calls it for you from :meth:`Tracker.attach`,
  :meth:`Placement.attach`, and :meth:`Simulation._setup`), every
  ``@on``-decorated method on it is subscribed automatically.
"""

from __future__ import annotations

import difflib
import heapq
import itertools
from collections import defaultdict
from typing import Any, Callable, Iterable


# Attribute name used by :func:`on` to attach topics to a method. Kept
# private — :meth:`EventQueue.subscribe_all` is the only consumer.
_SUBSCRIBED_ATTR: str = '_cloudy_subscribed_topics'


def _validate_topic(topic: Any) -> None:
    """Raise ``ValueError`` if ``topic`` isn't a known :class:`Topic` member.

    A bare string is accepted only if it equals one of the
    :class:`Topic` enum values (or a process subclass's
    ``<classname>.start`` / ``.stop`` topic, which can't be enumerated
    here). For the enumerable cases, suggest a close match via
    :func:`difflib.get_close_matches`.
    """
    # Lazy import — topics imports nothing else, so this is cheap.
    from cloudy.topics import Topic

    if isinstance(topic, Topic):
        return
    if not isinstance(topic, str):
        raise ValueError(f'Topic must be a Topic member or string, got {type(topic).__name__}')

    known: list[str] = [t.value for t in Topic]
    if topic in known:
        return
    # Allow per-class start/stop topics fired by the scheduler.
    if topic.endswith('.start') or topic.endswith('.stop'):
        return
    # Unknown — suggest close match.
    suggestions: list[str] = difflib.get_close_matches(topic, known, n=1)
    if suggestions:
        raise ValueError(
            f"Unknown topic: '{topic}'. Did you mean: '{suggestions[0]}'?"
        )
    raise ValueError(f"Unknown topic: '{topic}'.")


def on(*topics: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a method to auto-subscribe to one or more event topics.

    The method is unchanged at definition time; the decorator stashes
    the topic list on the function object. Later, when an instance is
    registered with :meth:`EventQueue.subscribe_all`, every decorated
    method is subscribed to those topics.

    Parameters
    ----------
    *topics : str
        One or more topic names. A single decorator can handle several
        topics with the same callback (e.g. ``vm.allocate`` /
        ``vm.deallocate``).

    Returns
    -------
    decorator
        A decorator that returns the original method, with topic
        metadata attached.
    """
    def decorator(method: Callable[..., Any]) -> Callable[..., Any]:
        setattr(method, _SUBSCRIBED_ATTR, topics)
        return method
    return decorator


class EventQueue:
    """A time-ordered publish/subscribe event queue.

    Subscribers register a callback against a topic via
    :meth:`subscribe`. Publishers schedule an event for a future (or
    current) simulation time via :meth:`publish`. The simulator drains
    the queue up to a given simulation time with :meth:`run_until`,
    which dispatches each due event to every subscriber of its topic.

    Events are ordered first by their scheduled time and then by
    publication order, so events scheduled at the same time fire in the
    order they were published.

    Attributes
    ----------
    _subscribers : dict[str, list[Callable]]
        Mapping of topic name to the list of subscriber callbacks
        registered against that topic, in registration order.
    _queue : list
        A binary heap of pending events. Each entry is a tuple of
        ``(scheduled_time, sequence, topic, args)``.
    _counter : itertools.count
        Monotonic sequence used as a tiebreaker so that events sharing
        the same scheduled time are dispatched in publication order.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self._queue: list[tuple[int | float, int, str, tuple[Any, ...]]] = []
        self._counter: itertools.count = itertools.count()

    def on(self, topic: str | Iterable[str]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator form of :meth:`subscribe` for runtime use.

        Defines a handler in-place and registers it::

            @sim.event_queue.on(Topic.VM_ALLOCATE)
            def log_allocations(host, vm):
                print(f'placed {vm.name} on {host.name}')

        The decorated function is returned unchanged so it can still be
        called directly — the decoration just schedules the
        subscription as a side-effect.
        """
        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self.subscribe(topic, handler)
            return handler
        return decorator

    def subscribe(
        self,
        topic: str | Iterable[str],
        handler: Callable[..., Any],
    ) -> EventQueue:
        """Register a handler for one or more topics.

        Multiple handlers may subscribe to the same topic; they are
        invoked in registration order when an event fires.

        Parameters
        ----------
        topic : str or iterable of str
            Either a single topic name or an iterable of topic names —
            useful when one handler should fire for several related
            topics (e.g. ``vm.allocate`` / ``vm.deallocate``).
        handler : Callable
            Callable invoked with the event payload positional
            arguments when an event fires.

        Returns
        -------
        EventQueue
            The queue instance, to allow method chaining.
        """
        topics_iter: Iterable[str] = (topic,) if isinstance(topic, str) else topic
        for t in topics_iter:
            _validate_topic(t)
            self._subscribers[t].append(handler)
        return self

    def subscribe_all(self, obj: Any) -> EventQueue:
        """Subscribe every :func:`on`-decorated method on ``obj``.

        Walks the bound methods of ``obj`` once, finds those marked by
        :func:`on`, and subscribes each to its topics. Idempotent only
        in the sense that calling :meth:`subscribe_all` twice subscribes
        twice — call it once per object.

        Parameters
        ----------
        obj : Any
            Any object with :func:`on`-decorated methods.

        Returns
        -------
        EventQueue
            The queue instance, to allow method chaining.
        """
        for attr_name in dir(obj):
            attr: Any = getattr(obj, attr_name, None)
            topics: tuple[str, ...] = getattr(attr, _SUBSCRIBED_ATTR, ())
            if topics:
                self.subscribe(topics, attr)
        return self

    def publish(self, topic: str, time: int | float, *args: Any) -> EventQueue:
        """Schedule an event to fire at the given simulation time.

        The event is delivered the next time :meth:`run_until` is
        called with a cutoff greater than or equal to ``time``.

        Parameters
        ----------
        topic : str
            Name of the topic the event belongs to.
        time : int | float
            Simulation time at which the event should fire.
        *args : Any
            Payload positional arguments forwarded to subscribers.

        Returns
        -------
        EventQueue
            The queue instance, to allow method chaining.
        """
        heapq.heappush(self._queue, (time, next(self._counter), topic, args))
        return self

    def run_until(self, time: int | float) -> EventQueue:
        """Dispatch every queued event with a scheduled time up to ``time``.

        Events fire in scheduled-time order, with ties broken by
        publication order. Each event is delivered to every subscriber
        of its topic, in the order subscribers were registered. New
        events published from within a handler are honored if their
        scheduled time also falls within the cutoff.

        Parameters
        ----------
        time : int | float
            Inclusive upper bound on the scheduled time of dispatched
            events.

        Returns
        -------
        EventQueue
            The queue instance, to allow method chaining.
        """
        while self._queue and self._queue[0][0] <= time:
            _, _, topic, args = heapq.heappop(self._queue)
            for handler in self._subscribers.get(topic, ()):
                handler(*args)
        return self

    def broadcast(self, topic: str, *args: Any) -> EventQueue:
        """Dispatch synchronously, bypassing the time queue.

        Use this for events that fall outside the simulation's time
        ordering — typically lifecycle markers like simulation start /
        stop / report. Each subscriber registered against ``topic`` is
        invoked immediately, in registration order.

        Parameters
        ----------
        topic : str
            Name of the topic the event belongs to.
        *args : Any
            Payload positional arguments forwarded to subscribers.

        Returns
        -------
        EventQueue
            The queue instance, to allow method chaining.
        """
        for handler in self._subscribers.get(topic, ()):
            handler(*args)
        return self

    def is_empty(self) -> bool:
        """``True`` when no events remain to be dispatched."""
        return not self._queue

    @property
    def next_time(self) -> int | float | None:
        """Scheduled time of the next due event, or ``None`` if the queue is empty.

        Used by :meth:`Simulation._advance_once` to jump the clock
        directly to the next event rather than ticking through empty
        time.
        """
        return self._queue[0][0] if self._queue else None
