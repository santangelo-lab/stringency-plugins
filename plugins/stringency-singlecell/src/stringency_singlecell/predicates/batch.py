"""Predicates on the batch-route judgment (operation assess_batch; owner decision 2026-10-07
afternoon: batch effect assessment is a judgment step with a hold before the run proceeds;
late afternoon: the hold asks only when the reviewers agreed, and accept means agreement)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE


@predicate(
    id="sc.batch_route_review",
    version=2,
    scope=["assess_batch"],
    phase="post",
    default=Disposition.FLAG,
    covers=["assess_batch.*", "reduce_pca.integration"],
    source=SOURCE,
)
def batch_route_review(ctx: GateContext) -> Verdict:
    """The three reviewers agreed on a batch route and the owner decides on it before the run
    moves on (owner, 2026-10-07, late afternoon; version 2 fixes the verdict semantics of v1,
    where `accept` meant "continue uncorrected" even when the reviewers had said to correct).

    Semantics by consensus state (the operator acts on the owner's verdict and reason):

    | consensus                      | hold | accept                                   | reject                        |
    |--------------------------------|------|------------------------------------------|-------------------------------|
    | agreed, proceed_uncorrected    | yes  | this run continues                       | the reason names a correction |
    | agreed, correct_batch          | yes  | a fork at 03_reduce with the recommended | the reason names the route    |
    |                                |      | correction                               |                               |
    | agreed, cannot_tell            | yes  | the reason must name the route           | the reason must name the route|
    | disagreement (accepted/override)| no  | the engine's item hold already asked;    |                               |
    |                                |      | the owner's label is the route           |                               |

    Fires only when the item's `source` is `agreed`; silent when the owner already chose the
    label at the disagreement item hold (`accepted`, `override`), when the item is unresolved,
    or when there is no consensus. Evidence: every item's label, source, replicate labels and
    confidences, the consensus label, and `recommended_correction` (the corrections the
    replicates recorded, when their structured records carry the field)."""
    if ctx.output is None or not ctx.output.consensus:
        return Verdict(False, None, {"note": "no consensus in the output bundle"})
    items: list[dict[str, Any]] = [
        {
            "item_id": it.get("item_id"),
            "label": it.get("label"),
            "source": it.get("source"),
            "replicate_labels": list(it.get("replicate_labels", [])),
            "replicate_confidence": list(it.get("replicate_confidence", [])),
        }
        for it in ctx.output.consensus
    ]
    sources = {it["source"] for it in items}
    if sources != {"agreed"}:
        return Verdict(
            False,
            None,
            {
                "note": "the route was decided at the disagreement hold or is unresolved; no second ask",
                "sources": sorted(str(s) for s in sources),
            },
        )
    label = items[0]["label"]
    recommended: list[str] = []
    for rep in ctx.output.replicates:
        recs = rep.get("items") if isinstance(rep, Mapping) else None
        if isinstance(rep, Mapping) and recs is None and "recommended_correction" in rep:
            recs = [rep]
        for rec in recs or []:
            if isinstance(rec, Mapping) and rec.get("recommended_correction"):
                recommended.append(str(rec["recommended_correction"]))
    evidence: dict[str, Any] = {"items": items, "consensus_label": label}
    if recommended:
        evidence["recommended_correction"] = recommended
    return Verdict(
        True,
        f"the batch route awaits the owner's decision (reviewers agreed: {label}): accept means "
        "you agree with the reviewers and the operator acts on that label (correct_batch: a fork "
        "at 03_reduce with the recommended correction; proceed_uncorrected: this run continues; "
        "cannot_tell: your reason must name the route); reject means you disagree and your "
        "reason names the route",
        evidence,
    )
