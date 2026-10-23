"""Predicates on the cluster annotation judgment (operation annotate_clusters; the owner,
2026-10-23: the fine label is the reviewers' free text, and a gene it names must be one the
reviewer cited for that cluster)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from stringency.predicates import Disposition, GateContext, Verdict, predicate
from stringency.predicates.context import EvidenceTable

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
