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
        "method": {
            "type": "string",
            "enum": ["logarea", "log_total"],
            "description": "LogArea (counts per cell area x scale_factor, log1p) or library-size log1p",
        },
        "scale_factor": {**_NUM, "minimum": 0, "description": "scale factor before log1p"},
    },
    "additionalProperties": False,
}
OPERATIONS["reduce_pca"] = {
    "type": "object",
    "properties": {
        "n_features": {**_INT, "description": "variable features kept for scaling and PCA"},
        "npcs": {
            **_INT,
            "description": "principal components computed (the elbow table covers them all)",
        },
        "integration": {
            "type": "string",
            "enum": ["none", "harmony", "rpca", "cca"],
            "description": (
                "batch integration after PCA; none first, a fork sets harmony when the "
                "clustering shows batch structure (owner, 2026-10-07)"
            ),
        },
        "batch_key": {
            "type": "string",
            "description": "meta.data column the integration corrects over (the design's batch)",
        },
    },
    "additionalProperties": False,
}
OPERATIONS["cluster_umap"] = {
    "type": "object",
    "properties": {
        "ndim": {
            **_INT,
            "description": "principal (or integrated) components used for the graph and UMAP",
        },
        "resolution": {
            **_NUM,
            "description": "the Louvain resolution whose clusters become the identity",
        },
        "resolutions": {
            "type": "array",
            "items": _NUM,
            "description": "every resolution computed (clustree, cluster counts)",
        },
        "k_neighbors": {**_INT, "description": "k of the shared nearest-neighbour graph"},
        "algorithm": {**_INT, "description": "Seurat FindClusters algorithm (1 Louvain, 4 Leiden)"},
        "umap_n_neighbors": {**_INT, "description": "uwot n_neighbors"},
        "umap_min_dist": {**_NUM, "minimum": 0, "description": "uwot min_dist"},
        "seed": {**_INT, "description": "random seed set before every stochastic call"},
    },
    "additionalProperties": False,
}
OPERATIONS["find_markers"] = {
    "type": "object",
    "properties": {
        "logfc_min": {**_NUM, "description": "minimum log fold change"},
        "min_pct": {
            **_NUM,
            "minimum": 0,
            "maximum": 1,
            "description": "minimum fraction of cells expressing",
        },
        "test": {"type": "string", "description": "Seurat test name"},
        "max_cells_per_ident": {
            **_INT,
            "description": "cells sampled per cluster for the test (seeded)",
        },
        "only_pos": {"type": "boolean", "description": "report positive markers only"},
        "top_n": {**_INT, "description": "markers kept per cluster in markers_top"},
    },
    "additionalProperties": False,
}
# The annotation judgment, the label application and the upstream report take no parameters.
OPERATIONS["annotate_clusters"] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}
OPERATIONS["apply_labels"] = {"type": "object", "properties": {}, "additionalProperties": False}
OPERATIONS["report_upstream"] = {"type": "object", "properties": {}, "additionalProperties": False}
# Judgment on the batch route after clustering (owner, 2026-10-07 afternoon): reviewers read the
# per-cluster batch tables and call proceed_uncorrected / correct_batch / cannot_tell from
# `batch_route@1`; no parameters, the guide is in the prompt. Its hold always opens
# (`sc.batch_route_review`).
OPERATIONS["assess_batch"] = {"type": "object", "properties": {}, "additionalProperties": False}
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
            "spatial_neighborhood",
            "characterise_niches",
            "report",
        )
    }
)

# The open tools (0.6.0; the method's trusted answers on a delivered upstream object). `factor`
# names a declared design factor and `reference` one of its levels; every other level is tested
# against it. `replicate_unit` is a decision point the person states: `animal` is the design's
# replication unit, `punch` is pseudoreplication and the tools say so in their coverage tables.
_FACTOR = {
    "factor": {"type": "string", "description": "the design factor whose levels are compared"},
    "reference": {
        "type": "string",
        "description": "the factor level the others are tested against",
    },
    "replicate_unit": {
        "type": "string",
        "enum": ["animal", "punch"],
        "description": "what counts as one replicate: the animal (the design's unit) or the punch",
    },
}
OPERATIONS["extract_cells"] = {"type": "object", "properties": {}, "additionalProperties": False}
OPERATIONS["compose_cells"] = {
    "type": "object",
    "properties": {
        **_FACTOR,
        "transform": {
            "type": "string",
            "enum": ["logit", "asin"],
            "description": "the proportion transform before the propeller-style t-test",
        },
        "tests": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["propeller", "edger_ql", "edger_density", "permutation"],
            },
            "description": (
                "the composition tests to run, one column block each; effect sizes with "
                "bootstrap intervals are always written"
            ),
        },
        "min_cells_per_sample": {
            **_INT,
            "description": "samples below this many cells are dropped",
        },
        "seed": {**_INT, "description": "seed of the bootstrap and permutation draws"},
    },
    "additionalProperties": False,
}
OPERATIONS["plot_composition"] = {
    "type": "object",
    "properties": {
        "measure": {
            "type": "string",
            "enum": ["proportion", "density", "count"],
            "description": "what each point shows per cell type",
        },
        "top_n": {**_INT, "description": "cell types drawn, the most abundant first"},
    },
    "additionalProperties": False,
}
OPERATIONS["test_differential_expression"] = {
    "type": "object",
    "properties": {
        **_FACTOR,
        "cell_types": {
            "type": "array",
            "items": {"type": "string"},
            "description": "cell types tested; every type when absent",
        },
        "min_cells_per_sample": {
            **_INT,
            "description": "pseudobulk samples below this many cells are dropped",
        },
        "min_samples_per_group": {
            **_INT,
            "description": "a contrast needs this many samples on each side",
        },
        "fdr": {**_NUM, "minimum": 0, "maximum": 1, "description": "the adjusted p threshold"},
    },
    "additionalProperties": False,
}
OPERATIONS["score_pathways"] = {
    "type": "object",
    "properties": {
        **_FACTOR,
        "genesets": {
            "type": "array",
            "items": {"type": "string"},
            "description": "names of the gene sets the method ships (innate, ...)",
        },
        "genes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "gene symbols scored together as one ad hoc module",
        },
        "geneset_name": {
            "type": "string",
            "description": "the name of the ad hoc module built from `genes`",
        },
        "min_genes": {
            **_INT,
            "description": "a module with fewer genes on the panel is scored but flagged",
        },
    },
    "additionalProperties": False,
}
OPERATIONS["neighborhood_enrichment"] = {
    "type": "object",
    "properties": {
        "factor": _FACTOR["factor"],
        "reference": _FACTOR["reference"],
        "radius_um": {**_NUM, "minimum": 0, "description": "the neighbourhood radius in microns"},
        "n_perms": {**_INT, "description": "label permutations behind the z-scores"},
        "seed": {**_INT, "description": "random seed of the permutations"},
    },
    "additionalProperties": False,
}
OPERATIONS["infer_cell_communication"] = {
    "type": "object",
    "properties": {
        "factor": _FACTOR["factor"],
        "reference": _FACTOR["reference"],
        "per_punch": {
            "type": "boolean",
            "description": "also infer one network per punch (replicate concordance)",
        },
        "nboot": {**_INT, "description": "permutations of the communication probability test"},
        "min_cells": {**_INT, "description": "cell types below this many cells are left out"},
        "comm_type": {
            "type": "string",
            "enum": ["secreted", "contact", "all"],
            "description": "the CellChatDB interaction classes used",
        },
        "seed": {**_INT, "description": "random seed set before the permutations"},
    },
    "additionalProperties": False,
}

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
