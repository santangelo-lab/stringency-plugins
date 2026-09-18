"""Domain wording for the methods paragraph and the init echo-back."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stringency.actions import Action
from stringency.config import Design, InputsManifest, Objective

_VERBS = {
    "split_punches": "the region was split into punches by the hand-drawn coordinates",
    "qc_cells": "cells were filtered on transcript count, gene count, and cell area",
    "resegment": "the region was resegmented",
}


def _plural(unit: str) -> str:
    """cell -> cells, punch -> punches, observation -> observations."""
    return unit + ("es" if unit.endswith(("ch", "sh", "s", "x", "z")) else "s")


def describe(action: Action) -> str:
    p = ", ".join(f"{k}={v}" for k, v in sorted(action.parameters.items()))
    verb = _VERBS.get(action.operation, f"{action.operation.replace('_', ' ')} was run")
    return verb + (f" with {p}" if p else "") + f" (step {action.step_id})"


def echo(
    design: Design, objective: Objective, inputs: InputsManifest, counts: Mapping[str, Any]
) -> str:
    parts: list[str] = []
    for name, summary in counts.items():
        if not isinstance(summary, dict):
            continue
        dom = summary.get("domain", {}) if isinstance(summary.get("domain"), dict) else {}
        t = summary.get("type")
        if t == "xenium_bundle":
            parts.append(
                f"{summary.get('n_obs')} cells on slide {dom.get('slide')} region {dom.get('region')}"
                f" (input {name})"
            )
        elif t == "tma_layout":
            parts.append(
                f"{summary.get('n_obs')} punches from {dom.get('n_animals')} animals on"
                f" {dom.get('n_slides')} slides (input {name})"
            )
        elif t == "punch_coordinates":
            parts.append(f"{summary.get('n_obs')} hand-drawn punch polygons (input {name})")
        elif (
            str(summary.get("extractor", "")).startswith("sc.qc_metrics_table")
            and "n_obs" in summary
        ):
            parts.append(f"{summary['n_obs']} punches in the QC metrics table (input {name})")
        elif "n_obs" in summary:
            parts.append(
                f"{summary['n_obs']} {_plural(design.units.get('observation', 'observation'))} (input {name})"
            )
    for fname, fac in design.factors.items():
        if len(fac.levels) == 1:
            parts.append(f"{fname} is fixed at {fac.levels[0]} (no control arm)")
        else:
            parts.append(f"{fname} levels {', '.join(fac.levels)}")
    if design.batch:
        parts.append(
            f"batch variable{'s' if len(design.batch) > 1 else ''}: {', '.join(design.batch)}"
        )
    if design.replication_unit:
        parts.append(f"the biological replicate is the {design.replication_unit}")
    if objective.contrasts:
        for c in objective.contrasts:
            parts.append(
                f"the question is {c[1]} versus {c[2]} {objective.question.replace('_', ' ')}"
            )
    else:
        parts.append(f"the question is {objective.question.replace('_', ' ')} with no contrasts")
    return "; ".join(parts) + "." if parts else ""
