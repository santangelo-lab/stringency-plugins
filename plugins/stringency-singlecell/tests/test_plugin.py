from stringency.plugins import load_plugins


def test_plugin_loads() -> None:
    plugins = load_plugins(refresh=True)
    assert "stringency-singlecell" in plugins
    p = plugins["stringency-singlecell"]
    assert (
        "anndata" in p.object_types
        and "qc_metrics_table" in p.object_types
        and "differential_expression" in p.objective_questions
    )
    assert (
        len(p.predicates()) == 25
    )  # 0.2.0 adds sc.export_mismatch; 0.3.0 the four upstream ones; 0.4.0 sc.batch_route_review;
    # 0.8.5 sc.fine_label_uncited; 0.8.6 sc.louvain_too_large; 0.9.0 spatial.domain_is_replicate
    assert (
        "cell_types_mouse@1" in p.vocabularies and "unknown" in p.vocabularies["cell_types_mouse@1"]
    )
    assert "flag_outlier_punches" in p.operations and "punch_qc_verdict@1" in p.vocabularies
    # @2 adds cell types and keeps every @1 label, so a project moving to @2 loses none
    v1, v2 = p.vocabularies["cell_types_mouse@1"], p.vocabularies["cell_types_mouse@2"]
    assert set(v1) < set(v2) and len(v2) == len(set(v2)) == len(v1) + 9
    assert {"cardiomyocyte", "adipocyte", "transit_amplifying_cell"} <= set(v2)
    assert p.vocabularies["punch_qc_verdict@1"] == ("keep", "review", "exclude", "already_excluded")
    # v2 (2026-09-21): the reviewer never excludes; exclusion is the owner's decision at the hold
    assert p.vocabularies["punch_qc_verdict@2"] == ("keep", "review", "already_excluded")


def test_open_mode_and_the_open_tools_operations() -> None:
    """0.6.0: the plugin admits open mode and types the open tools' operations, so a method's
    tools can list `open` and a project can be initialised from a delivery."""
    p = load_plugins(refresh=True)["stringency-singlecell"]
    assert "open" in p.modes and "pipeline" in p.modes
    for op in (
        "extract_cells",
        "compose_cells",
        "plot_composition",
        "test_differential_expression",
        "score_pathways",
        "neighborhood_enrichment",
        "infer_cell_communication",
    ):
        assert op in p.operations, op
        assert p.operations[op].params_schema.get("additionalProperties") is False, op
    tests = p.operations["compose_cells"].params_schema["properties"]["tests"]
    assert tests["type"] == "string" and "permutation" in tests["pattern"]  # comma-separated
    assert "shuffle_column" in p.tools


def test_open_tools_second_round_operations() -> None:
    """0.9.0 (the Xenium method's open-tools-v2-plan.md section 10): the layer parameters on the
    five open tools, the per-tool additions, the two domain operations and the generator."""
    p = load_plugins(refresh=True)["stringency-singlecell"]
    assert p.version == "0.9.0"
    layers = {
        "compose_cells": {"group_by", "subset", "denominator", "stratify_by", "block"},
        "plot_composition": {"group_by", "subset", "denominator", "stratify_by"},
        "score_pathways": {"group_by", "subset", "stratify_by"},
        "test_differential_expression": {"group_by", "subset", "stratify_by", "block"},
        "neighborhood_enrichment": {"group_by", "subset", "stratify_by"},
    }
    for op, keys in layers.items():
        props = p.operations[op].params_schema["properties"]
        assert keys <= set(props), (op, keys - set(props))
        # denominator only where proportions are drawn, block only where a model is fitted
        assert ("denominator" in props) == (op in ("compose_cells", "plot_composition")), op
        assert ("block" in props) == (op in ("compose_cells", "test_differential_expression")), op
        assert all(props[k].get("description") for k in keys), op
    de = p.operations["test_differential_expression"].params_schema["properties"]
    assert {"contrast_layer", "within", "method", "contamination_filter", "min_count"} <= set(de)
    assert de["method"]["enum"] == ["limma_voom", "edger_ql"]
    assert de["min_fraction"]["maximum"] == 1
    pc = p.operations["plot_composition"].params_schema["properties"]
    assert {"measure", "top_n", "factor", "reference", "replicate_unit"} <= set(pc)
    assert set(pc["measure"]["enum"]) == {"proportion", "count", "density"}
    nh = p.operations["neighborhood_enrichment"].params_schema["properties"]
    assert {"radius_um", "radii_um", "min_cells", "n_jobs"} <= set(nh)
    sweep = p.operations["sweep_domains"].params_schema
    assert set(sweep["properties"]) == {
        "group_by",
        "k_neighbors",
        "exclude",
        "n_domains_min",
        "n_domains_max",
        "seed",
    }
    call = p.operations["call_domains"].params_schema
    assert set(call["properties"]) == {"n_domains", "domain_names", "min_cells"}
    for op in (*layers, "sweep_domains", "call_domains"):
        assert p.operations[op].params_schema.get("additionalProperties") is False, op
    assert "shuffle_coordinates" in p.tools and p.tools["shuffle_coordinates"].script.exists()


