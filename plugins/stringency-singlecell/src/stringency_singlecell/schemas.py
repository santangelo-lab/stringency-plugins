"""Design schema, operation parameter schemas, and objective questions for the single-cell and
spatial domain. Settled for the Lyons CLP Xenium QC pipeline on 2026-09-17 (Lane C session C2,
`spec/design-schema.md`); the later operations keep provisional open schemas until their modules
are wrapped."""

from __future__ import annotations

from typing import Any

_FACTOR = {
    "type": "object",
    "required": ["column", "levels"],
    "properties": {
        "column": {"type": "string", "minLength": 1},
        "levels": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    },
    "additionalProperties": False,
}

DESIGN_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "stringency-singlecell design",
    "type": "object",
    "required": ["design", "units", "factors", "replication_unit"],
    "properties": {
        "design": {"const": 1},
        # observation: the row of the object (cell). sample: the punch (a column in the layout
        # table). Any further unit (animal, block, ...) is a column too. Values are column names
        # in the layout / obs table; the observation names the row and is not a column.
        "units": {
            "type": "object",
            "required": ["observation", "sample"],
            "properties": {
                # cell for object-level projects; punch for punch-level tables (the QC summary
                # and the outlier judgment read one row per punch)
                "observation": {"enum": ["cell", "punch"]},
                "sample": {"type": "string", "minLength": 1},
            },
            "additionalProperties": {"type": "string", "minLength": 1},
        },
        # A factor with one level (condition: CLP, no sham) is allowed and declared so the
        # absence of a control arm is on record; a factor a contrast names needs two.
        "factors": {"type": "object", "minProperties": 1, "additionalProperties": _FACTOR},
        "batch": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "replication_unit": {"type": "string", "minLength": 1},
        "holdout": {"type": "array"},
        "notes": {"type": "string"},
        "source": {"type": "string"},
    },
    "additionalProperties": False,
}

_NUM = {"type": "number"}
_INT = {"type": "integer", "minimum": 0}

# Operation parameter schemas. The QC pipeline's two operations are typed; ranges and defaults
# belong to the module (params.schema.json) and the policy, not here.
OPERATIONS: dict[str, dict[str, Any]] = {
    "split_punches": {
        "type": "object",
        "properties": {
            "min_transcripts": {**_INT, "description": "drop cells below this transcript count"},
            "min_area": {**_NUM, "minimum": 0, "description": "drop cells below this area (µm²)"},
            "qv_threshold": {
                **_NUM,
                "minimum": 0,
                "maximum": 40,
                "description": "transcript quality value floor",
            },
        },
        "additionalProperties": False,
    },
    "qc_cells": {
        "type": "object",
        "properties": {
            "min_nCount": {**_INT, "description": "minimum transcripts per cell"},
            "min_nFeature": {**_INT, "description": "minimum genes per cell"},
            "min_cellarea": {**_NUM, "minimum": 0, "description": "minimum cell area (µm²)"},
            "max_cellarea": {**_NUM, "minimum": 0, "description": "maximum cell area (µm²)"},
        },
        "additionalProperties": False,
    },
    "resegment": {"type": "object", "properties": {}, "additionalProperties": True},
}
# Later modules keep open schemas until each is wrapped from ROSC_MTA2.
# Judgment operation: reviewer agents read per-punch QC attributes whose band statistics (leave-
# one-out median ± k scaled MAD within tissue, optional reference and group bands, direction-aware
# departures) a pre-script computed, reason with the method's reviewer guide, and propose a
# verdict per punch from `punch_qc_verdict@2` (keep / review / already_excluded) with cited
# cells. No parameters: the guide is in the prompt.
OPERATIONS["merge_objects"] = {"type": "object", "properties": {}, "additionalProperties": False}
OPERATIONS["normalize"] = {
    "type": "object",
    "properties": {
        "method": {"type": "string", "enum": ["logarea", "log_total"], "description": "LogArea (counts per cell area x scale_factor, log1p) or library-size log1p"},
        "scale_factor": {**_NUM, "minimum": 0, "description": "scale factor before log1p"},
    },
    "additionalProperties": False,
}
OPERATIONS["reduce_cluster"] = {
    "type": "object",
    "properties": {
        "n_features": {**_INT, "description": "variable features"},
        "ndim": {**_INT, "description": "principal components used for the graph"},
        "resolutions": {"type": "array", "items": _NUM, "description": "Louvain resolutions computed"},
        "resolution": {**_NUM, "description": "the resolution whose clusters become the identity"},
        "seed": {**_INT, "description": "random seed"},
    },
    "additionalProperties": False,
}
OPERATIONS["find_markers"] = {
    "type": "object",
    "properties": {
        "logfc_min": {**_NUM, "description": "minimum log fold change"},
        "min_pct": {**_NUM, "minimum": 0, "maximum": 1, "description": "minimum fraction of cells expressing"},
        "test": {"type": "string", "description": "Seurat test name"},
    },
    "additionalProperties": False,
}
OPERATIONS["export_h5ad"] = {"type": "object", "properties": {}, "additionalProperties": False}
OPERATIONS["flag_outlier_punches"] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

OPERATIONS.update(
    {
        op: {"type": "object", "properties": {}, "additionalProperties": True}
        for op in (
            "select_hvg",
            "cluster",
            "annotate_clusters",
            "spatial_neighborhood",
            "characterise_niches",
            "test_differential_expression",
            "report",
        )
    }
)

OBJECTIVE_QUESTIONS: tuple[str, ...] = (
    "processed_object",  # deliver QC'd per-punch objects with sidecars (option 1, objectives note)
    "qc_summary",  # one report over the QC deliverables of many regions (cross-region QC, 2026-09-18)
    "differential_expression",
    "niche_characterisation",
    "interaction_inference",
)

# Defaults a drafting skill may name instead of asking (design 15; `plugins list --json`).
DEFAULTS: dict[str, Any] = {
    "min_cells_per_punch": 500,
    "max_qc_fail_fraction": 0.5,
    "coordinates_source": "manual annotation in Xenium Explorer",
}
