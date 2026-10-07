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
        len(p.predicates()) == 11
    )  # 0.2.0 adds sc.export_mismatch; 0.3.0 the four upstream ones; 0.4.0 sc.batch_route_review
    assert (
        "cell_types_mouse@1" in p.vocabularies and "unknown" in p.vocabularies["cell_types_mouse@1"]
    )
    assert "flag_outlier_punches" in p.operations and "punch_qc_verdict@1" in p.vocabularies
    assert p.vocabularies["punch_qc_verdict@1"] == ("keep", "review", "exclude", "already_excluded")
    # v2 (2026-09-21): the reviewer never excludes; exclusion is the owner's decision at the hold
    assert p.vocabularies["punch_qc_verdict@2"] == ("keep", "review", "already_excluded")
