# Object types (design 4.2), `stringency-singlecell` 0.4.0

Every extractor is a standalone script under `tools/`, run as `python3 <script> <path>
<design.json>` (or `Rscript <script> ...` for `extract_seurat.R`; the executor dispatches by suffix) inside the module environment; shared parsing is in `tools/_xenium_common.py`,
imported through the script's own directory so the plugin package need not be installed in the
container. `extract_xenium_bundle` and `extract_punch_bundle_set` need pyarrow and h5py; the rest
are stdlib.

| type | id | path | `n_obs` | `fields` | notes |
|---|---|---|---|---|---|
| `xenium_bundle` | `sc.xenium_bundle@1` | region bundle dir | cells | `cells_columns`, `h5_feature_types` | vendor or resegmented; only `cells.parquet` + `cell_feature_matrix.h5` required |
| `punch_coordinates` | `sc.punch_coordinates@1` | file or dir | punches | `punch_ids` | see coordinates-input.md |
| `tma_layout` | `sc.tma_layout@1` | CSV | rows | `columns` | the design's columns live here; `counts_per_group` per factor level |
| `punch_bundle_set` | `sc.punch_bundle_set@1` | dir of `punch_*/` bundles | cells | `punch_ids` | output of `split-punches` |
| `qc_object_set` | `sc.qc_object_set@1` | dir with `qc_summary.json` | cells after QC | `punch_ids` | output of `qc-cells` |
| `anndata` | `sc.anndata@1` | `.h5ad` | cells | obs columns | later modules |
| `analysis_summary` | `sc.analysis_summary@1` | JSON object of named facts | `n_cells` fact | the fact names | 0.8.0: what a module computed (a median UMI count, a PCA sentinel), read by the `sc.*` droplet predicates from `domain` |
| `seurat_object` | `sc.seurat_object@1` | `.rds` (Seurat v5) | cells | meta.data columns, reductions as `obsm` (`spatial` when any FOV has coordinates), layers, `uns_flags` from `obj@misc$stringency` | the R pipeline's objects (0.2.0, Lane F); extractor `tools/extract_seurat.R`, run as `Rscript` inside the module's image; same envelope keys as `anndata` so predicates stay object-agnostic |
| `cluster_evidence` | `sc.cluster_evidence@1` | dir with `manifest.json` | cells (manifest) | `summary_columns` of `cluster_summary.csv` (not `columns`, which would make `init.column_missing` check the design columns against it), `cluster_ids` | the tables the annotation judgment reads, written by `find-markers` (0.3.0, Lane F); contract below |
| `batch_evidence` | `sc.batch_evidence@1` | dir with `manifest.json` | cells (manifest) | `summary_columns` of `batch_overview.csv`; `uns_flags.batch_assessment` = the manifest's summary | the tables the batch-route judgment reads, written by `cluster-umap` (0.4.0); contract below |

`fields.columns` is set only on `tma_layout`, deliberately: `init.column_missing` checks every
design column against every object input that reports `columns`, and the design's columns
(`punch_id, animal, timepoint_h, condition, slide`) are layout columns, not raw-bundle columns.

## `xenium_bundle.domain`

`kind` (`vendor` when `experiment.xenium` exists, else `resegmented_or_split`), `slide`, `region`,
`cassette`, `run_name`, `analysis_sw_version`, `instrument_sw_version`, `preservation_method`,
`segmentation_stain`, `panel` (`name`, `design_id`, `predesigned_id`, `n_targets`,
`n_gene_targets`, `n_custom_gene_targets`, `species`), `n_cells`, `n_gene_features`,
`n_features`, vendor medians from `metrics_summary.csv`, medians recomputed from `cells.parquet`
(`median_transcript_counts`, `median_cell_area_um2`, `median_nucleus_area_um2`),
`region_area_um2`, `segmentation_methods` (counts), and the order checks
`h5_order_matches_cells`, `h5_set_matches_cells`, `n_cells_parquet`, `n_barcodes_h5`.

