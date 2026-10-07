#!/usr/bin/env python3
"""Generator for the negative control of assess-batch: copy a `batch_evidence` directory with the
slide structure removed, so the right answer is `proceed_uncorrected`. For every cluster the cells of
each time point are redistributed over the slides at the share that time point has in
slide_by_timepoint (so dominant_batch_pct equals expected_dominant_pct and batch_excess is zero), the
within-cluster kNN same-batch excess is set near zero (seeded, between -0.02 and 0.05), the overview
and the manifest summary are recomputed from the rewritten rows, and the single-time-point clusters
stay single-slide because the design puts them there. The depth and composition-by-time-point columns
are untouched. Registered as the plugin tool `mix_batches` (0.4.1; the engine resolves a control's
`generator.tool` through the plugin's tool registry and runs it with the job below); the method keeps
a documented copy beside the control `negative-batch-mixed` in stringency-xenium-method
`modules/assess-batch/controls/mix_batches.py`, the source of this file.

Job JSON on stdin: {"inputs": {"input": <fixture dir>}, "params": {"seed": int},
                    "outputs": {"object": <output dir>}}. Stdlib only.
"""

from __future__ import annotations

import csv
import json
import random
import shutil
import sys
from pathlib import Path


def read(p: Path) -> tuple[list[str], list[dict[str, str]]]:
    with p.open(newline="") as f:
        r = csv.DictReader(f)
        rows = list(r)
        return list(r.fieldnames or []), rows


def write(p: Path, cols: list[str], rows: list[dict[str, object]]) -> None:
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def main() -> int:
    job = json.load(sys.stdin)
    src = Path(job["inputs"]["input"])
    out = Path(job["outputs"]["object"])
    seed = int((job.get("params") or {}).get("seed", 1))
    rng = random.Random(seed)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out)
    manifest = json.loads((out / "manifest.json").read_text())
    batch_key = manifest.get("batch_key", "slide")
    tp_col = manifest.get("timepoint_column", "timepoint_h")
    rule = manifest.get("rule") or {}
    _, design = read(out / "slide_by_timepoint.csv")
    slides = sorted({r[batch_key] for r in design})
    tps = sorted({r[tp_col] for r in design})
    cells = {(r[batch_key], r[tp_col]): float(r["n_cells"]) for r in design}
    share = {
        (s, t): cells.get((s, t), 0.0) / max(sum(cells.get((x, t), 0.0) for x in slides), 1.0)
        for s in slides
        for t in tps
    }
    shared_tps = [t for t in tps if sum(1 for s in slides if cells.get((s, t), 0.0) > 0) > 1]
    _tp_cols, by_tp = read(out / "composition_by_timepoint.csv")
    tp_by_cluster = {r["cluster"]: r for r in by_tp}
    sl_cols, by_slide = read(out / "composition_by_slide.csv")
    a_cols, assess = read(out / "batch_assessment.csv")
    s_cols, summary = read(out / "cluster_summary.csv")
    summ_by_cluster = {r["cluster"]: r for r in summary}
    total = sum(float(r["n_cells"]) for r in assess)
    knn_w = 0.0
    knn_n = 0.0
    for a, sl in zip(assess, by_slide):
        c = a["cluster"]
        tp_row = tp_by_cluster[c]
        new_slide = {s: 0.0 for s in slides}
        for t in tps:
            m = float(tp_row.get(t, 0) or 0)
            for s in slides:
                new_slide[s] += m * share[(s, t)]
        n = sum(new_slide.values()) or 1.0
        for s in slides:
            sl[s] = str(round(new_slide[s]))
        sl["total"] = str(round(n))
        dom = max(new_slide, key=lambda s: new_slide[s])
        dom_pct = 100 * new_slide[dom] / n
        a["dominant_batch"] = dom
        a["dominant_batch_pct"] = f"{dom_pct:.1f}"
        a["expected_dominant_pct"] = f"{dom_pct:.1f}"
        a["batch_excess"] = "0.0"
        n_shared = sum(float(tp_row.get(t, 0) or 0) for t in shared_tps)
        if n_shared > 0:
            k = rng.uniform(-0.02, 0.05)
            a["knn_same_batch_excess"] = f"{k:.3f}"
            knn_w += k * n_shared
            knn_n += n_shared
        else:
            a["knn_same_batch_excess"] = ""
        a["flagged"] = "FALSE"
        s_row = summ_by_cluster.get(c)
        if s_row is not None:
            s_row["max_slide_pct"] = f"{dom_pct:.1f}"
            s_row["dominant_slide"] = dom
            s_row["batch_flag"] = "FALSE"
    write(out / "composition_by_slide.csv", sl_cols, by_slide)
    write(out / "batch_assessment.csv", a_cols, assess)
    write(out / "cluster_summary.csv", s_cols, summary)
    overall = round(knn_w / knn_n, 3) if knn_n else None
    o_cols, overview = read(out / "batch_overview.csv")
    ov = overview[0]
    ov["knn_same_batch_excess_overall"] = "" if overall is None else f"{overall:.3f}"
    ov["n_clusters_flagged"] = "0"
    ov["fraction_cells_in_flagged_clusters"] = "0"
    ov["rule_suspected"] = (
        "true"
        if (overall is not None and overall > float(rule.get("knn_threshold", 0.3)))
        else "false"
    )
    write(out / "batch_overview.csv", o_cols, overview)
    summ = manifest.get("summary") or {}
    summ.update(
        {
            "knn_same_batch_excess_overall": overall,
            "n_clusters_flagged": 0,
            "fraction_cells_in_flagged_clusters": 0,
            "suspected": ov["rule_suspected"] == "true",
        }
    )
    manifest["summary"] = summ
    manifest["source"] = (
        f"{manifest.get('source', '')}; mix_batches seed={seed}: slide structure removed (negative control)".strip(
            "; "
        )
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(
        f"mix_batches: {len(assess)} clusters redistributed over {len(slides)} slides; overall kNN excess {overall}; {int(total)} cells"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
