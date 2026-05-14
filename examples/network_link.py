"""Use the standalone network model — a worked example.

``cloudy.network`` is an *optional* building block: the core simulator
never creates a :class:`~cloudy.network.Link`, VMs and PMs have no NIC,
and the workload generates no traffic on its own. If you want network
effects, you build :class:`Link` s yourself and call :meth:`Link.send`
from your own event handlers; the link schedules a
:data:`cloudy.Topic.LINK_DELIVER` event at
``now + latency + payload_bytes / bandwidth``.

Here, two long-running service VMs are placed on two different hosts
(first-fit). When the *client* VM is placed, its handler sends a 1 MB
payload to the *server* VM over a 10 MB/s link with 5 time units of
latency, so delivery happens at ``t = 0 + 5 + 1e6 / 1e7 = 5.1`` — see
the ``link.deliver`` line in the log, while both VMs are still running.
A small :class:`~cloudy.Tracker` also counts received bytes, so the
total appears on the standard ``sim.report`` line. We limit the run
with ``run(duration=...)`` because the services never finish on their
own (a :class:`~cloudy.models.Daemon` runs forever); the run *pauses*
at the time limit with the VMs still placed.

(If the client ran a *finite* job instead, you would trigger the send
on :data:`cloudy.Topic.APP_START` — but then its VM is reclaimed when
the job ends, possibly before the payload arrives.)

Run with::

    python examples/network_link.py
"""

from dataclasses import dataclass, field

from cloudy import DataCenter, Daemon, PM, Request, Simulation, Topic, Tracker, VM, on
from cloudy.network import Link
from cloudy.policies import FirstFit, SpaceShared, TimeShared


@dataclass
class BytesReceived(Tracker):
    """Tally bytes delivered to each VM over the network → ``net.<vm>.bytes_in``."""

    _by_vm: dict[str, int] = field(default_factory=dict)

    @on(Topic.LINK_DELIVER)
    def _on_deliver(self, _src, dst, payload_bytes, _tag):   # payload: (src, dst, bytes, tag)
        self._by_vm[dst.name] = self._by_vm.get(dst.name, 0) + payload_bytes

    def report(self):
        return {f'net.{name}.bytes_in': n for name, n in self._by_vm.items()}


sim = Simulation(name='NetDemo', seed=42, tracker=BytesReceived())

# Two long-running services — a client and a server.
client = sim.create(VM, name='client', cpu=1, ram=512, scheduler=TimeShared())
client.run(Daemon(name='client-svc'))
server = sim.create(VM, name='server', cpu=1, ram=512, scheduler=TimeShared())
server.run(Daemon(name='server-svc'))

# Two hosts so first-fit puts the two VMs on different machines.
hosts = [sim.create(PM, name=f'pm-{i + 1}', cpu=(2,), ram=2048, hypervisor=SpaceShared()) for i in range(2)]
sim.datacenter = sim.create(DataCenter, name='dc', hosts=hosts, placement=FirstFit())
sim.requests = [sim.create(Request, arrival=0, vm=vm) for vm in (client, server)]

# A 10 MB/s link with 5 time units of latency between the two VMs.
link = Link(name='client->server', bandwidth=1e7, latency=5)
PAYLOAD_BYTES = 1_000_000


@sim.event_queue.on(Topic.VM_ALLOCATE)
def ship_payload(host, vm):
    """When the client lands on a host, send a payload to the server."""
    if vm is client:
        link.send(sim, client, server, PAYLOAD_BYTES)


sim.run(duration=6).report()
