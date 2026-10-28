# stringency-singlecell

**At 0.10.3 (2026-10-28).** The operation `measure_intensity`, for the Xenium method's `cell-intensity` 0.1.0 (its `docs/open-tools-v2-plan.md` 11.3 item 3, after Emons24): per punch (and stratum) and label of a layer, a grid of square quadrats over the punch's cells, the quadrats holding a cell taken as the tissue; per label the intensity per mm², the quadrat counts' coefficient of variation and dispersion index, and the chi-square quadrat test of uniform intensity (Baddeley15 section 6.4); per level the mean and sd over the replicates, descriptive; one map per punch. Its parameters: the layer parameters `group_by`, `subset` and `stratify_by` as the 0.9.0 tools, `quadrat_um` (the side in microns), `min_cells`, the design's `factor`, `reference` and `replicate_unit`, `plot_labels`, `cmap` and `seed` (logged only). No predicate judges it yet; the homogeneity gate `spatial.homogeneity_unstated` (a homogeneous null run on a label whose index is above a band, the assumption unstated) waits for the owner's reading of the index on the gut.

**At 0.10.2 (2026-10-27, later).** The operation `test_pair_correlation`, for the Xenium method's `pair-correlation` 0.1.0 (its `docs/open-tools-v2-plan.md` 4.11): per punch and pair of labels the cross pair-correlation function g(r) with a global envelope from random relabellings of the punch's cells, the mean g over a summary window as each replicate's statistic, tested between the factor's levels. Its parameters: `pairs` (`a:b;c:d`), the layer parameters `group_by`, `subset` and `stratify_by` as the 0.9.0 tools, the scale in microns (`r_max_um`, `r_step_um`, `r_summary_um` as `lo,hi`, `r_envelope_min_um`), `n_sim` (at least 19), `min_cells`, the design's `factor`, `reference` and `replicate_unit`, `level_colors` and `seed`. No predicate judges it yet: `spatial.neighborhood_undeclared` and `spatial.no_permutation_null` keep their scopes (their keys are a radius or k and `n_perms`, not a distance window and `n_sim`), so no earlier verdict changes. 0.10.1 made `shuffle_coordinates` permute an h5ad in place.

**At 0.10.0 (2026-10-27, later).** The operations of the Xenium method's milestones B to D (its `docs/open-tools-v2-plan.md` section 10.5): `measure_distance` (distance to a structure, binned curves and a trend test per replicate), `test_proximity_effect` (Sun24's near/far contrast with per-replicate effect sizes and a coordinate-permutation null), `test_spatial_autocorrelation` (Moran's I per punch with a permutation null), `summarise_sample_features` (one feature table per replicate); `neighborhood_enrichment` gains the layer parameters; the plain types `distance_table` and `sample_features`. The fine-label steps (the method's PLAN 3.17 and 3.21): `reconcile_fine_labels` (`min_reviewers`, `pct_diff_floor`, `logfc_min`), `choose_fine_label` (a judgment over the contested clusters) and its vocabulary `fine_label_choice@1` (`candidate_a`, `candidate_b`, `candidate_c`, `none`). Vocabularies scoped by organ (the owner, 2026-10-27, "only a kidney has nephrons"): a vocabulary YAML may carry `organs:` (label to organs, or `[any]`), loaded as `VOCABULARY_ORGANS` beside the engine's flat label tuples and filled for `tissue_structures_mouse@1` and `cell_types_mouse@2`; the predicate `sc.label_outside_organ@1` (post, flag, `annotate_clusters` and `label_domains`) flags a replicate's label whose organs exclude the project's organ (the objective's `01_merge.organ`, else the history's admitted `organ`, else the design's), not judged when the organ is unknown or the vocabulary has no map. The proximity tool's gates: `spatial.neighborhood_undeclared` reads `cutoff_um` (a positive number or `delaunay`) and, for `measure_distance`, `bins_um` and `max_distance_um`, and judges `test_proximity_effect`, `measure_distance` and `test_spatial_autocorrelation`; `spatial.no_permutation_null` judges `test_proximity_effect` (floor `ranges.spatial.n_perms_coordinate`, else 20, Sun24's coordinate-permutation design) and `test_spatial_autocorrelation` (`ranges.spatial.n_perms`, else 100). The keys and scopes are new, so no earlier verdict changes and both keep `@1`.

