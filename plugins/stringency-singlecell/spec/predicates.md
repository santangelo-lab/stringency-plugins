# Predicates (session 5 table, first four delivered 2026-09-17; four upstream ones 2026-10-07)

| id | phase | scope | default | fires when | covers |
|---|---|---|---|---|---|
| `spatial.coords_missing` | pre | `split_punches` | block | no `punch_coordinates` object; zero punches; a polygon has < 3 vertices or is unclosed; duplicate ids; a layout punch for the bundle's (slide, region) has no polygon; a polygon id is not in the layout | `split_punches.*` |
| `sc.low_cell_count` | post | `split_punches`, `qc_cells` | flag | an included punch in a `punch_bundle_set` or `qc_object_set` has fewer cells than the floor: policy `ranges.sc.cells_per_punch[<band>][0]`, else 500 | `split_punches.min_transcripts`, `.min_area` |
| `sc.qc_fail_fraction` | post | `qc_cells` | flag | an included punch's `fail_fraction` exceeds `ranges.sc.qc_fail_fraction[<band>][1]`, else 0.5 | the four `qc_cells` thresholds |
| `sc.area_join_unverified` | post | `qc_cells` | block, invariant | no `qc_object_set`, or its `join_verification` is not `verified`, not a keyed method, not every cell checked, no columns listed, or refused by the extractor | `qc_cells.min_cellarea`, `.max_cellarea` |
| `sc.exclusion_proposed` | post | `flag_outlier_punches` | flag | the judgment's consensus labels at least one punch `review` (vocabulary `punch_qc_verdict@2`, 2026-09-21: reviewers never exclude; the owner decides at this hold) or `exclude` (v1) | `flag_outlier_punches.*` |
| `sc.export_mismatch` | post | `export_h5ad` | block | the h5ad written for a Python step differs from its Seurat parent in cell or gene count, lacks an `obs` column of the parent, the label column, or `obsm["spatial"]` | `export_h5ad.*` |
| `sc.decision_unreviewed` | pre | `normalize`, `cluster_umap` | flag | the module declares `decision_points` and none of them is an agent proposal departing from its default (then `param.agent_proposed` holds instead), unless every decision point comes from a fork's `--set`; owner decision 2026-10-07: a person signs off on every decision point, even at the default; evidence default, value, source per point and the agent's `rationale_ref` | `normalize.method`, `.scale_factor`, `cluster_umap.ndim`, `.resolution` |
| `sc.batch_effect_suspected` (v2) | post | `cluster_umap` | **log** | the latest `seurat_object`'s `uns_flags.batch_assessment.suspected` is true (the clustering module's declared rule over composition per slide and the nearest-neighbour same-slide fraction within the time points both slides carry); since 0.4.0 the record of that rule only, logged and not held: the `assess_batch` judgment and `sc.batch_route_review` decide the route (v1 held here) | `cluster_umap.*`, `reduce_pca.integration` |
| `sc.batch_route_review` | post | `assess_batch` | flag | the batch-route judgment produced a consensus, whatever its label (owner, 2026-10-07: a hold before the run moves on, regardless of the verdict); `accept` continues this run uncorrected, `reject` closes the attempt and the operator forks at `03_reduce` with the correction the owner names; evidence every item's label, source, replicate labels and confidences, and the consensus label; silent only without a consensus | `assess_batch.*`, `reduce_pca.integration` |
| `sc.unknown_fraction` | post | `apply_labels` | flag | `domain.labels.unknown_fraction` of the latest `seurat_object` exceeds `ranges.sc.unknown_fraction[<band>][1]`, else 0.2 | `annotate_clusters.*` |
| `qc.filter_ordering` | post | `normalize`, `reduce_pca`, `cluster_umap` | flag | `uns_flags.normalisation.cells_filtered_after` is true: cells were removed after normalisation, so the normalised values no longer describe the population | `normalize.*` |

The first four read `ctx.state.objects[*].summary.domain` only; `sc.exclusion_proposed` reads
`ctx.output.consensus`; the 2026-10-07 four read `ctx.action` (decision points) or the latest
`seurat_object` summary's `uns_flags` and `domain.labels`. Fixtures: `tests/test_predicates.py`
`CASES` (must-fire and must-pass per id) plus the variant tests. Policy example for the method
repo:

```yaml
ranges:
  sc.cells_per_punch:   {strict: [2000, 1e9], standard: [500, 1e9], wide: [100, 1e9]}
  sc.qc_fail_fraction:  {strict: [0, 0.2],    standard: [0, 0.5],   wide: [0, 0.8]}
```
