"""Predicates on the cluster annotation judgment (operation annotate_clusters; the owner,
2026-10-23: the fine label is the reviewers' free text, and a gene it names must be one the
reviewer cited for that cluster) and on any judgment whose vocabulary is scoped by organ (0.10.0;
the owner, 2026-10-27: "only a kidney has nephrons")."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate
from stringency.predicates.context import EvidenceTable

from stringency_singlecell import VOCABULARY_ORGANS
from stringency_singlecell.predicates._common import SOURCE

# a gene-like token: starts with a letter or digit, may carry '-' or '.' inside (H2-Ab1)
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]*")
LIST_SPLIT = re.compile(r"[;,\s]+")


def _replicate_items(ctx: GateContext) -> list[tuple[int, Mapping[str, Any]]]:
    """(replicate number, item record) for every item of every valid replicate."""
    assert ctx.output is not None
    out: list[tuple[int, Mapping[str, Any]]] = []
    for i, (rep, ok) in enumerate(
        zip(ctx.output.replicates, ctx.output.replicate_valid, strict=True), start=1
    ):
        if not ok:
            continue
        items = rep.get("items", rep.get("judgments", []))
        for it in items if isinstance(items, list) else []:
            if isinstance(it, Mapping):
                out.append((i, it))
    return out


def _gene_universe(tables: Mapping[str, EvidenceTable]) -> set[str]:
    """What the evidence tables call a gene: the row keys of a table keyed by `gene` and the
    values of any `gene` column. No gene list of the plugin's own."""
    genes: set[str] = set()
    for t in tables.values():
        if t.key_column == "gene":
            genes.update(str(k) for k in t.rows)
        if "gene" in t.columns:
            genes.update(str(r.get("gene")) for r in t.rows.values() if r.get("gene"))
    return genes


def _named_genes(text: str, universe: set[str]) -> list[str]:
    """Genes a fine label names, in order. Exact match on the symbol; a token with a digit also
    matches regardless of case (`UCP1` names `Ucp1`), since such tokens are not English words. A
    hyphenated token that is not itself a symbol (`H2-Ab1` is one) is read part by part
    (`Ucp1-high`)."""
    by_upper = {g.upper(): g for g in universe}

    def match(tok: str) -> str | None:
        if tok in universe:
            return tok
        if any(ch.isdigit() for ch in tok):
            return by_upper.get(tok.upper())
        return None

    named: list[str] = []
    for tok in TOKEN.findall(text):
        tok = tok.rstrip(".-")
        gene = match(tok)
        found = [gene] if gene is not None else [match(p) for p in tok.split("-")]
        for g in found:
            if g is not None and g not in named:
                named.append(g)
    return named


def _cited_genes(
    refs: list[Any],
    tables: Mapping[str, EvidenceTable],
    universe: set[str],
    item_id: str,
    item_key: str | None,
    items: set[str],
) -> set[str]:
    """The genes an item's citations carry evidence about for that item: a row of a gene-keyed
    table cited in a column of this item (`avg_<item>`), or a row of this item (keyed by it, or
    whose item-key column is it) whose `gene` cell is the gene or whose cited value lists it
    (`top_markers`). A citation about another item, or about no item (the organ guide's marker
    list), carries none."""
    cited: set[str] = set()
    for ref in refs:
        if not isinstance(ref, Mapping):
            continue
        t = tables.get(str(ref.get("table")))
        if t is None:
            continue
        row_key, column = str(ref.get("row")), str(ref.get("column"))
        row = t.rows.get(row_key)
        if row is None:
            continue
        suffix = column.rsplit("_", 1)[-1] if "_" in column else None
        if t.key_column == "gene" and suffix == item_id:
            cited.add(row_key)
            continue
        if suffix is not None and suffix in items and suffix != item_id:
            continue
        of_item = row_key == item_id or (
            item_key is not None and str(row.get(item_key, "")) == item_id
        )
        if not of_item:
            continue
        if row.get("gene"):
            cited.add(str(row["gene"]))
        value = row.get(column, ref.get("value"))
        cited.update(tok for tok in LIST_SPLIT.split(str(value)) if tok in universe)
    return cited


@predicate(
    id="sc.fine_label_uncited",
    version=1,
    scope=["annotate_clusters"],
    phase="post",
    default=Disposition.FLAG,
    source=SOURCE,
)
def fine_label_uncited(ctx: GateContext) -> Verdict:
    """A valid replicate's `fine_label` names a gene that the same record does not cite, as
    supporting or contradicting evidence, for its own cluster. Genes are what the step's evidence
    tables call a gene (rows of a table keyed by `gene`, values of a `gene` column), so a symbol
    off every table is not recognised, and words that are not symbols ("IFN", "stress") are
    not checked here: a named state needs the state programme evidence (`annotation-controls.md`
    in the engine repository). Abstained items and items without a fine label are skipped.
    Evidence: per replicate and item, the fine label and the genes left uncited."""
    if ctx.output is None or not ctx.output.evidence_tables:
        return Verdict(False, None, {"note": "no evidence tables in the output bundle"})
    tables = ctx.output.evidence_tables
    universe = _gene_universe(tables)
    if not universe:
        return Verdict(False, None, {"note": "no table of the step names genes"})
    m = ctx.project.module_for(ctx.action.module)
    item_key = m.judgment.item_key if m is not None and m.judgment is not None else None
    items = {str(i) for i in ctx.output.items}
    if item_key is None:  # the items table's key column: the table whose rows are the items
        item_key = next(
            (t.key_column for t in tables.values() if items and set(t.rows) == items), None
        )
    uncited: list[dict[str, Any]] = []
    checked = 0
    for rep_no, it in _replicate_items(ctx):
        fine = it.get("fine_label")
        if it.get("abstain") or not isinstance(fine, str) or not fine.strip():
            continue
        named = _named_genes(fine, universe)
        if not named:
            continue
        checked += 1
        item_id = str(it.get("item_id"))
        refs = list(it.get("supporting_evidence", [])) + list(it.get("contradicting_evidence", []))
        cited = _cited_genes(refs, tables, universe, item_id, item_key, items)
        missing = [g for g in named if g not in cited]
        if missing:
            uncited.append(
                {"replicate": rep_no, "item": item_id, "fine_label": fine, "genes": missing}
            )
    if uncited:
        return Verdict(
            True,
            "a fine label names genes its reviewer did not cite for that cluster",
            {"uncited": uncited},
        )
    return Verdict(False, None, {"fine_labels_with_genes": checked})


