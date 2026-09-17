"""Predicates about per-punch cell counts and QC outcomes."""

from __future__ import annotations

from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE, band, objects_of_type

DEFAULT_MIN_CELLS_PER_PUNCH = 500
DEFAULT_MAX_QC_FAIL_FRACTION = 0.5


def _punches(ctx: GateContext) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for name, dom in objects_of_type(ctx, "punch_bundle_set", "qc_object_set"):
        for p in dom.get("punches", []):
            out.append((name, dict(p)))
    return out


@predicate(
    id="sc.low_cell_count",
    version=1,
    scope=["split_punches", "qc_cells"],
    phase="post",
    default=Disposition.FLAG,
    covers=["split_punches.min_transcripts", "split_punches.min_area"],
    source=SOURCE,
)
def low_cell_count(ctx: GateContext) -> Verdict:
    """A punch came out of the split or the QC with fewer cells than the policy band's floor
    (`sc.cells_per_punch`, else 500)."""
    rng = band(ctx, "sc.cells_per_punch")
    floor = rng[0] if rng else DEFAULT_MIN_CELLS_PER_PUNCH
    low = [
        {"object": name, "punch_id": p.get("punch_id"), "n_cells": p.get("n_cells")}
        for name, p in _punches(ctx)
        if p.get("n_cells") is not None and p.get("included", True) and p["n_cells"] < floor
    ]
    if low:
        return Verdict(True, "punch(es) below the cell-count floor", {"floor": floor, "low": low})
    return Verdict(False, None, {"floor": floor, "n_punches": len(_punches(ctx))})


@predicate(
    id="sc.qc_fail_fraction",
    version=1,
    scope=["qc_cells"],
    phase="post",
    default=Disposition.FLAG,
    covers=[
        "qc_cells.min_nCount",
        "qc_cells.min_nFeature",
        "qc_cells.min_cellarea",
        "qc_cells.max_cellarea",
    ],
    source=SOURCE,
)
def qc_fail_fraction(ctx: GateContext) -> Verdict:
    """The QC thresholds removed more of a punch than the policy band allows
    (`sc.qc_fail_fraction` upper bound, else 0.5)."""
    rng = band(ctx, "sc.qc_fail_fraction")
    ceiling = rng[1] if rng and len(rng) > 1 else DEFAULT_MAX_QC_FAIL_FRACTION
    high = []
    for name, dom in objects_of_type(ctx, "qc_object_set"):
        for p in dom.get("punches", []):
            ff = p.get("fail_fraction")
            if ff is not None and p.get("included", True) and ff > ceiling:
                high.append(
                    {
                        "object": name,
                        "punch_id": p.get("punch_id"),
                        "fail_fraction": ff,
                        "thresholds": p.get("thresholds", {}),
                    }
                )
    if high:
        return Verdict(
            True, "QC removed more cells than the band allows", {"ceiling": ceiling, "high": high}
        )
    return Verdict(False, None, {"ceiling": ceiling})
