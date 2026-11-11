"""Predicates for the delivery step (plugin 0.10.8; the Xenium method's `call-delivered`, its
PLAN 10.6): the module writes its facts as an `analysis_summary` (`delivery_facts`), which the
plugin's stdlib extractor carries into the state, so a predicate reads which control each
threshold came from without touching the data. Must-fire and must-pass fixtures in
`tests/test_predicates.py`."""

from __future__ import annotations

from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE, objects_of_type

# the rungs of the control ladder, in order; the first is the only one that is not a fallback
PRIMARY = "same_slide_same_tissue"


def _delivery_facts(ctx: GateContext) -> tuple[str | None, dict[str, Any]]:
    """The latest `analysis_summary` in the state that holds `threshold_groups`."""
    found: tuple[str | None, dict[str, Any]] = (None, {})
    for name, dom in objects_of_type(ctx, "analysis_summary"):
        if "threshold_groups" in dom:
            found = (name, dom)
    return found


@predicate(
    id="sc.threshold_from_fallback_control",
    version=1,
    scope=["call_delivered"],
    phase="post",
    default=Disposition.FLAG,
    covers=["call_delivered.percentile"],
    source=SOURCE,
)
def threshold_from_fallback_control(ctx: GateContext) -> Verdict:
    """A delivered call rests on its threshold, and a threshold rests on its control. When a
    slide and tissue has no control of its own, `call-delivered` takes the threshold from a
    fallback rung of the ladder (the same tissue on other slides, pooled; else another tissue
    on the same slide), and image background differs between slides and between tissues, so a
    person signs off each group thresholded that way (the owner, 2026-11-11: a flag, not a
    block). A group with no control on any rung has no threshold and its cells are uncalled;
    it is listed in the evidence and does not fire by itself. Reads `threshold_groups` of the
    module's `delivery_facts`: `[{slide, tissue, rung, control_punches, n_control_cells}]`.
    Without the fact the step is not judged and the evidence says so."""
    name, facts = _delivery_facts(ctx)
    groups = facts.get("threshold_groups")
    if name is None or not isinstance(groups, list):
        return Verdict(
            False,
            None,
            {"judged": False, "reason": "no analysis_summary holds threshold_groups"},
        )
    rows = [g for g in groups if isinstance(g, dict)]
    fallback = [g for g in rows if g.get("rung") not in (PRIMARY, None, "", "none")]
    uncalled = [g for g in rows if g.get("rung") in (None, "", "none")]
    ev = {
        "object": name,
        "n_groups": len(rows),
        "fallback": [
            {k: g.get(k) for k in ("slide", "tissue", "rung", "control_punches", "n_control_cells")}
            for g in fallback
        ],
        "without_control": [{k: g.get(k) for k in ("slide", "tissue")} for g in uncalled],
    }
    if fallback:
        named = "; ".join(
            f"{g.get('tissue')} on slide {g.get('slide')} from {g.get('rung')} "
            f"({g.get('control_punches')})"
            for g in fallback
        )
        return Verdict(
            True,
            f"{len(fallback)} of {len(rows)} slide-and-tissue group(s) took their threshold "
            f"from a control that is not their own: {named}",
            ev,
        )
    return Verdict(False, None, ev)
