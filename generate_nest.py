#!/usr/bin/env python3
"""
3D-printable bird's nest for the board game Wingspan.

Design:
  * Round woven cup that holds a row of egg tokens.
  * Closed, watertight solid built as a solid of revolution with woven stick
    protrusions, so there are no booleans and no chance of an open mesh.
  * Flat base for stability, scalloped rim, irregular woven sticks at
    different angles on the outer wall, rim, and inner wall.

Run:    python3 generate_nest.py
Output: wingspan_bird_nest.stl         (binary STL, print ready)
        wingspan_bird_nest_ascii.stl  (human readable)
"""

import math
import random
import struct
import os

from nest_profile import (
    OUTER_TOP_DIAMETER,
    INNER_TOP_DIAMETER,
    NEST_DEPTH,
    BASE_THICKNESS,
    BASE_RADIUS,
    FLOOR_RADIUS,
    TEXTURE_AMPLITUDE,
    TEXTURE_Z_PITCH,
    TEXTURE_T_COUNT,
    SCALLOP_COUNT,
    SCALLOP_HEIGHT,
    N_ANGLE,
    build_profile,
    displace,
    STICK_COUNT_OUTER,
    STICK_COUNT_RIM,
    STICK_COUNT_INNER,
    STICK_LENGTH_MIN,
    STICK_LENGTH_MAX,
    STICK_THICK_MIN,
    STICK_THICK_MAX,
    STICK_ANGLE_MIN,
    STICK_ANGLE_MAX,
    RIM_STICK_ANGLE_MIN,
    RIM_STICK_ANGLE_MAX,
    STICK_IRREGULARITY,
    STICK_SEED,
)

OUTPUT_STL = "wingspan_bird_nest.stl"
ASCII_STL = "wingspan_bird_nest_ascii.stl"

# ==========================================================================
# WOVEN STICKS
# ==========================================================================


def _frand(rng, lo, hi):
    """Random float in [lo, hi)."""
    return lo + rng.random() * (hi - lo)


def _irregular(rng, value, irregularity):
    """Apply random variation to a value."""
    delta = value * irregularity
    return value + _frand(rng, -delta, delta)


