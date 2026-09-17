"""In-memory GateContext builder for the singlecell predicates. Predicates read only
`ctx.state.objects`, `ctx.action`, `ctx.policy`, and `ctx.project.profile`, so the project
config is a stand-in; the engine's own classes are used wherever they are cheap to build."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stringency import hashing
from stringency.actions import Action
from stringency.config import Design, Objective
from stringency.policy import Policy, ProfilePolicy
from stringency.predicates.context import GateContext, OutputBundle, ProjectConfig
from stringency.state import ObjectState, State, StepRecord

DESIGN: dict[str, Any] = {
    "design": 1,
    "units": {"observation": "cell", "sample": "punch_id", "animal": "animal"},
    "factors": {
        "timepoint_h": {"column": "timepoint_h", "levels": ["6", "24", "48"]},
        "condition": {"column": "condition", "levels": ["CLP"]},
    },
    "batch": ["slide"],
    "replication_unit": "animal",
}

OBJECTIVE: dict[str, Any] = {
    "objective": 1,
    "id": "lyons_clp_xenium_qc",
    "question": "processed_object",
    "contrasts": [],
    "replication_unit": "animal",
    "min_n_per_group": 0,
    "deliverables": ["qc_objects", "cellstats", "qc_report"],
}


@dataclass(frozen=True)
class _Cfg:
    mode: str = "pipeline"
    profile: str = "standard"


def policy(ranges: dict[str, dict[str, list[float]]] | None = None) -> Policy:
    prof = {
        "strict": ProfilePolicy(remap={"flag": "block"}, params="locked", qc_ranges="strict"),
        "standard": ProfilePolicy(),
        "exploratory": ProfilePolicy(remap={"block": "flag"}, params="free", qc_ranges="wide"),
    }
    return Policy(version="test", profiles=prof, ranges=ranges or {})


def obj(type_: str, summary: dict[str, Any]) -> ObjectState:
    summary = {"extractor": f"sc.{type_}@1", "type": type_, **summary}
    return ObjectState(
        type=type_, digest=hashing.prefixed(hashing.hash_json(summary)), summary=summary
    )


def action(operation: str, step: str = "01_step", **params: Any) -> Action:
    return Action(
        action_id="A",
        run_id="RUN",
        step_id=step,
        attempt=1,
        operation=operation,
        module=f"{operation.replace('_', '-')}@0.1.0",
        parameters=dict(params),
        param_source={k: "default" for k in params},
        inputs={},
        input_digest="blake3:" + "00" * 32,
        params_hash="blake3:" + "00" * 32,
        proposed_by="pipeline",
    )


def ctx(
    operation: str,
    objects: dict[str, ObjectState],
    *,
    phase: str = "pre",
    profile: str = "standard",
    ranges: dict[str, dict[str, list[float]]] | None = None,
    history: tuple[StepRecord, ...] = (),
    output: OutputBundle | None = None,
    **params: Any,
) -> GateContext:
    design = Design.model_validate(DESIGN)
    objective = Objective.model_validate(OBJECTIVE)
    act = action(operation, **params)
    pc = ProjectConfig(
        config=_Cfg(profile=profile),  # type: ignore[arg-type]
        pipeline=None,  # type: ignore[arg-type]
        modules={},
        inputs=None,  # type: ignore[arg-type]
        object_types=(
            "xenium_bundle",
            "punch_coordinates",
            "tma_layout",
            "punch_bundle_set",
            "qc_object_set",
        ),
    )
    state = State(
        run_id="RUN",
        after_step=None,
        objects=objects,
        design=design.model_dump(),
        objective=objective.model_dump(),
        history=history,
        env={},
        mode="pipeline",
        profile=profile,
    )
    return GateContext(
        phase=phase,  # type: ignore[arg-type]
        project=pc,
        objective=objective,
        design=design,
        state=state,
        action=act,
        history=history,
        output=output,
        policy=policy(ranges),
    )


# ---- summaries in the shape the extractors emit -----------------------------------------


def bundle_summary(slide: str = "0076570", region: str = "Liver", n: int = 25720) -> dict[str, Any]:
    return {
        "n_obs": n,
        "n_var": 5106,
        "fields": {
            "cells_columns": ["cell_id", "cell_area"],
            "h5_feature_types": {"Gene Expression": 5106},
        },
        "counts_per_group": {},
        "domain": {
            "slide": slide,
            "region": region,
            "kind": "vendor",
            "n_cells": n,
            "h5_order_matches_cells": True,
            "h5_set_matches_cells": True,
        },
    }


def punch(
    pid: str, *, n_vertices: int = 4, closed: bool = True, rect: bool = True
) -> dict[str, Any]:
    return {
        "punch_id": pid,
        "n_vertices": n_vertices,
        "closed": closed,
        "area_um2": 7.5e6,
        "bbox": {"x_min": 0.0, "x_max": 2740.0, "y_min": 0.0, "y_max": 2740.0},
        "bbox_area_um2": 7.5e6,
        "is_rectangle": rect,
        "polygon": True,
    }


def coords_summary(punches: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [p["punch_id"] for p in punches]
    return {
        "n_obs": len(punches),
        "fields": {"punch_ids": ids},
        "counts_per_group": {},
        "domain": {
            "source": "manual annotation in Xenium Explorer",
            "format": "xenium_explorer_export",
            "input_unit": "file",
            "n_files": 1,
            "punches": punches,
            "duplicate_punch_ids": sorted({i for i in ids if ids.count(i) > 1}),
            "n_polygons_not_closed": sum(1 for p in punches if not p["closed"]),
            "n_degenerate": sum(1 for p in punches if p["n_vertices"] < 3),
            "all_rectangles": all(p["is_rectangle"] for p in punches),
        },
    }


LIVER_0076570 = ["24-2-Liver", "48-1-Liver", "48-2-Liver"]


def layout_summary(regions: dict[str, list[str]] | None = None) -> dict[str, Any]:
    regions = regions or {"0076570/Liver": LIVER_0076570}
    punches = [
        {
            "punch_id": pid,
            "slide": k.split("/")[0],
            "region": k.split("/")[1],
            "animal": pid.rsplit("-", 1)[0] if pid.count("-") >= 2 else pid,
            "timepoint_h": pid.split("-")[0],
            "organ": k.split("/")[1].lower(),
            "punch": "single",
        }
        for k, ids in regions.items()
        for pid in ids
    ]
    return {
        "n_obs": len(punches),
        "fields": {
            "columns": [
                "punch_id",
                "slide",
                "region",
                "animal",
                "timepoint_h",
                "organ",
                "punch",
                "condition",
            ]
        },
        "counts_per_group": {},
        "domain": {
            "punches": punches,
            "regions": regions,
            "n_slides": len({p["slide"] for p in punches}),
            "n_animals": len({p["animal"] for p in punches}),
            "missing_required_columns": [],
            "duplicate_punch_ids": [],
        },
    }


def set_summary(counts: dict[str, int]) -> dict[str, Any]:
    punches = [
        {
            "punch_id": k,
            "dir": f"punch_{k}",
            "n_cells": v,
            "h5_order_matches_cells": True,
            "h5_set_matches_cells": True,
        }
        for k, v in counts.items()
    ]
    return {
        "n_obs": sum(counts.values()),
        "fields": {"punch_ids": list(counts)},
        "counts_per_group": {},
        "domain": {
            "n_punches": len(punches),
            "punches": punches,
            "region_metrics_present": True,
            "all_h5_orders_match_cells": True,
        },
    }


def join_ok(n: int) -> dict[str, Any]:
    return {
        "method": "keyed_reindex_on_cell_id",
        "verified": True,
        "n_cells": n,
        "n_cells_checked": n,
        "columns_checked": ["cell_area", "nucleus_area", "transcript_counts"],
        "detail": "obs.index == barcodes; every joined value equals the by-id lookup",
        "verified_by_extractor": True,
    }


def qc_summary(
    rows: list[tuple[str, int, int]],
    join: dict[str, Any] | None = None,
    excluded: tuple[str, ...] = (),
) -> dict[str, Any]:
    punches = [
        {
            "punch_id": pid,
            "tissue": "liver",
            "included": pid not in excluded,
            "n_before": b,
            "n_after": a,
            "n_cells": a,
            "fail_fraction": round(1 - a / b, 4) if b else None,
            "thresholds": {
                "min_nCount": 10,
                "min_nFeature": 20,
                "min_cellarea": 10,
                "max_cellarea": 1000,
            },
        }
        for pid, b, a in rows
    ]
    n = sum(b for _, b, _ in rows)
    return {
        "n_obs": sum(a for _, _, a in rows),
        "fields": {"punch_ids": [r[0] for r in rows]},
        "counts_per_group": {},
        "domain": {
            "n_punches": len(rows),
            "punches": punches,
            "excluded_punches": list(excluded),
            "join_verification": join_ok(n) if join is None else join,
        },
    }
