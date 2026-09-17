#!/usr/bin/env python3
"""State extractor for object type `anndata` (design 4.2). Runs inside a module environment
that has anndata installed; the engine never imports it.

usage: extract_anndata.py <object.h5ad> <design.json>
Prints the envelope: extractor, type, n_obs, n_var, fields (obs columns with dtype, n_unique,
levels for categoricals; obsm, layers, uns flags), counts_per_group computed from the design's
factors and units, and a domain block.
"""

from __future__ import annotations

import json
import sys


def counts_per_group(obs, design):  # type: ignore[no-untyped-def]
    """Units of each declared unit column remaining per level of each declared factor."""
    units = design.get("units", {})
    out = {}
    for fname, fac in design.get("factors", {}).items():
        col = fac["column"]
        out[fname] = {}
        if col not in obs.columns:
            continue
        for lvl in fac.get("levels", []):
            mask = obs[col].astype(str) == str(lvl)
            per_unit = {}
            for uname, ucol in units.items():
                if uname == "observation" or ucol not in obs.columns:
                    per_unit[ucol if uname != "observation" else uname] = (
                        int(mask.sum()) if uname == "observation" else 0
                    )
                else:
                    per_unit[ucol] = int(obs.loc[mask, ucol].nunique())
            per_unit.setdefault(units.get("observation", "observation"), int(mask.sum()))
            out[fname][str(lvl)] = per_unit
    return out


def main(argv):  # type: ignore[no-untyped-def]
    path, design_path = argv[1], argv[2]
    with open(design_path) as f:
        design = json.load(f)
    import anndata as ad  # only inside the module environment

    adata = ad.read_h5ad(path, backed="r")
    obs = adata.obs
    fields = {}
    for c in obs.columns:
        s = obs[c]
        entry = {"dtype": str(s.dtype), "n_unique": int(s.nunique())}
        if str(s.dtype) == "category" and s.nunique() <= 50:
            entry["levels"] = [str(x) for x in s.cat.categories]
        fields[c] = entry
    uns = adata.uns if adata.uns is not None else {}
    flags = {k: True for k in ("log1p", "hvg", "neighbors", "pca") if k in uns}
    leiden = uns.get("leiden", {}) if isinstance(uns.get("leiden"), dict) else {}
    if "params" in leiden and "random_state" in leiden["params"]:
        flags["leiden_random_state"] = leiden["params"]["random_state"]
    out = {
        "extractor": "sc.anndata@1",
        "type": "anndata",
        "n_obs": int(adata.n_obs),
        "n_var": int(adata.n_vars),
        "fields": {
            "obs": fields,
            "obsm": sorted(adata.obsm.keys()),
            "layers": sorted(adata.layers.keys()),
            "uns_flags": flags,
        },
        "counts_per_group": counts_per_group(obs, design),
        "domain": {},
    }
    json.dump(out, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
