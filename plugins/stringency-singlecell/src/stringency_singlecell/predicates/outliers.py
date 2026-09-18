"""Predicates on the outlier-punch judgment (operation flag_outlier_punches)."""

from __future__ import annotations

from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE

PROPOSING = ("exclude", "review")


@predicate(
    id="sc.exclusion_proposed",
    version=1,
    scope=["flag_outlier_punches"],
    phase="post",
    default=Disposition.FLAG,
    covers=["flag_outlier_punches.*"],
    source=SOURCE,
)
def exclusion_proposed(ctx: GateContext) -> Verdict:
    """The consensus proposes excluding or reviewing at least one punch. A flag, so under the
    standard profile the run holds here and the owner accepts or rejects the proposal before
    anything downstream binds it. Evidence: the proposed punches with their verdicts and the
    replicates' labels. Verdicts without cited cells are the engine's `judg.evidence_exists`
    (block); no plugin predicate repeats that check."""
    if ctx.output is None:
        return Verdict(False, None, {"note": "no output bundle"})
    proposed: list[dict[str, Any]] = []
    for item in ctx.output.consensus:
        label = item.get("label")
        if label in PROPOSING:
            proposed.append(
                {
                    "punch_id": item.get("item_id"),
                    "verdict": label,
                    "replicate_labels": list(item.get("replicate_labels", [])),
                    "source": item.get("source"),
                }
            )
    ev: dict[str, Any] = {
        "n_items": len(ctx.output.consensus),
        "n_proposed": len(proposed),
        "proposed": proposed,
    }
    if proposed:
        kinds = sorted({p["verdict"] for p in proposed})
        return Verdict(True, f"{len(proposed)} punch(es) proposed for {' / '.join(kinds)}", ev)
    return Verdict(False, None, ev)
