#!/usr/bin/env python3
"""
Check an exported STL for watertightness (closed, manifold, consistent).

Usage:
    python3 check_export.py [path/to/file.stl]

The check is the same one the standalone generator runs: every directed
edge of the triangle soup must appear exactly once.  A mesh where each
undirected edge is shared by exactly two triangles, once in each
direction, is a closed oriented surface.

The STEP file is only checked for existence and size -- validating a
B-Rep needs a CAD kernel, which is what Fusion provides.
"""

import os
import struct
import sys


def read_triangles(path):
    """Yield (v0, v1, v2) vertex tuples from a binary or ASCII STL."""
    with open(path, "rb") as handle:
        header = handle.read(84)
        if len(header) < 84:
            return
        count = struct.unpack("<I", header[80:84])[0]
        if count > 0:
            data = handle.read(count * 50)
            for i in range(count):
                off = i * 50
                vals = struct.unpack("<12f", data[off:off + 48])
                yield (vals[3:6], vals[6:9], vals[9:12])
            return

    # ASCII fallback.
    with open(path, "r") as handle:
        verts = []
        for line in handle:
            line = line.strip()
            if line.startswith("vertex"):
                verts.append(tuple(float(x) for x in line.split()[1:4]))
                if len(verts) == 3:
                    yield (verts[0], verts[1], verts[2])
                    verts = []


def key(v, quant=1e-5):
    """Quantise a vertex so equal points hash to the same key."""
    return (round(v[0] / quant), round(v[1] / quant), round(v[2] / quant))


def check_stl(path):
    """Return (ok, message) for the given STL file."""
    if not os.path.isfile(path):
        return False, "file not found: %s" % path

    directed = {}
    degenerate = 0
    triangles = 0
    for tri in read_triangles(path):
        triangles += 1
        a, b, c = (key(v) for v in tri)
        if a == b or b == c or a == c:
            degenerate += 1
            continue
        for edge in ((a, b), (b, c), (c, a)):
            directed[edge] = directed.get(edge, 0) + 1

    if triangles == 0:
        return False, "no triangles found"

    bad = [e for e, n in directed.items() if n != 1]
    if bad:
        return False, ("not watertight: %d of %d directed edges are not used "
                       "exactly once" % (len(bad), len(directed)))

    # Every undirected edge must be shared by exactly two triangles.
    undirected = {}
    for (u, v) in directed:
        k = (u, v) if u <= v else (v, u)
        undirected[k] = undirected.get(k, 0) + 1
    boundary = [k for k, n in undirected.items() if n != 2]
    if boundary:
        return False, ("not manifold: %d edges are not shared by exactly two "
                       "triangles" % len(boundary))

    return True, ("OK: %d triangles, %d edges, watertight and manifold"
                  % (triangles, len(undirected)))


def check_step(path):
    """Return (ok, message) for the given STEP file."""
    if not os.path.isfile(path):
        return False, "file not found: %s" % path
    size = os.path.getsize(path)
    if size < 100:
        return False, "STEP file looks empty (%d bytes)" % size
    with open(path, "r", errors="ignore") as handle:
        head = handle.read(400)
    if "ISO-10303" not in head:
        return False, "STEP file does not look like an ISO-10303 file"
    return True, "OK: %d bytes, ISO-10303 STEP" % size


def main():
    args = sys.argv[1:]
    stl = args[0] if args else os.path.join(
        os.path.expanduser("~"), "3dprints_exports",
        "wingspan_bird_nest_fusion.stl")
    step = args[1] if len(args) > 1 else os.path.join(
        os.path.expanduser("~"), "3dprints_exports",
        "wingspan_bird_nest_fusion.step")

    stl_ok, stl_msg = check_stl(stl)
    step_ok, step_msg = check_step(step)

    print("STL  %s: %s" % (stl, stl_msg))
    print("STEP %s: %s" % (step, step_msg))

    return 0 if (stl_ok and step_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
