# stringency-plugins

Domain plugins for the [stringency](https://github.com/santangelo-lab/stringency) engine. One
package per subdirectory under `plugins/`, one uv workspace, one tag for all plugins. A plugin
teaches the engine a domain's vocabulary (object types and extractors, the design schema,
predicates, controlled vocabularies, phrasing); it runs no analysis. Analyses live in method
repositories (`stringency-xenium-method`, `stringency-plasmidsaurusRNAseq-method`), which depend
on these plugins.

| plugin | domain | status |
|---|---|---|
| `plugins/stringency-singlecell` | single-cell and spatial (Xenium) | skeleton; filled by the app-1 sessions |
| `plugins/stringency-bulkrna` | bulk RNA-seq | planned (Lane B session 1) |

## Develop

```bash
uv sync
uv run pytest
uv run ruff check .
```

## Install a plugin into a stringency engine

```bash
scripts/install.sh --prefix <prefix> \
  --plugin git+https://github.com/santangelo-lab/stringency-plugins@<tag>#subdirectory=plugins/stringency-singlecell
```

Repository layout decided 2026-09-17 (engine `spec/plans/roadmap-2026-09.md`, Lane D item 2).
