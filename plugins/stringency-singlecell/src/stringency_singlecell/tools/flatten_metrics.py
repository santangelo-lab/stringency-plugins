#!/usr/bin/env python3
"""Negative-control generator for flag_outlier_punches: flatten every numeric attribute of a
per-punch metrics table to its within-tissue median plus a small deterministic jitter, so that no
punch can lie beyond a mean ± 3 SD band. Shuffling punch ids would keep the same extreme values
in the table (an outlier stays an outlier under another name), so the null here removes the
signal instead of relabelling it. Categorical and identity columns are kept.

Job JSON on stdin: {"inputs": {"input": path}, "params": {"seed": int, "jitter": 0.02},
                    "outputs": {"object": path}}
"""

from __future__ import annotations

import csv
import json
import random
import statistics
import sys

KEEP = {
    "punch_id",
    "slide",
    "region",
    "organ",
    "animal",
    "timepoint_h",
    "animal_in_timepoint",
    "punch",
    "tissue",
    "segmentation",
    "histology_include",
    "histology_issue",
    "histology_reason",
    "region_id",
    "join_verified",
}


def main() -> int:
    job = json.load(sys.stdin)
    src, dst = job["inputs"]["input"], job["outputs"]["object"]
    params = job.get("params", {})
    seed, jitter = int(params.get("seed", 0)), float(params.get("jitter", 0.02))
    with open(src, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("empty metrics table")
    rng = random.Random(seed)
    cols = list(rows[0].keys())
    numeric = []
    for c in cols:
        if c in KEEP:
            continue
        try:
            [float(r[c]) for r in rows if r[c] not in ("", "NA", "nan")]
            numeric.append(c)
        except ValueError:
            continue
    by_tissue: dict[str, list[dict]] = {}
    for r in rows:
        by_tissue.setdefault(r.get("tissue") or r.get("organ") or "all", []).append(r)
    flattened = 0
    for c in numeric:
        for group in by_tissue.values():
            vals = [float(r[c]) for r in group if r[c] not in ("", "NA", "nan")]
            if not vals:
                continue
            med = statistics.median(vals)
            for r in group:
                if r[c] in ("", "NA", "nan"):
                    continue
                v = (
                    med * (1.0 + rng.uniform(-jitter, jitter))
                    if med != 0
                    else rng.uniform(-jitter, jitter)
                )
                r[c] = f"{v:.6g}"
                flattened += 1
    with open(dst, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(
        f"flattened {len(numeric)} numeric columns ({flattened} cells) to within-tissue medians ± {jitter:.0%} jitter, seed {seed}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
