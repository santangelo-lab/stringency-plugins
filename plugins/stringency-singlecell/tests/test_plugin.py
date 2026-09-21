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
    assert len(p.predicates()) == 5
    assert "flag_outlier_punches" in p.operations and "punch_qc_verdict@1" in p.vocabularies
    assert p.vocabularies["punch_qc_verdict@1"] == ("keep", "review", "exclude", "already_excluded")
    # v2 (2026-09-21): the reviewer never excludes; exclusion is the owner's decision at the hold
    assert p.vocabularies["punch_qc_verdict@2"] == ("keep", "review", "already_excluded")
