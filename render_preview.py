#!/usr/bin/env python3
"""Render a simple preview PNG of the nest STL (pure stdlib, no deps)."""

import math
import struct
import zlib
import generate_nest as g

W, H = 700, 520
BG = (245, 245, 248)

tris = g.generate_triangles()

az = math.radians(35.0)
el = math.radians(28.0)
ca, sa = math.cos(az), math.sin(az)
ce, se = math.cos(el), math.sin(el)


def to_cam(p):
    x, y, z = p
    x1 = x * ca + y * sa
    y1 = -x * sa + y * ca
    y2 = y1 * ce + z * se
    z2 = -y1 * se + z * ce
    return (x1, y2, z2)


cam = [to_cam((t[i], t[j], t[k]))
       for t in tris
       for (i, j, k) in [(0, 1, 2), (3, 4, 5), (6, 7, 8)]]

minx = min(c[0] for c in cam); maxx = max(c[0] for c in cam)
miny = min(c[1] for c in cam); maxy = max(c[1] for c in cam)
span = max(maxx - minx, maxy - miny)
scale = 0.82 * min(W, H) / span
ox = W / 2.0 - scale * (minx + maxx) / 2.0
oy = H / 2.0 + scale * (miny + maxy) / 2.0


def proj(p):
    x, y, z = to_cam(p)
    return (ox + scale * x, oy - scale * y, z)


light = (0.35, 0.5, 0.78)
ln = math.sqrt(sum(v * v for v in light))
light = tuple(v / ln for v in light)

buf = [[BG for _ in range(W)] for _ in range(H)]
zbuf = [[-1e18] * W for _ in range(H)]

for t in tris:
    a, b, c = proj(t[0:3]), proj(t[3:6]), proj(t[6:9])
    n = g.face_normal(t)
    nx, ny, nz = to_cam((n[0], n[1], n[2]))
    nl = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    diff = abs((nx * light[0] + ny * light[1] + nz * light[2]) / nl)
    shade = 0.45 + 0.55 * diff
    col = (int(min(255, 150 * shade)), int(min(255, 108 * shade)),
           int(min(255, 75 * shade)))

    minx2 = max(0, int(min(a[0], b[0], c[0])))
    maxx2 = min(W - 1, int(max(a[0], b[0], c[0])) + 1)
    miny2 = max(0, int(min(a[1], b[1], c[1])))
    maxy2 = min(H - 1, int(max(a[1], b[1], c[1])) + 1)
    for py in range(miny2, maxy2 + 1):
        for px in range(minx2, maxx2 + 1):
            d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(d) < 1e-9:
                continue
            l1 = ((b[1] - c[1]) * (px + 0.5 - c[0]) + (c[0] - b[0]) * (py + 0.5 - c[1])) / d
            l2 = ((c[1] - a[1]) * (px + 0.5 - c[0]) + (a[0] - c[0]) * (py + 0.5 - c[1])) / d
            l3 = 1.0 - l1 - l2
            if l1 < -0.001 or l2 < -0.001 or l3 < -0.001:
                continue
            z = l1 * a[2] + l2 * b[2] + l3 * c[2]
            if z > zbuf[py][px]:
                zbuf[py][px] = z
                buf[py][px] = col

raw = b""
for row in buf:
    raw += b"\x00" + b"".join(struct.pack("BBB", *p) for p in row)


def chunk(tag, data):
    c = struct.pack(">I", len(data)) + tag + data
    return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


png = b"\x89PNG\r\n\x1a\n"
png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
png += chunk(b"IDAT", zlib.compress(raw, 9))
png += chunk(b"IEND", b"")
open("preview.png", "wb").write(png)
print("wrote preview.png")
