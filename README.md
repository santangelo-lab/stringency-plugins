# stringency-plugins

Domain plugins for the [stringency](https://github.com/santangelo-lab/stringency) engine. One
package per subdirectory under `plugins/`, one uv workspace, one tag for all plugins. A plugin
teaches the engine a domain's vocabulary (object types and extractors, the design schema,
predicates, controlled vocabularies, phrasing); it runs no analysis. Analyses live in method
repositories, which depend on these plugins: `stringency-xenium-method` and
`stringency-scrnaseq-scanpy-method` need `stringency-singlecell`;
`stringency-plasmidsaurusRNAseq-method` (bulk RNA-seq) names no plugin yet.

| plugin | domain | status |
|---|---|---|
| `plugins/stringency-singlecell` | single-cell and spatial (Xenium), droplet scRNA-seq | 0.10.3 (2026-10-28; its package floor is engine 0.2.19, its tests run against the engine tag pinned under `tool.uv.sources`): the object types, extractors, design schema, predicates, vocabularies and typed operations used by `stringency-xenium-method` (QC, upstream, the spatial layers and the open-mode tools) and by `stringency-scrnaseq-scanpy-method` (the scRNA-seq QC, PCA, normalisation and pseudobulk predicates). The version history is in its README; this row is updated at each tag |
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

Repository layout decided 2026-09-17 (engine `spec/archive/roadmap-2026-09.md`, Lane D item 2). The CI workflow above and the version test (`tests/test_plugin.py`) have been in place since October 2026 (the engine's `spec/plans/roadmap-2026-10.md`, W3); a method states the plugin version it needs under `requires.plugins` in its `policy.yml`, which the engine checks at `lint`, `declare --check` and `init`.
