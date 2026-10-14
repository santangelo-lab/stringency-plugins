"""Predicates about the punch geometry inputs."""

from __future__ import annotations

from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE, objects_of_type


def _layout_by_region(ctx: GateContext) -> tuple[dict[str, list[str]] | None, set[str]]:
    """The layout's punch ids by `slide/region` key for every `xenium_bundle` in the state (None
    when there is no bundle or no layout), and every punch id the layout knows on any region."""
    bundles = list(objects_of_type(ctx, "xenium_bundle"))
    layouts = list(objects_of_type(ctx, "tma_layout"))
    if not bundles or not layouts:
        return None, set()
    _, lay = layouts[0]
    regions = lay.get("regions", {})
    by_region: dict[str, list[str]] = {}
    for _, b in bundles:
        key = f"{b.get('slide')}/{b.get('region')}"
        ids = regions.get(key)
        by_region[key] = list(ids) if ids is not None else []
    all_ids = {str(p.get("punch_id")) for p in lay.get("punches", [])}
    for region_ids in regions.values():
        all_ids.update(str(i) for i in region_ids)
    return by_region, all_ids


@predicate(
    id="spatial.coords_missing",
    version=2,
    scope=["split_punches"],
    phase="pre",
    default=Disposition.BLOCK,
    covers=["split_punches.*"],
    source=SOURCE,
)
def coords_missing(ctx: GateContext) -> Verdict:
    """The coordinates input has no punches, a polygon is degenerate or unclosed, a punch id is
    duplicated, a layout punch of any bound region has no polygon, or a polygon's id is not in the
    layout on any region (a mislabelled selection such as `21-1-Spleen-A`). Version 2 (2026-10-14,
    code review P1.3) checks every `xenium_bundle` in the state, not the first: a multi-region
    project (`xenium-qc-tma`, sixteen bundles) was validated on one region before execution and
    left the rest to the splitter. The evidence names each region that disagrees. Polygons that
    belong to regions this project does not bind are expected: the coordinates input is one
    directory for the whole slide set."""
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
    by_region, all_layout_ids = _layout_by_region(ctx)
    if by_region is None:
        return Verdict(False, None, ev)
    ev["regions_checked"] = sorted(by_region)
    have = set(ids)
    missing = {k: sorted(set(v) - have) for k, v in by_region.items() if set(v) - have}
    unknown = sorted(have - all_layout_ids)
    bound_ids = {i for v in by_region.values() for i in v}
    ev["n_polygons_for_other_regions"] = len((have & all_layout_ids) - bound_ids)
    if missing or unknown:
        ev.update({"layout_without_polygon": missing, "polygon_not_in_layout": unknown})
        where = ", ".join(sorted(missing)) if missing else "the bound regions"
        return Verdict(True, f"coordinates and layout disagree for {where}", ev)
    return Verdict(False, None, ev)
