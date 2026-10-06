"""Predicates about objects handed between languages (Lane F plan section 5.0, 2026-10-06)."""

from __future__ import annotations

from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE


def _by_type(ctx: GateContext, t: str) -> list[tuple[str, dict[str, Any]]]:
    return [(n, dict(o.summary)) for n, o in ctx.state.objects.items() if o.type == t]


@predicate(
    id="sc.export_mismatch",
    version=1,
    scope=["export_h5ad"],
    phase="post",
    default=Disposition.BLOCK,
    covers=["export_h5ad.*"],
    source=SOURCE,
)
def export_mismatch(ctx: GateContext) -> Verdict:
    """The h5ad written for the Python step does not match the Seurat object it came from: a
    different cell count, a different gene count, an `obs` column of the parent missing, or the
    label column the parent's state names absent. Reads the `anndata` and `seurat_object`
    summaries in the state; never the files."""
    sources = _by_type(ctx, "seurat_object")
    exports = _by_type(ctx, "anndata")
    if not sources or not exports:
        return Verdict(True, "export_h5ad left no seurat_object and anndata pair in the state", {})
    _, src = sources[-1]
    problems: list[dict[str, Any]] = []
    src_obs = set((src.get("fields") or {}).get("obs", {}).keys())
    label_col = ((src.get("domain") or {}).get("labels") or {}).get("column")
    for name, ex in exports:
        ex_obs = set((ex.get("fields") or {}).get("obs", {}).keys())
        if ex.get("n_obs") != src.get("n_obs"):
            problems.append({"object": name, "n_obs": ex.get("n_obs"), "parent_n_obs": src.get("n_obs")})
        if ex.get("n_var") != src.get("n_var"):
            problems.append({"object": name, "n_var": ex.get("n_var"), "parent_n_var": src.get("n_var")})
        missing = sorted(src_obs - ex_obs)
        if missing:
            problems.append({"object": name, "obs_missing": missing})
        if label_col and label_col not in ex_obs:
            problems.append({"object": name, "label_column_missing": label_col})
        spatial_in = "spatial" in ((src.get("fields") or {}).get("obsm") or [])
        spatial_out = "spatial" in ((ex.get("fields") or {}).get("obsm") or [])
        if spatial_in and not spatial_out:
            problems.append({"object": name, "obsm_spatial_missing": True})
    if problems:
        return Verdict(True, "the exported h5ad does not match its Seurat parent", {"problems": problems})
    return Verdict(False, None, {"n_obs": src.get("n_obs"), "exports": [n for n, _ in exports]})
