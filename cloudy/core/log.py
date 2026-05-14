"""Per-simulation logging — the default rendering of events as text lines.

Internal infrastructure: this is *how* a :class:`cloudy.Simulation`
prints its event log. It is kept out of ``simulation.py`` so the driver
stays focused on the event loop. The logger is named
``cloudy.<simulation-name>``; each line is prefixed ``<name>@<time> ``
and otherwise mirrors the publish/subscribe shape —
``<topic> key=value …`` — so the log is easy to grep, pipe to ``awk``,
and read as a simple CSV. Pass ``log=False`` to ``Simulation`` to
disable logging, or configure the ``cloudy`` logger yourself.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Callable

from cloudy.core.clock import Clock
from cloudy.topics import Topic


# Topic → ``str.format`` template for the default per-topic log subscribers.
#
# Covers events whose payload is empty or a handful of plain/named
# objects. The ``request.*`` events (payload: a list of Requests) and
# ``sim.report`` (payload: a dict) are logged by handler methods on
# ``Simulation`` that already do other bookkeeping, so their lines ride
# along there. ``link.deliver`` only ever fires if user code wires a
# :class:`cloudy.network.Link`, but having a template means it shows up
# in the standard log like everything else when it does.
LOG_TEMPLATES: dict[str, str] = {
    Topic.SIM_START:        'sim.start',
    Topic.SIM_STOP:         'sim.stop',
    Topic.SIM_PAUSE:        'sim.pause',
    Topic.APP_START:        'app.start vm={0.name} app={1.name}',
    Topic.APP_STOP:         'app.stop vm={0.name} app={1.name}',
    Topic.VM_ALLOCATE:      'vm.allocate host={0.name} vm={1.name}',
    Topic.VM_DEALLOCATE:    'vm.deallocate host={0.name} vm={1.name}',
    Topic.VM_MIGRATE_START: 'vm.migrate.start src={0.name} dst={1.name} vm={2.name}',
    Topic.VM_MIGRATE_DONE:  'vm.migrate.done src={0.name} dst={1.name} vm={2.name}',
    Topic.LINK_DELIVER:     'link.deliver src={0.name} dst={1.name} bytes={2}',
}


def get_logger(name: str, *, to_stdout: bool, clock: Clock) -> logging.Logger:
    """Return the logger for simulation ``name``, set up for Cloudy.

    Name-spaced ``cloudy.<name>`` so a caller can target one simulation
    or all of Cloudy via the parent ``cloudy`` logger. When ``to_stdout``
    is true a stdout handler is attached whose formatter prefixes each
    line with ``<name>@<clock.now> `` — the time read lazily, so any
    message logged anywhere in the run gets the current simulated time.
    Idempotent: calling twice does not stack the handler.
    """
    logger = logging.getLogger(f'cloudy.{name}')
    logger.propagate = False  # don't double-print via the root logger
    if to_stdout:
        logger.setLevel(logging.INFO)
        if not any(isinstance(h, _StdoutHandler) for h in logger.handlers):
            logger.addHandler(_StdoutHandler(name, clock))
    return logger


def topic_logger(logger: logging.Logger, template: str) -> Callable[..., Any]:
    """An event handler that ``logger.info``s ``template`` formatted with
    the event's payload arguments — see :data:`LOG_TEMPLATES`."""
    return lambda *args: logger.info(template.format(*args))


class _StdoutHandler(logging.StreamHandler):
    """Stdout handler that prefixes each line ``<name>@<clock.now> ``.

    A marker subclass so :func:`get_logger` can detect Cloudy's own
    handler and not stack duplicates if a ``Simulation`` is reconstructed
    in the same process.
    """

    def __init__(self, name: str, clock: Clock) -> None:
        super().__init__(stream=sys.stdout)
        self.setFormatter(_Formatter(name, clock))


class _Formatter(logging.Formatter):
    """Prefixes each record with ``<name>@<clock.now> ``, the time read
    lazily at format time."""

    def __init__(self, name: str, clock: Clock) -> None:
        super().__init__('%(message)s')
        self._name = name
        self._clock = clock

    def format(self, record: logging.LogRecord) -> str:
        return f'{self._name}@{self._clock.now} ' + record.getMessage()
