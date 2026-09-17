"""Every singlecell predicate has a must-fire and a must-pass fixture (design 6.1)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from stringency.plugins import load_plugins
from stringency.predicates import GateContext, registry

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

# (predicate id, must-fire ctx, must-pass ctx)
CASES: list[tuple[str, CtxFn, CtxFn]] = [
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
