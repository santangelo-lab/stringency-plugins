#!/usr/bin/env python3
"""Generator for the negative control of annotate-clusters: copy a `cluster_evidence` directory
with the gene symbols permuted across every marker and expression table, so no cluster's markers
cohere and the right answer is `unknown`. Source of the plugin tool `shuffle_markers` (the engine
resolves a control's `generator.tool` through the plugin's tool registry and runs it with the job
below). Registered as the plugin tool `shuffle_markers` (0.3.1); the method keeps a documented copy beside
the control `negative-shuffled-markers` in stringency-xenium-method `modules/annotate-clusters/controls/`.

Job JSON on stdin: {"inputs": {"input": <fixture dir>}, "params": {"seed": int},
                    "outputs": {"object": <output dir>}}. Stdlib only.
"""

from __future__ import annotations

import csv
import json
import random
import shutil
import sys
from pathlib import Path


def permute_column(path: Path, column: str, rng: random.Random) -> None:
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
        cols = list(rows[0].keys()) if rows else []
    vals = [r[column] for r in rows]
    perm = vals[:]
    rng.shuffle(perm)
    # a derangement is not required; a symbol landing on itself is one gene in thousands
    for r, v in zip(rows, perm, strict=True):
        r[column] = v
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    job = json.load(sys.stdin)
    src = Path(job["inputs"]["input"])
    out = Path(job["outputs"]["object"])
    seed = int((job.get("params") or {}).get("seed", 1))
    rng = random.Random(seed)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out)
    for name in (
        "markers.csv",
        "markers_top.csv",
        "cluster_avg_expression.csv",
        "cluster_pct_expressing.csv",
    ):
        p = out / name
        if p.exists():
            permute_column(p, "gene", rng)
    # top_markers in the summary must agree with the shuffled markers_top
    with open(out / "markers_top.csv", newline="") as f:
        top = list(csv.DictReader(f))
    first = {}
    for r in sorted(top, key=lambda r: (r["cluster"], int(r["rank"]))):
        first.setdefault(r["cluster"], []).append(r["gene"])
    with open(out / "cluster_summary.csv", newline="") as f:
        summ = list(csv.DictReader(f))
        cols = list(summ[0].keys())
    for r in summ:
        r["top_markers"] = ";".join(first.get(r["cluster"], [])[:8])
    with open(out / "cluster_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(summ)
    m = json.loads((out / "manifest.json").read_text())
    m["source"] = (
        f"{m.get('source', '')}; gene symbols permuted by shuffle_markers seed {seed} (negative control)"
    )
    (out / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")
    print(f"shuffled gene symbols in {out} with seed {seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
