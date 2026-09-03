from stringency.plugins import load_plugins


def test_plugin_loads() -> None:
    plugins = load_plugins(refresh=True)
    assert "stringency-singlecell" in plugins
    p = plugins["stringency-singlecell"]
    assert "anndata" in p.object_types and "differential_expression" in p.objective_questions
    assert p.predicates() == []
