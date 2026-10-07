#!/usr/bin/env python3
"""State extractor for object type `cluster_evidence` (sc.cluster_evidence@1): the directory the
method's `find-markers` module writes for the annotation judgment (`manifest.json`,
`cluster_summary.csv`, the composition tables, `markers.csv`, `markers_top.csv`,
`cluster_avg_expression.csv`, `cluster_pct_expressing.csv`, `batch_assessment.csv`). stdlib only.
Envelope: n_obs = cells (manifest), n_var = panel genes (manifest), fields.columns = the
cluster_summary columns, domain = organ, clustering column and resolution, cluster ids, files
present. Refuses a directory without `manifest.json` or `cluster_summary.csv`.

Usage: extract_cluster_evidence.py <dir> <design.json>
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

EXPECTED = [
    "manifest.json",
    "cluster_summary.csv",
    "composition_by_punch.csv",
    "composition_by_animal.csv",
    "composition_by_timepoint.csv",
    "composition_by_slide.csv",
    "markers.csv",
    "markers_top.csv",
    "cluster_avg_expression.csv",
    "cluster_pct_expressing.csv",
    "batch_assessment.csv",
]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: extract_cluster_evidence.py <dir> <design.json>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 1
    present = [n for n in EXPECTED if (root / n).exists()]
    missing = [n for n in ("manifest.json", "cluster_summary.csv") if n not in present]
    if missing:
        print(f"cluster_evidence at {root} lacks {', '.join(missing)}", file=sys.stderr)
        return 1
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("cluster_evidence") != 1:
        print(
            f"manifest.json is not a cluster_evidence contract (version 1): {root}", file=sys.stderr
        )
        return 1
    with open(root / "cluster_summary.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    cols = list(rows[0].keys()) if rows else []
    cluster_ids = [r.get("cluster", "") for r in rows]
    n_cells_rows = 0
    for r in rows:
        try:
            n_cells_rows += int(float(r.get("n_cells") or 0))
        except ValueError:
            pass
    panel = manifest.get("panel") or {}
    out = {
        "extractor": "sc.cluster_evidence@1",
        "type": "cluster_evidence",
        "n_obs": manifest.get("n_cells"),
        "n_var": panel.get("n_genes"),
        "fields": {"columns": cols, "cluster_ids": cluster_ids},
        "counts_per_group": {},
        "domain": {
            "organ": manifest.get("organ"),
            "species": manifest.get("species"),
            "clustering_column": manifest.get("clustering_column"),
            "resolution": manifest.get("resolution"),
            "n_clusters": len(rows),
            "n_clusters_manifest": manifest.get("n_clusters"),
            "cluster_ids": cluster_ids,
            "n_cells_in_summary": n_cells_rows,
            "punches": manifest.get("punches", []),
            "timepoint_levels": manifest.get("timepoint_levels", []),
            "batch_key": manifest.get("batch_key"),
            "normalisation": manifest.get("normalisation"),
            "files_present": present,
            "files_missing": [n for n in EXPECTED if n not in present],
        },
    }
    json.dump(out, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
