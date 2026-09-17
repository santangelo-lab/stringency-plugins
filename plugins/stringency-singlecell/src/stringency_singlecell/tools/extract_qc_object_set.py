#!/usr/bin/env python3
"""State extractor for object type `qc_object_set` (`sc.qc_object_set@1`). Stdlib only.

usage: extract_qc_object_set.py <set_dir> <design.json>

The output of `qc-cells`: a directory with one filtered object per punch and `qc_summary.json`
written by the module (contract in spec/object-types.md):

  {"qc_summary": 1,
   "punches": [{"punch_id": str, "tissue": str, "included": bool, "n_before": int,
                "n_after": int, "fail_fraction": float, "thresholds": {...}, "object": str}],
   "join_verification": {"method": "keyed_reindex_on_cell_id", "verified": bool,
                         "n_cells": int, "n_cells_checked": int,
                         "columns_checked": [str], "detail": str}}

`domain.join_verification` is what `sc.area_join_unverified` reads (ROSC defect A1): the module
must have joined `cells.parquet` to the matrix by key and re-checked every value by id.
`counts_per_group` uses `punch_metadata.csv` beside the summary when present.
"""

from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

from _xenium_common import emit

JOIN_METHODS_ACCEPTED = ("keyed_reindex_on_cell_id",)


def main(argv: list[str]) -> int:
    root = Path(argv[1])
    with open(argv[2]) as f:
        design = json.load(f)
    summary_path = root / "qc_summary.json"
    if not summary_path.exists():
        sys.stderr.write(f"{summary_path} missing; qc-cells must write it\n")
        return 2
    qs = json.loads(summary_path.read_text())
    punches = list(qs.get("punches", []))
    jv = dict(qs.get("join_verification", {}))
    n_cells = jv.get("n_cells")
    verified = (
        jv.get("verified") is True
        and jv.get("method") in JOIN_METHODS_ACCEPTED
        and isinstance(n_cells, int)
        and jv.get("n_cells_checked") == n_cells
        and n_cells == sum(int(p.get("n_before", 0)) for p in punches)
    )
    jv["verified_by_extractor"] = bool(verified)
    meta_rows = []
    meta = root / "punch_metadata.csv"
    if meta.exists():
        with open(meta, newline="") as f:
            meta_rows = list(csv.DictReader(f))
    by_id = {r.get("punch_id"): r for r in meta_rows}
    counts = {}
    if meta_rows:
        units = design.get("units", {})
        for fname, fac in design.get("factors", {}).items():
            col = fac["column"]
            counts[fname] = {}
            for lvl in fac.get("levels", []):
                sel = [p for p in punches if by_id.get(p["punch_id"], {}).get(col) == str(lvl)]
                per_unit = {"cell": sum(int(p.get("n_after", 0)) for p in sel)}
                for uname, ucol in units.items():
                    if uname == "observation":
                        continue
                    if ucol == "punch_id":
                        per_unit[ucol] = len(sel)
                    else:
                        per_unit[ucol] = len({by_id[p["punch_id"]].get(ucol) for p in sel})
                counts[fname][str(lvl)] = per_unit
    out = {
        "extractor": "sc.qc_object_set@1",
        "type": "qc_object_set",
        "n_obs": sum(int(p.get("n_after", 0)) for p in punches),
        "fields": {"punch_ids": [p.get("punch_id") for p in punches]},
        "counts_per_group": counts,
        "domain": {
            "n_punches": len(punches),
            "punches": [
                {
                    "punch_id": p.get("punch_id"),
                    "tissue": p.get("tissue"),
                    "included": p.get("included", True),
                    "n_before": p.get("n_before"),
                    "n_after": p.get("n_after"),
                    "n_cells": p.get("n_after"),
                    "fail_fraction": p.get("fail_fraction"),
                    "thresholds": p.get("thresholds", {}),
                }
                for p in punches
            ],
            "excluded_punches": [p.get("punch_id") for p in punches if p.get("included") is False],
            "join_verification": jv,
        },
    }
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
