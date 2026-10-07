"""Single-cell and spatial predicates (design 6.1). Importing this package registers them.

One file per concern; every predicate ships a must-fire and a must-pass fixture in
`tests/test_predicates.py` (CASES). Predicates read extractor summaries from `ctx.state.objects`
and never the data.
"""

from __future__ import annotations

from stringency_singlecell.predicates import (  # noqa: F401
    cells,
    decisions,
    join,
    objects,
    outliers,
    spatial,
)

SOURCE = "stringency-singlecell"
