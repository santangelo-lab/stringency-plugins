"""stringency-singlecell: domain plugin for single-cell and spatial (Xenium) analysis.

Object types: `xenium_bundle` (a region bundle), `punch_coordinates` (the hand-drawn selections),
`tma_layout` (the transcribed TMA map), `punch_bundle_set` (one bundle per punch after the
split), `qc_object_set` (QC'd objects plus `qc_summary.json`), and `anndata` (any later object).
Operations `split_punches` and `qc_cells` are typed; the later ones are provisional.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from stringency.plugins import ObjectType, Operation, Plugin, Tool

from stringency_singlecell import phrasing
from stringency_singlecell.schemas import DEFAULTS, DESIGN_SCHEMA, OBJECTIVE_QUESTIONS, OPERATIONS

NAME = "stringency-singlecell"
VERSION = "0.1.7"
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
    )
}

PLUGIN = Plugin(
    name=NAME,
    version=VERSION,
    modes=("pipeline",),
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
