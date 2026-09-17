#!/usr/bin/env python3
"""Build the per-region coordinates input from the per-punch Xenium Explorer exports.

usage: combine_coordinates.py <coords_dir> <tma_layout.csv> <slide> <region> <out.csv>

The documented concatenation step behind spec/coordinates-input.md: picks the punches the
layout assigns to (slide, region), concatenates their `<punch_id>_coordinates.csv` exports
verbatim in layout order (each export lacks a trailing newline, so one CRLF is inserted between
files), and refuses if any punch has no export or an export's selection name differs from its
file name. The result is one file, one hash, per region, still bit-for-bit the hand-drawn
polygons. Stdlib only.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

from _xenium_common import parse_selection_export, read_layout


def main(argv: list[str]) -> int:
    coords_dir, layout_path, slide, region, out = (
        Path(argv[1]),
        argv[2],
        argv[3],
        argv[4],
        Path(argv[5]),
    )
    _, rows = read_layout(layout_path)
    wanted = [r["punch_id"] for r in rows if r.get("slide") == slide and r.get("region") == region]
    if not wanted:
        sys.stderr.write(f"layout has no punches for slide {slide} region {region}\n")
        return 2
    chunks: list[bytes] = []
    problems: list[str] = []
    for pid in wanted:
        f = coords_dir / f"{pid}_coordinates.csv"
        if not f.exists():
            problems.append(f"no export for {pid}")
            continue
        data = f.read_bytes()
        names = [p["punch_id"] for p in parse_selection_export(data.decode("utf-8-sig", "replace"))]
        if names != [pid]:
            problems.append(f"{f.name} names {names}, expected [{pid}]")
        chunks.append(data)
    if problems:
        sys.stderr.write("\n".join(problems) + "\n")
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"\r\n".join(chunks) + b"\r\n")
    print(f"{out}: {len(wanted)} punches for slide {slide} {region}: {', '.join(wanted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