**At 0.9.0 (2026-10-27).** The open tools' second round, built to the contract of the Xenium method's `docs/open-tools-v2-plan.md` section 10. The layer parameters `group_by` (the cell-table column whose levels are the rows), `subset` (one clause, `<column> in <v1>,<v2>` or `<column> = <v>`), `stratify_by` (a second label column the analysis runs within), `denominator` (`all` or `subset`, on `compose_cells` and `plot_composition` only) and `block` (a model term, on `compose_cells` and `test_differential_expression` only) join the five open tools' operations. `test_differential_expression` gains `contrast_layer`, `within`, `method` (`limma_voom`, `edger_ql`) and the contamination filter (`contamination_filter`, `min_count`, `min_fraction`); `plot_composition` the design's `factor`, `reference` and `replicate_unit`; `neighborhood_enrichment` a radius sweep `radii_um` with `min_cells` and `n_jobs`. Two new operations: `sweep_domains` (`group_by`, `k_neighbors`, `exclude`, `n_domains_min`, `n_domains_max`, `seed`) and `call_domains` (`n_domains`, an integer of at least 2 or `unset`, which stops the step for a proposal; `domain_names`; `min_cells`). The plain types `cell_expression`, `domain_grid`, `domain_labels` and `cell_scores` are documented in `spec/object-types.md`, with the punch x cluster (x domain) `pseudobulk_set` and its `detected.csv`; plain types need no extractor. The generator `shuffle_coordinates` permutes the `(x, y)` pairs among the cells of each punch, the spatial tools' negative control. The predicate `spatial.domain_is_replicate@1` (post, flag, `call_domains`) reads `max_single_replicate_share` from the `domain_facts` summary and fires above `ranges.spatial.domain_replicate_share[<band>][1]`, else 0.9: a domain that is one replicate is a punch label, not anatomy. `spatial.neighborhood_undeclared` reads `k_neighbors` and `radii_um` and judges `sweep_domains`, and `sc.decision_unreviewed` adds `call_domains` to its scope, so a domain count taken at a default without a proposal is held as a clustering resolution is; neither changes an earlier verdict (the keys and the operations are new), so both keep their versions (`@1`, `@2`), which the methods' modules gate on.

