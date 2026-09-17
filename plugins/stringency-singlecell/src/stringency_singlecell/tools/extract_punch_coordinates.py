#!/usr/bin/env python3
"""State extractor for object type `punch_coordinates` (`sc.punch_coordinates@1`). Stdlib only.

usage: extract_punch_coordinates.py <file_or_dir> <design.json>

The hand-drawn punch selections from Xenium Explorer (spec/coordinates-input.md): one export, a
per-region concatenation of exports, a consolidated bounding-box CSV, or a directory of exports.
Emits every punch id with its vertex count, closure, exported area, bounding box, and whether it
is an axis-aligned rectangle, plus the source line the design requires for a manual input.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _xenium_common import SOURCE_LINE, emit, load_coordinates


def main(argv: list[str]) -> int:
    punches, meta = load_coordinates(argv[1])
    ids = [p["punch_id"] for p in punches]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    out = {
        "extractor": "sc.punch_coordinates@1",
        "type": "punch_coordinates",
        "n_obs": len(punches),
        "fields": {"punch_ids": ids},
        "counts_per_group": {},
        "domain": {
            "source": SOURCE_LINE,
            **meta,
            "punches": punches,
            "duplicate_punch_ids": dupes,
            "n_polygons_not_closed": sum(1 for p in punches if p["polygon"] and not p["closed"]),
            "n_degenerate": sum(1 for p in punches if p["n_vertices"] < 3),
            "all_rectangles": all(p["is_rectangle"] for p in punches) if punches else False,
        },
    }
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
