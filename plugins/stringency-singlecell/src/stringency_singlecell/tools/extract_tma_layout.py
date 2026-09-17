#!/usr/bin/env python3
"""State extractor for object type `tma_layout` (`sc.tma_layout@1`). Stdlib only.

usage: extract_tma_layout.py <tma_layout.csv> <design.json>

The transcribed TMA map: one row per punch with `punch_id, slide, region, animal, timepoint_h,
organ, punch` and whatever else the owner recorded. This is the table the design's columns
refer to, so `fields.columns` is set and `init.column_missing` checks the design against it.
`counts_per_group` counts distinct values of every non-observation design unit per factor level
(animals and punches per time point), which is what `obj.feasibility` reads.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _xenium_common import emit, layout_region_key, read_layout

REQUIRED = ("punch_id", "slide", "region", "animal", "timepoint_h", "organ")


def main(argv: list[str]) -> int:
    columns, rows = read_layout(argv[1])
    with open(argv[2]) as f:
        design = json.load(f)
    units = design.get("units", {})
    counts = {}
    for fname, fac in design.get("factors", {}).items():
        col = fac["column"]
        counts[fname] = {}
        for lvl in fac.get("levels", []):
            sel = [r for r in rows if r.get(col) == str(lvl)]
            per_unit = {}
            for uname, ucol in units.items():
                if uname == "observation":
                    continue
                per_unit[ucol] = len({r.get(ucol) for r in sel if ucol in r})
            counts[fname][str(lvl)] = per_unit
    regions: dict[str, list[str]] = {}
    for r in rows:
        regions.setdefault(layout_region_key(r.get("slide", ""), r.get("region", "")), []).append(
            r.get("punch_id", "")
        )
    ids = [r.get("punch_id", "") for r in rows]
    out = {
        "extractor": "sc.tma_layout@1",
        "type": "tma_layout",
        "n_obs": len(rows),
        "fields": {"columns": columns},
        "counts_per_group": counts,
        "domain": {
            "missing_required_columns": [c for c in REQUIRED if c not in columns],
            "punches": [
                {
                    k: r.get(k)
                    for k in (
                        "punch_id",
                        "slide",
                        "region",
                        "animal",
                        "timepoint_h",
                        "organ",
                        "punch",
                    )
                }
                for r in rows
            ],
            "regions": regions,
            "n_slides": len({r.get("slide") for r in rows}),
            "n_animals": len({r.get("animal") for r in rows}),
            "duplicate_punch_ids": sorted({i for i in ids if ids.count(i) > 1}),
        },
    }
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