**At 0.8.7 (2026-10-26).** `sc.louvain_too_large@2` judges only a module whose parameters declare `cluster_method`; a module without it is not judged and the evidence names the module. The Xenium method's `select-resolution` shares the `cluster_umap` operation, reads the clustered object and only sets the identity from a stored column, and version 1 flagged its proposal as Louvain on any organ above the threshold, even after a Leiden run. An absent value on a module that declares the parameter is still `seurat_louvain`. The Xenium method names `@2` in `cluster-umap/module.yml` and requires singlecell `>=0.8.7`. **At 0.8.6 (2026-10-26).** `sc.louvain_too_large@1` (pre, flag, scope `cluster_umap`): the step would run Seurat's Louvain (`cluster_method` `seurat_louvain`, or absent, the module's default) on an input `seurat_object` whose `n_obs` is above `ranges.sc.louvain_max_cells[<band>][1]`, else 600,000. Louvain on the Lyons v2 spleen (1.57 million cells) ran more than six hours without finishing a resolution; the Xenium method's `docs/tissue-defaults.md` recommends `igraph_leiden` above about 600,000 cells, and until now only a warning line in `cluster_umap.R` said so, after the step had started. The input is the state object whose digest the action binds; a count that cannot be read is not judged, and the evidence says so. The Xenium method lists the gate in `cluster-umap/module.yml` at a later tag. **At 0.8.5 (2026-10-23).** `sc.fine_label_uncited@1` (post, flag, scope `annotate_clusters`): a valid replicate's `fine_label` names a gene its record does not cite for its own cluster (the owner, 2026-10-23, after Lyons CLP gut cluster 9). Genes are what the step's evidence tables call a gene, so the plugin keeps no gene list; words that are not symbols ("IFN", "stress") are left to the state evidence the engine's `annotation-controls.md` plans. **At 0.8.4 (2026-10-22).** `sc.marker_panels@1` reports its columns as `fields.header`, not `fields.columns`, which `init.column_missing` reads as the design's own table (0.8.3 blocked `init` on a droplet project for that). **At 0.8.3 (2026-10-22).** Object type `marker_panels` (`sc.marker_panels@1`): a person's declared lineage panels as a CSV with columns `lineage` and `gene`, so a method takes the declaration as a hashed input under the confirm hold rather than as a parameter the engine ranges (the scrnaseq method at v0.1.4). **At 0.8.2 (2026-10-22).** `sc.normalization_depth@2` is silent on a targeted panel (`is_targeted_panel` true in the QC facts): a few hundred genes cannot reach the whole-transcriptome floor however deep the cells are; the evidence records the flag. Found on the scrnaseq method's first engine run (a 320-gene fixture at a median of 1371 UMIs). **At 0.8.1 (2026-10-22).** Three Xenium-era predicates narrowed so the droplet method is not judged by Xenium's claims: `sc.area_join_unverified@2` is silent for a module that declares no `qc_object_set`; `sc.low_cell_count@2` also reads a droplet QC step's `n_cells_retained`; `sc.decision_unreviewed@2` skips a decision point the pipeline gates with a `decision:` block. The Xenium method names `@2` at its next tag. **At 0.8.0 (2026-10-22).** Widened beyond Xenium for the benchmark's scRNA-seq method (engine `benchmark-plan.md`, Phase 1): the design's observation unit may be any name (cell, nucleus, spot, bead); the `qc_cells`, `normalize`, `select_hvg`, `cluster` and `reduce_pca` operation schemas take droplet-kit parameters; two operations, `qc_metrics` and `score_panels`; an `analysis_summary` object type (a JSON object of named facts, `sc.analysis_summary@1`); four predicates over those facts, `sc.qc_floor_above_data`, `sc.normalization_depth`, `sc.pc1_single_gene`, `sc.pca_depth_confounded`. **At 0.7.0 (2026-10-22).** The seven downstream predicates the design names (engine backlog L54): `de.replication_unit`, `de.covariate_omission`, `de.selection_bias`, `test.multiple_comparison`, `test.assumptions_unchecked`, `spatial.neighborhood_undeclared`, `spatial.no_permutation_null`, all pre-phase over the action's parameters, the design and the run's history (`spec/predicates.md`); a method lists them in its policy and the tools' gates. **At 0.6.2 (2026-10-20).** `test_differential_expression` takes `min_logfc` (limma's treat: the fold change a gene must reliably exceed; the shuffled negative control at two replicates a side called fold changes of 0.2 log2 without it). **At 0.6.1 (2026-10-20).** The open tools' list parameters (`tests`, `cell_types`, `genesets`, `genes`) are comma-separated strings, since `--set k=v` values arrive as text. **At 0.6.0 (2026-10-20; open tools need engine 0.2.23).** Open mode: `modes` gains `open`, so the Xenium method's tools can answer questions on a delivered object and a project can be initialised from a delivery; the open tools' operations are typed (`extract_cells`, `compose_cells`, `plot_composition`, `test_differential_expression`, `score_pathways`, `neighborhood_enrichment`, `infer_cell_communication`); the plain types they exchange are in `spec/object-types.md`; `shuffle_column` is their negative-control generator. Before that, **at 0.5.1 (2026-10-14; needs engine 0.2.19).** `spatial.coords_missing@2` checks every bound region; `sc.decision_unreviewed` treats a declared or inherited decision point as a person's; `VERSION` is tested against `pyproject.toml`; CI runs the tests, ruff and mypy (the `tools/` scripts excluded from typing). Before that, **at 0.5.0 (2026-10-08).** The plugin behind `stringency-xenium-method`'s `xenium-qc-tma` (split, QC,
summary, the outlier judgment) and `xenium-upstream` (merge to annotation) pipelines: object types
for Xenium bundles, punch coordinates, layouts, punch and QC object sets, Seurat objects, batch and
cluster evidence and QC metric tables, each with an extractor under `tools/`; predicates for
coordinates, cell counts, QC failure fractions, the cell-area join, exclusion proposals, unreviewed
decision points, batch effects and unknown fractions; vocabularies `punch_qc_verdict@2`,
`batch_route@1` and `cell_types_mouse@2` (Cell Ontology ids checked against OLS); the generator
tools `shuffle_markers` and `mix_batches` for the judgments' negative controls. The version history
below is in reverse order of writing, not of version; `git log` is the record. The `xenium-qc`
pipeline named below was removed from the method in rc11 (a single bundle binds `xenium-qc-tma`).

The `stringency` domain plugin for single-cell and spatial (Xenium) analysis; application 1 is the
Lyons CLP Xenium TMA, QC first (`stringency-xenium-method`). Version 0.1.0 (2026-09-17, Lane C
session C2) delivers the pieces the `xenium-qc` pipeline needs:

- object types `xenium_bundle`, `punch_coordinates`, `tma_layout`, `punch_bundle_set`,
  `qc_object_set` (plus the `anndata` stub), each with a standalone extractor under `tools/`
  (`spec/object-types.md`, `spec/coordinates-input.md`);
- typed operations `split_punches` and `qc_cells`; question `processed_object`;
- the design schema and the Lyons CLP design as its first instance (`spec/design-schema.md`);
- predicates `spatial.coords_missing`, `sc.low_cell_count`, `sc.qc_fail_fraction`, and the
  cell-area join guard `sc.area_join_unverified` (`spec/predicates.md`), each with must-fire and
  must-pass fixtures.

The predicate half (this package) is pure Python in the engine environment. The tool half
(`tools/`) runs inside module environments through the executor; pyarrow and h5py are needed there
for the bundle extractors (`pip install 'stringency-singlecell[extractors]'`), the rest are stdlib.
`tests/synthetic.py` writes a small vendor-layout bundle whose h5 barcodes are shuffled relative to
`cells.parquet`, so positional joins fail loudly; the method repo copies it for its fixtures.

From the workspace root: `uv sync && uv run pytest && uv run ruff check .`

