"""Event topics published by the simulator.

Topics are members of the :class:`Topic` :class:`enum.StrEnum`. Each
member's value is the canonical string emitted in the log. ``StrEnum``
lets them be used directly wherever a string is expected (logging,
serialisation), but :meth:`cloudy.EventQueue.subscribe`
validates that anything passed to it is either a ``Topic`` member or a
known string. A typo at subscribe time raises ``ValueError`` with a
``difflib`` close-match suggestion.

Importing the module lets you discover topics through attribute access::

    from cloudy import Topic

    sim.event_queue.subscribe(Topic.VM_ALLOCATE, lambda host, vm: print(f'{vm.name} placed on {host.name}'))

Subclasses of :class:`cloudy.models.App` (and of :class:`cloudy.models.Daemon`)
get topic strings derived from their lower-cased class name — for
example, a custom ``MyApp(App)`` triggers ``'myapp.start'`` /
``'myapp.stop'`` events. The :class:`Topic` enum covers the classes
that come with Cloudy; custom subclasses publish plain strings outside
the enum.
"""

from __future__ import annotations

from enum import StrEnum


class Topic(StrEnum):
    """Every event topic the simulator can publish.

    Members are :class:`str` values (via :class:`enum.StrEnum`) so they
    interoperate with any API that expects a string — logging,
    serialisation, raw event dispatch — while still being a closed,
    typo-proof set when used through :meth:`EventQueue.subscribe`.
    """

    # Simulation lifecycle ------------------------------------------------
    SIM_START = 'sim.start'
    """Payload: ``(simulation: Simulation)`` — fires once before the first step."""

    SIM_STOP = 'sim.stop'
    """Payload: ``(simulation: Simulation)`` — fires once after the last step."""

    SIM_PAUSE = 'sim.pause'
    """Payload: ``(simulation: Simulation)`` — fires when ``run(duration=…)`` returns."""

    SIM_REPORT = 'sim.report'
    """Payload: ``(simulation: Simulation, result: dict)`` — fires from :meth:`Simulation.report`."""

    SIM_TICK = 'sim.tick'
    """Payload: ``(simulation: Simulation, dt: float)`` — fires at the end of each :meth:`Simulation._advance_once`."""

    # Request lifecycle ---------------------------------------------------
    REQUEST_ARRIVE = 'request.arrive'
    """Payload: ``(requests: list[Request])``."""

    REQUEST_ACCEPT = 'request.accept'
    """Payload: ``(requests: list[Request])``."""

    REQUEST_REJECT = 'request.reject'
    """Payload: ``(requests: list[Request])``."""

    # App lifecycle (and App / Daemon subclasses) -------------------------
    APP_START = 'app.start'
    """Payload: ``(vm: VM, app: App)``."""

    APP_STOP = 'app.stop'
    """Payload: ``(vm: VM, app: App)``."""

    # VM placement --------------------------------------------------------
    VM_ALLOCATE = 'vm.allocate'
    """Payload: ``(host: PM, vm: VM)``."""

    VM_DEALLOCATE = 'vm.deallocate'
    """Payload: ``(host: PM, vm: VM)``."""

    VM_MIGRATE_START = 'vm.migrate.start'
    """Payload: ``(source: PM, target: PM, vm: VM)`` — a timed migration
    began; the VM keeps running on ``source`` until :data:`VM_MIGRATE_DONE`
    fires (see :meth:`cloudy.policies.Placement.migrate_vm` with
    ``duration > 0``)."""

    VM_MIGRATE_DONE = 'vm.migrate.done'
    """Payload: ``(source: PM, target: PM, vm: VM)`` — a placed VM has
    moved hosts; the *completion* of a migration (immediate, or the end
    of a timed one — see :meth:`cloudy.policies.Placement.migrate_vm`)."""

    # Network -------------------------------------------------------------
    LINK_DELIVER = 'link.deliver'
    """Payload: ``(src: VM, dst: VM, payload_bytes: int | float, tag: object | None)``."""
