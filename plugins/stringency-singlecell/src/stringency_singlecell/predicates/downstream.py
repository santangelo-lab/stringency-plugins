"""Predicates for the downstream tools (design 6.5 and 16; `omicsbench-assessment.md` 4.1;
backlog L54): the tests a method runs on composed cells and pseudobulk counts and the
neighbourhood statistics of a spatial dataset. All pre-phase: each reads the action's parameters
against `design.yml` (its units, replication unit, factors, batch and holdout) and the run's
history, never the data, so it is decidable before the tool runs and the person settles the
choice at the proposal. Scopes name the operations of the Xenium method's open tools
(`test_differential_expression`, `compose_cells`, `neighborhood_enrichment`, and from 0.9.0
`sweep_domains`); a method whose tools use other operation names lists them in its policy.

Version 1 of each (plugin 0.7.0, 2026-10-22). What the tools write after running
(`de_coverage.underpowered`, `test_coverage.pseudoreplication`) stays the report's; a
post-phase reading of those tables needs an extractor over the tool outputs and is not here."""

from __future__ import annotations

from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE, band

DE_OPS = ["test_differential_expression", "compose_cells"]
FINER_NAMES = {"cell", "cells", "observation", "punch", "punch_id", "sample", "spot", "nucleus"}


def _unit_rank(ctx: GateContext, name: str) -> int | None:
    """Where a unit name sits in the design's hierarchy: 0 the observation, 1 the sample, 2 the
    replication unit (or any coarser declared unit). None when the name is not a unit."""
    units = ctx.design.units
    rep = ctx.design.replication_unit
    if rep is not None and (name == rep or units.get(rep) == name or name == units.get(rep)):
        return 2
    if name in (units.get("observation"), "observation", "cell", "cells"):
        return 0
    if name in (units.get("sample"), "sample"):
        return 1
    for key, col in units.items():
        if name in (key, col):
            return 2 if key not in ("observation", "sample") else (0 if key == "observation" else 1)
    return None


@predicate(
    id="de.replication_unit",
    version=1,
    scope=DE_OPS,
    phase="pre",
    default=Disposition.BLOCK,
    covers=[f"{op}.replicate_unit" for op in DE_OPS],
    source=SOURCE,
)
def replication_unit(ctx: GateContext) -> Verdict:
    """A test whose `replicate_unit` is finer than the design's replication unit (a cell- or
    punch-level test with animals declared): the canonical silent statistical choice
    (OmicsBench; design 2.4). Fires when the design declares biological replicates and the
    proposed unit ranks below the replication unit in the design's units; the evidence names
    both. A unit the design does not know is left to `param.out_of_range`."""
    if not ctx.design.has_biological_replicates:
        return Verdict(False)
    proposed = ctx.action.parameters.get("replicate_unit")
    if proposed is None:
        return Verdict(False)
    rank = _unit_rank(ctx, str(proposed))
    if rank is None and str(proposed).lower() in FINER_NAMES:
        rank = 1 if str(proposed).lower() not in ("cell", "cells", "observation") else 0
    ev: dict[str, Any] = {
        "declared_replication_unit": ctx.design.replication_unit,
        "proposed": proposed,
        "units": dict(ctx.design.units),
    }
    if rank is not None and rank < 2:
        return Verdict(
            True,
            f"replicate_unit {proposed} is finer than the design's replication unit "
            f"{ctx.design.replication_unit}: pseudoreplication",
            ev,
        )
    return Verdict(False, None, ev)