Installing into an engine from a checkout of this workspace: the workspace root pins `stringency`
to its git URL for `uv sync`, which conflicts with the engine path `scripts/install.sh` passes, so
run the installer with `UV_NO_SOURCES=1` (and a fresh `--label`, since `uv venv` refuses to reuse
an existing venv without `UV_VENV_CLEAR=1`):

```bash
UV_NO_SOURCES=1 scripts/install.sh --prefix <prefix> --label 0.1.0+singlecell \
  --plugin <path or url>@v0.1.0#subdirectory=plugins/stringency-singlecell
```

Version 0.2.0 (2026-10-06, Lane F): object type `seurat_object` with the R extractor
`tools/extract_seurat.R` (the engine runs it as `Rscript` inside the module's image and it prints
the same envelope keys as the `anndata` extractor, with `uns_flags` read from `obj@misc$stringency`);
predicate `sc.export_mismatch` (block) on `export_h5ad`; typed operations `merge_objects`,
`normalize`, `find_markers`, `export_h5ad` (`reduce_cluster` was replaced in 0.3.0). The downstream pilot is in R
(owner decision 1, 2026-10-06; engine repo `spec/plans/spatial-method-plan.md` section 5).

Version 0.1.8 (2026-09-21): vocabulary `punch_qc_verdict@2` (`keep`, `review`, `already_excluded`)
for the redesigned outlier judgment, in which reviewer agents reason from direction-aware band
departures and a guide instead of applying a lookup rule, and never exclude; v1 stays loaded for
the record of the rejected Lyons CLP run. `sc.exclusion_proposed` fires on `review` as before.

Version 0.4.2 (2026-10-07, late afternoon): `sc.batch_route_review` v2, the owner's reading of the hold:
it opens only when the reviewers agreed (a disagreement is settled at the engine's item hold, whose label is
the route), `accept` means agreement with the reviewers and the operator acts on the label (`correct_batch`
forks at `03_reduce` with the recommended correction, `proceed_uncorrected` continues, `cannot_tell` needs the
route in the reason), `reject` means disagreement with the route in the reason; the evidence carries the
replicates' `recommended_correction`.

Version 0.4.1 (2026-10-07): generator tool `mix_batches`, the negative control of `assess-batch` (removes the
slide structure of a `batch_evidence` directory; source documented in the method's `modules/assess-batch/controls/`).

Version 0.4.0 (2026-10-07, afternoon): batch effect assessment is a judgment step of `xenium-upstream`
(owner decision): operation `assess_batch`; object type `batch_evidence` with
`tools/extract_batch_evidence.py`; vocabulary `batch_route@1` (`proceed_uncorrected`, `correct_batch`,
`cannot_tell`); predicate `sc.batch_route_review` (flag; always opens once the judgment has a consensus:
accept continues uncorrected, reject sends the operator to a fork at `03_reduce`); `sc.batch_effect_suspected`
is version 2 and logged, not held.

Version 0.3.1 (2026-10-07): tool `shuffle_markers` (the negative-control generator of `annotate-clusters`); the `cluster_evidence` extractor reports `summary_columns`, not `columns`.

Version 0.3.0 (2026-10-07, Lane F, the `xenium-upstream` pipeline): typed operations `reduce_pca`
(with `integration` none | harmony | rpca | cca), `cluster_umap`, `find_markers` extended,
`annotate_clusters`, `apply_labels`, `report_upstream`; object type `cluster_evidence` with
`tools/extract_cluster_evidence.py`; predicates `sc.decision_unreviewed` (a person signs off on
every decision point, even at the pipeline default; owner decision 2026-10-07),
`sc.batch_effect_suspected` (names the fork route with Harmony), `sc.unknown_fraction` and
`qc.filter_ordering`; vocabulary `cell_types_mouse@1` (43 labels for the four Lyons organs, a
draft for the owner's approval, with Cell Ontology ids in `terms`).

Version 0.5.0 (2026-10-08): vocabulary `cell_types_mouse@2`, @1 plus nine cell types the Lyons CLP lung and
gut runs showed missing (`cardiomyocyte`, `adipocyte`, `transit_amplifying_cell`, `eosinophil`, `basophil`,
`hematopoietic_progenitor`, `pulmonary_neuroendocrine_cell`, `interstitial_cell_of_cajal`, `schwann_cell`;
the file names the clusters that asked for each); @1 stays loaded for the projects that pinned it.
Every Cell Ontology id in both files was checked against OLS: three were wrong in @1 and are corrected
in both (`enteric_glia`, `red_pulp_macrophage`, `intestinal_stem_cell`); labels are unchanged.
`sc.decision_unreviewed` says when the agent proposed the default ("the agent proposed ndim 35, resolution
0.4, the defaults") instead of "taken at their defaults"; what fires is unchanged.
