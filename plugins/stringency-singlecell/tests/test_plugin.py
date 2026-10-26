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
        len(p.predicates()) == 24
    )  # 0.2.0 adds sc.export_mismatch; 0.3.0 the four upstream ones; 0.4.0 sc.batch_route_review;
    # 0.8.5 sc.fine_label_uncited; 0.8.6 sc.louvain_too_large
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
