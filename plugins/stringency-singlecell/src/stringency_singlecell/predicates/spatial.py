"""Predicates about the punch geometry inputs."""

from __future__ import annotations

from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE, objects_of_type


def _layout_ids_for_bundle(ctx: GateContext) -> tuple[list[str] | None, dict[str, Any]]:
    """Punch ids the layout assigns to the bundle's (slide, region); None if undecidable."""
    bundles = list(objects_of_type(ctx, "xenium_bundle"))
    layouts = list(objects_of_type(ctx, "tma_layout"))
    if not bundles or not layouts:
        return None, {}
    _, b = bundles[0]
    _, lay = layouts[0]
    key = f"{b.get('slide')}/{b.get('region')}"
    regions = lay.get("regions", {})
    ids = regions.get(key)
    return (list(ids) if ids is not None else None), {"region_key": key}


@predicate(
    id="spatial.coords_missing",
    version=1,
    scope=["split_punches"],
    phase="pre",
    default=Disposition.BLOCK,
    covers=["split_punches.*"],
    source=SOURCE,
)
def coords_missing(ctx: GateContext) -> Verdict:
    """The region's coordinates input has no punches, a polygon is degenerate or unclosed, a
    layout punch for this (slide, region) has no polygon, or a polygon's id is not in the layout
    (a mislabelled selection such as `21-1-Spleen-A`)."""
    coords = list(objects_of_type(ctx, "punch_coordinates"))
    if not coords:
        return Verdict(True, "no punch_coordinates input in state", {})
    _, dom = coords[0]
    punches = list(dom.get("punches", []))
    ids = [p.get("punch_id") for p in punches]
    ev: dict[str, Any] = {"n_punches": len(punches)}
    if not punches:
        return Verdict(True, "coordinates input holds no punches", ev)
    bad = [
        p.get("punch_id")
        for p in punches
        if int(p.get("n_vertices", 0)) < 3 or (p.get("polygon") and not p.get("closed"))
    ]
    if bad:
        ev["degenerate_or_unclosed"] = bad
        return Verdict(True, "degenerate or unclosed polygon(s)", ev)
    dupes = list(dom.get("duplicate_punch_ids", []))
    if dupes:
        ev["duplicate_punch_ids"] = dupes
        return Verdict(True, "duplicate punch id(s) in the coordinates", ev)
    layout_ids, extra = _layout_ids_for_bundle(ctx)
    ev.update(extra)
    if layout_ids is None:
        return Verdict(False, None, ev)
    missing = sorted(set(layout_ids) - set(ids))
    unknown = sorted(set(ids) - set(layout_ids))
    if missing or unknown:
        ev.update({"layout_without_polygon": missing, "polygon_not_in_layout": unknown})
        return Verdict(True, "coordinates and layout disagree for this region", ev)
    return Verdict(False, None, ev)
