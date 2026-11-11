#!/usr/bin/env python3
"""State extractor for object type `if_image` (plugin 0.10.6): an immunofluorescence image of a
slide as a TIFF or OME-TIFF, declared as an input of a step that measures it inside each cell
(the Xenium method's `if-intensity`). Reads the file's metadata only, never its pixels. Needs
tifffile, so it runs in the module's environment (the `xenium-py` image).

usage: extract_if_image.py <image.ome.tif> <design.json>
Prints the envelope: extractor, type, n_obs (pixels of a plane), n_var (channels), fields
(`channels`, the channel names in order, the list a step's channel parameter is one of),
counts_per_group (empty), and domain: `axes`, `shape`, `dtype`, `is_ome`, `n_levels`,
`pixel_size_um`, `single_plane` (no axis beside the channel, Y and X longer than one).
"""

from __future__ import annotations

import json
import re
import sys


def main(argv: list[str]) -> int:
    import tifffile

    with tifffile.TiffFile(argv[1]) as tif:
        series = tif.series[0]
        axes, shape = series.axes, [int(n) for n in series.shape]
        ome = tif.ome_metadata if tif.is_ome else None
        names = re.findall(r'<Channel\b[^>]*?\bName="([^"]*)"', ome) if ome else []
        size = re.search(r'PhysicalSizeX="([^"]*)"', ome) if ome else None
        c_axis = "C" if "C" in axes else ("S" if "S" in axes else "")
        n_channels = shape[axes.index(c_axis)] if c_axis else 1
        plane = 1
        for ax in "YX":
            plane *= shape[axes.index(ax)] if ax in axes else 0
        extra = [a for a, n in zip(axes, shape) if a not in ("Y", "X", c_axis) and n > 1]
        env = {
            "extractor": "sc.if_image@1",
            "type": "if_image",
            "n_obs": plane,
            "n_var": n_channels,
            "fields": {"channels": names or [str(i) for i in range(n_channels)]},
            "counts_per_group": {},
            "domain": {
                "axes": axes,
                "shape": shape,
                "dtype": str(series.dtype),
                "is_ome": bool(tif.is_ome),
                "n_levels": len(series.levels),
                "pixel_size_um": float(size.group(1)) if size else None,
                "single_plane": not extra and plane > 0,
            },
        }
    print(json.dumps(env, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
