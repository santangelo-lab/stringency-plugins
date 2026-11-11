# Design schema (session 1 question, settled 2026-09-17 for Lyons CLP)

```yaml
design: 1
units: {observation: cell, sample: punch_id, animal: animal}   # values are layout / obs columns
factors:
  timepoint_h: {column: timepoint_h, levels: ["6", "24", "48"]}
  condition:   {column: condition,   levels: ["CLP"]}          # one level: no sham arm, on record
batch: [slide]
replication_unit: animal
primary_factor: timepoint_h      # optional (0.10.5): the factor the study is laid out by
holdout: []
source: "..."   # optional; a manual declaration says where it came from
notes: "..."
```

Rules the schema enforces: `observation` is any unit name (`cell`, `nucleus`, `spot`, `bead`; `punch` for punch-level tables; 0.8.0, before it `cell` or `punch`); `sample` required; any further unit is a
column name; every factor has a column and at least one level (a contrast-bearing factor needs
two, which `init.contrast_undeclared` / `init.level_undeclared` catch at init); `batch` unique;
`replication_unit` required; `primary_factor` optional, a non-empty name (0.10.5: the factor a study is laid out by, a time course's time point; a method's modules read it from the job's design and stop when it is not a key of `factors`, which JSON schema cannot say); no unknown top-level keys. Rules the tests enforce beyond JSON
schema: `replication_unit` is one of the unit columns; the Lyons CLP file at
`/lab/projects/Lyons_CLP/design.yml` equals the reference design in `tests/helpers.py`.

Engine semantics that follow: `Design.columns()` is `[punch_id, animal, timepoint_h, condition,
slide]`, all present in `tma_layout.csv`, so `init.column_missing` passes on the layout input and
skips the bundle (which reports `cells_columns`, not `columns`). `has_biological_replicates` is
true (`animal` differs from the observation). `counts_per_group` from the layout: per time
point 2 animals and 14 punches; `obj.feasibility` has nothing to check while the QC project
declares no contrasts.
