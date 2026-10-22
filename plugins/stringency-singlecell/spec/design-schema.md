# Design schema (session 1 question, settled 2026-09-17 for Lyons CLP)

```yaml
design: 1
units: {observation: cell, sample: punch_id, animal: animal}   # values are layout / obs columns
factors:
  timepoint_h: {column: timepoint_h, levels: ["6", "24", "48"]}
  condition:   {column: condition,   levels: ["CLP"]}          # one level: no sham arm, on record
batch: [slide]
replication_unit: animal
holdout: []
source: "..."   # optional; a manual declaration says where it came from
notes: "..."
```

Rules the schema enforces: `observation` is any unit name (`cell`, `nucleus`, `spot`, `bead`; `punch` for punch-level tables; 0.8.0, before it `cell` or `punch`); `sample` required; any further unit is a
column name; every factor has a column and at least one level (a contrast-bearing factor needs
two, which `init.contrast_undeclared` / `init.level_undeclared` catch at init); `batch` unique;
`replication_unit` required; no unknown top-level keys. Rules the tests enforce beyond JSON
schema: `replication_unit` is one of the unit columns; the Lyons CLP file at
`/lab/projects/Lyons_CLP/design.yml` equals the reference design in `tests/helpers.py`.

Engine semantics that follow: `Design.columns()` is `[punch_id, animal, timepoint_h, condition,
slide]`, all present in `tma_layout.csv`, so `init.column_missing` passes on the layout input and
skips the bundle (which reports `cells_columns`, not `columns`). `has_biological_replicates` is
true (`animal` differs from the observation). `counts_per_group` from the layout: per time
point 2 animals and 14 punches; `obj.feasibility` has nothing to check while the QC project
declares no contrasts.
