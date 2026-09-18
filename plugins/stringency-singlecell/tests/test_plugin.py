from stringency.plugins import load_plugins


def test_plugin_loads() -> None:
    plugins = load_plugins(refresh=True)
    assert "stringency-singlecell" in plugins
    p = plugins["stringency-singlecell"]
    assert "anndata" in p.object_types and "differential_expression" in p.objective_questions
    assert len(p.predicates()) == 5
    assert "flag_outlier_punches" in p.operations and "punch_qc_verdict@1" in p.vocabularies
    assert p.vocabularies["punch_qc_verdict@1"] == ("keep", "review", "exclude", "already_excluded")
