#!/usr/bin/env Rscript
# State extractor for object type `seurat_object` (design 4.2; Lane F plan section 5.0, 2026-10-06).
# Runs inside the xenium-r module environment as `Rscript extract_seurat.R <object.rds>
# <design.json>`; the engine never imports R. Prints the design 4.2 envelope with the same keys
# the `anndata` extractor prints, so every predicate stays object-agnostic:
#   extractor, type, n_obs, n_var,
#   fields: obs (meta.data columns: dtype, n_unique, levels for factors with <= 50 levels),
#           columns (the same entries: the key the engine reads for an object's columns, for
#           `init.column_missing` and a pipeline's names; version 2, plugin 0.10.5, as the
#           anndata extractor writes it from 0.10.4; `obs` stays for this plugin's predicates),
#           feature_columns (the default assay's feature metadata columns: dtype, n_unique),
#           obsm (reductions, plus "spatial" when any FOV carries coordinates),
#           layers (the default assay's layer names), uns_flags (from obj@misc$stringency,
#           the R twin of the anndata `uns` flags: normalisation, hvg, pca, neighbors, clustering,
#           spatial_graph, labels, exclusions),
#   counts_per_group (units remaining per factor level, from design.json),
#   domain: assay, cells per cluster per punch and per animal when a clustering column is declared,
#           labels present and their vocabulary, the spatial graph's definition, fov names.
suppressPackageStartupMessages({
  library(jsonlite)
  library(SeuratObject)
})
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) stop("usage: extract_seurat.R <object.rds> <design.json>")
obj <- readRDS(args[1])
design <- fromJSON(args[2], simplifyVector = FALSE)
if (!inherits(obj, "Seurat")) stop("not a Seurat object: ", class(obj)[1])
md <- obj@meta.data
assay <- DefaultAssay(obj)
fields_obs <- list()
for (col in colnames(md)) {
  s <- md[[col]]
  entry <- list(dtype = class(s)[1], n_unique = length(unique(s)))
  if (is.factor(s) && nlevels(s) <= 50) entry$levels <- as.list(levels(s))
  if (is.character(s) && entry$n_unique <= 50) entry$levels <- as.list(sort(unique(s)))
  fields_obs[[col]] <- entry
}
# the default assay's feature table (Assay5 keeps it in @meta.data, Assay in @meta.features);
# an assay with none gives an empty object, not an empty array
empty_object <- setNames(list(), character())
if (length(fields_obs) == 0) fields_obs <- empty_object
fmeta <- tryCatch(obj[[assay]][[]], error = function(e) data.frame())
feature_columns <- empty_object
for (col in colnames(fmeta)) {
  feature_columns[[col]] <- list(dtype = class(fmeta[[col]])[1], n_unique = length(unique(fmeta[[col]])))
}
obsm <- names(obj@reductions)
if (length(obj@images) > 0) obsm <- c(obsm, "spatial")
obsm <- unique(obsm)
layers <- tryCatch(Layers(obj[[assay]]), error = function(e) character())
flags <- obj@misc$stringency
if (is.null(flags)) flags <- list()
# counts_per_group: units of each declared unit column remaining per level of each factor
units <- design$units; if (is.null(units)) units <- list()
cpg <- list()
for (fname in names(design$factors)) {
  fac <- design$factors[[fname]]; col <- fac$column
  cpg[[fname]] <- list()
  if (is.null(col) || !(col %in% colnames(md))) next
  for (lvl in fac$levels) {
    mask <- as.character(md[[col]]) == as.character(lvl)
    per <- list()
    for (uname in names(units)) {
      ucol <- units[[uname]]
      if (uname == "observation") { per[["observation"]] <- sum(mask); next }
      if (ucol %in% colnames(md)) per[[ucol]] <- length(unique(md[[ucol]][mask])) else per[[ucol]] <- 0L
    }
    if (is.null(per[["observation"]])) per[["observation"]] <- sum(mask)
    cpg[[fname]][[as.character(lvl)]] <- per
  }
}
domain <- list(assay = assay, fovs = as.list(names(obj@images)))
# exact names: `$` partial-matches, so with no `clustering` flag `flags$clustering` returned the
# `clustering_grid` flag of a cluster-umap 0.4 object and its eight columns (synthetic upstream
# run, 2026-10-14); a grid object has no identity yet and reports no clustering
clus <- flags[["clustering"]][["column"]]
if (!is.null(clus) && length(clus) == 1 && clus %in% colnames(md)) {
  domain$clustering_column <- clus
  domain$n_clusters <- length(unique(md[[clus]]))
  for (by in c("punch_id", "animal")) {
    if (by %in% colnames(md)) {
      tab <- as.data.frame(table(md[[clus]], md[[by]]), stringsAsFactors = FALSE)
      names(tab) <- c("cluster", by, "n_cells")
      domain[[paste0("cells_per_cluster_per_", by)]] <- tab
    }
  }
}
lab <- flags[["labels"]]
if (!is.null(lab$column) && lab$column %in% colnames(md)) {
  domain$labels <- list(column = lab$column, vocabulary = lab$vocabulary,
                        n_labels = length(unique(md[[lab$column]])),
                        unknown_fraction = if ("unknown" %in% md[[lab$column]]) mean(md[[lab$column]] == "unknown") else 0)
}
if (!is.null(flags[["spatial_graph"]])) domain$spatial_graph <- flags[["spatial_graph"]]
if (!is.null(flags[["exclusions"]])) domain$exclusions <- flags[["exclusions"]]
env <- list(
  extractor = "sc.seurat_object@2", type = "seurat_object",
  n_obs = ncol(obj), n_var = nrow(obj),
  fields = list(obs = fields_obs, columns = fields_obs, feature_columns = feature_columns,
                obsm = as.list(obsm), layers = as.list(layers), uns_flags = flags),
  counts_per_group = cpg,
  domain = domain
)
cat(toJSON(env, auto_unbox = TRUE, null = "null", digits = NA, dataframe = "rows"))
