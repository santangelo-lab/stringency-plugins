"""Domain wording for the methods paragraph and the init echo-back. Provisional."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stringency.actions import Action
from stringency.config import Design, InputsManifest, Objective


def describe(action: Action) -> str:
    p = ", ".join(f"{k}={v}" for k, v in sorted(action.parameters.items()))
    return f"{action.operation.replace('_', ' ')} was run" + (f" with {p}" if p else "") + f" (step {action.step_id})"


def echo(design: Design, objective: Objective, inputs: InputsManifest, counts: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for name, summary in counts.items():
        if isinstance(summary, dict) and "n_obs" in summary:
            parts.append(f"{summary['n_obs']} {design.units.get('observation', 'observations')}s (input {name})")
    if design.replication_unit:
        parts.append(f"the biological replicate is {design.replication_unit}")
    for c in objective.contrasts:
        parts.append(f"the question is {c[1]} versus {c[2]} {objective.question.replace('_', ' ')}")
    return "; ".join(parts) + "." if parts else ""
