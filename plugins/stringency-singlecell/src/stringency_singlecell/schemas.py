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
                # the row of the object: cell, nucleus, spot or bead for object-level projects;
                # punch for punch-level tables (the QC summary and the outlier judgment read one
                # row per punch). Any name from 0.8.0: the plugin is not Xenium's alone.
                "observation": {"type": "string", "minLength": 1},
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
# 0.10.0: the fine label (the Xenium method's PLAN 3.17 and 3.21): one fine label from three by
# agreement on evidence-backed claims, and a judgment that chooses among the reviewers' candidates
# for the contested clusters only (vocabulary fine_label_choice@1).
OPERATIONS["reconcile_fine_labels"] = {
    "type": "object",
    "properties": {
        "min_reviewers": {
            **_INT,
            "description": "candidates a gene or programme claim needs to stand",
        },
        "pct_diff_floor": {
            **_NUM,
            "minimum": 0,
            "maximum": 1,
            "description": "the fraction-expressing difference a gene claim needs",
        },
        "logfc_min": {
            **_NUM,
            "minimum": 0,
            "description": "the log fold change a gene claim needs",
        },
    },
    "additionalProperties": False,
}
# 0.10.0: the domain layer's names (the owner, 2026-10-27): a judgment labels each domain with a
# known tissue structure from tissue_structures_mouse@1 and a free-text name; a deterministic
# step writes the consensus onto the layer.
OPERATIONS["label_domains"] = {"type": "object", "properties": {}, "additionalProperties": False}
OPERATIONS["apply_domain_labels"] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}
OPERATIONS["choose_fine_label"] = {
    "type": "object",
    "properties": {},
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
# List-valued parameters are comma-separated strings: `--set k=v` values arrive as text (0.6.1).
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
            "type": "string",
            "pattern": "^(propeller|edger_ql|edger_density|permutation)(,(propeller|edger_ql|edger_density|permutation))*$",
            "description": (
                "comma-separated tests to run (propeller, edger_ql, edger_density, "
                "permutation), one column block each; effect sizes with bootstrap intervals "
                "are always written"
            ),
        },
        "min_cells_per_sample": {
            **_INT,
            "description": "samples below this many cells are dropped",
        },
        "seed": {**_INT, "description": "seed of the bootstrap and permutation draws"},
        "level_colors": {
            "type": "string",
            "description": (
                "colours of the factor's levels: '<level>=<colour>,...' (hex or an R colour "
                "name) or a scheme name (okabe-ito, viridis, sequential, grey); empty is the "
                "method's default"
            ),
        },
        "group_palette": {
            "type": "string",
            "description": (
                "colours of the groups: auto (family shading, or distinct colours when every "
                "group drawn is in one family), family, categorical, or '<group>=<colour>,...'"
            ),
        },
        "plot_test": {
            "type": "string",
            "description": "the test whose p-values the volcano-style figure draws; empty draws the first of `tests`",
        },
        "label_top": {
            "type": "integer",
            "minimum": 0,
            "description": "in the volcano-style figure, the groups labelled by smallest p when none passes the fdr",
        },
        "fdr": {
            **_NUM,
            "minimum": 0,
            "maximum": 1,
            "description": "the adjusted p below which a group is called and labelled in the test figure",
        },
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
        "level_colors": {
            "type": "string",
            "description": (
                "colours of the factor's levels: '<level>=<colour>,...' (hex or an R colour "
                "name) or a scheme name (okabe-ito, viridis, sequential, grey); empty is the "
                "method's default"
            ),
        },
        "group_palette": {
            "type": "string",
            "description": (
                "colours of the groups: auto (family shading, or distinct colours when every "
                "group drawn is in one family), family, categorical, or '<group>=<colour>,...'"
            ),
        },
    },
    "additionalProperties": False,
}
OPERATIONS["test_differential_expression"] = {
    "type": "object",
    "properties": {
        **_FACTOR,
        "cell_types": {
            "type": "string",
            "description": "comma-separated cell types to test; every type when absent",
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
        "min_logfc": {
            **_NUM,
            "minimum": 0,
            "description": "the log2 fold change a gene must reliably exceed (limma treat)",
        },
    },
    "additionalProperties": False,
}
OPERATIONS["score_pathways"] = {
    "type": "object",
    "properties": {
        **_FACTOR,
        "genesets": {
            "type": "string",
            "description": "comma-separated names of gene sets the method ships (innate, ...)",
        },
        "genes": {
            "type": "string",
            "description": "comma-separated gene symbols scored together as one ad hoc module",
        },
        "geneset_name": {
            "type": "string",
            "description": "the name of the ad hoc module built from `genes`",
        },
        "min_genes": {
            **_INT,
            "description": "a module with fewer genes on the panel is scored but flagged",
        },
        "min_cells_per_sample": {
            **_INT,
            "description": "samples below this many cells are dropped from the test",
        },
        "top_n": {
            **_INT,
            "description": "groups drawn in the figure, those whose means spread most first",
        },
        "plot_module": {
            "type": "string",
            "description": "the module the figure draws; empty draws the first scored",
        },
        "level_colors": {
            "type": "string",
            "description": (
                "colours of the factor's levels: '<level>=<colour>,...' (hex or an R colour "
                "name) or a scheme name (okabe-ito, viridis, sequential, grey); empty is the "
                "method's default"
            ),
        },
        "plot_cells": {
            "type": "boolean",
            "description": "also draw every cell's score as one violin per replicate within each level",
        },
        "overlay_reference": {
            "type": "boolean",
            "description": "in the per-cell figure, draw the reference level's pooled distribution as a grey outline behind each level",
        },
    },
    "additionalProperties": False,
}
# 0.10.0: milestones B to D of the Xenium method's open tools (its docs/open-tools-v2-plan.md
# section 10.5): distance to a structure, the near/far proximity contrast (Sun24), spatially
# variable genes, the per-replicate feature table.
_CLAUSE = {
    "type": "string",
    "pattern": "^$|^[A-Za-z_][A-Za-z0-9_.]* (in [^,]+(,[^,]+)*|= .+)$",
}
_LAYER = {
    "group_by": {
        "type": "string",
        "description": "the cell-table column whose levels are the rows",
    },
    "subset": {
        **_CLAUSE,
        "description": "one clause selecting the cells: '<column> in v1,v2' or '<column> = v'; empty is every cell",
    },
    "stratify_by": {
        "type": "string",
        "description": "a second label column the analysis runs within; empty is none",
    },
}
OPERATIONS["measure_distance"] = {
    "type": "object",
    "properties": {
        **_FACTOR,
        "target": {
            **_CLAUSE,
            "description": "the cells the distance is measured to: '<column> in v1,v2' or '<column> = v'",
        },
        "group_by": _LAYER["group_by"],
        "subset": _LAYER["subset"],
        "denominator": {
            "type": "string",
            "enum": ["all", "subset"],
            "description": "for proportions per bin: the replicate's cells, or the cells subset kept",
        },
        "bins_um": {
            "type": "string",
            "pattern": "^[0-9.]+(,[0-9.]+)*$",
            "description": "the bin edges of the distance in microns, comma-separated",
        },
        "max_distance_um": {
            **_NUM,
            "minimum": 0,
            "description": "cells farther than this from the target are left out",
        },
        "genes": {
            "type": "string",
            "description": "comma-separated genes whose mean normalised value is traced per bin",
        },
        "signed": {
            "type": "boolean",
            "description": "a domain target gives negative distances inside it",
        },
        "min_cells": {
            **_INT,
            "description": "a bin and replicate with fewer cells is written but flagged",
        },
        "level_colors": {
            "type": "string",
            "description": "colours of the factor's levels, as plot_composition",
        },
        "seed": {**_INT, "description": "random seed"},
        "plot_quantities": {
            "type": "string",
            "description": "comma-separated groups, scores or genes the figure draws, one panel each; empty draws the six groups whose shares change most and every score and gene",
        },
        "plot_max_um": {
            **_NUM,
            "minimum": 0,
            "description": "the figure's x limit in microns; 0 follows the bins that hold data",
        },
    },
    "additionalProperties": False,
}
OPERATIONS["test_proximity_effect"] = {
    "type": "object",
    "properties": {
        **_FACTOR,
        "effector": {**_CLAUSE, "description": "the cells whose proximity is the exposure"},
        "target": {**_CLAUSE, "description": "the cells whose state is read"},
        "cutoff_um": {
            "type": "string",
            "pattern": "^(delaunay|[0-9.]+)$",
            "description": "near is within this many microns of any effector; delaunay takes each punch's median Delaunay edge",
        },
        "annulus": {
            "type": "boolean",
            "description": "exclude touching cells: near is the ring from the cutoff to twice it",
        },
        "sweep": {
            "type": "string",
            "pattern": "^[0-9.]+(,[0-9.]+)*$",
            "description": "multiples of the cutoff the contrast is repeated at",
        },
        "scores": {
            "type": "string",
            "description": "comma-separated columns of the bound cell_scores to contrast; empty is every one",
        },
        "genes": {
            "type": "string",
            "description": "comma-separated genes to contrast from the expression h5ad",
        },
        "min_cells": {**_INT, "description": "the fewest cells an arm needs in a replicate"},
        "n_perms": {**_INT, "description": "coordinate permutations within punch behind the null"},
        "match_by": {
            "type": "string",
            "description": "comma-separated columns the far cells are matched on",
        },
        "seed": {**_INT, "description": "random seed of the matching and the permutations"},
    },
    "additionalProperties": False,
}
OPERATIONS["test_spatial_autocorrelation"] = {
    "type": "object",
    "properties": {
        "factor": _FACTOR["factor"],
        "reference": _FACTOR["reference"],
        "genes": {
            "type": "string",
            "description": "comma-separated genes; empty is every gene detected above min_detected",
        },
        "min_detected": {
            **_NUM,
            "minimum": 0,
            "maximum": 1,
            "description": "the fraction of cells with a count a gene needs to be tested",
        },
        "k_neighbors": {**_INT, "description": "the spatial neighbours of each cell"},
        "radius_um": {
            **_NUM,
            "minimum": 0,
            "description": "neighbours within this many microns instead of k",
        },
        "n_perms": {**_INT, "description": "permutations behind Moran's I null"},
        "fdr": {
            **_NUM,
            "minimum": 0,
            "maximum": 1,
            "description": "the adjusted p below which a gene is called in a punch",
        },
        "subset": _LAYER["subset"],
        "seed": {**_INT, "description": "random seed of the permutations"},
        "group_by": {
            "type": "string",
            "description": "the label layer whose per-cell means are subtracted for the residual Moran's I (cell_type, cluster, domain)",
        },
        "within": {
            **_CLAUSE,
            "description": "one clause restricting the cells to one group before the graph is built; empty is every cell",
        },
    },
    "additionalProperties": False,
}
OPERATIONS["summarise_sample_features"] = {
    "type": "object",
    "properties": {
        "replicate_unit": _FACTOR["replicate_unit"],
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
        "group_by": _LAYER["group_by"],
        "subset": _LAYER["subset"],
        "stratify_by": _LAYER["stratify_by"],
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

# 0.8.0 (2026-10-22): droplet and combinatorial kits, for the benchmark's scRNA-seq method
# (engine `benchmark-plan.md`, Phase 1). The Xenium operations gain the parameters a scanpy
# method takes; `qc_metrics` and `score_panels` are new; `replicate_unit` is any unit of the
# design (animal, donor) or a finer one, which `de.replication_unit` judges.
OPERATIONS["qc_cells"]["properties"].update(
    {
        "min_genes": {**_INT, "description": "minimum genes detected per cell"},
        "max_genes": {**_INT, "description": "maximum genes detected per cell (0 for none)"},
        "min_counts": {**_INT, "description": "minimum total counts per cell"},
        "max_pct_mt": {
            **_NUM,
            "minimum": 0,
            "maximum": 100,
            "description": "maximum percent mitochondrial counts (100 for none)",
        },
        "mt_prefix": {
            "type": "string",
            "description": "the gene-symbol prefix that marks mitochondrial genes (MT-, mt-)",
        },
        "keep_column": {
            "type": "string",
            "description": "an obs column to restrict cells by (empty for none)",
        },
        "keep_value": {"type": "string", "description": "the value of keep_column to keep"},
    }
)
OPERATIONS["normalize"]["properties"]["method"] = {
    "type": "string",
    "enum": ["logarea", "log_total", "pearson_residuals"],
    "description": (
        "LogArea (counts per cell area x scale_factor, log1p), library-size log1p, or analytic "
        "Pearson residuals (depth-aware)"
    ),
}
OPERATIONS["normalize"]["properties"].update(
    {
        "target_sum": {
            **_NUM,
            "minimum": 0,
            "description": "library size each cell is scaled to before log1p (0 keeps the median)",
        },
        "exclude_highly_expressed": {
            "type": "boolean",
            "description": "leave the most abundant genes out of the size factor",
        },
    }
)
OPERATIONS["reduce_pca"]["properties"].update(
    {
        "scale": {"type": "boolean", "description": "standardise each gene before PCA"},
        "regress_out": {
            "type": "string",
            "description": "comma-separated obs columns regressed out before PCA, empty for none",
        },
        "n_comps": {**_INT, "description": "principal components computed"},
        "use_hvg": {"type": "boolean", "description": "restrict PCA to the highly variable genes"},
    }
)
OPERATIONS["select_hvg"] = {
    "type": "object",
    "properties": {
        "n_top_genes": {**_INT, "description": "highly variable genes to keep"},
        "flavor": {
            "type": "string",
            "enum": ["seurat", "cell_ranger", "seurat_v3", "pearson_residuals"],
            "description": (
                "scanpy flavour: seurat and cell_ranger on log data; seurat_v3 and "
                "pearson_residuals on counts (depth-aware)"
            ),
        },
        "min_cells": {**_INT, "description": "genes detected in fewer cells are dropped first"},
        "batch_key": {
            "type": "string",
            "description": "obs column the selection is stratified by (empty for none)",
        },
    },
    "additionalProperties": False,
}
OPERATIONS["cluster"] = {
    "type": "object",
    "properties": {
        "n_neighbors": {**_INT, "description": "neighbours in the kNN graph"},
        "n_pcs": {**_INT, "description": "principal components the graph uses"},
        "resolution": {**_NUM, "minimum": 0, "description": "Leiden resolution"},
        "algorithm": {
            "type": "string",
            "enum": ["leiden", "louvain"],
            "description": "community detection",
        },
        "seed": {**_INT, "description": "random seed"},
    },
    "additionalProperties": False,
}
OPERATIONS["qc_metrics"] = {
    "type": "object",
    "properties": {
        "mt_prefix": {
            "type": "string",
            "description": "the gene-symbol prefix that marks mitochondrial genes",
        },
        "symbol_column": {
            "type": "string",
            "description": "var column holding gene symbols (empty: the index)",
        },
    },
    "additionalProperties": False,
}
OPERATIONS["score_panels"] = {
    "type": "object",
    "properties": {
        "panels": {
            "type": "string",
            "description": "JSON object lineage -> gene list, the declared marker panels",
        },
        "cluster_column": {"type": "string", "description": "obs column holding the clusters"},
        "symbol_column": {
            "type": "string",
            "description": "var column holding gene symbols (empty: the index)",
        },
    },
    "additionalProperties": False,
}
for _op in ("test_differential_expression", "compose_cells"):
    OPERATIONS[_op]["properties"]["replicate_unit"] = {
        "type": "string",
        "description": (
            "what counts as one replicate: a unit of the design (animal, donor) or a finer one "
            "(punch, cell), which de.replication_unit judges"
        ),
    }

# 0.9.0 (2026-10-27): the open tools, second round (the Xenium method's
# `docs/open-tools-v2-plan.md`, section 10, the contract every work package builds against).
# The layer parameters choose which cells enter and what a row is; the domain operations call
# spatial domains from the neighbour-label composition. Values arrive as text from `--set`, so a
# list is a comma-separated string and a clause is one string.
_COLUMN = "[A-Za-z_][A-Za-z0-9_.]*"
_CLAUSE = rf"^$|^\s*{_COLUMN}\s+in\s+[^,]+(\s*,\s*[^,]+)*\s*$|^\s*{_COLUMN}\s*=\s*[^,]+$"
_OPTIONAL_COLUMN = rf"^$|^{_COLUMN}$"
_LAYER: dict[str, dict[str, Any]] = {
    "group_by": {
        "type": "string",
        "pattern": rf"^{_COLUMN}$",
        "description": (
            "the cell-table column whose levels are the rows: cell_type, cluster, "
            "cell_type_fine, domain or any label column present"
        ),
    },
    "subset": {
        "type": "string",
        "pattern": _CLAUSE,
        "description": (
            "one clause selecting the cells that enter, `<column> in <v1>,<v2>` or "
            "`<column> = <v>`; empty means every cell"
        ),
    },
    "denominator": {
        "type": "string",
        "enum": ["all", "subset"],
        "description": "for proportions: all the replicate's cells, or only the cells subset kept",
    },
    "stratify_by": {
        "type": "string",
        "pattern": _OPTIONAL_COLUMN,
        "description": (
            "a second label column; the analysis runs within each of its levels and strata "
            "under the minimum cells are listed in the coverage table; empty for none"
        ),
    },
    "block": {
        "type": "string",
        "pattern": _OPTIONAL_COLUMN,
        "description": (
            "a column (the batch, slide) entered as a model term; when it is confounded with "
            "the factor it is not fitted and the coverage table says so; empty for none"
        ),
    },
}
_LAYER_KEYS = {
    "compose_cells": ("group_by", "subset", "denominator", "stratify_by", "block"),
    "plot_composition": ("group_by", "subset", "denominator", "stratify_by"),
    "score_pathways": ("group_by", "subset", "stratify_by"),
    "test_differential_expression": ("group_by", "subset", "stratify_by", "block"),
    "neighborhood_enrichment": ("group_by", "subset", "stratify_by"),
}
for _op, _keys in _LAYER_KEYS.items():
    OPERATIONS[_op]["properties"].update({k: dict(_LAYER[k]) for k in _keys})

OPERATIONS["test_differential_expression"]["properties"].update(
    {
        "contrast_layer": {
            "type": "string",
            "pattern": _OPTIONAL_COLUMN,
            "description": (
                "the column whose levels are contrasted: a design factor (the animals are the "
                "replicates) or a label column (cluster, domain: contrasted within animals, "
                "~ 0 + level + animal); empty for the factor"
            ),
        },
        "within": {
            "type": "string",
            "pattern": _CLAUSE,
            "description": (
                "one clause applied before the contrast, `<column> in <v1>,<v2>` or "
                "`<column> = <v>` (one lineage, one time point); empty for none"
            ),
        },
        "method": {
            "type": "string",
            "enum": ["limma_voom", "edger_ql"],
            "description": "the pseudobulk model: limma-voom with treat, or edgeR quasi-likelihood",
        },
        "contamination_filter": {
            "type": "boolean",
            "description": (
                "per group keep genes with at least min_count in at least min_fraction of the "
                "group's cells; the genes dropped are listed in de_coverage"
            ),
        },
        "min_count": {
            **_INT,
            "description": "the count a cell must reach for the contamination filter",
        },
        "min_fraction": {
            **_NUM,
            "minimum": 0,
            "maximum": 1,
            "description": "the fraction of the group's cells that must reach min_count",
        },
    }
)
OPERATIONS["plot_composition"]["properties"].update(
    {
        "measure": {
            "type": "string",
            "enum": ["proportion", "count", "density"],
            "description": (
                "what each bar segment shows: the share of the replicate's cells, the count, "
                "or cells per mm²"
            ),
        },
        "top_n": {
            **_INT,
            "description": "groups drawn, the most abundant first; the rest fold into other",
        },
        "factor": _FACTOR["factor"],
        "reference": {
            "type": "string",
            "description": "the factor level drawn first",
        },
        "replicate_unit": dict(OPERATIONS["compose_cells"]["properties"]["replicate_unit"]),
    }
)
OPERATIONS["neighborhood_enrichment"]["properties"].update(
    {
        "radii_um": {
            "type": "string",
            "pattern": r"^\s*[0-9]+(\.[0-9]+)?(\s*,\s*[0-9]+(\.[0-9]+)?)*\s*$",
            "description": (
                "comma-separated neighbourhood radii in microns (a sweep, 20,40,80); "
                "scale_stability says at how many the enrichment holds"
            ),
        },
        "min_cells": {
            **_INT,
            "description": "groups below this many cells in a punch are left out",
        },
        "n_jobs": {
            "type": "integer",
            "minimum": 1,
            "description": "worker processes of the permutations (1: squidpy issue 1318)",
        },
    }
)
OPERATIONS["sweep_domains"] = {
    "type": "object",
    "properties": {
        "group_by": {
            **_LAYER["group_by"],
            "description": "the label column whose neighbour composition defines a domain",
        },
        "k_neighbors": {
            "type": "integer",
            "minimum": 1,
            "description": "neighbours of each cell in the per-punch spatial graph",
        },
        "exclude": {
            "type": "string",
            "description": (
                "comma-separated labels left out of the neighbour composition (the technical "
                "ones: low_quality, mixed_doublet, unknown)"
            ),
        },
        "n_domains_min": {
            "type": "integer",
            "minimum": 2,
            "description": "the fewest domains in the k-means sweep",
        },
        "n_domains_max": {
            "type": "integer",
            "minimum": 2,
            "description": "the most domains in the k-means sweep",
        },
        "seed": {**_INT, "description": "seed of the k-means starts"},
    },
    "additionalProperties": False,
}
OPERATIONS["call_domains"] = {
    "type": "object",
    "properties": {
        "n_domains": {
            "anyOf": [{"type": "integer", "minimum": 2}, {"const": "unset"}],
            "description": (
                "the column of the sweep whose labels become the domains; unset stops the step "
                "so the operator proposes it from domain_sweep and a person approves it"
            ),
        },
        "domain_names": {
            "type": "string",
            "pattern": r"^$|^\s*[0-9]+\s*=\s*[^,=]+(\s*,\s*[0-9]+\s*=\s*[^,=]+)*\s*$",
            "description": "names for the numbered domains, `1=crypt,2=villus`; empty keeps numbers",
        },
        "min_cells": {
            **_INT,
            "description": "a domain and replicate under this many cells is listed, not dropped",
        },
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
