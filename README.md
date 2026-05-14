# Cloudy: A Pythonic cloud simulator

[![GPLv3 License](https://img.shields.io/badge/License-GPL%20v3-yellow.svg)](https://opensource.org/licenses/GPL-3.0)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Version](https://img.shields.io/badge/version-0.5.0-blue)
![Runtime deps](https://img.shields.io/badge/runtime%20deps-stdlib%20only-success)
[![DOI](https://img.shields.io/badge/DOI-10.1109%2FICEE63041.2024.10667881-blue)](https://doi.org/10.1109/ICEE63041.2024.10667881)
[![GitHub last commit](https://img.shields.io/github/last-commit/ahmad-siavashi/cloudy.svg)](https://github.com/ahmad-siavashi/cloudy)
![GitHub stars](https://img.shields.io/github/stars/ahmad-siavashi/cloudy?style=social)

![logo](logo.png)

Cloudy simulates VM placement, host-level resource management, and
in-guest CPU scheduling and memory allocation, with energy reporting.
It uses only the Python standard library at runtime. It is built for
researchers who add their own algorithms.

## Getting started

```bash
$ git clone https://github.com/ahmad-siavashi/cloudy.git
$ pip install -e .
$ python examples/basic_simulation.py
```

Requires Python ≥ 3.11.

## Quickstart

```python
from cloudy import App, DataCenter, PM, Request, Simulation, Topic, VM
from cloudy.policies import FirstFit, SpaceShared, TimeShared

sim = Simulation(name='Hello', seed=42)

app = sim.create(App, name='Nginx', length=(1, 1, 1))
vm = sim.create(VM, name='Web', cpu=1, ram=1024, scheduler=TimeShared())
vm.run(app)

pm = sim.create(PM, name='HPE', cpu=(2, 2), ram=2048, hypervisor=SpaceShared())
sim.datacenter = sim.create(DataCenter, name='dc', hosts=[pm], placement=FirstFit())
sim.requests = [sim.create(Request, arrival=0, vm=vm)]

@sim.event_queue.on(Topic.VM_ALLOCATE)
def log_alloc(host, vm):
    print(f'placed {vm.name} on {host.name}')

sim.run().report(to_csv='hello.csv')
```

Policies are passed as *instances*. `seed=` controls reproducibility.
The discrete-event loop advances the clock to the next scheduled event
when no work is pending between ticks.

## Customise a policy

Subclass a reference implementation and override one hook:

| Slot | Where it plugs in | Subclass / override | Example |
|---|---|---|---|
| [`Scheduler`](cloudy/policies/scheduler.py) | `VM(scheduler=...)` | `TimeShared` / `share(processes, cores_cycles)` | [custom_scheduler.py](examples/custom_scheduler.py) |
| [`Hypervisor`](cloudy/policies/hypervisor.py) | `PM(hypervisor=...)` | `SpaceShared` / `has_capacity(vm)` | [custom_hypervisor.py](examples/custom_hypervisor.py) |
| [`Placement`](cloudy/policies/placement.py) | `DataCenter(placement=...)` | `FirstFit` / `select_host(vm)` (or `migrate`) | [custom_placement.py](examples/custom_placement.py), [live_migration.py](examples/live_migration.py) |

```python
# A first-come-first-served scheduler: the first process gets every cycle.
class FCFS(Scheduler):
    def share(self, processes, cores_cycles):
        return [list(cores_cycles)] + [[0] * len(cores_cycles) for _ in processes[1:]]

# A round-robin placement: each VM goes to the next host in turn.
class RoundRobin(Placement):
    def select_host(self, vm):
        hosts = self.datacenter.hosts
        for i in range(len(hosts)):
            host = hosts[(self._next + i) % len(hosts)]
            if all(host.hypervisor.has_capacity(vm)):
                self._next = (self._next + i + 1) % len(hosts)
                return host
        return None
```

You can still override the full methods (`Scheduler.resume`,
`Placement.allocate`, etc.) when one hook is not enough. To collect
metrics, subclass `Tracker`.

## Subscribing to events

```python
from cloudy import Topic, on

# Class method — picked up by EventQueue.subscribe_all(obj).
class MyTracker(Tracker):
    @on(Topic.VM_ALLOCATE)
    def _record(self, host, vm): ...

# Runtime form.
@sim.event_queue.on(Topic.VM_ALLOCATE)
def log_alloc(host, vm): ...
```

If you subscribe with a plain string that matches no `Topic`, Cloudy
raises `ValueError` at subscribe time and suggests the closest match.

## Built-in metrics

`cloudy.metrics` provides ready-made trackers (`Utilisation`,
`CompletionTime`, `Concurrency`, `Energy`). Combine them with
`Composite`:

```python
from cloudy.metrics import Composite, Utilisation, CompletionTime, Energy
from cloudy.power import LinearPower

sim = Simulation(name='Demo', tracker=Composite([Utilisation(), CompletionTime(), Energy()]))
pm = sim.create(PM, ..., hypervisor=SpaceShared(), power=LinearPower(idle=100, peak=250))
```

`sim.run().report()` returns dot-namespaced fields like `util.HPE.cpu`,
`complete.p99`, `energy.HPE.kwh`, alongside `request.arrived` /
`accepted` / `rejected` / `pending`.

## Comparing policies

```python
from cloudy import compare

rows = compare(
    build_workload,
    seed=42,
    processes=4,
    placement_class=[FirstFit, MyPlacement],
    to_csv='sweep.csv'
)
```

`rows` is a list of plain dicts. Pass it to `pandas.DataFrame(...)`
yourself if you need one.

## Logging

Every line has the form `{Sim@time} {topic} key=value …`:

```
Hello@0 sim.start
Hello@0 request.arrive vm=Web
Hello@0 vm.allocate host=HPE vm=Web
Hello@1 app.start vm=Web app=Nginx
Hello@2 app.stop vm=Web app=Nginx
Hello@3 sim.report request.arrived=1 request.accepted=1 request.rejected=0 request.pending=0
```

Output uses the standard `logging` module, on the logger `cloudy.<simulation_name>`.

## Scope

Modelled: **placement** (host selection + per-tick consolidation),
**host-level resource management** (the hypervisor performs VM
admission control and runs the VM schedulers), and the **guest OS**
(how a VM's cycles are split among its processes, and which processes
the VM admits). Within this scope:

- **CPU is a throughput resource.** Work is measured in *cycles*
  (`App.length`). Cores supply cycles at a fixed rate (`PM.cpu`). A
  process completes when its cycle budget is spent.
- **Memory is allocated, not consumed over time.** `SpaceShared`
  reserves `vm.ram` when the VM is placed and holds it for the VM's
  lifetime. Inside the VM, the scheduler gives memory to processes
  (`Daemon.ram`) and rejects those that do not fit. Memory footprints
  are constant.
- **CPU quantities are host-relative.** `vm.cpu` is a core count. The
  VM runs at the host's per-core cycle rate. `App.length` is in cycles,
  not seconds.
- **Time units are generic** — except `cloudy.metrics.Energy`, which
  reports kWh and assumes one tick = one second.
- **Multi-tenancy is identity-only.** `vm.tenant` is readable from
  custom policies and trackers, but the framework enforces no quotas,
  fairness, or isolation.

Not modelled: GPUs, container orchestration, per-tenant
quotas/SLAs/billing, host memory overcommit / ballooning /
time-varying footprints, multiple data centers / zones / racks /
network topology, storage tiers, fault injection. The network is a
standalone, unintegrated `Link` model (see `cloudy/network.py`).

## Architecture

Hybrid discrete-time / discrete-event model. Workloads consume cycles
at each time step. Allocations, lifecycle markers, and custom topics
are dispatched through a per-simulation event queue (the future event
list). When no work is pending in between, `_advance_once` moves the
clock straight to the next queued event, so idle periods cost O(1).

While VMs are running, every time step runs every scheduler, so the
cost grows as `horizon × concurrent VMs`. Set `clock_resolution` to
match the workload's time resolution (for example, `300` for 5-minute
Azure v2 traces) to return to `O(events)`. Results are bit-identical to
`clock_resolution=1` when every event time is a multiple of the
resolution.

Two building blocks: a per-simulation `Clock` and `EventQueue`
(`cloudy/core/`).

### Generating HTML documentation

```bash
$ pip install -e ".[docs]"
$ pydoctor --project-name cloudy --html-output ./docs/ --docformat=numpy ./cloudy/
```

Open `docs/index.html`. Docstrings follow [NumPy style](https://numpydoc.readthedocs.io/en/latest/format.html).

## Citation

If Cloudy helps your research, please cite our paper:

> Siavashi, Ahmad, and Mahmoud Momtazpour. "Cloudy: A Pythonic cloud
> simulator." In *2024 32nd International Conference on Electrical
> Engineering (ICEE)*, pp. 1–5. IEEE, 2024.

```bibtex
@inproceedings{siavashi2024cloudy,
  title={Cloudy: A Pythonic cloud simulator},
  author={Siavashi, Ahmad and Momtazpour, Mahmoud},
  booktitle={2024 32nd International Conference on Electrical Engineering (ICEE)},
  pages={1--5},
  year={2024},
  organization={IEEE}
}
```