@predicate(
    id="de.covariate_omission",
    version=1,
    scope=DE_OPS,
    phase="pre",
    default=Disposition.FLAG,
    covers=[f"{op}.factor" for op in DE_OPS],
    source=SOURCE,
)
def covariate_omission(ctx: GateContext) -> Verdict:
    """The design declares a batch variable and the test's model has no term for it: the model
    is `~ factor` with `factor` the only term the action names, and no parameter (`covariates`,
    `batch`, `block`) carries the batch or the word `batch` (0.9.0: the method's tools default
    `block` to `batch`, the declared batch column resolved from the design at run time). Flag: the person decides whether the batch is
    confounded with the factor (then nothing can be done and the reason says so) or should be
    in the model. Evidence: the declared batch, the model terms."""
    batch = list(ctx.design.batch)
    if not batch:
        return Verdict(False)
    p = ctx.action.parameters
    terms: list[str] = []
    for key in ("factor", "covariates", "batch", "block", "formula"):
        v = p.get(key)
        if isinstance(v, str):
            terms += [
                t.strip() for t in v.replace("~", " ").replace("+", ",").split(",") if t.strip()
            ]
        elif isinstance(v, list):
            terms += [str(t) for t in v]
    # 0.9.0: the value `batch` (or `design`) in `block`, `batch` or `covariates` stands for the
    # declared batch column(s), which the tool resolves from the design; the term is present
    if any(t in ("batch", "design") for t in terms):
        terms = [t for t in terms if t not in ("batch", "design")] + batch
    missing = [b for b in batch if b not in terms]
    ev = {"declared_batch": batch, "model_terms": terms}
    if missing:
        return Verdict(
            True,
            f"the design declares batch {', '.join(missing)} and the model has no term for it",
            ev,
        )
    return Verdict(False, None, ev)


@predicate(
    id="de.selection_bias",
    version=1,
    scope=DE_OPS,
    phase="pre",
    default=Disposition.FLAG,
    covers=[f"{op}.factor" for op in DE_OPS],
    source=SOURCE,
)
def selection_bias(ctx: GateContext) -> Verdict:
    """The groups compared were derived from the same data the test reads, with no split
    (design 3.3: decidable from the history, not the object): the tested `factor` is not a
    declared design factor, a clustering or labelling step precedes this one in the run, and
    the design declares no holdout. Double dipping; the person decides whether the comparison
    is descriptive. Evidence: the factor, the design factors, the deriving step."""
    factor = ctx.action.parameters.get("factor")
    if not isinstance(factor, str) or not factor:
        return Verdict(False)
    declared = set(ctx.design.factors) | {f.column for f in ctx.design.factors.values()}
    if factor in declared:
        return Verdict(False)
    deriving = [
        h.step
        for h in ctx.history
        if any(k in h.operation for k in ("cluster", "label", "annotate", "classify"))
    ]
    if not deriving or ctx.design.holdout:
        return Verdict(False)
    return Verdict(
        True,
        f"factor {factor} is not a declared design factor; it was derived in step "
        f"{deriving[-1]} from the same data, with no holdout",
        {"factor": factor, "design_factors": sorted(declared), "derived_in": deriving},
    )


@predicate(
    id="test.multiple_comparison",
    version=1,
    scope=DE_OPS,
    phase="pre",
    default=Disposition.FLAG,
    covers=[f"{op}.fdr" for op in DE_OPS],
    source=SOURCE,
)
def multiple_comparison(ctx: GateContext) -> Verdict:
    """Many tests with no correction: a `correction` or `p_adjust` parameter set to none, or an
    `fdr` threshold of 1 or more (every gene or type is called). The tools correct by default
    (`adj.P.Val`, `_fdr` columns); this fires when a parameter turns it off."""
    p = ctx.action.parameters
    for key in ("correction", "p_adjust", "adjust"):
        v = p.get(key)
        if isinstance(v, str) and v.strip().lower() in ("none", "off", "no", "false"):
            return Verdict(True, f"{key} is {v}: no multiple-comparison correction", {key: v})
        if v is False:
            return Verdict(True, f"{key} is off: no multiple-comparison correction", {key: v})
    fdr = p.get("fdr")
    try:
        if fdr is not None and float(fdr) >= 1:
            return Verdict(
                True, f"fdr {fdr} calls every test: no correction in effect", {"fdr": fdr}
            )
    except (TypeError, ValueError):
        return Verdict(False)
    return Verdict(False)