def test_open_tools_second_round_schemas_validate() -> None:
    """The contract's values validate; an unknown parameter and a malformed value do not."""
    from stringency.schemas import validate

    ops = load_plugins(refresh=True)["stringency-singlecell"].operations

    def ok(op: str, params: dict) -> bool:
        return validate(params, ops[op].params_schema) == []

    assert ok(
        "compose_cells",
        {
            "factor": "timepoint_h",
            "reference": "control",
            "replicate_unit": "animal",
            "group_by": "cluster",
            "subset": "cell_type in enterocyte,goblet_cell",
            "denominator": "subset",
            "stratify_by": "domain",
            "block": "slide",
        },
    )
    assert ok("compose_cells", {"subset": "", "stratify_by": "", "block": ""})
    assert ok("plot_composition", {"subset": "domain = 3", "measure": "count", "top_n": 12})
    assert ok(
        "plot_composition",
        {"factor": "timepoint_h", "reference": "control", "replicate_unit": "punch"},
    )
    assert ok(
        "test_differential_expression",
        {
            "group_by": "cell_type",
            "contrast_layer": "domain",
            "within": "timepoint_h = 24",
            "method": "edger_ql",
            "contamination_filter": True,
            "min_count": 5,
            "min_fraction": 0.3,
            "block": "slide",
        },
    )
    assert ok("score_pathways", {"group_by": "cluster", "stratify_by": "domain"})
    assert ok("neighborhood_enrichment", {"radii_um": "20,40,80", "n_jobs": 1, "min_cells": 10})
    assert ok("neighborhood_enrichment", {"radii_um": "30", "radius_um": 30})
    assert ok(
        "sweep_domains",
        {
            "group_by": "cell_type",
            "k_neighbors": 25,
            "exclude": "low_quality,mixed_doublet,unknown",
            "n_domains_min": 4,
            "n_domains_max": 12,
            "seed": 1,
        },
    )
    assert ok("call_domains", {"n_domains": "unset", "domain_names": "", "min_cells": 50})
    assert ok("call_domains", {"n_domains": 6, "domain_names": "1=crypt,2=villus"})
    # an unknown parameter, and values outside the contract
    for op in ("compose_cells", "sweep_domains", "call_domains", "neighborhood_enrichment"):
        assert not ok(op, {"no_such_parameter": 1}), op
    assert not ok("score_pathways", {"denominator": "all"})  # proportions only
    assert not ok("neighborhood_enrichment", {"block": "slide"})
    assert not ok("compose_cells", {"denominator": "punch"})
    assert not ok("compose_cells", {"subset": "cell_type"})  # not a clause
    assert not ok("test_differential_expression", {"method": "deseq2"})
    assert not ok("test_differential_expression", {"min_fraction": 1.5})
    assert not ok("neighborhood_enrichment", {"radii_um": "20;40"})
    assert not ok("neighborhood_enrichment", {"n_jobs": 0})
    assert not ok("call_domains", {"n_domains": 1})
    assert not ok("call_domains", {"n_domains": "auto"})
    assert not ok("call_domains", {"domain_names": "crypt,villus"})
    assert not ok("sweep_domains", {"n_domains_min": 1})
