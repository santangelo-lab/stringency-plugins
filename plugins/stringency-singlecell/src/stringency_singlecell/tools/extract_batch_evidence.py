#!/usr/bin/env python3
"""State extractor for object type `batch_evidence` (sc.batch_evidence@1): the directory the
method's `cluster-umap` module writes for the batch-route judgment (`manifest.json`,
`batch_overview.csv` with one row for the dataset, `batch_assessment.csv` per cluster,
`cluster_summary.csv`, `slide_by_timepoint.csv`, the composition tables). stdlib only.
Envelope: n_obs = cells (manifest), n_var = 0 (no features), fields.summary_columns = the
batch_overview columns (not `columns`: `init.column_missing` checks design columns against any
object reporting that key), fields.uns_flags.batch_assessment = the manifest's summary (so a
predicate that reads `uns_flags.batch_assessment` works on this object as on a seurat_object),
domain = organ, cluster count, the rule's verdict, the overall kNN excess, files missing.
Refuses a directory without `manifest.json` or `batch_overview.csv`.

Usage: extract_batch_evidence.py <dir> <design.json>
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

EXPECTED = [
    "manifest.json",
    "batch_overview.csv",
    "batch_assessment.csv",
    "cluster_summary.csv",
    "slide_by_timepoint.csv",
    "composition_by_slide.csv",
    "composition_by_timepoint.csv",
    "composition_by_punch.csv",
    "composition_by_animal.csv",
]


def _num(x: object) -> float | None:
    try:
        return float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: extract_batch_evidence.py <dir> <design.json>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 1
    present = [n for n in EXPECTED if (root / n).exists()]
    missing = [n for n in ("manifest.json", "batch_overview.csv") if n not in present]
    if missing:
        print(f"batch_evidence at {root} lacks {', '.join(missing)}", file=sys.stderr)
        return 1
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("batch_evidence") != 1:
        print(
            f"manifest.json is not a batch_evidence contract (version 1): {root}", file=sys.stderr
        )
        return 1
    with open(root / "batch_overview.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    cols = list(rows[0].keys()) if rows else []
    overview = rows[0] if rows else {}
    summary = manifest.get("summary") or {}
    if not isinstance(summary, dict):
        summary = {}
    n_assess = 0
    if (root / "batch_assessment.csv").exists():
        with open(root / "batch_assessment.csv", newline="") as f:
            n_assess = sum(1 for _ in csv.DictReader(f))
    rule_suspected = str(overview.get("rule_suspected", summary.get("suspected", ""))).lower() in (
        "true",
        "1",
    )
    out = {
        "extractor": "sc.batch_evidence@1",
        "type": "batch_evidence",
        "n_obs": manifest.get("n_cells"),
        "n_var": 0,
        "fields": {
            "summary_columns": cols,
            "uns_flags": {"batch_assessment": summary},
        },
        "counts_per_group": {},
        "domain": {
            "organ": manifest.get("organ"),
            "dataset": overview.get("dataset"),
            "batch_key": manifest.get("batch_key"),
            "timepoint_column": manifest.get("timepoint_column"),
            "clustering_column": manifest.get("clustering_column"),
            "resolution": manifest.get("resolution"),
            "n_clusters": manifest.get("n_clusters"),
            "n_clusters_assessed": n_assess,
            "rule": manifest.get("rule"),
            "rule_suspected": rule_suspected,
            "knn_same_batch_excess_overall": _num(
                overview.get(
                    "knn_same_batch_excess_overall", summary.get("knn_same_batch_excess_overall")
                )
            ),
            "n_rows_overview": len(rows),
            "files_present": present,
            "files_missing": [n for n in EXPECTED if n not in present],
        },
    }
    json.dump(out, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
