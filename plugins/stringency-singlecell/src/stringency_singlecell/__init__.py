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

0.9.0 (2026-10-27, the open tools' second round; the Xenium method's `open-tools-v2-plan.md`
section 10): the layer parameters `group_by`, `subset`, `denominator` and `stratify_by` (and
`block` on `compose_cells` and `test_differential_expression`) on the five open tools'
operations; `test_differential_expression` gains `contrast_layer`, `within`, `method` and the
contamination filter, `plot_composition` the design's factor, `neighborhood_enrichment` a radius
sweep (`radii_um`); two new operations, `sweep_domains` and `call_domains` (`n_domains` an integer
or `unset`); the plain types `cell_expression`, `domain_grid`, `domain_labels` and `cell_scores`,
and a punch x cluster (x domain) `pseudobulk_set`; the negative-control generator
`shuffle_coordinates`; the predicate `spatial.domain_is_replicate` (a domain whose cells come
almost all from one replicate); `spatial.neighborhood_undeclared` reads `k_neighbors` and judges
`sweep_domains`, and `sc.decision_unreviewed` judges `call_domains`, both at their versions.

0.10.0 (2026-10-27, later): vocabularies scoped by organ, an `organs:` map in the YAML loaded as
`VOCABULARY_ORGANS` beside the flat label tuples the engine reads, and `sc.label_outside_organ`;
the proximity, distance and autocorrelation tools' scale and permutation gates (README).

0.10.2 (2026-10-27, later): the operation `test_pair_correlation` (the Xenium method's
pair-correlation tool: the cross pair-correlation function per punch with a random-labelling
envelope, its window mean tested between levels); no predicate judges it yet.

0.10.3 (2026-10-28): the operation `measure_intensity` (the Xenium method's cell-intensity tool:
per punch and label the intensity over the tissue's quadrats, the dispersion index and the
chi-square quadrat test of uniform intensity, a homogeneity check before a label-permutation
tool); no predicate judges it yet.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from stringency.plugins import ObjectType, Operation, Plugin, Tool

from stringency_singlecell import phrasing
from stringency_singlecell.schemas import DEFAULTS, DESIGN_SCHEMA, OBJECTIVE_QUESTIONS, OPERATIONS

NAME = "stringency-singlecell"
VERSION = "0.10.3"
_HERE = Path(__file__).parent
_TOOLS = _HERE / "tools"


# The organ names a vocabulary's `organs:` map may use; `any` is every organ (0.10.0).
ORGANS = (
    "liver",
    "lung",
    "small_intestine",
    "large_intestine",
    "spleen",
    "kidney",
    "heart",
    "skin",
    "brain",
)


def _vocabulary_files() -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for f in sorted((_HERE / "vocabularies").glob("*.yml")):
        data = yaml.safe_load(f.read_text()) or {}
        out.append((f"{data.get('name', f.stem)}@{data.get('version', '0')}", data))
    return out


def _load_vocabularies() -> dict[str, tuple[str, ...]]:
    return {ref: tuple(str(x) for x in data.get("labels", [])) for ref, data in _vocabulary_files()}


def _load_vocabulary_organs() -> dict[str, dict[str, tuple[str, ...]]]:
    """`name@version -> label -> organs` for every vocabulary carrying an `organs:` map (0.10.0;
    the owner 2026-10-27: a judgment vocabulary is matched by species and by tissue). The engine's
    `Plugin.vocabularies` stays the flat label tuple; the organ scope is the plugin's, read by
    `sc.label_outside_organ`. A label must be one of the vocabulary's, an organ one of `ORGANS` or
    `any`; a label the map leaves out is not judged."""
    out: dict[str, dict[str, tuple[str, ...]]] = {}
    for ref, data in _vocabulary_files():
        organs = data.get("organs")
        if not organs:
            continue
        labels = {str(x) for x in data.get("labels", [])}
        scoped: dict[str, tuple[str, ...]] = {}
        for label, where in dict(organs).items():
            where = [where] if isinstance(where, str) else list(where or ["any"])
            names = tuple(str(o).strip().lower() for o in where)
            bad = [o for o in names if o not in ORGANS and o != "any"]
            if str(label) not in labels or bad:
                raise ValueError(f"vocabulary {ref}: organs entry {label}: {where} is not valid")
            scoped[str(label)] = names
        out[ref] = scoped
    return out


VOCABULARY_ORGANS: dict[str, dict[str, tuple[str, ...]]] = _load_vocabulary_organs()


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
    # 0.8.0: a module's named facts (a JSON object), the state envelope for droplet methods
    "analysis_summary": _ot("analysis_summary", "extract_analysis_summary"),
    # 0.8.3: a person's declared lineage panels (CSV lineage, gene), an input and never a parameter
    "marker_panels": _ot("marker_panels", "extract_marker_panels"),
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
        "extract_analysis_summary",
        "extract_marker_panels",
        "shuffle_markers",  # negative-control generator for annotate-clusters: permutes gene symbols in a cluster_evidence dir
        "mix_batches",  # negative-control generator for assess-batch: removes the slide structure of a batch_evidence dir
        "shuffle_column",  # negative-control generator for the open tools (0.6.0): permutes a design column across the units of a table
        "shuffle_coordinates",  # negative-control generator for the spatial open tools (0.9.0): permutes (x, y) among the cells of each punch
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
