"""Extractors on a synthetic bundle (always) and on the real Lyons CLP inputs (when mounted)."""

from __future__ import annotations

import json
import os
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
    not RAW.exists() or not PROJ.exists(), reason=f"{RAW} or {PROJ} not mounted"
)


@pytest.mark.institutional
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


@pytest.mark.institutional
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


import shutil as _shutil

needs_r = pytest.mark.skipif(
    _shutil.which("Rscript") is None,
    reason="extract_seurat.R needs Rscript with SeuratObject and jsonlite (the xenium-r image)",
)


@needs_r
def test_extract_seurat_envelope(tmp_path: Path, design_json: Path) -> None:
    """Build a tiny Seurat object in R, run the extractor through the same path the engine uses
    (Rscript <tool> <object> <design>), and check the envelope keys the anndata extractor also
    prints."""
    import json
    import subprocess

    tools = Path(__file__).resolve().parents[1] / "src" / "stringency_singlecell" / "tools"
    rds = tmp_path / "obj.rds"
    r = f"""
    suppressPackageStartupMessages(library(SeuratObject))
    m <- matrix(rpois(60, 3), nrow = 6, dimnames = list(paste0("g", 1:6), paste0("c", 1:10)))
    obj <- CreateSeuratObject(CreateAssay5Object(counts = as(m, "dgCMatrix")), assay = "Xenium")
    obj$punch_id <- rep(c("6-1-Liver", "24-1-Liver"), each = 5); obj$animal <- rep(c("6-1", "24-1"), each = 5)
    obj$timepoint_h <- rep(c("6", "24"), each = 5); obj$condition <- "CLP"; obj$slide <- "0076581"; obj$cell_area <- runif(10, 20, 60)
    Misc(obj, slot = "stringency") <- list(normalisation = list(method = "logarea", scale_factor = 100))
    saveRDS(obj, "{rds}")
    """
    subprocess.run(["Rscript", "-e", r], check=True)
    out = subprocess.run(
        ["Rscript", str(tools / "extract_seurat.R"), str(rds), str(design_json)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    env = json.loads(out)
    assert env["extractor"] == "sc.seurat_object@1" and env["type"] == "seurat_object"
    assert env["n_obs"] == 10 and env["n_var"] == 6
    assert set(env["fields"]) == {"obs", "obsm", "layers", "uns_flags"}
    assert "cell_area" in env["fields"]["obs"] and "counts" in env["fields"]["layers"]
    assert env["fields"]["uns_flags"]["normalisation"]["method"] == "logarea"
    assert env["counts_per_group"]["timepoint_h"]["6"]["observation"] == 5


def test_cluster_evidence_extractor(tmp_path: Path, design_json: Path) -> None:
    import csv

    root = tmp_path / "cluster_evidence"
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "cluster_evidence": 1,
                "organ": "liver",
                "species": "mouse",
                "panel": {"n_genes": 5106},
                "clustering_column": "Xenium_snn_res.0.4",
                "resolution": 0.4,
                "n_clusters": 2,
                "n_cells": 103127,
                "punches": ["6-1-Liver", "24-1-Liver"],
                "timepoint_levels": ["6", "24", "48"],
                "batch_key": "slide",
                "normalisation": {"method": "logarea", "scale_factor": 100},
            }
        )
    )
    with open(root / "cluster_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cluster", "n_cells", "pct_cells", "top_markers"])
        w.writeheader()
        w.writerow(
            {"cluster": "0", "n_cells": 60000, "pct_cells": 58.2, "top_markers": "Apoa1;Apob"}
        )
        w.writerow({"cluster": "1", "n_cells": 43127, "pct_cells": 41.8, "top_markers": "Cdh5;Kdr"})
    env = run_tool("extract_cluster_evidence", root, design_json)
    assert env["extractor"] == "sc.cluster_evidence@1" and env["type"] == "cluster_evidence"
    assert env["n_obs"] == 103127 and env["n_var"] == 5106
    assert env["fields"]["summary_columns"][0] == "cluster" and env["domain"]["cluster_ids"] == [
        "0",
        "1",
    ]
    assert env["domain"]["n_cells_in_summary"] == 103127 and env["domain"]["organ"] == "liver"
    assert "markers.csv" in env["domain"]["files_missing"]
    # a directory without the manifest is refused
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "cluster_summary.csv").write_text("cluster,n_cells\n0,1\n")
    script = TOOLS["extract_cluster_evidence"].script
    res = subprocess.run(
        [sys.executable, str(script), str(bare), str(design_json)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 1 and "manifest.json" in res.stderr


def test_batch_evidence_extractor(tmp_path: Path, design_json: Path) -> None:
    import csv

    root = tmp_path / "batch_evidence"
    root.mkdir()
    summary = {
        "batch_key": "slide",
        "shared_timepoints": ["24"],
        "knn_same_batch_excess_overall": 0.344,
        "n_clusters_flagged": 0,
        "suspected": True,
    }
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "batch_evidence": 1,
                "organ": "liver",
                "batch_key": "slide",
                "timepoint_column": "timepoint_h",
                "clustering_column": "Xenium_snn_res.0.4",
                "resolution": 0.4,
                "n_clusters": 20,
                "n_cells": 103127,
                "rule": {"knn_threshold": 0.3},
                "summary": summary,
            }
        )
    )
    cols = [
        "dataset",
        "organ",
        "n_cells",
        "n_clusters",
        "batch_key",
        "knn_same_batch_excess_overall",
        "rule_suspected",
    ]
    with open(root / "batch_overview.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerow(
            {
                "dataset": "liver",
                "organ": "liver",
                "n_cells": 103127,
                "n_clusters": 20,
                "batch_key": "slide",
                "knn_same_batch_excess_overall": 0.344,
                "rule_suspected": "true",
            }
        )
    with open(root / "batch_assessment.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cluster", "n_cells", "batch_excess"])
        w.writeheader()
        w.writerow({"cluster": "0", "n_cells": 100, "batch_excess": 0.1})
        w.writerow({"cluster": "1", "n_cells": 200, "batch_excess": 0.6})
    env = run_tool("extract_batch_evidence", root, design_json)
    assert env["extractor"] == "sc.batch_evidence@1" and env["type"] == "batch_evidence"
    assert env["n_obs"] == 103127 and env["n_var"] == 0
    assert env["fields"]["summary_columns"] == cols and "columns" not in env["fields"]
    assert env["fields"]["uns_flags"]["batch_assessment"]["suspected"] is True
    d = env["domain"]
    assert d["organ"] == "liver" and d["dataset"] == "liver" and d["n_clusters_assessed"] == 2
    assert d["rule_suspected"] is True and d["knn_same_batch_excess_overall"] == 0.344
    assert "slide_by_timepoint.csv" in d["files_missing"]
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "manifest.json").write_text(json.dumps({"batch_evidence": 1}))
    res = subprocess.run(
        [sys.executable, str(TOOLS["extract_batch_evidence"].script), str(bare), str(design_json)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 1 and "batch_overview.csv" in res.stderr


def test_shuffle_markers_tool(tmp_path: Path) -> None:
    """The negative-control generator permutes gene symbols across the marker and expression
    tables of a cluster_evidence directory and rewrites top_markers; shapes are unchanged."""
    import csv
    import subprocess
    import sys

    from stringency_singlecell import TOOLS

    src = tmp_path / "ev"
    src.mkdir()
    genes = [f"G{i}" for i in range(40)]
    (src / "manifest.json").write_text(json.dumps({"cluster_evidence": 1, "n_clusters": 2}))

    def write(name: str, fields: list[str], rows: list[dict]) -> None:
        with open(src / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    top = [
        {"cluster": str(c), "rank": str(r + 1), "gene": genes[c * 20 + r], "avg_log2FC": "1.0"}
        for c in range(2)
        for r in range(10)
    ]
    write("markers_top.csv", ["cluster", "rank", "gene", "avg_log2FC"], top)
    write(
        "markers.csv",
        ["cluster", "gene", "avg_log2FC"],
        [{k: v for k, v in r.items() if k != "rank"} for r in top],
    )
    write(
        "cluster_avg_expression.csv",
        ["gene", "0", "1"],
        [{"gene": g, "0": "1", "1": "0"} for g in genes],
    )
    write(
        "cluster_pct_expressing.csv",
        ["gene", "0", "1"],
        [{"gene": g, "0": "0.5", "1": "0.1"} for g in genes],
    )
    write(
        "cluster_summary.csv",
        ["cluster", "n_cells", "top_markers"],
        [
            {"cluster": "0", "n_cells": "10", "top_markers": "x"},
            {"cluster": "1", "n_cells": "20", "top_markers": "y"},
        ],
    )
    out = tmp_path / "generated"
    job = {"inputs": {"input": str(src)}, "params": {"seed": 3}, "outputs": {"object": str(out)}}
    subprocess.run(
        [sys.executable, str(TOOLS["shuffle_markers"].script)],
        input=json.dumps(job),
        text=True,
        check=True,
        capture_output=True,
    )
    with open(out / "markers_top.csv", newline="") as f:
        shuffled = list(csv.DictReader(f))
    assert len(shuffled) == len(top) and [r["cluster"] for r in shuffled] == [
        r["cluster"] for r in top
    ]
    assert sorted(r["gene"] for r in shuffled) == sorted(r["gene"] for r in top)
    assert sum(a["gene"] != b["gene"] for a, b in zip(shuffled, top, strict=True)) > 5
    with open(out / "cluster_avg_expression.csv", newline="") as f:
        avg = list(csv.DictReader(f))
    assert len(avg) == 40 and list(avg[0].keys()) == ["gene", "0", "1"]
    with open(out / "cluster_summary.csv", newline="") as f:
        summ = {r["cluster"]: r["top_markers"] for r in csv.DictReader(f)}
    first = {}
    for r in sorted(shuffled, key=lambda r: (r["cluster"], int(r["rank"]))):
        first.setdefault(r["cluster"], []).append(r["gene"])
    assert summ["0"] == ";".join(first["0"][:8]) and summ["1"] == ";".join(first["1"][:8])
    assert "shuffle_markers seed 3" in json.loads((out / "manifest.json").read_text())["source"]


@pytest.mark.institutional
def test_mix_batches_tool(tmp_path: Path) -> None:
    """The negative-control generator of assess-batch removes the slide structure of a
    batch_evidence directory: batch_excess zero everywhere, overall kNN excess near zero, the
    cluster count and the file set unchanged. Runs on the method's synthetic split fixture."""
    import csv
    import shutil
    import subprocess
    import sys

    from stringency_singlecell import TOOLS

    method = Path(
        os.environ.get("STRINGENCY_XENIUM_METHOD")
        or Path.home() / "github" / "stringency-xenium-method"
    )
    fixture = method / "modules" / "assess-batch" / "controls" / "fixtures" / "batch_split"
    if not fixture.exists():
        pytest.skip(f"{fixture} not present (set STRINGENCY_XENIUM_METHOD to a method checkout)")
    src = tmp_path / "split"
    shutil.copytree(fixture, src)
    out = tmp_path / "mixed"
    job = {"inputs": {"input": str(src)}, "params": {"seed": 1}, "outputs": {"object": str(out)}}
    subprocess.run(
        [sys.executable, str(TOOLS["mix_batches"].script)],
        input=json.dumps(job),
        text=True,
        check=True,
        capture_output=True,
    )
    assert sorted(p.name for p in out.iterdir()) == sorted(p.name for p in src.iterdir())
    with open(src / "batch_assessment.csv", newline="") as f:
        before = list(csv.DictReader(f))
    with open(out / "batch_assessment.csv", newline="") as f:
        after = list(csv.DictReader(f))
    assert len(after) == len(before)
    assert [r["cluster"] for r in after] == [r["cluster"] for r in before]
    assert all(float(r["batch_excess"]) == 0.0 for r in after)
    assert all(r["flagged"] == "FALSE" for r in after)
    with open(out / "batch_overview.csv", newline="") as f:
        ov = next(iter(csv.DictReader(f)))
    assert abs(float(ov["knn_same_batch_excess_overall"])) < 0.06
    assert ov["rule_suspected"] == "false" and ov["n_clusters_flagged"] == "0"
    manifest = json.loads((out / "manifest.json").read_text())
    assert "mix_batches seed=1" in manifest["source"]
    assert manifest["summary"]["suspected"] is False


def test_shuffle_column_tool(tmp_path: Path) -> None:
    """The open tools' negative-control generator permutes a design column across units: every
    row of a unit keeps one value, the multiset of unit values is unchanged, and a directory
    input is copied with its named file rewritten."""
    import csv
    import subprocess
    import sys

    from stringency_singlecell import TOOLS

    src = tmp_path / "cells.csv"
    units = {"ctrl-1": "control", "ctrl-2": "control", "24-1": "24", "24-2": "24"}
    rows = [
        {"cell_id": f"{u}_{i}", "punch_id": u, "timepoint_h": t, "cell_type": "a"}
        for u, t in units.items()
        for i in range(5)
    ]
    with open(src, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    out = tmp_path / "shuffled.csv"
    job = {"inputs": {"input": str(src)}, "params": {"seed": 2}, "outputs": {"object": str(out)}}
    subprocess.run(
        [sys.executable, str(TOOLS["shuffle_column"].script)],
        input=json.dumps(job),
        text=True,
        check=True,
        capture_output=True,
    )
    with open(out, newline="") as f:
        got = list(csv.DictReader(f))
    assert [r["cell_id"] for r in got] == [r["cell_id"] for r in rows]
    per_unit = {}
    for r in got:
        per_unit.setdefault(r["punch_id"], set()).add(r["timepoint_h"])
    assert all(len(v) == 1 for v in per_unit.values())
    assert sorted(next(iter(v)) for v in per_unit.values()) == sorted(units.values())
    # a directory input: the named file inside is rewritten, the rest copied
    d = tmp_path / "pb"
    d.mkdir()
    (d / "counts.csv").write_text("gene,s1\nA,1\n")
    with open(d / "samples.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sample", "animal", "timepoint_h"])
        w.writeheader()
        w.writerows(
            [
                {"sample": "s1", "animal": "a1", "timepoint_h": "control"},
                {"sample": "s2", "animal": "a1", "timepoint_h": "control"},
                {"sample": "s3", "animal": "a2", "timepoint_h": "24"},
            ]
        )
    out_d = tmp_path / "pb_shuffled"
    job = {
        "inputs": {"input": str(d)},
        "params": {"seed": 1, "column": "timepoint_h", "by": "animal", "file": "samples.csv"},
        "outputs": {"object": str(out_d)},
    }
    subprocess.run(
        [sys.executable, str(TOOLS["shuffle_column"].script)],
        input=json.dumps(job),
        text=True,
        check=True,
        capture_output=True,
    )
    assert (out_d / "counts.csv").read_text() == "gene,s1\nA,1\n"
    with open(out_d / "samples.csv", newline="") as f:
        s = {r["sample"]: r["timepoint_h"] for r in csv.DictReader(f)}
    # both samples of animal a1 move together; per animal the values are still one each
    assert s["s1"] == s["s2"] and sorted({s["s1"], s["s3"]}) == ["24", "control"]


def test_extract_marker_panels(tmp_path: Path, design_json: Path) -> None:
    """0.8.3: the declared panels as lineage -> genes, duplicates dropped, missing columns named."""
    f = tmp_path / "panels.csv"
    f.write_text("lineage,gene\nT,CD3E\nT,CD3D\nT,CD3E\nB,MS4A1\n")
    out = run_tool("extract_marker_panels", f, design_json)
    assert out["extractor"] == "sc.marker_panels@1" and out["type"] == "marker_panels"
    assert out["n_obs"] == 4 and out["n_var"] == 3
    assert out["fields"] == {"header": ["lineage", "gene"]} and "columns" not in out["fields"]
    assert out["domain"]["panels"] == {"T": ["CD3E", "CD3D"], "B": ["MS4A1"]}
    assert (
        out["domain"]["genes_per_lineage"] == {"T": 2, "B": 1} and out["domain"]["n_lineages"] == 2
    )
    g = tmp_path / "bad.csv"
    g.write_text("cell_type,marker\nT,CD3E\n")
    out = run_tool("extract_marker_panels", g, design_json)
    assert (
        out["domain"]["missing_required_columns"] == ["lineage", "gene"]
        and out["domain"]["panels"] == {}
    )
