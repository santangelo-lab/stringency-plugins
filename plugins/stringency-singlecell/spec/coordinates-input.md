# Coordinates input: unit and format (decision 5 of the Lane C day-1 plan, settled 2026-09-17)

**Decision (session C1, from the splitter): the manual coordinates input is a directory of
per-punch Xenium Explorer exports named `<punch_id>_coordinates.csv`.** That is the splitter's
`--cell_stats_dir` mode; the consolidated `all_punch_coordinates.csv` (`punch_id, x_min, x_max,
y_min, y_max, ...`) is a *derived output* of `run_metrics.py`, never an input. The splitter reduces
each polygon to its bounding box. The `punch_coordinates` object type therefore treats the
directory as its primary shape, and `split-punches` passes it to the splitter unchanged.

## Engine limitation, to be fixed before `init` can bind a directory

`stringency init` hashes every input with `hashing.hash_file`, which opens the path as a file, so
a directory input raises `IsADirectoryError` today. `hashing.hash_dir` (sorted relative paths and
content hashes) exists and is unused. Until the engine dispatches on `is_dir()` (a Lane A fix,
reported from session C2), the hashable fallback is one file per region built by
`tools/combine_coordinates.py`: the exports for the layout's punches of (slide, region)
concatenated verbatim in layout order, one CRLF between them. The extractor parses that file
identically; the `split-punches` module would have to write it back out as a directory for the
splitter, so the fallback is for `init` only, not the preferred declared input. The eight fallback
files for Lyons CLP are at `/lab/projects/Lyons_CLP/punch_coordinates/by_region/`.

The same limitation applies to the region bundle itself (`xenium_bundle` is a directory), so the
fix is needed for the first real run regardless of this decision.

## Accepted shapes (`sc.punch_coordinates@1`)

| shape | detection | `domain.input_unit` / `format` | status |
|---|---|---|---|
| directory of `*_coordinates.csv` exports | `is_dir()` | `directory` / formats seen | **primary** |
| one export | first line | `file` / `xenium_explorer_export` | parsed; a single-punch region only |
| several exports concatenated | same | `file` / `xenium_explorer_export` | fallback for `init` (above) |
| consolidated bbox CSV | header columns | `file` / `bbox_csv` (`polygon: false`) | parsed for provenance of old splits; not an input |

Both `#Selection names:` (XOA 6.1 exports) and the older `#Selection name:` / `#Area` headers
parse; CRLF, a UTF-8 BOM, and a missing trailing newline are tolerated. Per punch the extractor
emits `n_vertices` (distinct), `closed`, `area_um2` (from the header), `bbox`, `bbox_area_um2`,
`is_rectangle`. In a directory, `punch_id` comes from the selection name inside the file, and the
`spatial.coords_missing` predicate catches a name that is not in the layout.

## Lyons CLP

42 exports under `/lab/projects/Lyons_CLP/punch_coordinates/`, ids reconciled to `tma_layout.csv`
on 2026-09-17. Two selections are not axis-aligned rectangles (`24-1-Spleen-A`, `6-2-Spleen-B`;
bounding box 1.0 and 0.7 percent larger than the drawn area); the splitter's bbox filter includes
that margin, and `is_rectangle` is recorded so the QC report can say so.
