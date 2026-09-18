"""Extractors on a synthetic bundle (always) and on the real Lyons CLP inputs (when mounted)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from stringency.plugins import load_plugins

from tests.helpers import DESIGN
from tests.synthetic import area_for, write_bundle, write_layout, write_selection_export

RAW = Path("/lab/raw/2026-08_xenium_lyons-clp/output-XETG00215__0076570__Liver__20260828__175931")
PROJ = Path("/lab/projects/Lyons_CLP")
TOOLS = load_plugins(refresh=True)["stringency-singlecell"].tools

PUNCHES = {
    "6-1-Test": (0.0, 2000.0, 0.0, 2000.0),
    "6-2-Test": (3000.0, 5000.0, 0.0, 2000.0),
    "24-1-Test": (0.0, 2000.0, 3000.0, 5000.0),
}


def run_tool(name: str, *args: str | Path) -> dict:
    script = TOOLS[name].script
    res = subprocess.run(
        [sys.executable, str(script), *map(str, args)], capture_output=True, text=True, check=False
    )
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


@pytest.fixture(scope="module")
def design_json(tmp_path_factory: pytest.TempPathFactory) -> Path:
    p = tmp_path_factory.mktemp("design") / "design.json"
    p.write_text(json.dumps(DESIGN))
    return p


@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_bundle(tmp_path_factory.mktemp("bundle") / "output-synthetic", punches=PUNCHES)


@pytest.fixture(scope="module")
def coords_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("coords")
    for pid, box in PUNCHES.items():
        write_selection_export(d / f"{pid}_coordinates.csv", pid, box)
    return d


@pytest.fixture(scope="module")
def layout(tmp_path_factory: pytest.TempPathFactory) -> Path:
    rows = [
        {
            "punch_id": pid,
            "tma": "TMA0",
            "slide": "0000001",
            "region": "Test",
            "animal": pid.rsplit("-", 1)[0],
            "timepoint_h": pid.split("-")[0],
            "organ": "test",
            "punch": "single",
            "condition": "CLP",
            "genotype": "WT",
        }
        for pid in PUNCHES
    ]
    return write_layout(tmp_path_factory.mktemp("layout") / "tma_layout.csv", rows)


# --- synthetic --------------------------------------------------------------------------------


def test_synthetic_bundle_shuffles_h5_and_area_is_a_function_of_id(bundle: Path) -> None:
    import h5py
    import pyarrow.parquet as pq

    t = pq.read_table(bundle / "cells.parquet", columns=["cell_id", "cell_area"])
    ids = t["cell_id"].to_pylist()
    with h5py.File(bundle / "cell_feature_matrix.h5") as f:
        bc = [b.decode() for b in f["matrix/barcodes"][:]]
    assert set(ids) == set(bc) and ids != bc, (
        "the fixture must hold the same ids in a different order"
    )
    assert all(a == area_for(i) for i, a in zip(ids, t["cell_area"].to_pylist(), strict=True))
    # what ROSC A1 did: a positional join. Same set, zero NAs, wrong values.
    positional = dict(zip(bc, t["cell_area"].to_pylist(), strict=True))
    wrong = sum(1 for cid, a in positional.items() if a != area_for(cid))
    assert wrong > 0.9 * len(ids)


def test_extract_xenium_bundle_synthetic(bundle: Path, design_json: Path) -> None:
    out = run_tool("extract_xenium_bundle", bundle, design_json)
    assert out["extractor"] == "sc.xenium_bundle@1" and out["type"] == "xenium_bundle"
    assert out["n_obs"] == 300 and out["n_var"] == 50
    assert "columns" not in out["fields"] and "cells_columns" in out["fields"]
    d = out["domain"]
    assert d["slide"] == "0000001" and d["region"] == "Test" and d["kind"] == "vendor"
    assert d["h5_set_matches_cells"] is True and d["h5_order_matches_cells"] is False
    assert d["median_cell_area_um2"] > 0 and d["panel"]["n_gene_targets"] == 50


def test_extract_punch_coordinates_dir_file_and_combined(
    coords_dir: Path, design_json: Path, layout: Path, tmp_path: Path
) -> None:
    out = run_tool("extract_punch_coordinates", coords_dir, design_json)
    assert (
        out["n_obs"] == 3
        and out["domain"]["input_unit"] == "directory"
        and out["domain"]["all_rectangles"]
    )
    assert out["domain"]["source"] == "manual annotation in Xenium Explorer"
    one = run_tool(
        "extract_punch_coordinates", coords_dir / "6-1-Test_coordinates.csv", design_json
    )
    assert one["fields"]["punch_ids"] == ["6-1-Test"]
    p = one["domain"]["punches"][0]
    assert (
        p["n_vertices"] == 4
        and p["closed"]
        and p["bbox"] == {"x_min": 0.0, "x_max": 2000.0, "y_min": 0.0, "y_max": 2000.0}
    )
    combined = tmp_path / "0000001_Test.csv"
    res = subprocess.run(
        [
            sys.executable,
            str(TOOLS["combine_coordinates"].script),
            str(coords_dir),
            str(layout),
            "0000001",
            "Test",
            str(combined),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    both = run_tool("extract_punch_coordinates", combined, design_json)
    assert both["fields"]["punch_ids"] == list(PUNCHES) and both["domain"]["input_unit"] == "file"
    key = lambda p: p["punch_id"]
    assert sorted(both["domain"]["punches"], key=key) == sorted(out["domain"]["punches"], key=key)
    # bit-for-bit: the combined file is the exports joined by one CRLF
    parts = [(coords_dir / f"{pid}_coordinates.csv").read_bytes() for pid in PUNCHES]
    assert combined.read_bytes() == b"\r\n".join(parts) + b"\r\n"


def test_combine_refuses_missing_or_misnamed(
    coords_dir: Path, layout: Path, tmp_path: Path
) -> None:
    (coords_dir / "24-1-Test_coordinates.csv").rename(coords_dir / "21-1-Test_coordinates.csv")
    try:
        res = subprocess.run(
            [
                sys.executable,
                str(TOOLS["combine_coordinates"].script),
                str(coords_dir),
                str(layout),
                "0000001",
                "Test",
                str(tmp_path / "x.csv"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 2 and "no export for 24-1-Test" in res.stderr
    finally:
        (coords_dir / "21-1-Test_coordinates.csv").rename(coords_dir / "24-1-Test_coordinates.csv")


def test_singular_selection_header_parses(tmp_path: Path, design_json: Path) -> None:
    p = tmp_path / "old_coordinates.csv"
    p.write_bytes(
        b"#Selection name: D3-SC-SP1\r\n#Area (\xc2\xb5m^2): 100.0\r\nSelection,X,Y,Class,Color\r\n"
        b"D3-SC-SP1,0,0,U,#c\r\nD3-SC-SP1,0,10,U,#c\r\nD3-SC-SP1,10,10,U,#c\r\nD3-SC-SP1,10,0,U,#c\r\nD3-SC-SP1,0,0,U,#c"
    )
    out = run_tool("extract_punch_coordinates", p, design_json)
    assert (
        out["fields"]["punch_ids"] == ["D3-SC-SP1"]
        and out["domain"]["punches"][0]["area_um2"] == 100.0
    )


def test_extract_bbox_csv_format(tmp_path: Path, design_json: Path) -> None:
    p = tmp_path / "all_punch_coordinates.csv"
    p.write_text(
        "punch_id,x_min,x_max,y_min,y_max,region_area\nA,0,10,0,10,100\nB,20,30,0,10,100\n"
    )
    out = run_tool("extract_punch_coordinates", p, design_json)
    assert out["domain"]["format"] == "bbox_csv" and out["fields"]["punch_ids"] == ["A", "B"]
    assert out["domain"]["punches"][0]["polygon"] is False


def test_extract_tma_layout_synthetic(layout: Path, design_json: Path) -> None:
    out = run_tool("extract_tma_layout", layout, design_json)
    assert out["n_obs"] == 3 and "punch_id" in out["fields"]["columns"]
    assert out["counts_per_group"]["timepoint_h"]["6"] == {"punch_id": 2, "animal": 2}
    assert out["counts_per_group"]["timepoint_h"]["48"] == {"punch_id": 0, "animal": 0}
    assert out["domain"]["regions"] == {"0000001/Test": list(PUNCHES)}
    assert out["domain"]["missing_required_columns"] == []


def test_extract_punch_bundle_set_and_qc_object_set(
    bundle: Path, design_json: Path, tmp_path: Path
) -> None:
    import shutil

    root = tmp_path / "split"
    for pid in list(PUNCHES)[:2]:
        shutil.copytree(bundle, root / f"punch_{pid}")
    (root / "region_metrics.csv").write_text("punch_id,n\n")
    (root / "punch_metadata.csv").write_text(
        "punch_id,slide,animal,timepoint_h,condition\n6-1-Test,0000001,6-1,6,CLP\n6-2-Test,0000001,6-2,6,CLP\n"
    )
    out = run_tool("extract_punch_bundle_set", root, design_json)
    assert out["n_obs"] == 600 and out["fields"]["punch_ids"] == ["6-1-Test", "6-2-Test"]
    assert out["domain"]["all_h5_orders_match_cells"] is False
    assert out["counts_per_group"]["timepoint_h"]["6"] == {"cell": 600, "punch_id": 2, "animal": 2}

    qc = tmp_path / "qc"
    qc.mkdir()
    (qc / "qc_summary.json").write_text(
        json.dumps(
            {
                "qc_summary": 1,
                "punches": [
                    {
                        "punch_id": "6-1-Test",
                        "tissue": "test",
                        "included": True,
                        "n_before": 300,
                        "n_after": 250,
                        "fail_fraction": 0.1667,
                        "thresholds": {"min_nCount": 10},
                        "object": "6-1-Test.h5ad",
                    }
                ],
                "join_verification": {
                    "method": "keyed_reindex_on_cell_id",
                    "verified": True,
                    "n_cells": 300,
                    "n_cells_checked": 300,
                    "columns_checked": ["cell_area"],
                    "detail": "ok",
                },
            }
        )
    )
    out = run_tool("extract_qc_object_set", qc, design_json)
    assert (
        out["n_obs"] == 250 and out["domain"]["join_verification"]["verified_by_extractor"] is True
    )
    # a summary whose n_cells disagrees with the punches is refused by the extractor
    s = json.loads((qc / "qc_summary.json").read_text())
    s["join_verification"]["n_cells"] = s["join_verification"]["n_cells_checked"] = 299
    (qc / "qc_summary.json").write_text(json.dumps(s))
    out = run_tool("extract_qc_object_set", qc, design_json)
    assert out["domain"]["join_verification"]["verified_by_extractor"] is False


# --- real inputs, read-only -------------------------------------------------------------------

real = pytest.mark.skipif(
    not RAW.exists() or not PROJ.exists(), reason="Lyons CLP data not mounted"
)


@real
def test_real_liver_bundle(design_json: Path) -> None:
    out = run_tool("extract_xenium_bundle", RAW, design_json)
    d = out["domain"]
    assert (
        out["n_obs"] == 25720
        and d["slide"] == "0076570"
        and d["region"] == "Liver"
        and d["cassette"] == "TMA2"
    )
    assert (
        d["analysis_sw_version"] == "xenium-4.0.2.2" and d["panel"]["predesigned_id"] == "mAtlas_v1"
    )
    assert d["h5_set_matches_cells"] is True


@real
def test_real_coordinates_and_layout_agree(design_json: Path) -> None:
    coords = run_tool("extract_punch_coordinates", PROJ / "punch_coordinates", design_json)
    layout = run_tool("extract_tma_layout", PROJ / "tma_layout.csv", design_json)
    assert coords["n_obs"] == 42 and layout["n_obs"] == 42
    assert sorted(coords["fields"]["punch_ids"]) == sorted(
        p["punch_id"] for p in layout["domain"]["punches"]
    )
    assert (
        coords["domain"]["duplicate_punch_ids"] == []
        and coords["domain"]["n_polygons_not_closed"] == 0
    )
    assert layout["counts_per_group"]["timepoint_h"]["24"] == {"punch_id": 14, "animal": 2}


def test_qc_metrics_table_extractor_on_synthetic(tmp_path) -> None:
    import csv
    import json
    import subprocess
    import sys
    from pathlib import Path

    rows = [
        {
            "punch_id": "6-1-Liver",
            "tissue": "liver",
            "region_id": "0076581_Liver",
            "histology_include": "True",
            "histology_issue": "False",
            "num_cells": 7000,
            "cells_per_mm2": 2600,
            "median_transcripts_per_cell": 950,
            "median_genes_per_cell": 380,
            "fraction_transcripts_decoded_q20": 0.78,
            "percent_transcripts_in_cells": 0.86,
            "fail_fraction": 0.02,
        },
        {
            "punch_id": "24-2-Gut-A",
            "tissue": "gut",
            "region_id": "0076570_Gut",
            "histology_include": "False",
            "histology_issue": "True",
            "num_cells": 19030,
            "cells_per_mm2": 3739,
            "median_transcripts_per_cell": 280,
            "median_genes_per_cell": 150,
            "fraction_transcripts_decoded_q20": 0.75,
            "percent_transcripts_in_cells": 0.99,
            "fail_fraction": 0.157,
        },
    ]
    p = tmp_path / "qc_metrics_all.csv"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    tool = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "stringency_singlecell"
        / "tools"
        / "extract_qc_metrics_table.py"
    )
    out = json.loads(
        subprocess.run(
            [sys.executable, str(tool), str(p), "{}"], check=True, capture_output=True, text=True
        ).stdout
    )
    assert out["extractor"] == "sc.qc_metrics_table@1" and out["n_obs"] == 2
    assert out["domain"]["n_included"] == 1 and out["domain"]["n_excluded"] == 1
    assert (
        out["domain"]["tissues"] == ["gut", "liver"]
        and out["domain"]["core_attributes_missing"] == []
    )
    assert out["fields"]["punch_ids"] == ["6-1-Liver", "24-2-Gut-A"]
