#!/usr/bin/env python3
"""State extractor for object type `xenium_bundle` (`sc.xenium_bundle@1`, design 4.2).

usage: extract_xenium_bundle.py <bundle_dir> <design.json>

A Xenium Onboard Analysis region bundle (or a Proseg-resegmented one: only `cells.parquet` and
`cell_feature_matrix.h5` are required; `metrics_summary.csv`, `experiment.xenium`, and
`gene_panel.json` enrich the summary when present). Needs pyarrow and h5py in the module
environment. `fields` carries `cells_columns`, not `columns`: the design's columns (punch,
animal, time point, slide) live in the layout table, not in the raw bundle, so
`init.column_missing` must not look for them here. `domain.h5_order_matches_cells` records whether
the h5 barcode sequence equals the `cells.parquet` `cell_id` sequence; it is recorded, never
assumed (ROSC defect A1).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

from _xenium_common import bundle_summary, emit, is_bundle


def main(argv: list[str]) -> int:
    bundle = Path(argv[1])
    if not is_bundle(bundle):
        sys.stderr.write(f"{bundle} has no cells.parquet; not a Xenium bundle\n")
        return 2
    s = bundle_summary(bundle)
    out = {
        "extractor": "sc.xenium_bundle@1",
        "type": "xenium_bundle",
        "n_obs": s["n_cells"],
        "n_var": s["n_gene_features"],
        "fields": {
            "cells_columns": s.pop("cells_columns"),
            "h5_feature_types": s.pop("h5_feature_types"),
        },
        "counts_per_group": {},
        "domain": s,
    }
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
