# Predicates (session 5 table, first four delivered 2026-09-17; four upstream ones 2026-10-07)

| id | phase | scope | default | fires when | covers |
|---|---|---|---|---|---|
| `spatial.coords_missing` (@2) | pre | `split_punches` | block | no `punch_coordinates` object; zero punches; a polygon has < 3 vertices or is unclosed; duplicate ids; a layout punch of any bound bundle's (slide, region) has no polygon (version 2, 2026-10-14: every bundle, not the first; evidence names the region); a polygon id is not in the layout on any region | `split_punches.*` |
| `sc.low_cell_count` | post | `split_punches`, `qc_cells` | flag | an included punch in a `punch_bundle_set` or `qc_object_set` has fewer cells than the floor: policy `ranges.sc.cells_per_punch[<band>][0]`, else 500 | `split_punches.min_transcripts`, `.min_area` |
| `sc.qc_fail_fraction` | post | `qc_cells` | flag | an included punch's `fail_fraction` exceeds `ranges.sc.qc_fail_fraction[<band>][1]`, else 0.5 | the four `qc_cells` thresholds |
| `sc.area_join_unverified` | post | `qc_cells` | block, invariant | no `qc_object_set`, or its `join_verification` is not `verified`, not a keyed method, not every cell checked, no columns listed, or refused by the extractor | `qc_cells.min_cellarea`, `.max_cellarea` |
| `sc.exclusion_proposed` | post | `flag_outlier_punches` | flag | the judgment's consensus labels at least one punch `review` (vocabulary `punch_qc_verdict@2`, 2026-09-21: reviewers never exclude; the owner decides at this hold) or `exclude` (v1) | `flag_outlier_punches.*` |
| `sc.export_mismatch` | post | `export_h5ad` | block | the h5ad written for a Python step differs from its Seurat parent in cell or gene count, lacks an `obs` column of the parent, the label column, or `obsm["spatial"]` | `export_h5ad.*` |
| `sc.decision_unreviewed` | pre | `normalize`, `cluster_umap` | flag | the module declares `decision_points` and none of them is an agent proposal departing from its default (then `param.agent_proposed` holds instead), unless every decision point comes from a fork's `--set`, the objective's `params` (`declared`) or the parent run of a fork (`inherited`); owner decision 2026-10-07: a person signs off on every decision point, even at the default; evidence default, value, source per point and the agent's `rationale_ref` | `normalize.method`, `.scale_factor`, `cluster_umap.ndim`, `.resolution` |
| `sc.batch_effect_suspected` (v2) | post | `cluster_umap` | **log** | the latest `seurat_object`'s `uns_flags.batch_assessment.suspected` is true (the clustering module's declared rule over composition per slide and the nearest-neighbour same-slide fraction within the time points both slides carry); since 0.4.0 the record of that rule only, logged and not held: the `assess_batch` judgment and `sc.batch_route_review` decide the route (v1 held here) | `cluster_umap.*`, `reduce_pca.integration` |
| `sc.batch_route_review` (v2) | post | `assess_batch` | flag | the batch-route judgment's reviewers AGREED on a label (`source: agreed`); the owner decides before the run moves on (owner, 2026-10-07): `accept` means agreement with the reviewers and the operator acts on the label (`correct_batch`: a fork at `03_reduce` with the recommended correction; `proceed_uncorrected`: the run continues; `cannot_tell`: the reason must name the route), `reject` means disagreement and the reason names the route; silent when the owner already chose the label at the disagreement item hold (`accepted`, `override`), when unresolved, or without a consensus (v1 fired on any consensus and read `accept` as "continue uncorrected"); evidence every item's label, source, replicate labels and confidences, the consensus label, and `recommended_correction` from the replicates | `assess_batch.*`, `reduce_pca.integration` |
| `sc.unknown_fraction` | post | `apply_labels` | flag | `domain.labels.unknown_fraction` of the latest `seurat_object` exceeds `ranges.sc.unknown_fraction[<band>][1]`, else 0.2 | `annotate_clusters.*` |
| `qc.filter_ordering` | post | `normalize`, `reduce_pca`, `cluster_umap` | flag | `uns_flags.normalisation.cells_filtered_after` is true: cells were removed after normalisation, so the normalised values no longer describe the population | `normalize.*` |
| `de.replication_unit` | pre | `test_differential_expression`, `compose_cells` | block | the design declares biological replicates and the proposed `replicate_unit` ranks below the replication unit in the design's units (cell, punch, sample): pseudoreplication (0.7.0, 2026-10-22, L54) | `*.replicate_unit` |
| `de.covariate_omission` | pre | the same | flag | the design declares a batch variable and no model term carries it (`factor`, `covariates`, `batch`, `block`, `formula`); the person says whether it is confounded or belongs in the model | `*.factor` |
| `de.selection_bias` | pre | the same | flag | the tested `factor` is not a declared design factor, a clustering, labelling or annotation step precedes this one in the run, and the design has no holdout: the groups were derived from the data under test | `*.factor` |
| `test.multiple_comparison` | pre | the same | flag | `correction`, `p_adjust` or `adjust` is none or off, or `fdr` is 1 or more: no correction in effect | `*.fdr` |
| `test.assumptions_unchecked` | pre | the same | flag | `min_samples_per_group` below the floor (`ranges.test.min_samples_per_group[<band>][0]`, else 2) or `min_cells_per_sample` of 0: the test's dispersion has nothing to stand on | `*.min_samples_per_group` |
| `spatial.neighborhood_undeclared` | pre | `neighborhood_enrichment` | block | no positive `radius_um`, `radius`, `k`, `n_neighs` or `n_neighbors` among the step's parameters: the neighbourhood's scale is implicit | `neighborhood_enrichment.radius_um` |
| `spatial.no_permutation_null` | pre | `neighborhood_enrichment` | block | `n_perms` absent, zero or below the floor (`ranges.spatial.n_perms[<band>][0]`, else 100) | `neighborhood_enrichment.n_perms` |
| `sc.qc_floor_above_data` | pre | `qc_cells` | block | `min_genes` above the data's `n_genes_p99` or `min_counts` above `total_counts_p99` (facts the QC metrics step wrote into an `analysis_summary`): a whole-transcriptome floor on a targeted panel (0.8.0, benchmark Phase 1) | `qc_cells.min_genes`, `.min_counts` |
| `sc.normalization_depth` | pre | `normalize`, `select_hvg` | flag | a log-based method or flavour proposed when `median_umis_per_cell` is below `ranges.sc.lognorm_min_median_umis[<band>][0]`, else 2000 | `normalize.method`, `select_hvg.flavor` |
| `sc.pc1_single_gene` | post | `reduce_pca` | flag | `pc1_top_abs_load` above `ranges.sc.pc1_top_abs_load[<band>][1]`, else 0.5: PC1 is one gene (no per-gene scaling) | `reduce_pca.scale` |
| `sc.pca_depth_confounded` | post | `reduce_pca` | flag | `max_top5_depth_corr` above `ranges.sc.max_top5_depth_corr[<band>][1]`, else 0.5: a top PC tracks sequencing depth | `reduce_pca.regress_out` |

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
