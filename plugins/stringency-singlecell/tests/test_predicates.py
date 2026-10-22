"""Every singlecell predicate has a must-fire and a must-pass fixture (design 6.1)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from stringency.plugins import load_plugins
from stringency.predicates import GateContext, registry
from stringency.predicates.context import OutputBundle

from tests.helpers import (
    LIVER_0076570,
    action,
    bundle_summary,
    coords_summary,
    ctx,
    join_ok,
    layout_summary,
    manifest,
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


def _seurat(
    n_obs: int = 1000,
    n_var: int = 5106,
    obs: tuple[str, ...] = ("punch_id", "animal", "timepoint_h", "cell_type"),
    spatial: bool = True,
    label: str | None = "cell_type",
    flags: dict | None = None,
    unknown_fraction: float = 0.0,
) -> dict:
    """A seurat_object envelope as tools/extract_seurat.R prints it (Lane F plan 5.0)."""
    labels = (
        {"column": label, "vocabulary": "cell_types_mouse@1", "unknown_fraction": unknown_fraction}
        if label
        else None
    )
    return {
        "extractor": "sc.seurat_object@1",
        "type": "seurat_object",
        "n_obs": n_obs,
        "n_var": n_var,
        "fields": {
            "obs": {c: {"dtype": "character", "n_unique": 3} for c in obs},
            "obsm": (["pca", "umap"] + (["spatial"] if spatial else [])),
            "layers": ["counts", "data"],
            "uns_flags": {
                "normalisation": {"method": "logarea", "scale_factor": 100},
                "labels": labels,
                **(flags or {}),
            },
        },
        "counts_per_group": {},
        "domain": {"assay": "Xenium", "labels": labels},
    }


NORM = manifest("normalize", ("method", "scale_factor"), {"method": "logarea", "scale_factor": 100})


def _decision(sources: dict[str, str], **params) -> GateContext:
    """A normalize step whose decision points come from `sources` (default | agent | fork)."""
    values = {"method": "logarea", "scale_factor": 100, **params}
    return ctx(
        "normalize",
        {},
        act=action("normalize", sources=sources, rationale_ref="blake3:ab", **values),
        module=NORM,
    )


BATCH_SUSPECT = {
    "suspected": True,
    "rule": "knn_same_slide_excess_24h > 0.25 in clusters holding > 5% of cells",
    "batch_key": "slide",
    "n_clusters": 20,
    "n_clusters_single_batch_mixed_timepoint": 4,
    "knn_same_batch_excess_24h": 0.41,
}
BATCH_CLEAR = {**BATCH_SUSPECT, "suspected": False, "knn_same_batch_excess_24h": 0.03}


def _anndata(
    n_obs: int = 1000,
    n_var: int = 5106,
    obs: tuple[str, ...] = ("punch_id", "animal", "timepoint_h", "cell_type"),
    spatial: bool = True,
) -> dict:
    return {
        "extractor": "sc.anndata@1",
        "type": "anndata",
        "n_obs": n_obs,
        "n_var": n_var,
        "fields": {
            "obs": {c: {"dtype": "category", "n_unique": 3} for c in obs},
            "obsm": (["spatial"] if spatial else []),
            "layers": [],
            "uns_flags": {},
        },
        "counts_per_group": {},
        "domain": {},
    }


def _export(parent: dict, out: dict) -> dict:
    return {"object": obj("seurat_object", parent), "h5ad": obj("anndata", out)}


# (predicate id, must-fire ctx, must-pass ctx)
def _de(operation: str = "test_differential_expression", **params: object) -> GateContext:
    """A downstream test's action under the Lyons-shaped design (replication unit animal,
    batch slide, factors timepoint_h and condition)."""
    base: dict[str, object] = {
        "factor": "timepoint_h",
        "reference": "control",
        "replicate_unit": "animal",
        "fdr": 0.05,
        "min_samples_per_group": 2,
        "min_cells_per_sample": 30,
    }
    base.update(params)
    return ctx(operation, {}, **base)


def _derived(**params: object) -> GateContext:
    from stringency.state import StepRecord

    hist = (StepRecord(step="04_cluster", operation="cluster_umap", params={}, output_digests={}),)
    base: dict[str, object] = {
        "factor": "cluster",
        "reference": "0",
        "replicate_unit": "animal",
        "fdr": 0.05,
    }
    base.update(params)
    return ctx("test_differential_expression", {}, history=hist, **base)


def _nhood(**params: object) -> GateContext:
    base: dict[str, object] = {"factor": "timepoint_h", "radius_um": 30, "n_perms": 200, "seed": 0}
    base.update(params)
    act = action("neighborhood_enrichment", **base)
    return ctx("neighborhood_enrichment", {}, act=act)


def _summary(**facts: object) -> dict:
    return {
        "obj": obj(
            "analysis_summary",
            {"n_obs": 0, "n_var": 0, "fields": {}, "counts_per_group": {}, "domain": facts},
        )
    }


def _scrna(
    operation: str, facts: dict, phase: str = "pre", ranges: dict | None = None, **params: object
) -> GateContext:
    act = action(operation, **params)
    return ctx(operation, _summary(**facts), phase=phase, ranges=ranges, act=act)


CASES: list[tuple[str, CtxFn, CtxFn]] = [
    # droplet and combinatorial kits (plugin 0.8.0, benchmark Phase 1)
    (
        "sc.qc_floor_above_data",
        lambda: _scrna("qc_cells", {"n_genes_p99": 150, "n_genes": 386}, min_genes=200),
        lambda: _scrna("qc_cells", {"n_genes_p99": 150}, min_genes=20),
    ),
    (
        "sc.normalization_depth",
        lambda: _scrna("normalize", {"median_umis_per_cell": 1655}, method="log_total"),
        lambda: _scrna("normalize", {"median_umis_per_cell": 1655}, method="pearson_residuals"),
    ),
    (
        "sc.pc1_single_gene",
        lambda: _scrna("reduce_pca", {"pc1_top_abs_load": 0.93}, phase="post", scale=False),
        lambda: _scrna("reduce_pca", {"pc1_top_abs_load": 0.12}, phase="post", scale=True),
    ),
    (
        "sc.pca_depth_confounded",
        lambda: _scrna("reduce_pca", {"max_top5_depth_corr": 0.81}, phase="post"),
        lambda: _scrna("reduce_pca", {"max_top5_depth_corr": 0.2}, phase="post"),
    ),
    # the downstream tools (plugin 0.7.0, L54)
    (
        "de.replication_unit",
        lambda: _de(replicate_unit="punch"),
        lambda: _de(replicate_unit="animal"),
    ),
    ("de.covariate_omission", lambda: _de(), lambda: _de(covariates="slide")),
    ("de.selection_bias", lambda: _derived(), lambda: _derived(factor="timepoint_h")),
    ("test.multiple_comparison", lambda: _de(fdr=1.0), lambda: _de(fdr=0.05)),
    ("test.assumptions_unchecked", lambda: _de(min_samples_per_group=1), lambda: _de()),
    ("spatial.neighborhood_undeclared", lambda: _nhood(radius_um=None), lambda: _nhood()),
    ("spatial.no_permutation_null", lambda: _nhood(n_perms=10), lambda: _nhood()),
    (
        "sc.decision_unreviewed",
        # the operator proposed the pipeline default with a reason: a person still signs off
        lambda: _decision({"method": "agent", "scale_factor": "default"}),
        # the operator departed from the default: param.agent_proposed holds instead
        lambda: _decision({"method": "agent"}, method="log_total"),
    ),
    (
        "sc.batch_effect_suspected",
        lambda: ctx(
            "cluster_umap",
            {"obj": obj("seurat_object", _seurat(flags={"batch_assessment": BATCH_SUSPECT}))},
            phase="post",
        ),
        lambda: ctx(
            "cluster_umap",
            {"obj": obj("seurat_object", _seurat(flags={"batch_assessment": BATCH_CLEAR}))},
            phase="post",
        ),
    ),
    (
        "sc.unknown_fraction",
        lambda: ctx(
            "apply_labels",
            {"obj": obj("seurat_object", _seurat(unknown_fraction=0.31))},
            phase="post",
        ),
        lambda: ctx(
            "apply_labels",
            {"obj": obj("seurat_object", _seurat(unknown_fraction=0.05))},
            phase="post",
        ),
    ),
    (
        "qc.filter_ordering",
        lambda: ctx(
            "normalize",
            {
                "obj": obj(
                    "seurat_object",
                    _seurat(
                        flags={
                            "normalisation": {
                                "method": "logarea",
                                "scale_factor": 100,
                                "cells_filtered_after": True,
                            }
                        }
                    ),
                )
            },
            phase="post",
        ),
        lambda: ctx("normalize", {"obj": obj("seurat_object", _seurat())}, phase="post"),
    ),
    (
        "sc.export_mismatch",
        lambda: ctx(
            "export_h5ad",
            _export(_seurat(), _anndata(n_obs=990, obs=("punch_id", "animal", "timepoint_h"))),
            phase="post",
        ),
        lambda: ctx("export_h5ad", _export(_seurat(), _anndata()), phase="post"),
    ),
    (
        "sc.batch_route_review",
        # always fires once the judgment has a consensus, whatever the label (owner, 2026-10-07)
        lambda: ctx(
            "assess_batch", {}, phase="post", output=_consensus({"liver": "proceed_uncorrected"})
        ),
        # must-pass only without a consensus: nothing to decide on
        lambda: ctx("assess_batch", {}, phase="post", output=_consensus({})),
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


TWO_REGIONS = {"0076570/Liver": LIVER_0076570, "0076581/Lung": ["6-1-Lung-A", "6-2-Lung-A"]}


def _two_regions(coords: list[dict]) -> dict:
    """A multi-region project: two bundles bound, one layout over both (version 2, 2026-10-14)."""
    return {
        "bundle_a": obj("xenium_bundle", bundle_summary("0076570", "Liver")),
        "bundle_b": obj("xenium_bundle", bundle_summary("0076581", "Lung")),
        "layout": obj("tma_layout", layout_summary(TWO_REGIONS)),
        "coords": obj("punch_coordinates", coords_summary(coords)),
    }


def test_coords_missing_checks_every_bound_region() -> None:
    fn = registry.get("spatial.coords_missing").fn  # type: ignore[union-attr]
    assert registry.get("spatial.coords_missing").version == 2  # type: ignore[union-attr]
    # the first region is complete, the second lacks a polygon: version 1 passed this
    v = fn(ctx("split_punches", _two_regions(GOOD_COORDS + [punch("6-1-Lung-A")])))
    assert v.fired and v.reason == "coordinates and layout disagree for 0076581/Lung"
    assert v.evidence["layout_without_polygon"] == {"0076581/Lung": ["6-2-Lung-A"]}
    assert v.evidence["regions_checked"] == ["0076570/Liver", "0076581/Lung"]
    # every bound region covered: passes, and a polygon of an unbound region is not a mislabel
    extra = TWO_REGIONS | {"0076570/Spleen": ["24-1-Spleen-A"]}
    objs = _two_regions(
        GOOD_COORDS + [punch("6-1-Lung-A"), punch("6-2-Lung-A"), punch("24-1-Spleen-A")]
    )
    objs["layout"] = obj("tma_layout", layout_summary(extra))
    v = fn(ctx("split_punches", objs))
    assert not v.fired and v.evidence["n_polygons_for_other_regions"] == 1


def test_decision_unreviewed_the_other_cases() -> None:
    fn = registry.get("sc.decision_unreviewed").fn  # type: ignore[union-attr]
    # nobody proposed anything: the defaults were taken silently, a person signs off
    v = fn(_decision({}))
    assert v.fired and v.evidence["rationale_ref"] == "blake3:ab"
    assert v.evidence["decision_points"]["method"] == {
        "default": "logarea",
        "value": "logarea",
        "source": "default",
    }
    assert v.reason == (
        "decision points method, scale_factor were taken at their defaults; "
        "a person signs off on the choice"
    )
    # the agent proposed the defaults with a reason: the hold says so rather than "taken"
    v = fn(_decision({"method": "agent", "scale_factor": "agent"}))
    assert v.fired and v.reason.startswith("the agent proposed method logarea, scale_factor ")
    assert "the defaults; a person signs off" in v.reason
    v = fn(_decision({"method": "agent"}))
    assert v.reason.startswith("the agent proposed method logarea, the default and decision point")
    assert "scale_factor was taken at its default" in v.reason
    # every decision point is a fork's --set: a person's recorded decision, nothing opens
    assert not fn(_decision({"method": "fork", "scale_factor": "fork"}, method="log_total")).fired
    # likewise a value the objective declared or a fork's parent admitted (engine 0.2.17, 0.2.18)
    assert not fn(_decision({"method": "declared", "scale_factor": "inherited"})).fired
    assert not fn(
        _decision({"method": "fork", "scale_factor": "declared"}, method="log_total")
    ).fired
    # one point inherited and the other taken silently: the silent one still needs a person
    v = fn(_decision({"method": "inherited"}))
    assert v.fired and "scale_factor was taken at its default" in v.reason
    # one fork value and one silent default: the default still needs a sign-off
    assert fn(_decision({"method": "fork"}, method="log_total")).fired
    # a module without decision points opens nothing
    plain = manifest("normalize", (), {"method": "logarea"})
    assert not fn(
        ctx("normalize", {}, act=action("normalize", method="logarea"), module=plain)
    ).fired


def test_unknown_fraction_reads_the_policy_ceiling() -> None:
    fn = registry.get("sc.unknown_fraction").fn  # type: ignore[union-attr]
    strict = {"sc.unknown_fraction": {"strict": [0, 0.1], "standard": [0, 0.2], "wide": [0, 0.4]}}
    c = ctx(
        "apply_labels",
        {"obj": obj("seurat_object", _seurat(unknown_fraction=0.15))},
        phase="post",
        ranges=strict,
    )
    assert not fn(c).fired
    c = ctx(
        "apply_labels",
        {"obj": obj("seurat_object", _seurat(unknown_fraction=0.15))},
        phase="post",
        profile="strict",
        ranges=strict,
    )
    assert fn(c).fired


def test_coords_missing_no_input_or_empty() -> None:
    assert _run("spatial.coords_missing", ctx("split_punches", _inputs(None)))
    assert _run("spatial.coords_missing", ctx("split_punches", _inputs([])))


def test_coords_missing_polygon_not_in_layout_is_a_mislabel() -> None:
    # the 2026-09-16 export named a spleen punch `21-1-Spleen-A`; the layout says 24-1
    coords = GOOD_COORDS[:2] + [punch("21-2-Liver")]
    v = registry.get("spatial.coords_missing").fn(ctx("split_punches", _inputs(coords)))  # type: ignore[union-attr]
    assert v.fired and v.evidence["polygon_not_in_layout"] == ["21-2-Liver"]
    assert v.evidence["layout_without_polygon"] == {"0076570/Liver": ["48-2-Liver"]}


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
    out = _consensus(
        {"24-2-Gut-A": "already_excluded", "6-2-Spleen-A": "review", "6-1-Liver": "keep"}
    )
    v = registry.get("sc.exclusion_proposed").fn(
        ctx("flag_outlier_punches", {}, phase="post", output=out)
    )  # type: ignore[union-attr]
    assert v.fired and v.evidence["n_proposed"] == 1 and "review" in (v.reason or "")


def test_exclusion_proposed_is_a_flag() -> None:
    spec = registry.get("sc.exclusion_proposed")
    assert spec is not None and spec.default.value == "flag" and not spec.invariant


def test_export_mismatch_names_each_problem() -> None:
    c = ctx(
        "export_h5ad",
        _export(_seurat(), _anndata(n_obs=990, n_var=5000, obs=("punch_id",), spatial=False)),
        phase="post",
    )
    v = registry.get("sc.export_mismatch").fn(c)
    assert v.fired
    kinds = {k for p in v.evidence["problems"] for k in p if k != "object"}
    assert {
        "n_obs",
        "n_var",
        "obs_missing",
        "label_column_missing",
        "obsm_spatial_missing",
    } <= kinds


def test_export_mismatch_fires_without_a_pair() -> None:
    c = ctx("export_h5ad", {"object": obj("seurat_object", _seurat())}, phase="post")
    assert registry.get("sc.export_mismatch").fn(c).fired


REASON_V2 = (
    "the batch route awaits the owner's decision (reviewers agreed: {lab}): accept means "
    "you agree with the reviewers and the operator acts on that label (correct_batch: a fork "
    "at 03_reduce with the recommended correction; proceed_uncorrected: this run continues; "
    "cannot_tell: your reason must name the route); reject means you disagree and your "
    "reason names the route"
)


def _consensus_from(labels: dict[str, str], source: str, replicates=()) -> OutputBundle:
    out = _consensus(labels)
    items = tuple({**it, "source": source} for it in out.consensus)
    return OutputBundle(
        outputs=out.outputs, consensus=items, items=out.items, replicates=tuple(replicates)
    )


def test_batch_route_review_fires_on_every_agreed_label() -> None:
    for lab in ("proceed_uncorrected", "correct_batch", "cannot_tell"):
        v = registry.get("sc.batch_route_review").fn(
            ctx("assess_batch", {}, phase="post", output=_consensus({"liver": lab}))
        )  # type: ignore[union-attr]
        assert v.fired and v.evidence["consensus_label"] == lab
        assert v.reason == REASON_V2.format(lab=lab)
        assert v.evidence["items"][0]["replicate_labels"] == [lab, lab, lab]
        assert "recommended_correction" not in v.evidence
    v = registry.get("sc.batch_route_review").fn(ctx("assess_batch", {}, phase="post"))  # type: ignore[union-attr]
    assert not v.fired


def test_batch_route_review_silent_when_the_owner_decided_at_the_item_hold() -> None:
    for source in ("accepted", "override", "unresolved"):
        v = registry.get("sc.batch_route_review").fn(
            ctx(
                "assess_batch",
                {},
                phase="post",
                output=_consensus_from({"liver": "correct_batch"}, source),
            )
        )  # type: ignore[union-attr]
        assert not v.fired, source
        assert v.evidence["sources"] == [source]


def test_batch_route_review_carries_the_recommended_correction() -> None:
    reps = [
        {
            "items": [
                {"item_id": "liver", "label": "correct_batch", "recommended_correction": "harmony"}
            ]
        },
        {
            "items": [
                {"item_id": "liver", "label": "correct_batch", "recommended_correction": "harmony"}
            ]
        },
        {
            "items": [
                {"item_id": "liver", "label": "correct_batch", "recommended_correction": "rpca"}
            ]
        },
    ]
    v = registry.get("sc.batch_route_review").fn(
        ctx(
            "assess_batch",
            {},
            phase="post",
            output=_consensus_from({"liver": "correct_batch"}, "agreed", reps),
        )
    )  # type: ignore[union-attr]
    assert v.fired
    assert v.evidence["recommended_correction"] == ["harmony", "harmony", "rpca"]


def test_batch_effect_suspected_is_logged_not_held() -> None:
    spec = registry.get("sc.batch_effect_suspected")
    assert spec is not None and spec.version == 2
    assert str(spec.default).lower().endswith("log")


# --- the downstream predicates, the other ways they fire and pass ---------------------------


def test_replication_unit_reads_the_design_hierarchy() -> None:
    assert _run("de.replication_unit", _de(replicate_unit="cell")) is True
    assert _run("de.replication_unit", _de(replicate_unit="punch_id")) is True
    assert (
        _run("de.replication_unit", _de(operation="compose_cells", replicate_unit="punch")) is True
    )
    v = registry.get("de.replication_unit").fn(_de(replicate_unit="punch"))  # type: ignore[union-attr]
    assert v.evidence["declared_replication_unit"] == "animal" and v.evidence["proposed"] == "punch"
    assert _run("de.replication_unit", _de(replicate_unit="sheep")) is False  # left to out_of_range


def test_covariate_omission_sees_the_model_terms() -> None:
    v = registry.get("de.covariate_omission").fn(_de())  # type: ignore[union-attr]
    assert v.fired and v.evidence == {"declared_batch": ["slide"], "model_terms": ["timepoint_h"]}
    assert _run("de.covariate_omission", _de(formula="~ slide + timepoint_h")) is False
    assert _run("de.covariate_omission", _de(batch=["slide"])) is False


def test_selection_bias_needs_a_deriving_step_and_no_holdout() -> None:
    assert _run("de.selection_bias", _de(factor="cluster")) is False  # nothing derived it
    v = registry.get("de.selection_bias").fn(_derived())  # type: ignore[union-attr]
    assert v.fired and v.evidence["derived_in"] == ["04_cluster"]


def test_multiple_comparison_and_assumptions_variants() -> None:
    assert _run("test.multiple_comparison", _de(correction="none")) is True
    assert _run("test.multiple_comparison", _de(p_adjust=False)) is True
    assert _run("test.assumptions_unchecked", _de(min_cells_per_sample=0)) is True
    # the policy sets the sample floor
    c = ctx(
        "test_differential_expression",
        {},
        ranges={"test.min_samples_per_group": {"standard": [3, 1e9]}},
        factor="timepoint_h",
        min_samples_per_group=2,
    )
    assert _run("test.assumptions_unchecked", c) is True


def test_neighbourhood_variants() -> None:
    assert _run("spatial.neighborhood_undeclared", _nhood(radius_um=None, k=15)) is False
    assert _run("spatial.no_permutation_null", _nhood(n_perms=None)) is True
    c = ctx(
        "neighborhood_enrichment",
        {},
        ranges={"spatial.n_perms": {"standard": [500, 1e9]}},
        act=action("neighborhood_enrichment", radius_um=30, n_perms=200),
    )
    assert _run("spatial.no_permutation_null", c) is True


def test_scrna_predicates_read_the_policy_and_the_latest_summary() -> None:
    """Plugin 0.8.0: the floors and ceilings come from policy ranges; a missing fact is silence;
    the evidence names the floor and the data."""
    pid = "sc.normalization_depth"
    assert (
        _run(pid, _scrna("normalize", {"median_umis_per_cell": 4000}, method="log_total")) is False
    )
    c = _scrna(
        "normalize",
        {"median_umis_per_cell": 4000},
        ranges={"sc.lognorm_min_median_umis": {"standard": [5000, 1e9]}},
        method="log_total",
    )
    assert _run(pid, c) is True
    assert _run(pid, _scrna("select_hvg", {"median_umis_per_cell": 900}, flavor="seurat")) is True
    assert (
        _run(pid, _scrna("select_hvg", {"median_umis_per_cell": 900}, flavor="seurat_v3")) is False
    )
    assert _run(pid, _scrna("normalize", {}, method="log_total")) is False
    c = _scrna(
        "reduce_pca",
        {"pc1_top_abs_load": 0.4},
        phase="post",
        ranges={"sc.pc1_top_abs_load": {"standard": [0, 0.3]}},
    )
    assert _run("sc.pc1_single_gene", c) is True
    assert (
        _run(
            "sc.qc_floor_above_data", _scrna("qc_cells", {"total_counts_p99": 400}, min_counts=1000)
        )
        is True
    )
    v = registry.get("sc.qc_floor_above_data").fn(  # type: ignore[union-attr]
        _scrna("qc_cells", {"n_genes_p99": 150, "n_genes": 386}, min_genes=200)
    )
    assert v.evidence == {"min_genes": 200.0, "n_genes_p99": 150.0, "n_genes": 386}


def test_narrowed_xenium_predicates_leave_a_droplet_method_alone() -> None:
    """0.8.1: a QC module that declares no qc_object_set is not asked for a join; the retained
    count of a droplet QC step feeds low_cell_count; a decision point with a `decision:` block
    is the engine's and decision_unreviewed skips it."""
    from stringency.modules import ModuleManifest
    from stringency.pipelines import Pipeline

    droplet = ModuleManifest(
        contract=1,
        name="qc-cells",
        version="0.1.0",
        kind="deterministic",
        operation="qc_cells",
        domain="stringency-singlecell",
        env="scanpy-agent",
        outputs={"qc_object": {"type": "anndata", "format": "h5ad"}},
        params_schema={"type": "object", "properties": {}},
    )
    c = ctx("qc_cells", {}, phase="post", module=droplet)
    assert _run("sc.area_join_unverified", c) is False
    xen = ModuleManifest(
        contract=1,
        name="qc-cells",
        version="0.1.0",
        kind="deterministic",
        operation="qc_cells",
        domain="stringency-singlecell",
        env="xenium-r",
        outputs={"qc_objects": {"type": "qc_object_set", "format": "dir"}},
        params_schema={"type": "object", "properties": {}},
    )
    assert _run("sc.area_join_unverified", ctx("qc_cells", {}, phase="post", module=xen)) is True
    few = _summary(n_cells_retained=12, n_cells_in=5000)
    assert _run("sc.low_cell_count", ctx("qc_cells", few, phase="post")) is True
    many = _summary(n_cells_retained=4000, n_cells_in=5000)
    assert _run("sc.low_cell_count", ctx("qc_cells", many, phase="post")) is False
    # decision_unreviewed: the pipeline gates `method` with a decision block, scale_factor not
    pipe = Pipeline.model_validate(
        {
            "pipeline": 1,
            "name": "p",
            "version": "0.1.0",
            "domain": "stringency-singlecell",
            "answers": [],
            "steps": [
                {
                    "id": "01_step",
                    "module": "normalize@0.1.0",
                    "params": {
                        "method": {
                            "default": "logarea",
                            "options": ["logarea", "log_total"],
                            "decision": {"evidence": {"text": "x"}, "hold": "always"},
                        },
                        "scale_factor": {"default": 100, "range": [10, 10000]},
                    },
                }
            ],
        }
    )
    import dataclasses

    base = _decision({})
    c2 = dataclasses.replace(base, project=dataclasses.replace(base.project, pipeline=pipe))
    v = registry.get("sc.decision_unreviewed").fn(c2)  # type: ignore[union-attr]
    assert v.fired and list(v.evidence["decision_points"]) == ["scale_factor"]
