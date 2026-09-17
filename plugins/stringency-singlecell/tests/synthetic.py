"""A tiny synthetic Xenium region bundle for extractor tests, in the vendor layout.

The h5 barcodes are written in a DIFFERENT order from `cells.parquet` (a shuffle), and
`cell_area` is a known function of the cell id, so any positional join between the two files
produces detectably wrong areas. This is the fixture guard from the Lane C plan (ROSC defect A1);
the method repo copies this generator for its own fixtures. Requires pyarrow and h5py.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

GENES = [f"Gene{i:03d}" for i in range(50)]
CONTROLS = ["NegControlProbe_1", "NegControlCodeword_1", "UnassignedCodeword_1"]


def area_for(cell_id: str) -> float:
    """cell_area as a function of the id, so a wrong join is visible by value."""
    return 20.0 + (int(cell_id.split("-")[0][1:]) % 97) * 3.0


def cell_ids(n: int) -> list[str]:
    return [f"c{i:05d}-1" for i in range(n)]


def write_bundle(
    root: Path,
    *,
    n_cells: int = 300,
    slide: str = "0000001",
    region: str = "Test",
    seed: int = 7,
    shuffle_h5: bool = True,
    punches: dict[str, tuple[float, float, float, float]] | None = None,
) -> Path:
    """Write a bundle at `root`. Cells are placed uniformly in [0, 6000) µm unless `punches`
    gives boxes (x_min, x_max, y_min, y_max) to place cells in, round-robin."""
    import h5py
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq

    rng = random.Random(seed)
    root.mkdir(parents=True, exist_ok=True)
    ids = cell_ids(n_cells)
    boxes = list(punches.values()) if punches else [(0.0, 6000.0, 0.0, 6000.0)]
    xs, ys = [], []
    for i in range(n_cells):
        b = boxes[i % len(boxes)]
        xs.append(rng.uniform(b[0] + 1, b[1] - 1))
        ys.append(rng.uniform(b[2] + 1, b[3] - 1))
    tc = [rng.randint(5, 400) for _ in ids]
    table = pa.table(
        {
            "cell_id": pa.array(ids, pa.large_string()),
            "x_centroid": xs,
            "y_centroid": ys,
            "transcript_counts": pa.array(tc, pa.int64()),
            "total_counts": pa.array([t + rng.randint(0, 3) for t in tc], pa.int64()),
            "cell_area": [area_for(c) for c in ids],
            "nucleus_area": [area_for(c) / 2 for c in ids],
            "nucleus_count": pa.array([1] * n_cells, pa.int64()),
            "segmentation_method": pa.array(
                ["Segmented by interior stain (18S)"] * n_cells, pa.large_string()
            ),
        }
    )
    pq.write_table(table, root / "cells.parquet")

    order = list(range(n_cells))
    if shuffle_h5:
        rng.shuffle(order)
    barcodes = [ids[i] for i in order]
    features = GENES + CONTROLS
    ftypes = ["Gene Expression"] * len(GENES) + [
        "Negative Control Probe",
        "Negative Control Codeword",
        "Unassigned Codeword",
    ]
    n_feat = len(features)
    # CSC over cells (columns): indptr per barcode column, as 10x writes it
    data, indices, indptr = [], [], [0]
    for i in order:
        k = max(1, tc[i] // 40)
        rows = sorted(rng.sample(range(len(GENES)), min(k, len(GENES))))
        for r in rows:
            indices.append(r)
            data.append(rng.randint(1, 20))
        indptr.append(len(data))
    with h5py.File(root / "cell_feature_matrix.h5", "w") as f:
        g = f.create_group("matrix")
        g.create_dataset("barcodes", data=np.array([b.encode() for b in barcodes], dtype="S10"))
        g.create_dataset("data", data=np.array(data, dtype=np.int32))
        g.create_dataset("indices", data=np.array(indices, dtype=np.int64))
        g.create_dataset("indptr", data=np.array(indptr, dtype=np.int64))
        g.create_dataset("shape", data=np.array([n_feat, n_cells], dtype=np.int32))
        fg = g.create_group("features")
        fg.create_dataset(
            "id", data=np.array([f"ENSMUSG{i:011d}".encode() for i in range(n_feat)], dtype="S31")
        )
        fg.create_dataset("name", data=np.array([x.encode() for x in features], dtype="S31"))
        fg.create_dataset("feature_type", data=np.array([x.encode() for x in ftypes], dtype="S25"))
        fg.create_dataset("genome", data=np.array([b"mm10"] * n_feat, dtype="S7"))
        fg.create_dataset("_all_tag_keys", data=np.array([b"genome"], dtype="S6"))
    (root / "experiment.xenium").write_text(
        json.dumps(
            {
                "major_version": 6,
                "minor_version": 1,
                "patch_version": 0,
                "run_name": "synthetic",
                "region_name": region,
                "preservation_method": "ffpe",
                "num_cells": n_cells,
                "cassette_name": "TMA0",
                "slide_id": slide,
                "panel_name": "synthetic_panel",
                "analysis_sw_version": "xenium-0.0.0",
                "instrument_sw_version": "0",
                "segmentation_stain": "synthetic",
                "region_area": 3.6e7,
            }
        )
    )
    with open(root / "metrics_summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "run_name",
                "cassette_name",
                "region_name",
                "panel_name",
                "predesigned_panel_id",
                "region_area",
                "num_cells_detected",
                "median_transcripts_per_cell",
                "median_genes_per_cell",
            ]
        )
        w.writerow(
            [
                "synthetic",
                "TMA0",
                region,
                "synthetic_panel",
                "synthetic_base",
                3.6e7,
                n_cells,
                sorted(tc)[n_cells // 2],
                10,
            ]
        )
    (root / "gene_panel.json").write_text(
        json.dumps(
            {
                "metadata": {},
                "payload": {
                    "panel": {
                        "identity": {"name": "synthetic_panel", "design_id": "SYN"},
                        "num_gene_targets": 0,
                        "species": "Mouse",
                        "type": {"descriptor": "predesigned", "data": {}},
                    },
                    "targets": [
                        {"type": {"descriptor": "gene", "data": {"name": g}}} for g in GENES
                    ],
                },
            }
        )
    )
    return root


def write_selection_export(
    path: Path, punch_id: str, box: tuple[float, float, float, float]
) -> Path:
    """One Xenium Explorer export: CRLF, two `#` headers, closed 5-vertex rectangle, no trailing newline."""
    x0, x1, y0, y1 = box
    area = (x1 - x0) * (y1 - y0)
    lines = [
        f"#Selection names: {punch_id}",
        f"#Areas (µm^2): {area:.1f}",
        "Selection,X,Y,Class,Color",
    ]
    for x, y in [(x1, y0), (x1, y1), (x0, y1), (x0, y0), (x1, y0)]:
        lines.append(f"{punch_id},{x},{y},Unclassified,#c2c2c2")
    path.write_bytes("\r\n".join(lines).encode("utf-8"))
    return path


def write_layout(path: Path, rows: list[dict[str, str]]) -> Path:
    cols = [
        "punch_id",
        "tma",
        "slide",
        "region",
        "tma_row",
        "tma_col",
        "animal",
        "timepoint_h",
        "animal_in_timepoint",
        "organ",
        "punch",
        "condition",
        "genotype",
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    return path
