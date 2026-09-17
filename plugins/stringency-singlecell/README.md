# stringency-singlecell

The `stringency` domain plugin for single-cell and spatial analysis (application 1, the spatial TMA
pipeline). This is the Phase A skeleton: an entry point, an `sc.anndata` extractor stub that emits
the state envelope with `counts_per_group` computed from a design file, an empty predicate
registry, a `vocabularies/` directory, and `spec/` for the specs the app-1 design sessions produce.

The predicate half (this package) is pure Python and lives in the engine environment. The tool
half (`tools/`) runs inside module environments through the executor; scanpy and anndata are
imported only there, never by the engine.

```
uv sync --all-groups
uv run pytest
stringency plugins list     # shows stringency-singlecell alongside stringency-toy
```