# The method's ORGAN_ALIASES (stringency-xenium-method modules/_pylib/annotation_evidence.py):
# the spellings a manifest or parameter uses for the vocabularies' organ names.
ORGAN_ALIASES = {
    "gut": "small_intestine",
    "sintest": "small_intestine",
    "sintestine": "small_intestine",
    "small intestine": "small_intestine",
    "lgintest": "large_intestine",
    "colon": "large_intestine",
}
UNSET_ORGAN = {"", "unset", "none", "null", "unknown"}


def canon_organ(v: object) -> str:
    """An organ in the vocabularies' spelling: lower case, underscores, the method's aliases."""
    o = str(v if v is not None else "").strip().lower()
    o = ORGAN_ALIASES.get(o, o).replace(" ", "_")
    return ORGAN_ALIASES.get(o, o)


def _set_organ(v: object) -> str | None:
    return str(v) if isinstance(v, str) and v.strip().lower() not in UNSET_ORGAN else None


def project_organ(ctx: GateContext) -> tuple[str | None, str | None]:
    """(organ as written, where it was read) for the project, or (None, None). Read in order:
    the objective's `params` (`01_merge.organ` first, then any other step's `organ`, by step
    name), then the run's history (the latest admitted step whose parameters carry `organ`),
    then the design's `organ` if the file declares one. `unset` and empty are unknown."""
    params = ctx.objective.params or {}
    steps = ["01_merge"] + sorted(k for k in params if k != "01_merge")
    for step in steps:
        organ = _set_organ((params.get(step) or {}).get("organ"))
        if organ is not None:
            return organ, f"objective.params.{step}.organ"
    for rec in reversed(ctx.history):
        organ = _set_organ(rec.params.get("organ"))
        if organ is not None:
            return organ, f"history.{rec.step}.organ"
    organ = _set_organ((ctx.design.model_extra or {}).get("organ"))
    if organ is not None:
        return organ, "design.organ"
    return None, None


@predicate(
    id="sc.label_outside_organ",
    version=1,
    scope=["annotate_clusters", "label_domains"],
    phase="post",
    default=Disposition.FLAG,
    covers=[],
    source=SOURCE,
)
def label_outside_organ(ctx: GateContext) -> Verdict:
    """A valid replicate labels an item with a vocabulary label not found in the project's organ
    (a `periportal` domain in the gut, a `hepatocyte` cluster in the lung): the label's `organs`
    in the vocabulary's map (`VOCABULARY_ORGANS`, the YAML's `organs:`) do not include the organ
    and are not `any`. The vocabulary is the step's module manifest's `vocabulary`; the organ is
    read as `project_organ` says, with the method's aliases (`gut` is `small_intestine`).
    Abstained items, labels the map leaves out, and labels outside the vocabulary (the engine's
    `judg.vocabulary_resolves`) are skipped. Not judged (`judged: false`, the reason) without an
    output, a module vocabulary with an organs map, or a known organ. Evidence: per item and
    replicate the item, label, label_organs, project_organ and replicate."""
    if ctx.output is None:
        return Verdict(False, None, {"judged": False, "reason": "no output bundle"})
    m = ctx.project.module_for(ctx.action.module)
    vocab = m.vocabulary if m is not None else None
    organs = VOCABULARY_ORGANS.get(str(vocab)) if vocab else None
    if not organs:
        return Verdict(
            False,
            None,
            {
                "judged": False,
                "reason": f"vocabulary {vocab} has no organs map",
                "vocabulary": vocab,
            },
        )
    written, source = project_organ(ctx)
    if written is None:
        return Verdict(
            False,
            None,
            {"judged": False, "reason": "the project's organ is unknown", "vocabulary": vocab},
        )
    organ = canon_organ(written)
    outside: list[dict[str, Any]] = []
    checked = 0
    for rep_no, it in _replicate_items(ctx):
        label = it.get("label")
        if it.get("abstain") or not isinstance(label, str) or label not in organs:
            continue
        checked += 1
        where = organs[label]
        if "any" in where or organ in where:
            continue
        outside.append(
            {
                "item": str(it.get("item_id")),
                "label": label,
                "label_organs": list(where),
                "project_organ": organ,
                "replicate": rep_no,
            }
        )
    ev: dict[str, Any] = {
        "vocabulary": vocab,
        "project_organ": organ,
        "organ_written": written,
        "organ_source": source,
        "labels_checked": checked,
    }
    if outside:
        first = outside[0]
        more = f" and {len(outside) - 1} more" if len(outside) > 1 else ""
        return Verdict(
            True,
            f"item {first['item']} is labelled {first['label']}, found in "
            f"{', '.join(first['label_organs'])}, not in {organ}{more}",
            {**ev, "outside": outside},
        )
    return Verdict(False, None, ev)
