"""Every singlecell predicate has a must-fire and a must-pass fixture (design 6.1)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from stringency.plugins import load_plugins
from stringency.predicates import GateContext, registry
from stringency.predicates.context import OutputBundle

from tests.helpers import (
    LIVER_0076570,
    bundle_summary,
    coords_summary,
    ctx,
    join_ok,
    layout_summary,
    obj,
    punch,
    qc_summary,
    set_summary,
)

load_plugins(refresh=True)

CtxFn = Callable[[], GateContext]


def _inputs(coords: list[dict] | None, *, layout: bool = True) -> dict:
    objs = {"bundle": obj("xenium_bundle", bundle_summary())}
    if layout:
        objs["layout"] = obj("tma_layout", layout_summary())
    if coords is not None:
        objs["coords"] = obj("punch_coordinates", coords_summary(coords))
    return objs


GOOD_COORDS = [punch(p) for p in LIVER_0076570]

def _seurat(n_obs: int = 1000, n_var: int = 5106, obs: tuple[str, ...] = ("punch_id", "animal", "timepoint_h", "cell_type"), spatial: bool = True, label: str | None = "cell_type") -> dict:
    """A seurat_object envelope as tools/extract_seurat.R prints it (Lane F plan 5.0)."""
    return {
        "extractor": "sc.seurat_object@1", "type": "seurat_object", "n_obs": n_obs, "n_var": n_var,
        "fields": {"obs": {c: {"dtype": "character", "n_unique": 3} for c in obs},
                   "obsm": (["pca", "umap"] + (["spatial"] if spatial else [])), "layers": ["counts", "data"],
                   "uns_flags": {"normalisation": {"method": "logarea", "scale_factor": 100}, "labels": {"column": label, "vocabulary": "cell_types_liver@1"} if label else None}},
        "counts_per_group": {}, "domain": {"assay": "Xenium", "labels": {"column": label, "vocabulary": "cell_types_liver@1"} if label else None},
    }


def _anndata(n_obs: int = 1000, n_var: int = 5106, obs: tuple[str, ...] = ("punch_id", "animal", "timepoint_h", "cell_type"), spatial: bool = True) -> dict:
    return {"extractor": "sc.anndata@1", "type": "anndata", "n_obs": n_obs, "n_var": n_var,
            "fields": {"obs": {c: {"dtype": "category", "n_unique": 3} for c in obs}, "obsm": (["spatial"] if spatial else []), "layers": [], "uns_flags": {}},
            "counts_per_group": {}, "domain": {}}


def _export(parent: dict, out: dict) -> dict:
    return {"object": obj("seurat_object", parent), "h5ad": obj("anndata", out)}


# (predicate id, must-fire ctx, must-pass ctx)
CASES: list[tuple[str, CtxFn, CtxFn]] = [
    (
        "sc.export_mismatch",
        lambda: ctx("export_h5ad", _export(_seurat(), _anndata(n_obs=990, obs=("punch_id", "animal", "timepoint_h"))), phase="post"),
        lambda: ctx("export_h5ad", _export(_seurat(), _anndata()), phase="post"),
    ),
    (
        "sc.exclusion_proposed",
        lambda: ctx(
            "flag_outlier_punches",
            {},
            phase="post",
            output=_consensus({"6-2-Spleen-A": "exclude", "6-1-Liver": "keep"}),
        ),
        lambda: ctx(
            "flag_outlier_punches",
            {},
            phase="post",
            output=_consensus({"24-2-Gut-A": "already_excluded", "6-1-Liver": "keep"}),
        ),
    ),
    (
        "spatial.coords_missing",
        lambda: ctx("split_punches", _inputs(GOOD_COORDS[:2])),  # 48-2-Liver has no polygon
        lambda: ctx("split_punches", _inputs(GOOD_COORDS)),
    ),
    (
        "sc.low_cell_count",
        lambda: ctx(
            "split_punches",
            {"set": obj("punch_bundle_set", set_summary({"24-2-Liver": 9000, "48-1-Liver": 120}))},
            phase="post",
        ),
        lambda: ctx(
            "split_punches",
            {"set": obj("punch_bundle_set", set_summary({"24-2-Liver": 9000, "48-1-Liver": 8000}))},
            phase="post",
        ),
    ),
    (
        "sc.qc_fail_fraction",
        lambda: ctx(
            "qc_cells",
            {
                "qc": obj(
                    "qc_object_set",
                    qc_summary([("24-2-Liver", 9000, 8500), ("48-1-Liver", 8000, 2000)]),
                )
            },
            phase="post",
        ),
        lambda: ctx(
            "qc_cells",
            {
                "qc": obj(
                    "qc_object_set",
                    qc_summary([("24-2-Liver", 9000, 8500), ("48-1-Liver", 8000, 7000)]),
                )
            },
            phase="post",
        ),
    ),
    (
        "sc.area_join_unverified",
        lambda: ctx(
            "qc_cells",
            {
                "qc": obj(
                    "qc_object_set",
                    qc_summary(
                        [("24-2-Liver", 9000, 8500)],
                        join={
                            "method": "positional",
                            "verified": True,
                            "n_cells": 9000,
                            "n_cells_checked": 9000,
                            "columns_checked": ["cell_area"],
                        },
                    ),
                )
            },
            phase="post",
        ),
        lambda: ctx(
            "qc_cells",
            {"qc": obj("qc_object_set", qc_summary([("24-2-Liver", 9000, 8500)]))},
            phase="post",
        ),
    ),
]


def _run(pid: str, c: GateContext) -> bool:
    spec = registry.get(pid)
    assert spec is not None, pid
    assert spec.in_phase(c.phase), f"{pid} not in phase {c.phase}"
    assert spec.in_scope(c.action.operation), f"{pid} not in scope for {c.action.operation}"
    return spec.fn(c).fired


@pytest.mark.parametrize("pid,fire,pass_", CASES, ids=[c[0] for c in CASES])
def test_must_fire_and_must_pass(pid: str, fire: CtxFn, pass_: CtxFn) -> None:
    assert _run(pid, fire()) is True, f"{pid} should fire"
    assert _run(pid, pass_()) is False, f"{pid} should pass"


def test_every_plugin_predicate_has_a_case() -> None:
    mine = {s.id for s in registry.all() if s.source == "stringency-singlecell"}
    assert mine == {c[0] for c in CASES}


# --- coords_missing, the other ways it fires ------------------------------------------------


def test_coords_missing_no_input_or_empty() -> None:
    assert _run("spatial.coords_missing", ctx("split_punches", _inputs(None)))
    assert _run("spatial.coords_missing", ctx("split_punches", _inputs([])))


def test_coords_missing_polygon_not_in_layout_is_a_mislabel() -> None:
    # the 2026-09-16 export named a spleen punch `21-1-Spleen-A`; the layout says 24-1
    coords = GOOD_COORDS[:2] + [punch("21-2-Liver")]
    v = registry.get("spatial.coords_missing").fn(ctx("split_punches", _inputs(coords)))  # type: ignore[union-attr]
    assert v.fired and v.evidence["polygon_not_in_layout"] == ["21-2-Liver"]
    assert v.evidence["layout_without_polygon"] == ["48-2-Liver"]


def test_coords_missing_passes_with_other_regions_polygons() -> None:
    """The coordinates directory holds every punch of every region (42 files on 2026-09-17);
    polygons that the layout assigns to other regions are expected, not a mislabel. This is the
    case that blocked the first real run."""
    from tests.helpers import layout_summary, obj

    regions = {"0076570/Liver": LIVER_0076570, "0076570/Spleen": ["24-2-Spleen-A", "48-1-Spleen-A"]}
    inputs = _inputs(GOOD_COORDS + [punch("24-2-Spleen-A"), punch("48-1-Spleen-A")])
    inputs["layout"] = obj("tma_layout", layout_summary(regions))
    v = registry.get("spatial.coords_missing").fn(ctx("split_punches", inputs))  # type: ignore[union-attr]
    assert not v.fired and v.evidence["n_polygons_for_other_regions"] == 2
    # a polygon on no region at all still fires
    inputs = _inputs(GOOD_COORDS + [punch("21-1-Spleen-A")])
    inputs["layout"] = obj("tma_layout", layout_summary(regions))
    v = registry.get("spatial.coords_missing").fn(ctx("split_punches", inputs))  # type: ignore[union-attr]
    assert v.fired and v.evidence["polygon_not_in_layout"] == ["21-1-Spleen-A"]


def test_coords_missing_degenerate_or_unclosed() -> None:
    bad = GOOD_COORDS[:2] + [punch("48-2-Liver", n_vertices=2)]
    assert _run("spatial.coords_missing", ctx("split_punches", _inputs(bad)))
    bad = GOOD_COORDS[:2] + [punch("48-2-Liver", closed=False)]
    assert _run("spatial.coords_missing", ctx("split_punches", _inputs(bad)))


def test_coords_missing_undecidable_without_layout_passes_when_polygons_exist() -> None:
    assert not _run(
        "spatial.coords_missing", ctx("split_punches", _inputs(GOOD_COORDS[:1], layout=False))
    )


# --- bands from the policy ----------------------------------------------------------------


def test_low_cell_count_reads_policy_band() -> None:
    ranges = {
        "sc.cells_per_punch": {"strict": [2000, 1e9], "standard": [500, 1e9], "wide": [100, 1e9]}
    }
    s = {"set": obj("punch_bundle_set", set_summary({"a": 1500}))}
    assert _run(
        "sc.low_cell_count", ctx("split_punches", s, phase="post", profile="strict", ranges=ranges)
    )
    assert not _run(
        "sc.low_cell_count",
        ctx("split_punches", s, phase="post", profile="standard", ranges=ranges),
    )


def test_qc_fail_fraction_reads_policy_band() -> None:
    ranges = {"sc.qc_fail_fraction": {"strict": [0, 0.2], "standard": [0, 0.5], "wide": [0, 0.8]}}
    s = {"qc": obj("qc_object_set", qc_summary([("a", 1000, 700)]))}
    assert _run(
        "sc.qc_fail_fraction", ctx("qc_cells", s, phase="post", profile="strict", ranges=ranges)
    )
    assert not _run(
        "sc.qc_fail_fraction", ctx("qc_cells", s, phase="post", profile="standard", ranges=ranges)
    )


def test_excluded_punches_do_not_flag() -> None:
    s = {"qc": obj("qc_object_set", qc_summary([("a", 1000, 100)], excluded=("a",)))}
    assert not _run("sc.qc_fail_fraction", ctx("qc_cells", s, phase="post"))
    assert not _run("sc.low_cell_count", ctx("qc_cells", s, phase="post"))


# --- the A1 guard, each way it can be incomplete -------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {**join_ok(9000), "verified": False},
        {**join_ok(9000), "n_cells_checked": 8999},
        {**join_ok(9000), "columns_checked": []},
        {**join_ok(9000), "method": "match_positional"},
        {**join_ok(9000), "verified_by_extractor": False},
    ],
    ids=["absent", "not-verified", "partial", "no-columns", "positional", "extractor-refused"],
)
def test_area_join_unverified_variants(bad: dict) -> None:
    s = {"qc": obj("qc_object_set", qc_summary([("24-2-Liver", 9000, 8500)], join=bad))}
    assert _run("sc.area_join_unverified", ctx("qc_cells", s, phase="post"))


def test_area_join_unverified_when_no_qc_object() -> None:
    assert _run("sc.area_join_unverified", ctx("qc_cells", {}, phase="post"))


def test_area_join_is_invariant_and_blocks() -> None:
    spec = registry.get("sc.area_join_unverified")
    assert spec is not None and spec.invariant and spec.default.value == "block"


# --- sc.exclusion_proposed: the judgment's consensus proposes at least one exclusion/review -----


def _consensus(labels: dict[str, str]) -> OutputBundle:
    from stringency.predicates.context import OutputInfo

    items = tuple(
        {
            "item_id": pid,
            "label": lab,
            "ontology_id": None,
            "source": "agreed",
            "replicate_labels": [lab, lab, lab],
            "replicate_confidence": ["high", "high", "medium"],
            "review_id": None,
            "hold_id": None,
            "notes": [],
        }
        for pid, lab in labels.items()
    )
    return OutputBundle(
        outputs={"consensus": OutputInfo("consensus", "consensus", "x", "blake3:00")},
        consensus=items,
        items=tuple(labels),
    )


def test_exclusion_proposed_fires_on_exclude_or_review() -> None:
    for lab in ("exclude", "review"):
        out = _consensus(
            {"24-2-Gut-A": "already_excluded", "6-2-Spleen-A": lab, "6-1-Liver": "keep"}
        )
        v = registry.get("sc.exclusion_proposed").fn(
            ctx("flag_outlier_punches", {}, phase="post", output=out)
        )  # type: ignore[union-attr]
        assert v.fired and v.evidence["n_proposed"] == 1
        assert v.evidence["proposed"][0]["punch_id"] == "6-2-Spleen-A"
        assert v.evidence["proposed"][0]["verdict"] == lab


def test_exclusion_proposed_passes_when_nothing_proposed() -> None:
    out = _consensus({"24-2-Gut-A": "already_excluded", "6-1-Liver": "keep", "6-2-Liver": "keep"})
    v = registry.get("sc.exclusion_proposed").fn(
        ctx("flag_outlier_punches", {}, phase="post", output=out)
    )  # type: ignore[union-attr]
    assert not v.fired and v.evidence["n_items"] == 3
    assert not _run("sc.exclusion_proposed", ctx("flag_outlier_punches", {}, phase="post"))


def test_exclusion_proposed_fires_on_v2_review_only_consensus() -> None:
    out = _consensus({"24-2-Gut-A": "already_excluded", "6-2-Spleen-A": "review", "6-1-Liver": "keep"})
    v = registry.get("sc.exclusion_proposed").fn(
        ctx("flag_outlier_punches", {}, phase="post", output=out)
    )  # type: ignore[union-attr]
    assert v.fired and v.evidence["n_proposed"] == 1 and "review" in (v.reason or "")


def test_exclusion_proposed_is_a_flag() -> None:
    spec = registry.get("sc.exclusion_proposed")
    assert spec is not None and spec.default.value == "flag" and not spec.invariant


def test_export_mismatch_names_each_problem() -> None:
    c = ctx("export_h5ad", _export(_seurat(), _anndata(n_obs=990, n_var=5000, obs=("punch_id",), spatial=False)), phase="post")
    v = registry.get("sc.export_mismatch").fn(c)
    assert v.fired
    kinds = {k for p in v.evidence["problems"] for k in p if k != "object"}
    assert {"n_obs", "n_var", "obs_missing", "label_column_missing", "obsm_spatial_missing"} <= kinds


def test_export_mismatch_fires_without_a_pair() -> None:
    c = ctx("export_h5ad", {"object": obj("seurat_object", _seurat())}, phase="post")
    assert registry.get("sc.export_mismatch").fn(c).fired
