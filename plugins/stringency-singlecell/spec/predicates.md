# Predicates (session 5 table, first four delivered 2026-09-17)

| id | phase | scope | default | fires when | covers |
|---|---|---|---|---|---|
| `spatial.coords_missing` | pre | `split_punches` | block | no `punch_coordinates` object; zero punches; a polygon has < 3 vertices or is unclosed; duplicate ids; a layout punch for the bundle's (slide, region) has no polygon; a polygon id is not in the layout | `split_punches.*` |
| `sc.low_cell_count` | post | `split_punches`, `qc_cells` | flag | an included punch in a `punch_bundle_set` or `qc_object_set` has fewer cells than the floor: policy `ranges.sc.cells_per_punch[<band>][0]`, else 500 | `split_punches.min_transcripts`, `.min_area` |
| `sc.qc_fail_fraction` | post | `qc_cells` | flag | an included punch's `fail_fraction` exceeds `ranges.sc.qc_fail_fraction[<band>][1]`, else 0.5 | the four `qc_cells` thresholds |
| `sc.area_join_unverified` | post | `qc_cells` | block, invariant | no `qc_object_set`, or its `join_verification` is not `verified`, not a keyed method, not every cell checked, no columns listed, or refused by the extractor | `qc_cells.min_cellarea`, `.max_cellarea` |
| `sc.exclusion_proposed` | post | `flag_outlier_punches` | flag | the judgment's consensus labels at least one punch `review` (vocabulary `punch_qc_verdict@2`, 2026-09-21: reviewers never exclude; the owner decides at this hold) or `exclude` (v1) | `flag_outlier_punches.*` |

The first four read `ctx.state.objects[*].summary.domain` only; `sc.exclusion_proposed` reads
`ctx.output.consensus`. Fixtures: `tests/test_predicates.py`
`CASES` (must-fire and must-pass per id) plus the variant tests. Policy example for the method
repo:

```yaml
ranges:
  sc.cells_per_punch:   {strict: [2000, 1e9], standard: [500, 1e9], wide: [100, 1e9]}
  sc.qc_fail_fraction:  {strict: [0, 0.2],    standard: [0, 0.5],   wide: [0, 0.8]}
```
