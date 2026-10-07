"""Predicates on the batch-route judgment (operation assess_batch; owner decision 2026-10-07
afternoon: batch effect assessment is a judgment step with a hold before the run proceeds)."""

from __future__ import annotations

from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE


@predicate(
    id="sc.batch_route_review",
    version=1,
    scope=["assess_batch"],
    phase="post",
    default=Disposition.FLAG,
    covers=["assess_batch.*", "reduce_pca.integration"],
    source=SOURCE,
)
def batch_route_review(ctx: GateContext) -> Verdict:
    """The batch-route judgment has a consensus and the owner decides before the run moves on,
    whatever the reviewers said (the owner wants a hold here regardless of the verdict). The
    engine's flag verdicts carry the routes: `accept` clears the hold and this run continues
    without correction; `reject` closes the attempt, and the operator forks at `03_reduce` with
    the correction the owner names in the reason (`integration=harmony` by default). Does not
    fire only when the step produced no consensus (nothing to decide on). Evidence: every item's
    label, source and replicate labels and confidences, and the consensus label."""
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
    label = items[0]["label"]
    return Verdict(
        True,
        f"the batch route awaits the owner's decision (reviewers' consensus: {label}): accept "
        "continues this run without correction; reject closes it, and the operator forks at "
        "03_reduce with the correction named in your reason",
        {"items": items, "consensus_label": label},
    )
