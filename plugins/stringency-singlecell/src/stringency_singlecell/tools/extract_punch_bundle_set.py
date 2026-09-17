#!/usr/bin/env python3
"""State extractor for object type `punch_bundle_set` (`sc.punch_bundle_set@1`).

usage: extract_punch_bundle_set.py <set_dir> <design.json>

The output of `split-punches`: a directory whose immediate subdirectories are one Xenium bundle
per punch (each with `cells.parquet` and `cell_feature_matrix.h5`), optionally with
`region_metrics.csv` and `punch_cell_summary.csv` beside them. `domain.punches` lists every
punch with its cell count and order check so `sc.low_cell_count` is decidable from state.
`counts_per_group` counts punches and cells per design factor level when the set directory
holds the layout-derived `punch_metadata.csv` (punch_id plus the design columns); otherwise {}.
"""

from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

from _xenium_common import bundle_summary, emit, is_bundle


def counts_per_group(meta_rows, design, punches):  # type: ignore[no-untyped-def]
    units = design.get("units", {})
    by_id = {r.get("punch_id", ""): r for r in meta_rows}
    out = {}
    for fname, fac in design.get("factors", {}).items():
        col = fac["column"]
        out[fname] = {}
        for lvl in fac.get("levels", []):
            ids = [
                p["punch_id"] for p in punches if by_id.get(p["punch_id"], {}).get(col) == str(lvl)
            ]
            per_unit = {"cell": sum(p["n_cells"] or 0 for p in punches if p["punch_id"] in ids)}
            for uname, ucol in units.items():
                if uname == "observation":
                    continue
                if ucol == "punch_id":
                    per_unit[ucol] = len(ids)
                else:
                    per_unit[ucol] = len({by_id[i].get(ucol) for i in ids if i in by_id})
            out[fname][str(lvl)] = per_unit
    return out


def main(argv: list[str]) -> int:
    root = Path(argv[1])
    with open(argv[2]) as f:
        design = json.load(f)
    subs = sorted(p for p in root.iterdir() if p.is_dir() and is_bundle(p))
    punches = []
    for p in subs:
        s = bundle_summary(p)
        punches.append(
            {
                "punch_id": p.name.removeprefix("punch_"),
                "dir": p.name,
                "n_cells": s["n_cells"],
                "h5_order_matches_cells": s["h5_order_matches_cells"],
                "h5_set_matches_cells": s["h5_set_matches_cells"],
                "median_transcript_counts": s["median_transcript_counts"],
                "median_cell_area_um2": s["median_cell_area_um2"],
            }
        )
    meta_rows = []
    meta = root / "punch_metadata.csv"
    if meta.exists():
        with open(meta, newline="") as f:
            meta_rows = list(csv.DictReader(f))
    out = {
        "extractor": "sc.punch_bundle_set@1",
        "type": "punch_bundle_set",
        "n_obs": sum(p["n_cells"] or 0 for p in punches),
        "fields": {"punch_ids": [p["punch_id"] for p in punches]},
        "counts_per_group": counts_per_group(meta_rows, design, punches) if meta_rows else {},
        "domain": {
            "n_punches": len(punches),
            "punches": punches,
            "region_metrics_present": (root / "region_metrics.csv").exists(),
            "all_h5_orders_match_cells": all(p["h5_order_matches_cells"] for p in punches)
            if punches
            else False,
        },
    }
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
