#!/usr/bin/env python3
"""Generator for the spatial negative controls of the open tools (0.9.0): copy a cell table (or a
directory holding one) with the `(x, y)` pairs permuted among the cells of each unit, so no
spatial structure survives while every cell keeps its labels. A domain call, an enrichment or a
distance test that still finds structure on the copy is over-answering.

The unit is the `by` column (default `punch_id`): coordinates move only between cells of one
unit, so each punch keeps its footprint and its multiset of positions, and the label columns are
untouched. A pair moves as a pair. Registered as the plugin tool `shuffle_coordinates`; the
engine resolves a control's `generator.tool` through the plugin's tool registry and runs it with
the job below.

Job JSON on stdin: {"inputs": {"input": <csv/tsv file, an h5ad (0.10.1: obsm["spatial"] and the
                                        obs x, y columns), or a dir>},
                    "params": {"by": "punch_id", "seed": 1, "x": "x", "y": "y",
                               "file": "cells.csv"},   # `file` only when the input is a dir
                    "outputs": {"object": <file or dir>}}. Stdlib only.
"""

from __future__ import annotations

import csv
import json
import random
import shutil
import sys
from pathlib import Path
from typing import Any


def permute_coordinates(path: Path, x: str, y: str, by: str, rng: random.Random) -> int:
    delim = "\t" if path.suffix.lower() in (".tsv", ".tab") else ","
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f, delimiter=delim))
        cols = list(rows[0].keys()) if rows else []
    for c in (x, y, by):
        if c not in cols:
            raise SystemExit(f"{path}: no column {c!r} (columns: {', '.join(cols)})")
    members: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        members.setdefault(r[by], []).append(i)
    for idx in members.values():
        pairs = [(rows[i][x], rows[i][y]) for i in idx]
        rng.shuffle(pairs)
        for i, (xv, yv) in zip(idx, pairs, strict=True):
            rows[i][x], rows[i][y] = xv, yv
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=delim)
        w.writeheader()
        w.writerows(rows)
    return len(members)


def _obs_column(f: Any, name: str) -> list[str]:
    """An obs column of an h5ad as strings: a categorical group (codes, categories) or an array."""
    node = f["obs"][name]
    if hasattr(node, "keys"):  # a categorical: codes into categories
        cats = [c.decode() if isinstance(c, bytes) else str(c) for c in node["categories"][()]]
        return [cats[int(i)] for i in node["codes"][()]]
    vals = node[()]
    return [v.decode() if isinstance(v, bytes) else str(v) for v in vals]


def permute_h5ad(path: Path, x: str, y: str, by: str, rng: random.Random) -> int:
    """The same permutation on an AnnData file (0.10.1): the rows of obsm["spatial"] are
    permuted among the cells of each unit of the obs column `by`, and the obs columns `x` and
    `y` with them when present, so the file's coordinates and its cell table agree. Needs h5py
    (the plugin's extractor extra); the file is rewritten in place."""
    import h5py

    with h5py.File(path, "r+") as f:
        units = _obs_column(f, by)
        members: dict[str, list[int]] = {}
        for i, u in enumerate(units):
            members.setdefault(u, []).append(i)
        spatial = f["obsm"]["spatial"][()]
        has_xy = x in f["obs"] and y in f["obs"] and not hasattr(f["obs"][x], "keys")
        xs = f["obs"][x][()] if has_xy else None
        ys = f["obs"][y][()] if has_xy else None
        for idx in members.values():
            order = list(idx)
            rng.shuffle(order)
            spatial[idx] = spatial[order]
            if has_xy:
                xs[idx] = xs[order]
                ys[idx] = ys[order]
        f["obsm"]["spatial"][...] = spatial
        if has_xy:
            f["obs"][x][...] = xs
            f["obs"][y][...] = ys
    return len(members)


def main() -> int:
    job = json.load(sys.stdin)
    src = Path(job["inputs"]["input"])
    out = Path(job["outputs"]["object"])
    params = job.get("params") or {}
    by = str(params.get("by", "punch_id"))
    x, y = str(params.get("x", "x")), str(params.get("y", "y"))
    seed = int(params.get("seed", 1))
    rng = random.Random(seed)
    if src.is_dir():
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(src, out)
        target = out / str(params.get("file", "cells.csv"))
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out)
        target = out
    if target.suffix.lower() == ".h5ad":
        n = permute_h5ad(target, x, y, by, rng)
    else:
        n = permute_coordinates(target, x, y, by, rng)
    print(f"permuted ({x}, {y}) within {n} units of {by} in {target} with seed {seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
