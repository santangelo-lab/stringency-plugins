"""Design schema and operation vocabulary. Provisional until app-1 sessions 1 through 3."""

from __future__ import annotations

from typing import Any

DESIGN_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["design", "units", "factors", "replication_unit"],
    "properties": {
        "design": {"const": 1},
        "units": {
            "type": "object",
            "required": ["observation", "sample"],
            "additionalProperties": {"type": "string"},
        },
        "factors": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["column", "levels"],
                "properties": {
                    "column": {"type": "string"},
                    "levels": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                },
            },
        },
        "batch": {"type": "array", "items": {"type": "string"}},
        "replication_unit": {"type": "string"},
        "holdout": {"type": "array"},
    },
}

# Operation names the spatial TMA pipeline is expected to use (design 3.1 example). Parameter
# schemas are filled from session 3.
OPERATIONS: dict[str, dict[str, Any]] = {
    op: {"type": "object", "properties": {}, "additionalProperties": True}
    for op in (
        "qc_filter", "normalize", "select_hvg", "cluster", "find_markers", "annotate_clusters",
        "spatial_neighborhood", "characterise_niches", "test_differential_expression", "report",
    )
}
