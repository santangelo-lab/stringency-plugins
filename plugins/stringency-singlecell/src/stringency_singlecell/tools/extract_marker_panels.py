#!/usr/bin/env python3
"""State extractor for object type `marker_panels` (plugin 0.8.3): a person's declaration of
the lineages expected in a tissue and the marker genes that define each, as a CSV with the
columns `lineage` and `gene`, one row per gene. A declaration is an input, hashed and covered by
the confirm hold, never a parameter the engine ranges (engine backlog L97). Stdlib only.

usage: extract_marker_panels.py <panels.csv> <design.json>
Prints the envelope: extractor, type, n_obs (rows), n_var (distinct genes), fields (the
columns), counts_per_group (empty), and domain: `lineages` (in file order), `n_lineages`,
`genes_per_lineage` (lineage -> count), `panels` (lineage -> genes), `missing_required_columns`.
"""

from __future__ import annotations

import csv
import json
import sys

REQUIRED = ("lineage", "gene")


def main(argv: list[str]) -> int:
    with open(argv[1], newline="") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    missing = [c for c in REQUIRED if c not in columns]
    panels: dict[str, list[str]] = {}
    if not missing:
        for r in rows:
            lineage, gene = str(r.get("lineage", "")).strip(), str(r.get("gene", "")).strip()
            if lineage and gene and gene not in panels.setdefault(lineage, []):
                panels[lineage].append(gene)
    env = {
        "extractor": "sc.marker_panels@1",
        "type": "marker_panels",
        "n_obs": len(rows),
        "n_var": len({g for gs in panels.values() for g in gs}),
        "fields": {"columns": columns},
        "counts_per_group": {},
        "domain": {
            "missing_required_columns": missing,
            "lineages": list(panels),
            "n_lineages": len(panels),
            "genes_per_lineage": {k: len(v) for k, v in panels.items()},
            "panels": panels,
        },
    }
    print(json.dumps(env, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
