"""The cell-area join guard (ROSC defect A1).

ROSC_MTA's `AppendAreaParquet` joined `cells.parquet` to the matrix positionally through a
reversed `match()`. Same id set, different order, zero NAs: every cell area landed on the wrong
cell and the QC filter and normalisation carried it silently through eleven tissues. `qc-cells`
performs that join again, so it must prove, per execution, that it joined by key and re-checked
every value by id. The proof is the `join_verification` block in `qc_summary.json`, surfaced by
the `qc_object_set` extractor; this predicate blocks when the proof is absent or incomplete.
"""

from __future__ import annotations

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE, objects_of_type

ACCEPTED_METHODS = ("keyed_reindex_on_cell_id",)


@predicate(
    id="sc.area_join_unverified",
    version=2,
    scope=["qc_cells"],
    phase="post",
    default=Disposition.BLOCK,
    covers=["qc_cells.min_cellarea", "qc_cells.max_cellarea"],
    invariant=True,
    source=SOURCE,
)
def area_join_unverified(ctx: GateContext) -> Verdict:
    """No qc_object_set in the post state carries a complete, keyed, all-cells join
    verification."""
    sets = list(objects_of_type(ctx, "qc_object_set"))
    if not sets:
        # version 2 (0.8.1): the claim is the Xenium QC module's, which declares a
        # qc_object_set output; a droplet QC module declares none and makes no join
        m = ctx.project.module_for(ctx.action.module)
        if m is not None and not any(o.type == "qc_object_set" for o in m.outputs.values()):
            return Verdict(False, None, {"objects": []})
        return Verdict(True, "qc_cells produced no qc_object_set with a join verification", {})
    problems = []
    for name, dom in sets:
        jv = dom.get("join_verification") or {}
        why = []
        if jv.get("verified") is not True:
            why.append("verified is not true")
        if jv.get("method") not in ACCEPTED_METHODS:
            why.append(f"method {jv.get('method')!r} is not a keyed join")
        n, checked = jv.get("n_cells"), jv.get("n_cells_checked")
        if not isinstance(n, int) or n <= 0:
            why.append("n_cells missing")
        elif checked != n:
            why.append(f"checked {checked} of {n} cells")
        if not jv.get("columns_checked"):
            why.append("no columns_checked")
        if jv.get("verified_by_extractor") is False:
            why.append("extractor could not confirm the block against the punch counts")
        if why:
            problems.append({"object": name, "why": why, "join_verification": jv})
    if problems:
        return Verdict(
            True, "cell-area join not verified by key for every cell", {"problems": problems}
        )
    return Verdict(False, None, {"objects": [n for n, _ in sets]})
