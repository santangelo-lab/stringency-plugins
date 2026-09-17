"""Helpers shared by the predicates: find objects by type and read their domain blocks."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from stringency.exit_codes import ConfigError
from stringency.predicates import GateContext

SOURCE = "stringency-singlecell"


def objects_of_type(ctx: GateContext, *types: str) -> Iterator[tuple[str, dict[str, Any]]]:
    """(object name, domain block) for every state object whose type is in `types`."""
    for name, obj in ctx.state.objects.items():
        if obj.type in types:
            dom = obj.summary.get("domain", {})
            yield name, dict(dom) if isinstance(dom, dict) else {}


def band(ctx: GateContext, key: str) -> list[float] | None:
    """The policy range for `key` under the project's profile, if the policy declares one."""
    try:
        return ctx.policy.range_for(key, ctx.project.profile)
    except ConfigError:  # a policy without that profile: fall back to the predicate default
        return None
