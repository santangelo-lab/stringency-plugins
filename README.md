# stringency-plugins

Domain plugins for the [stringency](https://github.com/santangelo-lab/stringency) engine. One
package per subdirectory under `plugins/`, one uv workspace, one tag for all plugins. A plugin
teaches the engine a domain's vocabulary (object types and extractors, the design schema,
predicates, controlled vocabularies, phrasing); it runs no analysis. Analyses live in method
repositories (`stringency-xenium-method`, `stringency-plasmidsaurusRNAseq-method`), which depend
on these plugins.

| plugin | domain | status |
|---|---|---|
| `plugins/stringency-singlecell` | single-cell and spatial (Xenium) | 0.5.1 (2026-10-14, needs engine 0.2.19; 0.5.0 of 2026-10-08 ran Lyons v2): the object types, extractors, design schema, predicates, vocabularies (`punch_qc_verdict@2`, `batch_route@1`, `cell_types_mouse@2`) and typed operations that `stringency-xenium-method`'s `xenium-qc-tma` and `xenium-upstream` pipelines use; see its README |
| `plugins/stringency-bulkrna` | bulk RNA-seq | not started (engine roadmap Lane B, dormant) |

## Develop

```bash
uv sync
uv run pytest          # tests marked institutional skip off the lab workstation, naming the path
uv run ruff check .
uv run mypy plugins/stringency-singlecell/src
```

`.github/workflows/ci.yml` runs the same on every push and pull request. The engine the tests
run against is the tag `tool.uv.sources` pins; bump it with the `stringency>=` floor in the
plugin's `pyproject.toml` and `uv lock` when a plugin needs a newer engine.

## Tags

Every tag from `v0.2.0` on was pushed after `ruff` and the tests passed. The tags `v0.1.2`,
`v0.1.3`, `v0.1.5` and `v0.1.6` (2026-09-18) were pushed before the checks ran and are not
usable; they stay because session notes and project traces cite them.

## Install a plugin into a stringency engine

```bash
scripts/install.sh --prefix <prefix> \
  --plugin git+https://github.com/santangelo-lab/stringency-plugins@<tag>#subdirectory=plugins/stringency-singlecell
```

Repository layout decided 2026-09-17 (engine `spec/archive/roadmap-2026-09.md`, Lane D item 2). A CI workflow, a `requires` check against the engine and a version test are scheduled in the engine's `spec/plans/roadmap-2026-10.md` (W3).
