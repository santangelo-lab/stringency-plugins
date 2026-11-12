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
    """The latest `analysis_summary` in the state that holds `n_groups_fallback` (the flat
    facts, which the extractor carries into the state) or `threshold_groups` (the list, which
    it drops: only a state built by hand holds it)."""
    found: tuple[str | None, dict[str, Any]] = (None, {})
    for name, dom in objects_of_type(ctx, "analysis_summary"):
        if "n_groups_fallback" in dom or "threshold_groups" in dom:
            found = (name, dom)
    return found


def _from_flat_facts(name: str, facts: dict[str, Any]) -> Verdict:
    """The verdict from the flat facts `call-delivered` writes beside `threshold_groups`
    (`n_groups`, `n_groups_fallback`, `groups_fallback`, `n_groups_without_control`,
    `groups_without_control`): the extractor keeps numbers, text and booleans only."""
    try:
        n = int(facts["n_groups_fallback"])
    except (TypeError, ValueError):
        return Verdict(False, None, {"judged": False, "reason": "n_groups_fallback is not a count"})
    ev = {
        "object": name,
        "n_groups": facts.get("n_groups"),
        "n_fallback": n,
        "fallback": facts.get("groups_fallback", ""),
        "without_control": facts.get("groups_without_control", ""),
    }
    if n > 0:
        return Verdict(
            True,
            f"{n} of {facts.get('n_groups')} slide-and-tissue group(s) took their threshold from "
            f"a control that is not their own: {facts.get('groups_fallback', '')}",
            ev,
        )
    return Verdict(False, None, ev)


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
    module's `delivery_facts`: `[{slide, tissue, rung, control_punches, n_control_cells}]`;
    under the engine, whose extractor keeps only flat facts, it reads `n_groups_fallback` and
    `groups_fallback`, which the module writes beside the list. Without either the step is not
    judged and the evidence says so."""
    name, facts = _delivery_facts(ctx)
    groups = facts.get("threshold_groups")
    if name is not None and not isinstance(groups, list) and "n_groups_fallback" in facts:
        return _from_flat_facts(name, facts)
    if name is None or not isinstance(groups, list):
        return Verdict(
            False,
            None,
            {
                "judged": False,
                "reason": "no analysis_summary holds n_groups_fallback or threshold_groups",
            },
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


@predicate(
    id="sc.delivery_test_on_threshold_level",
    version=1,
    scope=["test_delivery"],
    phase="post",
    default=Disposition.FLAG,
    covers=["test_delivery.reference", "test_delivery.subset"],
    source=SOURCE,
)
def delivery_test_on_threshold_level(ctx: GateContext) -> Verdict:
    """A test of the delivered fraction that compares the level whose cells set the thresholds
    (the control the image's percentile was taken from). That level's fraction is held near
    1 - percentile by construction, 5 percent at 0.95, and its spread between replicates is
    understated, so a contrast with it is anti-conservative: a person signs it off or chooses a
    reference and a subset that leave it out (the Xenium method's review of its X6 pull
    request, 2026-11-11). Reads the flat facts of the module's `test_facts`
    `analysis_summary`: `n_contrasts_with_threshold_level`, `contrasts_with_threshold_level`,
    `threshold_levels`. Without them the step is not judged and the evidence says so."""
    found: tuple[str | None, dict[str, Any]] = (None, {})
    for obj_name, dom in objects_of_type(ctx, "analysis_summary"):
        if "n_contrasts_with_threshold_level" in dom:
            found = (obj_name, dom)
    name, facts = found
    if name is None:
        return Verdict(
            False,
            None,
            {
                "judged": False,
                "reason": "no analysis_summary holds n_contrasts_with_threshold_level",
            },
        )
    try:
        n = int(facts["n_contrasts_with_threshold_level"])
    except (TypeError, ValueError):
        return Verdict(False, None, {"judged": False, "reason": "the count is not a number"})
    ev = {
        "object": name,
        "n_contrasts": n,
        "contrasts": facts.get("contrasts_with_threshold_level", ""),
        "threshold_levels": facts.get("threshold_levels", ""),
    }
    if n > 0:
        return Verdict(
            True,
            f"{n} contrast(s) compare the level that set the thresholds "
            f"({facts.get('threshold_levels', '')}): {facts.get('contrasts_with_threshold_level', '')}; "
            "its delivered fraction is held near 1 - percentile and its spread understated",
            ev,
        )
    return Verdict(False, None, ev)
