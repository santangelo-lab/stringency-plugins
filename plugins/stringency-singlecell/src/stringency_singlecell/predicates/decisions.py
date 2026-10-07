"""Predicates about the person's sign-off on analysis decisions and about what the clustering
shows (Lane F upstream pipeline, owner decisions 2026-10-07)."""

from __future__ import annotations

from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE, band


def _latest_seurat(ctx: GateContext) -> dict[str, Any] | None:
    objs = [dict(o.summary) for o in ctx.state.objects.values() if o.type == "seurat_object"]
    return objs[-1] if objs else None


def _uns(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not summary:
        return {}
    flags = (summary.get("fields") or {}).get("uns_flags") or {}
    return dict(flags) if isinstance(flags, dict) else {}


@predicate(
    id="sc.decision_unreviewed",
    version=1,
    scope=["normalize", "cluster_umap"],
    phase="pre",
    default=Disposition.FLAG,
    covers=[
        "normalize.method",
        "normalize.scale_factor",
        "cluster_umap.ndim",
        "cluster_umap.resolution",
    ],
    source=SOURCE,
)
def decision_unreviewed(ctx: GateContext) -> Verdict:
    """Every decision point gets a person's sign-off, even at the pipeline default (owner,
    2026-10-07). `param.agent_proposed` holds when the agent departs from a default; this
    predicate holds in the complementary case, so a step with decision points opens exactly one
    hold: when no decision point is an agent proposal that departs from its default. A fork's
    `--set` is a person's recorded decision, so a step whose decision points all come from a fork
    opens nothing. Evidence: each decision point's default, value and source, and the agent's
    rationale reference when it stated one."""
    m = ctx.project.module_for(ctx.action.module)
    if m is None or not m.decision_points:
        return Verdict(False)
    step = (
        ctx.project.pipeline.step(ctx.action.step_id)
        if ctx.project.pipeline is not None and ctx.project.pipeline.has_step(ctx.action.step_id)
        else None
    )
    points: dict[str, dict[str, Any]] = {}
    departing: list[str] = []
    all_fork = True
    for name in m.decision_points:
        default: Any = None
        if step is not None and name in step.params:
            default = step.params[name].default
        elif name in m.declared_params:
            schema = m.declared_params[name]
            default = schema.get("default") if isinstance(schema, dict) else None
        value = ctx.action.parameters.get(name, default)
        source = ctx.action.param_source.get(name, "default")
        points[name] = {"default": default, "value": value, "source": source}
        if source == "agent" and value != default:
            departing.append(name)
        if source != "fork":
            all_fork = False
    if departing or all_fork:
        return Verdict(False, None, {"decision_points": points, "departing": departing})
    names = ", ".join(sorted(points))
    return Verdict(
        True,
        f"decision points {names} were taken at their defaults; a person signs off on the choice",
        {"decision_points": points, "rationale_ref": ctx.action.rationale_ref},
    )


@predicate(
    id="sc.batch_effect_suspected",
    version=2,
    scope=["cluster_umap"],
    phase="post",
    default=Disposition.LOG,
    covers=["cluster_umap.*", "reduce_pca.integration"],
    source=SOURCE,
)
def batch_effect_suspected(ctx: GateContext) -> Verdict:
    """The clustering step assessed batch structure (composition per slide, nearest-neighbour
    same-slide fraction within the time point both slides carry) and wrote
    `misc$stringency$batch_assessment` with `suspected` from a declared rule. Since 0.4.0 this
    is the RECORD of that rule, logged and not held (owner, 2026-10-07 afternoon): the batch
    route is decided by the `assess_batch` judgment that follows and its always-open hold
    (`sc.batch_route_review`). Version 1 opened a flag hold here."""
    ba = _uns(_latest_seurat(ctx)).get("batch_assessment")
    if not isinstance(ba, dict):
        return Verdict(False, None, {"batch_assessment": None})
    if ba.get("suspected") is True:
        return Verdict(
            True,
            "the clustering module's rule finds a batch structure the time points do not explain; "
            "logged, not held: the assess_batch judgment and its hold decide the route",
            {"batch_assessment": ba},
        )
    return Verdict(False, None, {"batch_assessment": ba})


@predicate(
    id="sc.unknown_fraction",
    version=1,
    scope=["apply_labels"],
    phase="post",
    default=Disposition.FLAG,
    covers=["annotate_clusters.*"],
    source=SOURCE,
)
def unknown_fraction(ctx: GateContext) -> Verdict:
    """After the labels are applied, the fraction of cells labelled `unknown` exceeds the policy
    ceiling (`ranges.sc.unknown_fraction[<band>][1]`, 0.2 when the policy has none): the organ
    is poorly resolved at this clustering and a person decides whether to recluster or proceed."""
    summ = _latest_seurat(ctx)
    labels = ((summ or {}).get("domain") or {}).get("labels") or {}
    frac = labels.get("unknown_fraction")
    if frac is None:
        return Verdict(False, None, {"labels": labels})
    rng = band(ctx, "sc.unknown_fraction")
    ceiling = float(rng[1]) if rng else 0.2
    if float(frac) > ceiling:
        return Verdict(
            True,
            f"{float(frac):.3f} of cells are labelled unknown, above the ceiling {ceiling:g}",
            {"unknown_fraction": frac, "ceiling": ceiling, "labels": labels},
        )
    return Verdict(False, None, {"unknown_fraction": frac, "ceiling": ceiling})


@predicate(
    id="qc.filter_ordering",
    version=1,
    scope=["normalize", "reduce_pca", "cluster_umap"],
    phase="post",
    default=Disposition.FLAG,
    covers=["normalize.*"],
    source=SOURCE,
)
def filter_ordering(ctx: GateContext) -> Verdict:
    """Cells were removed after normalisation (`misc$stringency$normalisation$cells_filtered_after`
    is true), so the normalised values and any size factors no longer describe the population
    the downstream steps see. The QC step owns all cell filtering (Lyons decision 2026-09-17)."""
    norm = _uns(_latest_seurat(ctx)).get("normalisation")
    if not isinstance(norm, dict):
        return Verdict(False, None, {"normalisation": None})
    if norm.get("cells_filtered_after") is True:
        return Verdict(
            True,
            "cells were filtered after normalisation; the normalised values no longer match the population",
            {"normalisation": norm},
        )
    return Verdict(False, None, {"normalisation": norm})
