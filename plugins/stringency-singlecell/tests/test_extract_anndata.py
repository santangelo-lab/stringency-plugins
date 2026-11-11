"""The `anndata` extractor at version 2 (plugin 0.10.4): the obs columns under `fields.columns`,
the key the engine reads (`init.column_missing`; a pipeline's names, engine 0.2.42), with the
values of a categorical or text column of fifty or fewer. Needs anndata, so it runs in a module
environment and is skipped where the package is absent (CI's bare runner)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = (
    Path(__file__).parent.parent / "src" / "stringency_singlecell" / "tools" / "extract_anndata.py"
)


def test_obs_columns_are_written_where_the_engine_reads_them(tmp_path: Path) -> None:
    ad = pytest.importorskip("anndata")
    np = pytest.importorskip("numpy")
    pd = pytest.importorskip("pandas")
    n = 60
    obs = pd.DataFrame(
        {
            "condition": pd.Categorical(["ctrl", "stim"] * (n // 2)),
            "cell_type": ["T", "B", "Mono"] * (n // 3),
            "barcode": [f"bc{i}" for i in range(n)],
            "n_counts": np.arange(n, dtype=float),
        },
        index=[f"c{i}" for i in range(n)],
    )
    path = tmp_path / "t.h5ad"
    var = pd.DataFrame(
        {"gene_symbols": [f"G{i}" for i in range(5)], "highly_variable": [True] * 5},
        index=[f"ENSG{i}" for i in range(5)],
    )
    ad.AnnData(X=np.ones((n, 5), dtype="float32"), obs=obs, var=var).write_h5ad(path)
    design = tmp_path / "design.json"
    design.write_text(json.dumps({"factors": {}, "units": {}}))
    r = subprocess.run(
        [sys.executable, str(TOOL), str(path), str(design)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["extractor"] == "sc.anndata@2"
    cols = out["fields"]["columns"]
    assert cols == out["fields"]["obs"]  # the plugin's predicates still read `obs`
    assert cols["condition"]["levels"] == ["ctrl", "stim"]
    assert cols["cell_type"]["levels"] == ["B", "Mono", "T"]
    assert "levels" not in cols["barcode"] and "levels" not in cols["n_counts"]
    feats = out["fields"]["feature_columns"]
    assert sorted(feats) == ["gene_symbols", "highly_variable"]
    assert feats["gene_symbols"]["n_unique"] == 5
