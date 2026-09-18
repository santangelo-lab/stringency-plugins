#!/usr/bin/env python3
"""State extractor for object type `qc_metrics_table` (sc.qc_metrics_table@1): the per-punch
cross-region QC table written by qc-cells (`qc_metrics.csv`) or concatenated by qc-report-all
(`qc_metrics_all.csv`). stdlib only. Envelope: n_obs = punches, fields.columns, domain with the
tissues, regions, counts of included/excluded/flagged punches, and whether the seven core
attributes the outlier judgment reads are present.

Usage: extract_qc_metrics_table.py <path.csv> <design.json>
"""

from __future__ import annotations

import csv
import json
import sys

CORE = [
    "num_cells",
    "cells_per_mm2",
    "median_transcripts_per_cell",
    "median_genes_per_cell",
    "fraction_transcripts_decoded_q20",
    "percent_transcripts_in_cells",
    "fail_fraction",
]


def truthy(v: object) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes", "y")


def main() -> int:
    path = sys.argv[1]
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    cols = list(rows[0].keys()) if rows else []
    tissues = sorted({(r.get("tissue") or r.get("organ") or "").lower() for r in rows} - {""})
    regions = sorted(
        {r.get("region_id") or f"{r.get('slide', '')}_{r.get('region', '')}" for r in rows}
    )
    included = [r for r in rows if truthy(r.get("histology_include", "true"))]
    out = {
        "extractor": "sc.qc_metrics_table@1",
        "n_obs": len(rows),
        "fields": {"columns": cols, "punch_ids": [r.get("punch_id", "") for r in rows]},
        "domain": {
            "n_punches": len(rows),
            "n_included": len(included),
            "n_excluded": len(rows) - len(included),
            "n_histology_issue": sum(1 for r in rows if truthy(r.get("histology_issue", "false"))),
            "tissues": tissues,
            "regions": regions,
            "punches_per_tissue": {
                t: sum(1 for r in rows if (r.get("tissue") or r.get("organ") or "").lower() == t)
                for t in tissues
            },
            "core_attributes_present": [c for c in CORE if c in cols],
            "core_attributes_missing": [c for c in CORE if c not in cols],
            "duplicate_punch_ids": sorted(
                {
                    p
                    for p in (r.get("punch_id") for r in rows)
                    if [x.get("punch_id") for x in rows].count(p) > 1
                }
            ),
        },
    }
    json.dump(out, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
