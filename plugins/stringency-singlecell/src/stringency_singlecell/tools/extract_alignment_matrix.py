#!/usr/bin/env python3
"""State extractor for object type `alignment_matrix` (plugin 0.10.6): the 3 by 3 affine matrix
that aligns an image to a Xenium run, as Xenium Explorer exports it (image pixels to Xenium
pixels), a CSV of three rows of three numbers. Made by a person and declared as an input: the
extractor reads its form and what it says (scale, rotation), never whether it is right.
Stdlib only.

usage: extract_alignment_matrix.py <matrix.csv> <design.json>
Prints the envelope: extractor, type, n_obs (rows), n_var (columns), fields (empty),
counts_per_group (empty), and domain: `well_formed` (3 by 3, numeric, last row 0 0 1, invertible),
`problems` (why not), `scale` (Xenium pixels per image pixel), `rotation_deg`, `translation`.
"""

from __future__ import annotations

import csv
import json
import math
import sys


def main(argv: list[str]) -> int:
    with open(argv[1], newline="") as f:
        raw = [[c.strip() for c in row] for row in csv.reader(f) if any(c.strip() for c in row)]
    problems: list[str] = []
    m: list[list[float]] = []
    try:
        m = [[float(c) for c in row] for row in raw]
    except ValueError:
        problems.append("a cell is not a number")
    if not problems and (len(m) != 3 or any(len(r) != 3 for r in m)):
        problems.append(f"{len(m)} row(s) of {sorted({len(r) for r in m})} column(s), not 3 by 3")
    domain: dict[str, object] = {}
    if not problems:
        (a, b, tx), (c, d, ty), last = m
        if [round(v, 12) for v in last] != [0.0, 0.0, 1.0]:
            problems.append("the last row is not 0, 0, 1")
        det = a * d - b * c
        if abs(det) < 1e-12:
            problems.append("the matrix cannot be inverted")
        else:
            domain.update(
                scale=math.sqrt(abs(det)),
                rotation_deg=math.degrees(math.atan2(c, a)),
                translation=[tx, ty],
            )
    env = {
        "extractor": "sc.alignment_matrix@1",
        "type": "alignment_matrix",
        "n_obs": len(raw),
        "n_var": max((len(r) for r in raw), default=0),
        "fields": {},
        "counts_per_group": {},
        "domain": {"well_formed": not problems, "problems": problems, **domain},
    }
    print(json.dumps(env, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
