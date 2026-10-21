"""stringency-singlecell: domain plugin for single-cell and spatial (Xenium) analysis.

Object types: `xenium_bundle` (a region bundle), `punch_coordinates` (the hand-drawn selections),
`tma_layout` (the transcribed TMA map), `punch_bundle_set` (one bundle per punch after the
split), `qc_object_set` (QC'd objects plus `qc_summary.json`), `anndata` (an h5ad object) and
`seurat_object` (a Seurat v5 `.rds`, read by an R extractor inside the module's image; 0.2.0) and
`cluster_evidence` (the tables the annotation judgment reads; 0.3.0) and `batch_evidence` (the
tables the batch-route judgment reads; 0.4.0). The QC and upstream
operations are typed, and from 0.6.0 the open tools' operations (extract_cells, compose_cells,
plot_composition, test_differential_expression, score_pathways, neighborhood_enrichment,
infer_cell_communication); the niche and report ones are provisional. The open tools write plain
types (`cell_table`, `punch_table`, `pseudobulk_set`, `proportion_table`; spec/object-types.md)
that need no extractor.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from stringency.plugins import ObjectType, Operation, Plugin, Tool

from stringency_singlecell import phrasing
from stringency_singlecell.schemas import DEFAULTS, DESIGN_SCHEMA, OBJECTIVE_QUESTIONS, OPERATIONS

NAME = "stringency-singlecell"
VERSION = "0.7.0"
_HERE = Path(__file__).parent
_TOOLS = _HERE / "tools"


def _load_vocabularies() -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    for f in sorted((_HERE / "vocabularies").glob("*.yml")):
        data = yaml.safe_load(f.read_text()) or {}
        name, version, labels = (
            data.get("name", f.stem),
            data.get("version", "0"),
            data.get("labels", []),
        )
        out[f"{name}@{version}"] = tuple(str(x) for x in labels)
    return out


def _ot(name: str, extractor: str) -> ObjectType:
    return ObjectType(name=name, extractor=extractor, extractor_id=f"sc.{name}@1")


OBJECT_TYPES = {
    "xenium_bundle": _ot("xenium_bundle", "extract_xenium_bundle"),
    "punch_coordinates": _ot("punch_coordinates", "extract_punch_coordinates"),
    "tma_layout": _ot("tma_layout", "extract_tma_layout"),
    "punch_bundle_set": _ot("punch_bundle_set", "extract_punch_bundle_set"),
    "qc_object_set": _ot("qc_object_set", "extract_qc_object_set"),
    "anndata": _ot("anndata", "extract_anndata"),
    "qc_metrics_table": _ot("qc_metrics_table", "extract_qc_metrics_table"),
    "seurat_object": _ot("seurat_object", "extract_seurat"),
    "cluster_evidence": _ot("cluster_evidence", "extract_cluster_evidence"),
    "batch_evidence": _ot("batch_evidence", "extract_batch_evidence"),
}

TOOLS = {
    name: Tool(name, _TOOLS / f"{name}.py", env=None)
    for name in (
        "extract_xenium_bundle",
        "extract_punch_coordinates",
        "extract_tma_layout",
        "extract_punch_bundle_set",
        "extract_qc_object_set",
        "extract_anndata",
        "combine_coordinates",
        "flatten_metrics",
        "extract_qc_metrics_table",
        "extract_cluster_evidence",
        "extract_batch_evidence",
        "shuffle_markers",  # negative-control generator for annotate-clusters: permutes gene symbols in a cluster_evidence dir
        "mix_batches",  # negative-control generator for assess-batch: removes the slide structure of a batch_evidence dir
        "shuffle_column",  # negative-control generator for the open tools (0.6.0): permutes a design column across the units of a table
    )
}
# the one R tool: the engine dispatches `.R` scripts through Rscript inside the module's env
TOOLS["extract_seurat"] = Tool("extract_seurat", _TOOLS / "extract_seurat.R", env=None)

PLUGIN = Plugin(
    name=NAME,
    version=VERSION,
    modes=("pipeline", "open"),  # open mode from 0.6.0: the method's open tools answer questions
    predicates_module="stringency_singlecell.predicates",
    operations={k: Operation(name=k, params_schema=v) for k, v in OPERATIONS.items()},
    object_types=OBJECT_TYPES,
    design_schema=DESIGN_SCHEMA,
    objective_questions=OBJECTIVE_QUESTIONS,
    vocabularies=_load_vocabularies(),
    tools=TOOLS,
    defaults=DEFAULTS,
    describe=phrasing.describe,
    echo=phrasing.echo,
)
