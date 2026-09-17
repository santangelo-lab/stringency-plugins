"""stringency-singlecell: domain plugin skeleton for single-cell and spatial analysis."""

from __future__ import annotations

from pathlib import Path

import yaml
from stringency.plugins import ObjectType, Operation, Plugin, Tool

from stringency_singlecell import phrasing
from stringency_singlecell.schemas import DESIGN_SCHEMA, OPERATIONS

NAME = "stringency-singlecell"
VERSION = "0.0.1"
_HERE = Path(__file__).parent


def _load_vocabularies() -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    for f in sorted((_HERE / "vocabularies").glob("*.yml")):
        data = yaml.safe_load(f.read_text()) or {}
        name, version, labels = data.get("name", f.stem), data.get("version", "0"), data.get("labels", [])
        out[f"{name}@{version}"] = tuple(str(x) for x in labels)
    return out


PLUGIN = Plugin(
    name=NAME,
    version=VERSION,
    modes=("pipeline",),
    predicates_module="stringency_singlecell.predicates",
    operations={k: Operation(name=k, params_schema=v) for k, v in OPERATIONS.items()},
    object_types={
        "anndata": ObjectType(name="anndata", extractor="extract_anndata", extractor_id="sc.anndata@1"),
    },
    design_schema=DESIGN_SCHEMA,
    objective_questions=("differential_expression", "niche_characterisation", "interaction_inference"),
    vocabularies=_load_vocabularies(),
    tools={
        "extract_anndata": Tool("extract_anndata", _HERE / "tools" / "extract_anndata.py", env=None),
    },
    describe=phrasing.describe,
    echo=phrasing.echo,
)
