"""The design schema, the Lyons CLP design as its first instance, and the plugin surface."""

from __future__ import annotations

import re
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
        (lambda d: d["units"].__setitem__("observation", ""), "observation"),
        (lambda d: d.pop("replication_unit"), "replication_unit"),
        (
            lambda d: d["factors"].__setitem__("timepoint_h", {"column": "t", "levels": []}),
            "levels",
        ),
        (lambda d: d.__setitem__("extra", 1), "extra"),
        (lambda d: d.__setitem__("factors", {}), "factors"),
    ],
    ids=[
        "obs-empty",
        "no-replication-unit",
        "empty-levels",
        "unknown-key",
        "no-factors",
    ],
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


@pytest.mark.institutional
@pytest.mark.skipif(not LYONS_DESIGN.exists(), reason=f"{LYONS_DESIGN} not mounted")
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
    # the string the engine records equals the package version (they drifted once, 0.4.0 -> 0.4.1)
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    m = re.search(r'^version = "([^"]+)"', pyproject.read_text(), flags=re.MULTILINE)
    assert m and m.group(1) == VERSION
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
        "sc.exclusion_proposed",
        "sc.export_mismatch",
        "sc.decision_unreviewed",
        "sc.louvain_too_large",  # 0.8.6
        "sc.batch_effect_suspected",
        "sc.batch_route_review",
        "sc.unknown_fraction",
        "sc.fine_label_uncited",  # 0.8.5
        "qc.filter_ordering",
        # the downstream seven (0.7.0, engine backlog L54)
        "de.replication_unit",
        "de.covariate_omission",
        "de.selection_bias",
        "test.multiple_comparison",
        "test.assumptions_unchecked",
        "spatial.neighborhood_undeclared",
        "spatial.no_permutation_null",
        # droplet kits (0.8.0)
        "sc.qc_floor_above_data",
        "sc.normalization_depth",
        "sc.pc1_single_gene",
        "sc.pca_depth_confounded",
    }
    assert "assess_batch" in p.operations and p.vocabularies["batch_route@1"] == (
        "proceed_uncorrected",
        "correct_batch",
        "cannot_tell",
    )
    assert "reduce_cluster" not in p.operations
    assert validate({"integration": "harmony", "n_features": 2000}, OPERATIONS["reduce_pca"]) == []
    assert validate({"integration": "mnn"}, OPERATIONS["reduce_pca"])
    assert (
        validate(
            {"ndim": 35, "resolution": 0.4, "resolutions": [0.2, 0.4]}, OPERATIONS["cluster_umap"]
        )
        == []
    )
    assert validate({"anything": 1}, OPERATIONS["annotate_clusters"])


def test_observation_unit_may_be_any_name() -> None:
    """0.8.0: the plugin is not Xenium's alone; a droplet design names the cell, a nucleus, a
    spot or a bead as the observation and a donor as the sample and replication unit."""
    from stringency.schemas import validate

    from stringency_singlecell.schemas import DESIGN_SCHEMA

    d = {
        "design": 1,
        "units": {"observation": "nucleus", "sample": "donor"},
        "factors": {"condition": {"column": "condition", "levels": ["ctrl", "stim"]}},
        "batch": [],
        "replication_unit": "donor",
    }
    assert validate(d, DESIGN_SCHEMA) == []