Measured on the real `0076570` Liver bundle (XOA 6.1, xenium-4.0.2.2): both files are sorted by
`cell_id` and `h5_order_matches_cells` is **true**. The order disagreement that hid ROSC defect A1
arose in the *split* punch bundles (the old splitter's set iteration), not in the vendor bundle.
The flag is recorded on every bundle regardless; `qc-cells` must not rely on it.

## `punch_bundle_set`

Immediate subdirectories that are bundles, sorted by name; `punch_id` is the directory name with a
`punch_` prefix removed. Per punch: `n_cells`, `h5_order_matches_cells`, `h5_set_matches_cells`,
`median_transcript_counts`, `median_cell_area_um2`. If the set holds `punch_metadata.csv`
(`punch_id` plus the design columns, written by `split-punches` from the layout),
`counts_per_group` counts cells, punches, and animals per factor level.

## `qc_object_set` and the `qc_summary.json` contract

`qc-cells` writes, beside its per-punch objects:

```json
{"qc_summary": 1,
 "punches": [{"punch_id": "24-2-Liver", "tissue": "liver", "included": true,
              "n_before": 9000, "n_after": 8500, "fail_fraction": 0.0556,
              "thresholds": {"min_nCount": 10, "min_nFeature": 20, "min_cellarea": 10, "max_cellarea": 1000},
              "object": "24-2-Liver.h5ad"}],
 "join_verification": {"method": "keyed_reindex_on_cell_id", "verified": true,
                       "n_cells": 9000, "n_cells_checked": 9000,
                       "columns_checked": ["cell_area", "nucleus_area", "transcript_counts"],
                       "detail": "obs.index == barcodes for every cell; every joined value equals the by-id lookup"}}
```

The extractor recomputes `verified_by_extractor`: true only if `verified`, an accepted `method`,
`n_cells_checked == n_cells`, and `n_cells == sum(n_before)`. `sc.area_join_unverified` blocks
on anything less. `included: false` marks punches the histology review excluded; the flag
predicates skip them.

## `cluster_evidence`

Written by the method's `find-markers` module after clustering, read by `annotate-clusters`
(the judgment's `pre.py` turns it into evidence tables) and by `upstream-report`. One directory:

| file | content |
|---|---|
| `manifest.json` | `{"cluster_evidence": 1, organ, species, panel: {n_genes}, clustering_column, resolution, n_clusters, n_cells, punches: [...], timepoint_levels: [...], batch_key, normalisation}` |
| `cluster_summary.csv` | one row per cluster: `cluster, n_cells, pct_cells, median_counts, median_genes, median_cell_area, n_punches, max_punch, max_punch_pct, dominant_timepoint, pct_tp_<level>` per time point level, `max_slide_pct, dominant_slide, top_markers, batch_flag` |
| `composition_by_punch.csv`, `composition_by_animal.csv`, `composition_by_timepoint.csv`, `composition_by_slide.csv` | wide counts, `cluster` first column |
| `markers.csv` | `cluster, gene, avg_log2FC, pct_in, pct_out, pct_diff, p_val, p_val_adj` (FindAllMarkers) |
| `markers_top.csv` | `cluster, rank, gene, avg_log2FC, pct_in, pct_out, pct_diff`, the top `top_n` per cluster |
| `cluster_avg_expression.csv`, `cluster_pct_expressing.csv` | `gene` first column, one column per cluster id |
| `batch_assessment.csv` | per cluster, what `misc$stringency$batch_assessment` summarises |

The extractor (stdlib) refuses a directory without `manifest.json` (contract version 1) or
`cluster_summary.csv`; `domain.files_missing` lists any other file absent so a predicate or the
report can say what the evidence lacked.

## `batch_evidence`

Written by the method's `cluster-umap` module beside the clustered object, read by `assess-batch`
(the batch-route judgment; its `pre.py` turns it into evidence tables) and by `upstream-report`.
One directory:

| file | content |
|---|---|
| `manifest.json` | `{"batch_evidence": 1, organ, batch_key, timepoint_column, clustering_column, resolution, n_clusters, n_cells, rule: {knn_threshold, excess_threshold, min_cluster_frac, frac_threshold, text}, summary: {the batch_summary dict}, files}` |
| `batch_overview.csv` | ONE row, the judgment's item: `dataset` (item key, the organ), `organ, n_cells, n_clusters, batch_key, batch_levels` (semicolon list), `timepoint_column, shared_timepoints` (semicolon list), `knn_same_batch_excess_overall, n_clusters_flagged, fraction_cells_in_flagged_clusters, min_animals_per_batch_in_shared_timepoints, rule_suspected` |
| `batch_assessment.csv` | per cluster: `cluster, n_cells, pct_cells, dominant_batch, dominant_batch_pct, expected_dominant_pct, batch_excess, n_cells_shared_timepoints, knn_same_batch_excess, flagged` |
| `cluster_summary.csv` | the clustering module's per-cluster summary |
| `slide_by_timepoint.csv` | `slide, timepoint_h, n_cells, n_animals, n_punches, punches`: the design's confounding, as a table the reviewer can cite |
| `composition_by_slide.csv`, `composition_by_timepoint.csv`, `composition_by_punch.csv`, `composition_by_animal.csv` | wide counts, `cluster` first column |

The extractor (stdlib) refuses a directory without `manifest.json` (contract version 1) or
`batch_overview.csv`; it reports the manifest's summary under `uns_flags.batch_assessment` so a
predicate written against the Seurat object's flag reads this object the same way.

## Plain types written by the open tools (0.6.0)

The Xenium method's open tools (engine open mode) exchange tables through types that are not
plugin object types: no extractor runs on them, `topo.input_type_mismatch` compares the strings,
and a tool's input of one of these types binds the latest artifact of that type without `--in`.
A method that writes them follows these columns; the first column is the row key an answer cites.

| type | format | first column | columns |
|---|---|---|---|
| `cell_table` | csv | `cell_id` (unique: `<punch_id>_<barcode>`) | `punch_id, animal, timepoint_h, condition, slide, cell_type, cell_type_fine, cluster, x, y, cell_area, nCount_Xenium` (the design columns as declared; the label column from `misc$stringency$labels$column`) |
| `punch_table` | csv | `punch_id` | the design columns, `n_cells, area_mm2, density_cells_per_mm2` (convex hull of the punch's cells) |
| `pseudobulk_set` | dir | `counts.csv`: `gene`; `samples.csv`: `sample` | `counts.csv` one column per `<punch_id>|<cell_type>` sample; `samples.csv`: `punch_id, cell_type, animal, timepoint_h, condition, slide, n_cells` |
| `proportion_table` | csv | `cell_type` | one column per punch (the fraction of the punch's cells), `total` |

Negative controls on these tables use the plugin tool `shuffle_column` (params `column`, `by`,
`seed`, and `file` for a directory), which permutes one design column across units.
