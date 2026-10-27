"""Predicates for the spatial domain calls (plugin 0.9.0; the Xenium method's
`open-tools-v2-plan.md` 4.6 and section 10): `call-domains` writes its facts as an
`analysis_summary` object (`domain_facts`: `n_domains`, `max_single_replicate_share`), which the
plugin's stdlib extractor carries into the state, so a predicate reads the computed diagnostic
without touching the data. Must-fire and must-pass fixtures in `tests/test_predicates.py`."""

from __future__ import annotations

from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate

from stringency_singlecell.predicates._common import SOURCE, band, objects_of_type

DEFAULT_MAX_REPLICATE_SHARE = 0.9


def _latest_fact(ctx: GateContext, key: str) -> tuple[str | None, dict[str, Any]]:
    """The name and facts of the latest `analysis_summary` in the state that holds `key` (a
    later step's summary overrides an earlier one), or (None, {}) when none does."""
    found: tuple[str | None, dict[str, Any]] = (None, {})
    for name, dom in objects_of_type(ctx, "analysis_summary"):
        if key in dom:
            found = (name, dom)
    return found


def _num(v: Any) -> float | None:
    try:
        return None if v is None or isinstance(v, bool) else float(v)
    except (TypeError, ValueError):
        return None


@predicate(
    id="spatial.domain_is_replicate",
    version=1,
    scope=["call_domains"],
    phase="post",
    default=Disposition.FLAG,
    covers=["call_domains.n_domains"],
    source=SOURCE,
)
def domain_is_replicate(ctx: GateContext) -> Verdict:
    """A domain whose cells come almost all from one replicate is a punch label, not anatomy
    (ROSC's liver caveat): `max_single_replicate_share` (the largest share of any one domain's
    cells that a single replicate holds, written by `call-domains` into its `domain_facts`) above
    the ceiling, policy `ranges.spatial.domain_replicate_share[<band>][1]`, else 0.9. The
    labelling has found the punches, not the tissue; a person decides whether a smaller
    `n_domains` or another `group_by` is the answer. Without the fact the step is not judged and
    the evidence says so. Evidence: the share, the ceiling, the number of domains."""
    name, facts = _latest_fact(ctx, "max_single_replicate_share")
    if name is None:
        return Verdict(
            False,
            None,
            {"judged": False, "reason": "no analysis_summary holds max_single_replicate_share"},
        )
    share = _num(facts.get("max_single_replicate_share"))
    n_domains = facts.get("n_domains", ctx.action.parameters.get("n_domains"))
    if share is None:
        return Verdict(
            False,
            None,
            {
                "judged": False,
                "reason": f"max_single_replicate_share in {name} is not a number",
                "max_single_replicate_share": facts.get("max_single_replicate_share"),
            },
        )
    b = band(ctx, "spatial.domain_replicate_share")
    ceiling = float(b[1]) if b and len(b) > 1 else DEFAULT_MAX_REPLICATE_SHARE
    ev = {
        "max_single_replicate_share": share,
        "threshold": ceiling,
        "n_domains": n_domains,
        "object": name,
    }
    if share > ceiling:
        return Verdict(
            True,
            f"a domain's cells come {share:.0%} from one replicate, above {ceiling:g}: a "
            "domain that is one replicate is a punch label, not anatomy",
            ev,
        )
    return Verdict(False, None, ev)
