"""The design schema, the Lyons CLP design as its first instance, and the plugin surface."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from stringency.config import Design
from stringency.plugins import load_plugins
from stringency.schemas import schema_is_valid, validate

from stringency_singlecell.schemas import DESIGN_SCHEMA, OPERATIONS
from tests.helpers import DESIGN

LYONS_DESIGN = Path("/lab/projects/Lyons_CLP/design.yml")


def test_design_schema_is_a_valid_schema() -> None:
    assert schema_is_valid(DESIGN_SCHEMA) is None


def test_reference_design_validates_and_loads() -> None:
    assert validate(DESIGN, DESIGN_SCHEMA) == []
    d = Design.model_validate(DESIGN)
    assert d.has_biological_replicates
    assert d.columns() == ["punch_id", "animal", "timepoint_h", "condition", "slide"]
    assert d.replication_unit in d.units.values()


@pytest.mark.parametrize(
    "mutate,fragment",
    [
        (lambda d: d["units"].__setitem__("observation", "punch"), "observation"),
        (lambda d: d.pop("replication_unit"), "replication_unit"),
        (
            lambda d: d["factors"].__setitem__("timepoint_h", {"column": "t", "levels": []}),
            "levels",
        ),
        (lambda d: d.__setitem__("extra", 1), "extra"),
        (lambda d: d.__setitem__("factors", {}), "factors"),
    ],
    ids=["obs-not-cell", "no-replication-unit", "empty-levels", "unknown-key", "no-factors"],
)
def test_design_schema_rejects(mutate, fragment: str) -> None:  # type: ignore[no-untyped-def]
    import copy

    d = copy.deepcopy(DESIGN)
    mutate(d)
    problems = validate(d, DESIGN_SCHEMA)
    assert problems and any(fragment in p for p in problems), problems


def test_single_level_condition_factor_is_allowed() -> None:
    assert DESIGN["factors"]["condition"]["levels"] == ["CLP"]
    assert validate(DESIGN, DESIGN_SCHEMA) == []


@pytest.mark.skipif(not LYONS_DESIGN.exists(), reason="Lyons CLP project directory not mounted")
def test_lyons_clp_design_file_is_the_reference_design() -> None:
    d = yaml.safe_load(LYONS_DESIGN.read_text())
    assert validate(d, DESIGN_SCHEMA) == []
    core = {k: d[k] for k in DESIGN}
    assert core == DESIGN
    assert d.get("source"), "a manual declaration carries a source line"


def test_operation_schemas_are_valid_and_typed() -> None:
    for name, schema in OPERATIONS.items():
        assert schema_is_valid(schema) is None, name
    assert (
        validate(
            {"min_transcripts": 10, "min_area": 50, "qv_threshold": 25}, OPERATIONS["split_punches"]
        )
        == []
    )
    assert validate({"min_transcripts": -1}, OPERATIONS["split_punches"])
    assert validate({"bogus": 1}, OPERATIONS["qc_cells"])
    assert (
        validate(
            {"min_nCount": 60, "min_nFeature": 50, "min_cellarea": 20, "max_cellarea": 300},
            OPERATIONS["qc_cells"],
        )
        == []
    )


def test_plugin_surface() -> None:
    p = load_plugins(refresh=True)["stringency-singlecell"]
    from stringency_singlecell import VERSION

    assert p.version == VERSION
    assert "processed_object" in p.objective_questions
    assert "qc_summary" in p.objective_questions
    assert set(p.object_types) >= {
        "xenium_bundle",
        "punch_coordinates",
        "tma_layout",
        "punch_bundle_set",
        "qc_object_set",
    }
    for ot in p.object_types.values():
        assert ot.extractor in p.tools and p.tools[ot.extractor].script.exists()
        assert ot.extractor_id == f"sc.{ot.name}@1"
    assert p.defaults["min_cells_per_punch"] == 500
    assert set(p.predicates()) == {
        "sc.area_join_unverified",
        "sc.low_cell_count",
        "sc.qc_fail_fraction",
        "spatial.coords_missing",
    }