@predicate(
    id="test.assumptions_unchecked",
    version=1,
    scope=DE_OPS,
    phase="pre",
    default=Disposition.FLAG,
    covers=[f"{op}.min_samples_per_group" for op in DE_OPS],
    source=SOURCE,
)
def assumptions_unchecked(ctx: GateContext) -> Verdict:
    """A test run without the floor its assumptions need: fewer than two samples a side
    (`min_samples_per_group` below 2: a moderated t or quasi-likelihood dispersion has nothing
    to estimate from) or no floor on cells per sample (`min_cells_per_sample` of 0: a sample of
    one cell enters the model as a replicate). The policy may set the sample floor with
    `ranges.test.min_samples_per_group`. Evidence: the parameter and the floor."""
    p = ctx.action.parameters
    floor_band = band(ctx, "test.min_samples_per_group")
    floor = int(floor_band[0]) if floor_band else 2
    mspg = p.get("min_samples_per_group")
    try:
        if mspg is not None and int(mspg) < floor:
            return Verdict(
                True,
                f"min_samples_per_group {mspg} is below {floor}: the test's dispersion cannot be estimated",
                {"min_samples_per_group": mspg, "floor": floor},
            )
        mcps = p.get("min_cells_per_sample")
        if mcps is not None and int(mcps) <= 0:
            return Verdict(
                True,
                "min_cells_per_sample is 0: a sample of any size enters the model as a replicate",
                {"min_cells_per_sample": mcps},
            )
    except (TypeError, ValueError):
        return Verdict(False)
    return Verdict(False)


@predicate(
    id="spatial.neighborhood_undeclared",
    version=1,
    scope=["neighborhood_enrichment", "sweep_domains"],
    phase="pre",
    default=Disposition.BLOCK,
    covers=["neighborhood_enrichment.radius_um", "sweep_domains.k_neighbors"],
    source=SOURCE,
)
def neighborhood_undeclared(ctx: GateContext) -> Verdict:
    """The neighbourhood's scale is not a declared parameter of the step: no `radius_um`,
    `radius`, `k`, `k_neighbors`, `n_neighs` or `n_neighbors` in the action's parameters, or one
    without a positive value, and no `radii_um` whose every value is positive. A neighbourhood
    statistic with an implicit scale cannot be compared across runs. From 0.9.0 it reads
    `k_neighbors` and `radii_um` (the radius sweep) and judges `sweep_domains`, whose spatial
    graph is the domain call's scale; neither key was a parameter of any earlier step and the
    operation is new, so every earlier verdict is unchanged and the version stays 1 (the
    engine's precedent, `topo.predecessor_incomplete@1`). Evidence: the parameters seen."""
    p = ctx.action.parameters
    for key in ("radius_um", "radius", "k", "k_neighbors", "n_neighs", "n_neighbors"):
        v = p.get(key)
        try:
            if v is not None and not isinstance(v, bool) and float(v) > 0:
                return Verdict(False, None, {"scale": {key: v}})
        except (TypeError, ValueError):
            continue
    radii = p.get("radii_um")
    if isinstance(radii, str) and radii.strip():
        try:
            values = [float(r) for r in radii.split(",")]
        except ValueError:
            values = []
        if values and all(r > 0 for r in values):
            return Verdict(False, None, {"scale": {"radii_um": radii}})
    return Verdict(
        True,
        "no neighbourhood scale (radius_um, radii_um, radius, k, k_neighbors, n_neighs) is a "
        "declared parameter of this step",
        {"parameters": sorted(p)},
    )


@predicate(
    id="spatial.no_permutation_null",
    version=1,
    scope=["neighborhood_enrichment"],
    phase="pre",
    default=Disposition.BLOCK,
    covers=["neighborhood_enrichment.n_perms"],
    source=SOURCE,
)
def no_permutation_null(ctx: GateContext) -> Verdict:
    """A neighbourhood enrichment without a permutation null, or with too few permutations to
    stand on: `n_perms` (or `n_permutations`) absent, zero, or below the floor, policy
    `ranges.spatial.n_perms[<band>][0]`, else 100. Evidence: the count and the floor."""
    p = ctx.action.parameters
    floor_band = band(ctx, "spatial.n_perms")
    floor = int(floor_band[0]) if floor_band else 100
    n = p.get("n_perms", p.get("n_permutations"))
    try:
        count = int(n) if n is not None else 0
    except (TypeError, ValueError):
        count = 0
    if count < floor:
        return Verdict(
            True,
            f"{count} permutation(s) behind the enrichment null; the floor is {floor}",
            {"n_perms": n, "floor": floor},
        )
    return Verdict(False, None, {"n_perms": n, "floor": floor})
