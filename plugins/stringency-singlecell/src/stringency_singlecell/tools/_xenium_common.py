"""Shared parsing for the Xenium extractors. Stdlib only; pyarrow and h5py are imported lazily
by the callers that need them. Imported by the tool scripts through their own directory, so the
plugin package need not be installed inside the module environment.

Coordinates input (spec/coordinates-input.md): the hand-drawn Xenium Explorer selection export,
one file per punch, `#Selection names: <id>` / `#Areas (µm^2): <a>` / `Selection,X,Y,Class,Color`
with CRLF line ends and no trailing newline. Accepted units: one such file, several concatenated
into one file per region (`combine_coordinates.py`), a consolidated bounding-box CSV with columns
`punch_id,x_min,x_max,y_min,y_max` (what the splitter consumes), or a directory of per-punch files.
"""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
from typing import Any

SOURCE_LINE = "manual annotation in Xenium Explorer"
SELECTION_HEADERS = ("#selection names:", "#selection name:")
AREA_HEADERS = ("#areas", "#area")
BBOX_COLUMNS = ("punch_id", "x_min", "x_max", "y_min", "y_max")


def _fnum(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_selection_export(text: str) -> list[dict[str, Any]]:
    """Parse one or more Xenium Explorer selection blocks. Returns one dict per selection."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[dict[str, Any]] = []
    names: list[str] = []
    areas: list[float | None] = []
    rows_by_name: dict[str, list[tuple[float, float]]] = {}
    order: list[str] = []
    in_table = False

    def flush() -> None:
        nonlocal names, areas, rows_by_name, order, in_table
        for i, name in enumerate(order):
            verts = rows_by_name.get(name, [])
            area = None
            if name in names and len(areas) == len(names):
                area = areas[names.index(name)]
            elif len(areas) == 1:
                area = areas[0]
            blocks.append(_punch_from_vertices(name, verts, area))
        names, areas, rows_by_name, order, in_table = [], [], {}, [], False

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith(SELECTION_HEADERS):
            if order or names:
                flush()
            names = [n.strip() for n in line.split(":", 1)[1].split(",") if n.strip()]
            continue
        if low.startswith(AREA_HEADERS) and ":" in line:
            areas = [_fnum(a.strip()) for a in line.split(":", 1)[1].split(",")]
            continue
        if low.startswith("selection,"):
            in_table = True
            continue
        if line.startswith("#"):
            continue
        parts = next(csv.reader([line]))
        if len(parts) < 3:
            continue
        name = parts[0].strip()
        x, y = _fnum(parts[1]), _fnum(parts[2])
        if x is None or y is None:
            continue
        if name not in rows_by_name:
            rows_by_name[name] = []
            order.append(name)
        rows_by_name[name].append((x, y))
    if order or names:
        flush()
    return blocks


def _punch_from_vertices(
    name: str, verts: list[tuple[float, float]], area: float | None
) -> dict[str, Any]:
    closed = len(verts) >= 2 and verts[0] == verts[-1]
    distinct = verts[:-1] if closed else verts
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    bbox = (
        {"x_min": min(xs), "x_max": max(xs), "y_min": min(ys), "y_max": max(ys)} if verts else None
    )
    bbox_area = (bbox["x_max"] - bbox["x_min"]) * (bbox["y_max"] - bbox["y_min"]) if bbox else None
    is_rect = False
    if bbox is not None and len(distinct) == 4:
        corners = {
            (bbox["x_min"], bbox["y_min"]),
            (bbox["x_min"], bbox["y_max"]),
            (bbox["x_max"], bbox["y_min"]),
            (bbox["x_max"], bbox["y_max"]),
        }
        is_rect = set(distinct) == corners
    return {
        "punch_id": name,
        "n_vertices": len(distinct),
        "closed": closed,
        "area_um2": area,
        "bbox": bbox,
        "bbox_area_um2": bbox_area,
        "is_rectangle": is_rect,
        "polygon": True,
    }


def parse_bbox_csv(text: str) -> list[dict[str, Any]]:
    rows = list(csv.DictReader(io.StringIO(text.replace("\r\n", "\n"))))
    out: list[dict[str, Any]] = []
    for r in rows:
        bbox = {k: _fnum(r.get(k, "")) for k in BBOX_COLUMNS[1:]}
        if any(v is None for v in bbox.values()):
            continue
        out.append(
            {
                "punch_id": r["punch_id"].strip(),
                "n_vertices": 4,
                "closed": True,
                "area_um2": _fnum(r.get("region_area", "")),
                "bbox": bbox,
                "bbox_area_um2": (bbox["x_max"] - bbox["x_min"]) * (bbox["y_max"] - bbox["y_min"]),
                "is_rectangle": True,
                "polygon": False,
            }
        )
    return out


def detect_format(text: str) -> str:
    first = text.lstrip().split("\n", 1)[0].strip().lower()
    if first.startswith(SELECTION_HEADERS) or first.startswith("selection,"):
        return "xenium_explorer_export"
    cols = [c.strip() for c in first.split(",")]
    if all(c in cols for c in BBOX_COLUMNS):
        return "bbox_csv"
    return "unknown"


def load_coordinates(path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Punches from a file or a directory. Returns (punches, meta)."""
    p = Path(path)
    if p.is_dir():
        files = sorted(q for q in p.iterdir() if q.suffix.lower() == ".csv")
        punches: list[dict[str, Any]] = []
        fmts: set[str] = set()
        for f in files:
            text = f.read_text(encoding="utf-8-sig", errors="replace")
            fmt = detect_format(text)
            fmts.add(fmt)
            punches += _parse_by_format(text, fmt)
        return punches, {
            "input_unit": "directory",
            "n_files": len(files),
            "format": ",".join(sorted(fmts)) or "empty",
        }
    text = p.read_text(encoding="utf-8-sig", errors="replace")
    fmt = detect_format(text)
    return _parse_by_format(text, fmt), {"input_unit": "file", "n_files": 1, "format": fmt}


def _parse_by_format(text: str, fmt: str) -> list[dict[str, Any]]:
    if fmt == "xenium_explorer_export":
        return parse_selection_export(text)
    if fmt == "bbox_csv":
        return parse_bbox_csv(text)
    return []


def read_layout(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [{k: (v or "").strip() for k, v in r.items()} for r in reader]
        return list(reader.fieldnames or []), rows


def layout_region_key(slide: str, region: str) -> str:
    return f"{slide}/{region}"


# ---- bundle readers -----------------------------------------------------------------------


def read_metrics_summary(bundle: Path) -> dict[str, str]:
    p = bundle / "metrics_summary.csv"
    if not p.exists():
        return {}
    with open(p, newline="") as f:
        rows = list(csv.DictReader(f))
    return rows[0] if rows else {}


def read_experiment(bundle: Path) -> dict[str, Any]:
    p = bundle / "experiment.xenium"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def read_gene_panel(bundle: Path) -> dict[str, Any]:
    p = bundle / "gene_panel.json"
    if not p.exists():
        return {}
    try:
        g = json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}
    payload = g.get("payload", g)
    panel = payload.get("panel", {}) if isinstance(payload, dict) else {}
    ident = panel.get("identity", {})
    base = panel.get("type", {}).get("data", {}).get("base_panel_identity", {})
    targets = payload.get("targets", []) if isinstance(payload, dict) else []
    n_gene = sum(
        1 for t in targets if isinstance(t, dict) and t.get("type", {}).get("descriptor") == "gene"
    )
    return {
        "name": ident.get("name"),
        "design_id": ident.get("design_id"),
        "predesigned_id": base.get("design_id"),
        "n_targets": len(targets),
        "n_gene_targets": n_gene,
        "n_custom_gene_targets": panel.get("num_gene_targets"),
        "species": panel.get("species"),
    }


def is_bundle(path: Path) -> bool:
    return (path / "cells.parquet").exists()


def cells_summary(bundle: Path) -> dict[str, Any]:
    """Column list, n cells, medians, segmentation method counts, and the cell_id sequence."""
    import pyarrow.parquet as pq  # inside the module environment

    pf = pq.ParquetFile(bundle / "cells.parquet")
    cols = list(pf.schema_arrow.names)
    want = [
        c
        for c in (
            "cell_id",
            "transcript_counts",
            "cell_area",
            "nucleus_area",
            "segmentation_method",
        )
        if c in cols
    ]
    t = pf.read(columns=want)
    out: dict[str, Any] = {"columns": cols, "n_cells": t.num_rows}
    ids = t["cell_id"].to_pylist() if "cell_id" in want else []
    out["cell_ids"] = [str(i) for i in ids]
    for c in ("transcript_counts", "cell_area", "nucleus_area"):
        if c in want:
            vals = sorted(v for v in t[c].to_pylist() if v is not None)
            out[f"median_{c}"] = _median(vals)
    if "segmentation_method" in want:
        counts: dict[str, int] = {}
        for v in t["segmentation_method"].to_pylist():
            counts[str(v)] = counts.get(str(v), 0) + 1
        out["segmentation_methods"] = counts
    return out


def _median(vals: list[float]) -> float | None:
    n = len(vals)
    if n == 0:
        return None
    mid = n // 2
    return float(vals[mid]) if n % 2 else float((vals[mid - 1] + vals[mid]) / 2)


def h5_summary(bundle: Path) -> dict[str, Any]:
    import h5py  # inside the module environment

    p = bundle / "cell_feature_matrix.h5"
    if not p.exists():
        return {}
    with h5py.File(p, "r") as f:
        barcodes = [b.decode() if isinstance(b, bytes) else str(b) for b in f["matrix/barcodes"][:]]
        ft = f["matrix/features/feature_type"][:]
        types: dict[str, int] = {}
        for v in ft:
            k = v.decode() if isinstance(v, bytes) else str(v)
            types[k] = types.get(k, 0) + 1
        shape = [int(x) for x in f["matrix/shape"][:]]
    return {"barcodes": barcodes, "feature_types": types, "shape": shape}


def order_checks(cell_ids: list[str], barcodes: list[str]) -> dict[str, Any]:
    """Recorded, never assumed (ROSC defect A1). Same set is necessary; same order is what a
    positional join silently requires."""
    return {
        "h5_order_matches_cells": bool(cell_ids) and cell_ids == barcodes,
        "h5_set_matches_cells": set(cell_ids) == set(barcodes),
        "n_cells_parquet": len(cell_ids),
        "n_barcodes_h5": len(barcodes),
    }


def bundle_summary(bundle: Path) -> dict[str, Any]:
    """Everything the xenium_bundle and punch_bundle_set extractors share."""
    ms = read_metrics_summary(bundle)
    ex = read_experiment(bundle)
    panel = read_gene_panel(bundle)
    cells = cells_summary(bundle)
    h5 = h5_summary(bundle)
    checks = order_checks(cells.get("cell_ids", []), h5.get("barcodes", []))
    kind = "vendor" if ex else "resegmented_or_split"
    genes = (h5.get("feature_types") or {}).get("Gene Expression")
    return {
        "kind": kind,
        "slide": ex.get("slide_id") or ms.get("slide_id"),
        "region": ex.get("region_name") or ms.get("region_name"),
        "cassette": ex.get("cassette_name") or ms.get("cassette_name"),
        "run_name": ex.get("run_name") or ms.get("run_name"),
        "analysis_sw_version": ex.get("analysis_sw_version"),
        "instrument_sw_version": ex.get("instrument_sw_version"),
        "preservation_method": ex.get("preservation_method"),
        "segmentation_stain": ex.get("segmentation_stain"),
        "panel": panel
        or {"name": ms.get("panel_name"), "predesigned_id": ms.get("predesigned_panel_id")},
        "n_cells": cells.get("n_cells"),
        "n_gene_features": genes,
        "n_features": (h5.get("shape") or [None])[0],
        "vendor_num_cells_detected": _fnum(ms.get("num_cells_detected", "")),
        "vendor_median_transcripts_per_cell": _fnum(ms.get("median_transcripts_per_cell", "")),
        "vendor_median_genes_per_cell": _fnum(ms.get("median_genes_per_cell", "")),
        "median_transcript_counts": cells.get("median_transcript_counts"),
        "median_cell_area_um2": cells.get("median_cell_area"),
        "median_nucleus_area_um2": cells.get("median_nucleus_area"),
        "region_area_um2": _fnum(ms.get("region_area", "")) or ex.get("region_area"),
        "segmentation_methods": cells.get("segmentation_methods", {}),
        "cells_columns": cells.get("columns", []),
        "h5_feature_types": h5.get("feature_types", {}),
        **checks,
    }


def emit(out: dict[str, Any]) -> None:
    import sys

    json.dump(out, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


def script_dir_on_path() -> None:
    import sys

    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
