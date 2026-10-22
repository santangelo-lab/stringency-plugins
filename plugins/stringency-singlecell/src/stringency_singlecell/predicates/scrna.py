"""Predicates for droplet and combinatorial single-cell RNA-seq (plugin 0.8.0; the engine's
`benchmark-plan.md` Phase 1): each reads a fact a module wrote into an `analysis_summary` object
(the latest in the state) against the action's parameters and the policy's ranges. A sentinel
on a computed diagnostic is a gate. Must-fire and must-pass fixtures in `tests/test_predicates.py`."""

from __future__ import annotations

from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE, band, objects_of_type


def _facts(ctx: GateContext) -> dict[str, Any]:
    """The facts of the latest `analysis_summary` in the state, merged over earlier ones (a later
    step's summary adds to, and overrides, an earlier step's)."""
    out: dict[str, Any] = {}
    for _, dom in objects_of_type(ctx, "analysis_summary"):
        out.update(dom)
    return out


def _num(v: Any) -> float | None:
    try:
        return None if v is None or isinstance(v, bool) else float(v)
    except (TypeError, ValueError):
        return None


@predicate(
    id="sc.qc_floor_above_data",
    version=1,
    scope=["qc_cells"],
    phase="pre",
    default=Disposition.BLOCK,
    covers=["qc_cells.min_genes", "qc_cells.min_counts"],
    source=SOURCE,
)
def qc_floor_above_data(ctx: GateContext) -> Verdict:
    """A QC floor above what the data holds: `min_genes` above the 99th percentile of genes per
    cell (`n_genes_p99` from the QC metrics step), or `min_counts` above `total_counts_p99`.
    Whole-transcriptome thresholds on a targeted panel retain no cells; the metrics step
    measured the distribution, so the floor is checked before a cell is dropped. Evidence: the
    floor, the percentile, the panel size."""
    facts = _facts(ctx)
    p = ctx.action.parameters
    for param, fact in (("min_genes", "n_genes_p99"), ("min_counts", "total_counts_p99")):
        floor, p99 = _num(p.get(param)), _num(facts.get(fact))
        if floor is None or p99 is None:
            continue
        if floor > p99:
            return Verdict(
                True,
                f"{param} {floor:g} is above the data's 99th percentile ({fact} {p99:g}); nearly "
                "every cell would be dropped",
                {param: floor, fact: p99, "n_genes": facts.get("n_genes")},
            )
    return Verdict(False)


@predicate(
    id="sc.normalization_depth",
    version=2,
    scope=["normalize", "select_hvg"],
    phase="pre",
    default=Disposition.FLAG,
    covers=["normalize.method", "select_hvg.flavor"],
    source=SOURCE,
)
def normalization_depth(ctx: GateContext) -> Verdict:
    """Library-size log-normalisation (or the log-based HVG flavour) proposed on shallow data:
    `median_umis_per_cell` (from the QC metrics step) below the floor, policy
    `ranges.sc.lognorm_min_median_umis[<band>][0]`, else 2000. At that depth the log transform
    inflates the variance of low-count genes and HVG selection picks noise; a depth-aware
    method (Pearson residuals, seurat_v3 on counts) is the alternative the hold names.
    Version 2 (0.8.2): a targeted panel (`is_targeted_panel` true in the facts) is not judged
    by the whole-transcriptome floor, since a few hundred genes cannot reach it however deep the
    cells are; the evidence says so and the predicate is silent (the scrnaseq method's first
    engine run, 2026-10-22, on a 320-gene fixture at a median of 1371 UMIs).
    Evidence: the method or flavour, the median, the floor, the panel flag."""
    p = ctx.action.parameters
    method = str(p.get("method") or p.get("flavor") or "")
    if method not in ("log_total", "logarea", "seurat", "cell_ranger"):
        return Verdict(False)
    facts = _facts(ctx)
    median = _num(facts.get("median_umis_per_cell"))
    if median is None:
        return Verdict(False)
    b = band(ctx, "sc.lognorm_min_median_umis")
    floor = float(b[0]) if b else 2000.0
    ev = {"method": method, "median_umis_per_cell": median, "floor": floor}
    if facts.get("is_targeted_panel") is True:
        ev["is_targeted_panel"] = True
        return Verdict(False, None, ev)
    if median < floor:
        return Verdict(
            True,
            f"{method} proposed at a median of {median:g} UMIs per cell, below {floor:g}: a "
            "depth-aware method (pearson_residuals, seurat_v3) is the alternative",
            ev,
        )
    return Verdict(False, None, ev)


@predicate(
    id="sc.pc1_single_gene",
    version=1,
    scope=["reduce_pca"],
    phase="post",
    default=Disposition.FLAG,
    covers=["reduce_pca.scale"],
    source=SOURCE,
)
def pc1_single_gene(ctx: GateContext) -> Verdict:
    """The first principal component is one gene: `pc1_top_abs_load` (the largest absolute gene
    loading on PC1, written by the PCA step) above the ceiling, policy
    `ranges.sc.pc1_top_abs_load[<band>][1]`, else 0.5. Without per-gene scaling a few abundant
    transcripts carry PC1 as a near-unit vector. Evidence: the loading and the ceiling."""
    load = _num(_facts(ctx).get("pc1_top_abs_load"))
    if load is None:
        return Verdict(False)
    b = band(ctx, "sc.pc1_top_abs_load")
    ceiling = float(b[1]) if b else 0.5
    ev = {"pc1_top_abs_load": load, "ceiling": ceiling}
    if load > ceiling:
        return Verdict(True, f"PC1's largest gene loading is {load:.3f}, above {ceiling:g}", ev)
    return Verdict(False, None, ev)


@predicate(
    id="sc.pca_depth_confounded",
    version=1,
    scope=["reduce_pca"],
    phase="post",
    default=Disposition.FLAG,
    covers=["reduce_pca.regress_out"],
    source=SOURCE,
)
def pca_depth_confounded(ctx: GateContext) -> Verdict:
    """A top principal component tracks sequencing depth: `max_top5_depth_corr` (the strongest
    absolute correlation between the top five PCs and log total counts, written by the PCA
    step) above the ceiling, policy `ranges.sc.max_top5_depth_corr[<band>][1]`, else 0.5.
    Evidence: the correlation and the ceiling."""
    corr = _num(_facts(ctx).get("max_top5_depth_corr"))
    if corr is None:
        return Verdict(False)
    b = band(ctx, "sc.max_top5_depth_corr")
    ceiling = float(b[1]) if b else 0.5
    ev = {"max_top5_depth_corr": corr, "ceiling": ceiling}
    if corr > ceiling:
        return Verdict(
            True, f"a top-5 PC correlates {corr:.3f} with sequencing depth, above {ceiling:g}", ev
        )
    return Verdict(False, None, ev)
