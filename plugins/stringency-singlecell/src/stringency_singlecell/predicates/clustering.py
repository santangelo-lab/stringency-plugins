"""Predicates about the clustering step's proposal, read before it runs (plugin 0.8.6)."""

from __future__ import annotations

from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE, band

DEFAULT_LOUVAIN_MAX_CELLS = 600_000


def _input_cells(ctx: GateContext) -> int | None:
    """`n_obs` of the state object the action binds as a `seurat_object` input, matched by
    digest; None when no input is a `seurat_object` in the state or its count is not a number."""
    seurat = {
        o.digest.removeprefix("blake3:"): o
        for o in ctx.state.objects.values()
        if o.type == "seurat_object"
    }
    for digest in ctx.action.inputs.values():
        o = seurat.get(digest.removeprefix("blake3:"))
        if o is None:
            continue
        n = o.summary.get("n_obs")
        if isinstance(n, bool) or not isinstance(n, int | float):
            return None
        return int(n)
    return None


@predicate(
    id="sc.louvain_too_large",
    version=2,
    scope=["cluster_umap"],
    phase="pre",
    default=Disposition.FLAG,
    covers=["cluster_umap.cluster_method"],
    source=SOURCE,
)
def louvain_too_large(ctx: GateContext) -> Verdict:
    """The clustering step would run Seurat's Louvain on more cells than Louvain finishes in
    reasonable time (`sc.louvain_max_cells` upper bound, else 600,000). Fires when the step's
    module declares a `cluster_method` parameter, the proposed value is `seurat_louvain` (or
    absent, since that is the module's default), and the `n_obs` the extractor recorded for the
    step's input `seurat_object` is above the threshold. Louvain's time grows much faster than
    the number of cells: on the Lyons v2 spleen (1.57 million cells) it ran more than six hours
    without finishing a resolution, and the Xenium method's `docs/tissue-defaults.md` recommends
    `igraph_leiden` above about 600,000 cells. Flag: a person decides at the proposal rather
    than after hours of compute. A module without `cluster_method` is not judged: version 2
    (0.8.7), since the Xenium method's `select-resolution` shares the `cluster_umap` operation
    and only sets the identity from a stored column (version 1 flagged it as Louvain). A count
    that cannot be read is not judged either; the evidence says which. Evidence: n_cells,
    threshold, cluster_method."""
    rng = band(ctx, "sc.louvain_max_cells")
    threshold = rng[1] if rng and len(rng) > 1 else DEFAULT_LOUVAIN_MAX_CELLS
    m = ctx.project.module_for(ctx.action.module)
    if m is None or "cluster_method" not in m.declared_params:
        return Verdict(
            False,
            None,
            {
                "module": ctx.action.module,
                "threshold": threshold,
                "note": "the module declares no cluster_method parameter"
                if m is not None
                else "the module's manifest is not in the project",
            },
        )
    method = ctx.action.parameters.get("cluster_method") or "seurat_louvain"
    n_cells = _input_cells(ctx)
    ev: dict[str, Any] = {"n_cells": n_cells, "threshold": threshold, "cluster_method": method}
    if n_cells is None:
        ev["note"] = "the cell count of the input seurat_object is not in the state"
        return Verdict(False, None, ev)
    if method == "seurat_louvain" and n_cells > threshold:
        return Verdict(
            True,
            f"Seurat Louvain proposed on {n_cells:,} cells, above the {threshold:,.0f} it can "
            "cluster in reasonable time; cluster_method=igraph_leiden clusters the same SNN graph",
            ev,
        )
    return Verdict(False, None, ev)
