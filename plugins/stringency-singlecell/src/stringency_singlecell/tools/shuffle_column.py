#!/usr/bin/env python3
"""Generator for the negative controls of the open tools (0.6.0): copy a table (or a directory
holding one) with one design column permuted across its units, so the factor no longer tracks
the cells and a test that still finds differences is over-answering.

The unit is the `by` column: every row of one unit keeps one value, and the values are permuted
between units (not between rows, which would leave the per-unit mix intact). Registered as the
plugin tool `shuffle_column`; the engine resolves a control's `generator.tool` through the
plugin's tool registry and runs it with the job below.

Job JSON on stdin: {"inputs": {"input": <csv/tsv file or dir>},
                    "params": {"column": "timepoint_h", "by": "punch_id", "seed": 1,
                               "file": "samples.csv"},   # `file` only when the input is a dir
                    "outputs": {"object": <file or dir>}}. Stdlib only.
"""

from __future__ import annotations

import csv
import json
import random
import shutil
import sys
from pathlib import Path


def permute_by_unit(path: Path, column: str, by: str, rng: random.Random) -> int:
    delim = "\t" if path.suffix.lower() in (".tsv", ".tab") else ","
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f, delimiter=delim))
        cols = list(rows[0].keys()) if rows else []
    for c in (column, by):
        if c not in cols:
            raise SystemExit(f"{path}: no column {c!r} (columns: {', '.join(cols)})")
    units = list(dict.fromkeys(r[by] for r in rows))
    value_of = {u: next(r[column] for r in rows if r[by] == u) for u in units}
    perm = [value_of[u] for u in units]
    rng.shuffle(perm)
    new = dict(zip(units, perm, strict=True))
    for r in rows:
        r[column] = new[r[by]]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=delim)
        w.writeheader()
        w.writerows(rows)
    return len(units)


def main() -> int:
    job = json.load(sys.stdin)
    src = Path(job["inputs"]["input"])
    out = Path(job["outputs"]["object"])
    params = job.get("params") or {}
    column = str(params.get("column", "timepoint_h"))
    by = str(params.get("by", "punch_id"))
    seed = int(params.get("seed", 1))
    rng = random.Random(seed)
    if src.is_dir():
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(src, out)
        target = out / str(params.get("file", "samples.csv"))
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out)
        target = out
    n = permute_by_unit(target, column, by, rng)
    print(f"permuted {column} across {n} units of {by} in {target} with seed {seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
