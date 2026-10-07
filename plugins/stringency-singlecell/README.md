# stringency-singlecell

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

Version 0.3.0 (2026-10-07, Lane F, the `xenium-upstream` pipeline): typed operations `reduce_pca`
(with `integration` none | harmony | rpca | cca), `cluster_umap`, `find_markers` extended,
`annotate_clusters`, `apply_labels`, `report_upstream`; object type `cluster_evidence` with
`tools/extract_cluster_evidence.py`; predicates `sc.decision_unreviewed` (a person signs off on
every decision point, even at the pipeline default; owner decision 2026-10-07),
`sc.batch_effect_suspected` (names the fork route with Harmony), `sc.unknown_fraction` and
`qc.filter_ordering`; vocabulary `cell_types_mouse@1` (43 labels for the four Lyons organs, a
draft for the owner's approval, with Cell Ontology ids in `terms`).