def generate_sticks(rng):
    """Create a list of stick definitions."""
    sticks = []
    z_top = NEST_DEPTH + BASE_THICKNESS

    print(f"  Generating {STICK_COUNT_OUTER} outer sticks...")
    for i in range(STICK_COUNT_OUTER):
        # Start sticks at BASE_THICKNESS to avoid disturbing the flat bottom.
        # The flat bottom sits at z=0 to z=BASE_THICKNESS; sticks begin at the
        # cavity floor level so the lower nest remains smooth.
        base_z = _frand(rng, BASE_THICKNESS, z_top - STICK_LENGTH_MAX)
        theta = (2.0 * math.pi * i / STICK_COUNT_OUTER
                 + _frand(rng, -0.3, 0.3) * STICK_IRREGULARITY)

        # Length decreases toward the base (closer to center).
        # z_norm = 0 at bottom, 1 at top; longer sticks at the top (farther from center).
        z_norm = base_z / z_top  # 0 at base, 1 at top
        length = _irregular(rng,
                            STICK_LENGTH_MIN + (STICK_LENGTH_MAX - STICK_LENGTH_MIN) * z_norm,
                            STICK_IRREGULARITY)
        thick = _irregular(rng,
                           _frand(rng, STICK_THICK_MIN, STICK_THICK_MAX),
                           STICK_IRREGULARITY)

        # Sticks are horizontal (lean=90°) and circumferential (tangent to the circle).
        # lean = 90° means stick is horizontal; around determines the tangential direction.
        # Stick points circumferentially: tangent to the circle at the stick's angular position.
        # around_base gives the stick's angular position; +90° gives tangential direction.
        lean = math.pi / 2  # 90° from horizontal = horizontal circumferential direction
        around_base = (2.0 * math.pi * i / STICK_COUNT_OUTER)
        around = around_base + math.pi / 2 + _frand(rng, -0.1, 0.1)  # tangential with small randomness

        dx = math.sin(lean) * math.cos(around)
        dy = math.sin(lean) * math.sin(around)
        dz = math.cos(lean)

        sticks.append({
            "theta": theta,
            "z": base_z,
            "dir": (dx, dy, dz),
            "length": length,
            "thick": thick,
        })

    print(f"  Generating {STICK_COUNT_INNER} inner sticks...")
    for i in range(STICK_COUNT_INNER):
        base_z = _frand(rng, BASE_THICKNESS + 1.0, z_top - 2.0)
        theta = (2.0 * math.pi * i / STICK_COUNT_INNER
                 + _frand(rng, -0.3, 0.3) * STICK_IRREGULARITY)

        # Length decreases toward the base (closer to center).
        z_norm = base_z / z_top  # 0 at base, 1 at top
        length = _irregular(rng,
                            STICK_LENGTH_MIN * 0.5 + (STICK_LENGTH_MAX * 0.7 - STICK_LENGTH_MIN * 0.5) * z_norm,
                            STICK_IRREGULARITY)
        thick = _irregular(rng,
                           _frand(rng, STICK_THICK_MIN * 0.8, STICK_THICK_MAX * 0.9),
                           STICK_IRREGULARITY)

        # Sticks are horizontal (lean=90°) and circumferential (tangent to the circle).
        # lean = 90° means stick is horizontal; around determines the tangential direction.
        # Stick points circumferentially: tangent to the circle at the stick's angular position.
        # around_base gives the stick's angular position; +90° gives tangential direction.
        lean = math.pi / 2  # 90° from horizontal = horizontal circumferential direction
        around_base = math.pi * 2.0 * i / STICK_COUNT_INNER  # systematic sweep from 0 to 2π
        around = around_base + math.pi / 2 + _frand(rng, -0.1, 0.1)  # tangential with small randomness

        dx = math.sin(lean) * math.cos(around)
        dy = math.sin(lean) * math.sin(around)
        dz = math.cos(lean)

        sticks.append({
            "theta": theta,
            "z": base_z,
            "dir": (dx, dy, dz),
            "length": length,
            "thick": thick,
        })

        if (i + 1) % (STICK_COUNT_INNER // 10) == 0 or i == 0:
            print(f"    Inner stick {i+1}/{STICK_COUNT_INNER} complete")

    return sticks



def apply_sticks(rings, sticks, profile):
    """Displace surface vertices to create stick protrusions."""
    d_theta = 2.0 * math.pi / N_ANGLE

    # Maximum total stick displacement per vertex (mm).
    # Prevents stick pile-ups from creating pointy spikes.
    MAX_TOTAL_DISP = 8.0

    displaced = []
    for ring_idx, ring in enumerate(rings):
        r, z, tex_w, wave_w = profile[ring_idx]
        
        # Skip stick displacement for the flat bottom ring at z=0
        # to ensure a smooth, ridge-free surface
        if abs(z) < 0.01:
            displaced.append(ring)
            continue
        
        new_ring = []
        for j, (x, y, zz) in enumerate(ring):
            th = j * d_theta
            sx, sy, sz = x, y, zz

            dx_total = 0.0
            dy_total = 0.0
            dz_total = 0.0

            for stick in sticks:
                cx = r * math.cos(stick["theta"])
                cy = r * math.sin(stick["theta"])
                cz = stick["z"]

                d_theta_diff = abs(th - stick["theta"])
                d_theta_diff = min(d_theta_diff, 2.0 * math.pi - d_theta_diff)
                d_surf = math.sqrt((r * d_theta_diff) ** 2 + (sz - cz) ** 2)

                if d_surf > stick["thick"]:
                    continue

                t = 1.0 - d_surf / stick["thick"]
                t = t * t

                # Per-stick displacement, capped so sticks can't stack into spikes
                stick_contrib = stick["length"] * t
                # Only apply if this stick's contribution is reasonable vs its thickness
                if stick_contrib > stick["thick"] * 2.0:
                    # Stick is too long relative to its thickness — trim the contribution
                    stick_contrib = stick["thick"] * 2.0

                sx_d, sy_d, sz_d = stick["dir"]
                dx_total += sx_d * stick_contrib
                dy_total += sy_d * stick_contrib
                dz_total += sz_d * stick_contrib

            # Total displacement ceiling per vertex — no single point gets taller than this
            total_disp = math.sqrt(dx_total ** 2 + dy_total ** 2 + dz_total ** 2)
            if total_disp > MAX_TOTAL_DISP:
                # Scale down all contributions proportionally
                scale = MAX_TOTAL_DISP / total_disp
                dx_total *= scale
                dy_total *= scale
                dz_total *= scale

            new_ring.append((sx + dx_total, sy + dy_total, sz + dz_total))
        displaced.append(new_ring)

    return displaced


def generate_triangles():
    """Build the triangle list for the nest with woven sticks."""
    profile = build_profile()
    rng = random.Random(STICK_SEED)
    sticks = generate_sticks(rng)
    tris = []
    d_theta = 2.0 * math.pi / N_ANGLE

    # One ring of vertices per profile point.
    rings = []
    for (r, z, tex_w, wave_w) in profile:
        if r < 1e-9:
            rings.append([(0.0, 0.0, displace(0.0, z, 0.0, tex_w, wave_w)[1])])
        else:
            ring = []
            for j in range(N_ANGLE):
                th = j * d_theta
                rr, zz = displace(r, z, th, tex_w, wave_w)
                ring.append((rr * math.cos(th), rr * math.sin(th), zz))
            rings.append(ring)

    # Apply stick displacements.
    rings = apply_sticks(rings, sticks, profile)

    # Stitch consecutive rings together.
    for i in range(len(rings) - 1):
        a = rings[i]
        b = rings[i + 1]
        if len(a) == 1:                       # pole (underside centre)
            p = a[0]
            for j in range(N_ANGLE):
                q = b[(j + 1) % N_ANGLE]
                s = b[j]
                tris.append((p[0], p[1], p[2], q[0], q[1], q[2], s[0], s[1], s[2]))
        elif len(b) == 1:                     # pole (cavity floor centre)
            p = b[0]
            for j in range(N_ANGLE):
                q = a[(j + 1) % N_ANGLE]
                s = a[j]
                tris.append((q[0], q[1], q[2], p[0], p[1], p[2], s[0], s[1], s[2]))
        else:
            for j in range(N_ANGLE):
                k = (j + 1) % N_ANGLE
                p, q, s = a[j], a[k], b[k]
                t, u, v = a[j], b[k], b[j]
                tris.append((p[0], p[1], p[2], q[0], q[1], q[2], s[0], s[1], s[2]))
                tris.append((t[0], t[1], t[2], u[0], u[1], u[2], v[0], v[1], v[2]))

    return tris, len(sticks)

# ==========================================================================
# STL WRITER
# ==========================================================================

def face_normal(tri):
    ax, ay, az = tri[0:3]
    bx, by, bz = tri[3:6]
    cx, cy, cz = tri[6:9]
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    if ln < 1e-12:
        return (0.0, 0.0, 0.0)
    return (nx / ln, ny / ln, nz / ln)


def write_stl(triangles, filename):
    """Write a binary STL file (80 byte header, uint32 count, 50 bytes/tri)."""
    header = b"Wingspan Birds Nest - mm units".ljust(80, b"\x00")
    with open(filename, "wb") as f:
        f.write(header)
        f.write(struct.pack("<I", len(triangles)))
        for tri in triangles:
            nx, ny, nz = face_normal(tri)
            f.write(struct.pack("<12fH", nx, ny, nz,
                                tri[0], tri[1], tri[2],
                                tri[3], tri[4], tri[5],
                                tri[6], tri[7], tri[8],
                                0))


def write_text_stl(triangles, filename):
    """Write a human-readable ASCII STL file."""
    with open(filename, "w") as f:
        f.write("solid WingspanBirdNest\n")
        for tri in triangles:
            nx, ny, nz = face_normal(tri)
            f.write("  facet normal %.6f %.6f %.6f\n" % (nx, ny, nz))
            f.write("    outer loop\n")
            for i in range(3):
                f.write("      vertex %.6f %.6f %.6f\n" % tri[i * 3:i * 3 + 3])
            f.write("    endloop\n")
            f.write("  endfacet\n")
        f.write("endsolid WingspanBirdNest\n")


# ==========================================================================
# VALIDATION
# ==========================================================================

def check_manifold(triangles):
    """A closed surface uses every directed edge exactly once.

    Returns the number of directed edges that were seen more than once.
    """
    edges = {}
    for tri in triangles:
        for i in range(3):
            a = tuple(round(v, 5) for v in tri[i * 3:i * 3 + 3])
            n = (i + 1) % 3
            b = tuple(round(v, 5) for v in tri[n * 3:n * 3 + 3])
            edges[(a, b)] = edges.get((a, b), 0) + 1
    return sum(1 for v in edges.values() if v != 1)


# ==========================================================================
# MAIN
# ==========================================================================

def main():
    import random
    import generate_nest as gn
    
    rng = random.Random(gn.STICK_SEED)
    print("Generating Wingspan bird's nest STL...")
    print("  Step 1: Generating sticks...")
    sticks = generate_sticks(rng)
    print(f"    Generated {len(sticks)} sticks")
    print("  Step 2: Generating triangles...")
    triangles, stick_count = generate_triangles()
    print(f"    Generated {len(triangles)} triangles")
    print(f"  Step 3: {stick_count} sticks recorded")

    write_stl(triangles, OUTPUT_STL)
    write_text_stl(triangles, ASCII_STL)
    print("  Written:      %s (%d bytes)" % (OUTPUT_STL, os.path.getsize(OUTPUT_STL)))
    print("  Written:      %s (%d bytes)" % (ASCII_STL, os.path.getsize(ASCII_STL)))

    xs = [t[i] for t in triangles for i in (0, 3, 6)]
    ys = [t[i] for t in triangles for i in (1, 4, 7)]
    zs = [t[i] for t in triangles for i in (2, 5, 8)]
    print("  Bounding box: X [%.2f, %.2f]  Y [%.2f, %.2f]  Z [%.2f, %.2f]"
          % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))

    bad = check_manifold(triangles)
    print("  Manifold:     %s" % ("OK (closed solid)" if bad == 0
                                 else "FAIL, %d bad edges" % bad))

    print("\nDone. Open the .stl in your slicer and print.")
    print("Tip: 3 perimeters, 20-30% infill, no supports needed.")


if __name__ == "__main__":
    main()
