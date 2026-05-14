"""Compare policy choices on the same workload.

Researchers building a paper's results table often want to ask: "how
does my new policy compare with three baselines on this workload?".
:func:`compare` runs the same workload once per policy choice and
returns the report metrics in a uniform shape.

The result is a list of dicts. Convert it to a pandas ``DataFrame``
yourself if you need one; Cloudy uses only the standard library::

    rows = compare(build, placement_class=[A, B, C])
    import pandas as pd
    df = pd.DataFrame(rows)
"""

from __future__ import annotations

import csv
import multiprocessing
from typing import Any, Callable

from cloudy.simulation import Simulation


def compare(builder: Callable[..., Any], *, seed: int | list[int] | None = None, processes: int = 1, to_csv: str | None = None, **parameter_lists: list[Any]) -> list[dict[str, Any]]:
    """Run ``builder`` once per parameter row and collect reports.

    Parameters
    ----------
    builder : Callable
        Called as ``builder(sim, **params)`` with a fresh
        :class:`Simulation` and one parameter row. The builder must
        populate ``sim.requests`` and ``sim.datacenter`` before
        returning.
    seed : int, list[int], or None
        Reproducibility seed forwarded to each row's
        :class:`Simulation`. A single ``int`` seeds every row
        identically; a ``list[int]`` of length ``n`` seeds each row
        from its corresponding entry. ``None`` (default) leaves the
        global RNG state alone.
    processes : int
        Number of worker processes for parallel sweeps. Default 1
        (serial). Above 1 uses stdlib :mod:`multiprocessing`. The
        builder must be importable in workers — closures over local
        state won't pickle.
    to_csv : str, optional
        Path to write the results dict-of-rows as CSV. The file is
        written via stdlib :mod:`csv`; columns are the union of all
        keys across all rows.
    **parameter_lists : list
        Each kwarg is a list of values to sweep. All lists must have
        the same length; ``compare`` runs one simulation per index —
        this is a *parallel* sweep, not a Cartesian product. For a
        Cartesian sweep, generate the rows yourself with
        :func:`itertools.product` and call :func:`compare` once per row.

    Returns
    -------
    list of dict
        One row per simulation. Each row is the parameter values that
        produced it (classes are serialised to ``cls.__name__`` so the
        result is ready for a CSV / DataFrame) merged with all metric
        keys from :meth:`Simulation.report`.

    Raises
    ------
    ValueError
        If no parameter list is given, or if the lists have different
        lengths.
    """
    if not parameter_lists:
        raise ValueError('compare() needs at least one parameter list.')

    lengths = {k: len(v) for k, v in parameter_lists.items()}
    n = next(iter(lengths.values()))
    if any(length != n for length in lengths.values()):
        raise ValueError(f'All parameter lists must have the same length; got {lengths}.')

    seeds: list[int | None]
    if seed is None:
        seeds = [None] * n
    elif isinstance(seed, int):
        seeds = [seed] * n
    else:
        if len(seed) != n:
            raise ValueError(f'seed list has length {len(seed)}; expected {n}.')
        seeds = list(seed)

    rows: list[tuple[int, dict[str, Any]]] = [(i, {k: values[i] for k, values in parameter_lists.items()}) for i in range(n)]

    if processes <= 1:
        results: list[dict[str, Any]] = [_run_one(builder, i, params, seeds[i]) for i, params in rows]
    else:
        with multiprocessing.Pool(processes=processes) as pool:
            args = [(builder, i, params, seeds[i]) for i, params in rows]
            results = pool.starmap(_run_one, args)

    if to_csv is not None:
        _write_csv(to_csv, results)

    return results


def _run_one(builder: Callable[..., Any], i: int, params: dict[str, Any], seed: int | None) -> dict[str, Any]:
    """Run a single ``compare()`` row. Module-level so it pickles for
    multiprocessing workers."""
    sim = Simulation(name=f'compare-{i}', log=False, seed=seed)
    builder(sim, **params)
    sim.run()
    report = sim.report(to_stdout=False)
    row: dict[str, Any] = {k: _serialize_param(v) for k, v in params.items()}
    row.update(report)
    return row


def _serialize_param(value: Any) -> Any:
    """Make ``value`` table-friendly. Classes become their ``__name__``."""
    if isinstance(value, type):
        return value.__name__
    return value


def _write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    """Write ``rows`` to ``path`` via stdlib :mod:`csv`.

    The column set is the union of all keys across all rows; missing
    fields are written as empty strings.
    """
    if not rows:
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
