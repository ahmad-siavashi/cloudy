"""``Bound`` — shared logic to create a policy on its own, then bind it to its owner.

A :class:`cloudy.policies.Scheduler`, :class:`~cloudy.policies.Hypervisor`,
:class:`~cloudy.policies.Placement`, or :class:`cloudy.Tracker` is created
on its own (``TimeShared()``, ``SpaceShared()``, a custom subclass, …)
and then *bound* to the model it serves — a :class:`~cloudy.VM`,
:class:`~cloudy.PM`, :class:`~cloudy.DataCenter`, or
:class:`~cloudy.Simulation` — by a one-line ``attach(owner)`` call the
framework makes for you (from the owner's ``__post_init__``, or from
``Simulation.__post_init__`` for the tracker). :class:`Bound` captures
that two-step pattern once, so each policy base doesn't repeat the
back-reference, the ``clock``/``event_queue`` proxies, and the ``@on``
auto-subscription.

This is internal infrastructure. Subclassing a policy never requires
reading it: you override the policy's hook (``share`` / ``has_capacity`` /
``select_host`` / ``report``) and use ``self.owner`` — or the friendly
alias the base re-exposes it under (``self.vm`` / ``self.host`` /
``self.datacenter`` / ``self.simulation``) — plus ``self.clock`` and
``self.event_queue``.
"""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from cloudy.core.clock import Clock
from cloudy.core.event_queue import EventQueue


class _Owner(Protocol):
    """What :class:`Bound` needs from whatever it's attached to: an object
    that carries the simulation's clock and event queue. Every
    :class:`cloudy.models.SimObject` (``VM`` / ``PM`` / ``DataCenter``)
    and :class:`cloudy.Simulation` itself satisfies this."""

    clock: Clock
    event_queue: EventQueue


# The owner type a Bound subclass is parameterised with — e.g. a
# Scheduler is Bound[VM], so its `owner` reads back as a VM.
Owner = TypeVar('Owner', bound=_Owner)


class Bound(Generic[Owner]):
    """Mixin for an object created bare and later bound to a single owner.

    After :meth:`attach`, the owner is :attr:`owner`, and — since every
    owner carries the simulation's clock and event queue — :attr:`clock`
    and :attr:`event_queue` are too (proxied through the owner). Reading
    any of them before :meth:`attach` raises a clear :class:`RuntimeError`
    rather than handing back a confusing ``None``.

    :meth:`attach` also subscribes every :func:`cloudy.on`-decorated
    method on this object to the owner's event queue — so a custom
    policy can react to events just by decorating a handler, with no
    ``attach`` override. Override :meth:`attach` only for setup that
    reads the owner's own fields (as :class:`cloudy.policies.SpaceShared`
    does, to build its free-resource pools), and call
    ``super().attach(owner)`` first.
    """

    def attach(self, owner: Owner) -> None:
        self._owner: Owner = owner
        owner.event_queue.subscribe_all(self)

    @property
    def owner(self) -> Owner:
        try:
            return self._owner
        except AttributeError:
            raise RuntimeError(
                f'{type(self).__name__} is not attached yet — pass it to '
                f'the model that uses it (a VM, PM, DataCenter, or Simulation).'
            ) from None

    @property
    def clock(self) -> Clock:
        return self.owner.clock

    @property
    def event_queue(self) -> EventQueue:
        return self.owner.event_queue
