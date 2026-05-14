# Changelog

All notable changes to Cloudy are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Cloudy
uses [Semantic Versioning](https://semver.org/). Each entry states
*what* changed and *why*.

## [0.5.0] — 2026-05-19

A large restructuring release. The goal was to make Cloudy smaller,
clearer, and easier for researchers to extend. Code written for 0.4.x
will not run unchanged — see **Migration notes** at the end of this
section.

### Added

- **Live VM migration.** A per-tick `Placement.migrate()` hook and a
  `migrate_vm()` mechanism move a running VM between hosts. The move
  emits timed `vm.migrate.start` / `vm.migrate.done` events, and the
  guest keeps running on the source host until the memory copy commits.
  *Why:* dynamic consolidation and load-balancing studies need
  migration.
- **Standalone network model.** A point-to-point `Link` (bandwidth and
  latency) with a small API (`Link.send(sim, ...)`) and fail-fast
  validation, plus a worked example. *Why:* lets a study add network
  effects without making the core simulator network-aware.
- **`Scheduler.has_finite_work`.** The engine asks the scheduler
  instead of inspecting process types. *Why:* custom process classes
  now work without engine changes.

### Changed

- **Flat `cloudy/` package.** The old `src/` layout is gone; import
  from `cloudy` (and `cloudy.policies`, `cloudy.metrics`, ...). *Why:*
  simpler imports.
- **Resource model reshaped around RAM footprints.** `cpu` / `ram` are
  plain numbers on the model; the policies decide what they mean. *Why:*
  keeps the model small and policy-driven.
- **Per-simulation timekeeping.** The `Clock` and `EventQueue` belong
  to each `Simulation`; there is no module-level global state. *Why:*
  lets several simulations run independently.
- **Schedulers run before events each tick.** *Why:* prevents a
  newly placed VM from receiving CPU before it is ready.
- **VM lifecycle moved to `Placement`.** The base class handles the
  hypervisor allocation and the `vm.allocate` / `vm.deallocate` events.
  *Why:* a custom placement now overrides one method.
- **`pop_stopped` unified.** An app is deallocated in the same tick it
  stops. *Why:* removes a one-tick accounting gap.
- **Metric keys are dot-namespaced** (`util.HPE.cpu`, `complete.p99`,
  `energy.HPE.kwh`). *Why:* several trackers can be merged into one
  flat result without key collisions.
- **Type hints and PEP 8 naming** applied across the package. *Why:*
  readability for researchers reading the source.
- **Examples reworked:** `basic_simulation`, `compare_placement`,
  `custom_scheduler`, `custom_hypervisor`, `custom_placement`,
  `custom_tracker`, `live_migration`, `network_link`.

### Removed

- **Container-as-a-Service layer** and the old `src/` package. *Why:*
  to make Cloudy easier to learn.
- **GPU-specific modelling.** *Why:* to make Cloudy easier to learn;
  CPU and RAM cover the studied cases.

### Renamed

- `perpetual` → `infinite` (a workload that never ends).
- `VM_MIGRATE` → `VM_MIGRATE_DONE` (this event now marks completion of
  the memory copy, paired with the new `VM_MIGRATE_START`).

### Migration notes

- Replace `from src...` imports with `from cloudy...`.
- Remove GPU and container code; model those resources in a custom
  policy if a study needs them.
- Pass policies as instances (for example, `scheduler=TimeShared()`).
- Update names: `VM_MIGRATE` → `VM_MIGRATE_DONE`, `perpetual` →
  `infinite`.

## [0.4.1] — 2026-04-28

### Fixed

- **Thread/core parallelism bound.** An app now spreads over
  `min(cores, threads)`, not every core. *Why:* a process with fewer
  threads than cores must not occupy extra cores.
- **Time-share slice.** Removed an incorrect `* duration` factor from
  the per-app cycle share in `OsTimeShared`. *Why:* each app received
  the wrong number of cycles per tick.
- **Stop-event tag.** The `*.stop` event is now tagged with the class
  of the app that actually stopped, not the loop variable. *Why:*
  subscribers received the wrong topic.
- **Model identity comparison.** `Base`, `App`, and `Container` now use
  identity equality (`eq=False`). *Why:* the generated structural
  `__eq__` made distinct objects compare equal, which broke
  identity-based bookkeeping (dict keys, set membership).
- **`__contain__` → `__contains__`** on `Vmm`. *Why:* the `in` operator
  only calls `__contains__`, so the misspelled method was never used.
- **GPU guard now raises.** An `AssertionError` was constructed but not
  raised. *Why:* the "GPU requirement must not exceed 1.0" check had no
  effect.

## [0.4.0] — 2024-07-28

Baseline for this changelog.

[0.5.0]: https://github.com/ahmad-siavashi/cloudy/compare/0.4.1...0.5.0
[0.4.1]: https://github.com/ahmad-siavashi/cloudy/compare/0.4.0...0.4.1
[0.4.0]: https://github.com/ahmad-siavashi/cloudy/releases/tag/0.4.0
