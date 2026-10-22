#!/usr/bin/env python3
"""State extractor for object type `analysis_summary` (plugin 0.8.0): a JSON object of named
facts a module writes about what it computed (a median UMI count, a PCA sentinel, cells
retained), carried into the state envelope's `domain` block so predicates can read them without
touching the data. Runs anywhere; needs nothing but the standard library.

usage: extract_analysis_summary.py <summary.json> <design.json>
Prints the envelope: extractor, type, n_obs (the `n_cells` fact when present, else 0), n_var
(`n_genes`, else 0), fields (the fact names with their JSON types), counts_per_group (empty),
and domain (the facts, numbers and strings and booleans only; nested values are dropped).
"""

from __future__ import annotations

import json
import sys


def main(argv: list[str]) -> int:
    path = argv[1]
    with open(path) as f:
        doc = json.load(f)
    if not isinstance(doc, dict):
        print("analysis_summary must be a JSON object", file=sys.stderr)
        return 2
    domain = {k: v for k, v in doc.items() if isinstance(v, (int, float, str, bool))}
    fields = {k: type(v).__name__ for k, v in doc.items()}
    env = {
        "extractor": "sc.analysis_summary@1",
        "type": "analysis_summary",
        "n_obs": int(doc.get("n_cells", 0) or 0),
        "n_var": int(doc.get("n_genes", 0) or 0),
        "fields": fields,
        "counts_per_group": {},
        "domain": domain,
    }
    print(json.dumps(env, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
