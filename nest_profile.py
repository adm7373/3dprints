#!/usr/bin/env python3
"""nest_profile.py - Profile and parameters for Wingspan bird's nest generation.

This module defines the geometric profile (2D cross-section) and all parameters
used during nest generation. The profile is a closed 2D shape defining the nest's
silhouette, and parameters control stick generation, texture, and dimensions.

Design principles:
- All dimensions in millimeters (mm)
- Profile follows a closed loop at z=0 (bottom), z=BASE_THICKNESS (cavity floor),
  and up to the rim/top.
- Sticks are generated circumferentially (tangent to radius) with length gradation
  from center to rim.
- Texture is applied via sinusoidal displacement around the revolved solid.
"""

# ============================================================================
# GEOMETRIC PARAMETERS
# These control the overall size and shape of the nest.
# ============================================================================

#: Outer diameter of the nest top (including rim). Affects total width.
#: Typical value: 70.0 mm
#: User reduced BASE_RADIUS so scaled to 35.0 mm for proportional consistency
OUTER_TOP_DIAMETER = 75.0

#: Inner diameter of the nest top (the opening where eggs sit). Affects egg
#: clearance. Typical value: 60.0 mm
#: Scaled proportionally: 30.0 mm
INNER_TOP_DIAMETER = 70.0

#: Vertical depth of the nest bowl, from bottom to rim top.
#: Typical value: 28.0 mm
#: Scaled proportionally: 14.0 mm
NEST_DEPTH = 30.0

#: Thickness of the nest bottom/base. The nest sits flat on the table on this
#: surface.
#: Typical value: 3.0 mm
#: Scaled proportionally: 1.5 mm
BASE_THICKNESS = 1.5

#: Radius of the flat bottom surface. The nest has no center post; it sits
#: directly on the table within this radius.
#: Typical value: 30.0 mm
#: User reduced to 15.0 mm for smaller nest
BASE_RADIUS = 15.0

#: Radius of the cavity floor (the flat disc inside the bowl where eggs rest).
#: Must be <= BASE_RADIUS. Typical value: 25.0 mm
#: Scaled proportionally and ensure <= BASE_RADIUS: 12.5 mm
FLOOR_RADIUS = 12.5

# ============================================================================
# TEXTURE PARAMETERS
# These control the sinusoidal displacement applied to the revolved solid.
# ============================================================================

#: Amplitude of radial texture displacement (how far sticks/texture protrude).
#: Controls the 'scalloped' or 'woven' appearance along the wall.
#: Typical value: 0.5-2.0 mm. Larger values make more pronounced sticks.
#: User wants increased stick visibility - scaled proportionally from original.
#: Original 0.5mm for 70mm nest; scaled to 0.25mm for 35mm nest, but
#: increased to 0.5mm for good visibility at smaller scale
TEXTURE_AMPLITUDE = 2.5

#: Pitch (frequency) of z-axis texture variation.
#: Controls how quickly the texture pattern repeats vertically.
#: Typical value: 0.1 - smaller values give wider-spaced ripples.
TEXTURE_Z_PITCH = 0.1

#: Number of angular divisions for texture mapping.
#: Higher values = finer texture detail around the circumference.
#: Typical value: 32 - balance between quality and file size.
TEXTURE_T_COUNT = 320

# ============================================================================
# SCALLOP PARAMETERS
# These control the physical scallop/wave features on the nest surface.
# ============================================================================

#: Number of scallop/wave features around the circumference.
#: Determines how many 'rib-like' features appear around the nest.
#: Typical value: 6
SCALLOP_COUNT = 0

#: Height/depth of each scallop feature.
#: Controls how deep the scallop indentations are.
#: Typical value: 1.0 mm
SCALLOP_HEIGHT = 1.0

# ============================================================================
# ANGULAR RESOLUTION
# ============================================================================

#: Number of angular divisions around the revolved solid.
#: Higher values = smoother surface, more triangles in the STL.
#: Typical value: 32 (balance between quality and file size).
N_ANGLE = 32000

# ============================================================================
# STICK PARAMETERS
# These control the woven stick protrusions on the nest exterior.
# ============================================================================

#: Number of outer sticks around the nest wall.
#: Determines density of outer woven layer.
STICK_COUNT_OUTER = 500

#: Number of rim sticks around the nest top edge.
STICK_COUNT_RIM = 120

#: Number of inner sticks around the nest interior.
STICK_COUNT_INNER = 375

#: Minimum stick length (near the base/center of the nest).
STICK_LENGTH_MIN = 13.0

#: Maximum stick length (near the rim/top of the nest).
STICK_LENGTH_MAX = 38.0

#: Minimum stick thickness.
STICK_THICK_MIN = 2.8

#: Maximum stick thickness.
STICK_THICK_MAX = 5.0

#: Minimum stick angle relative to horizontal (degrees).
STICK_ANGLE_MIN = -20

#: Maximum stick angle relative to horizontal (degrees).
STICK_ANGLE_MAX = 20

#: Minimum rim stick angle relative to horizontal (degrees).
RIM_STICK_ANGLE_MIN = -30

#: Maximum rim stick angle relative to horizontal (degrees).
RIM_STICK_ANGLE_MAX = 30

#: Irregularity factor for stick positioning (0.0 - 1.0).
STICK_IRREGULARITY = 0.4

#: Random seed for stick generation.
STICK_SEED = 42

# ============================================================================
# DERIVED/INTERNAL (typically not user-configurable)
# ============================================================================

#: Ratio of inner top radius to outer top radius, computed from diameters.
r_inner_top_ratio = None  # computed at runtime

#: Number of profile segments for outer wall.
n_outer = 25

#: Number of profile segments for inner wall.
n_inner = 10


import math


def _frand(rng, lo, hi):
    """Return a random float in [lo, hi)."""
    return lo + rng.random() * (hi - lo)


def _irregular(rng, value, irregularity):
    """Apply random variation to a value."""
    delta = value * irregularity
    return value + _frand(rng, -delta, delta)


def build_profile():
    """Return the closed profile as a list of (r, z, tex_w, wave_w) tuples."""
    p = []

    # ---- flat underside (sits on the table) ------------------------------
    p.append((0.0, 0.0, 0.0, 0.0))
    p.append((BASE_RADIUS, 0.0, 0.0, 0.0))

    # ---- cavity floor: flat disc at z=BASE_THICKNESS ---------------------
    p.append((0.0, BASE_THICKNESS, 0.0, 0.0))
    p.append((FLOOR_RADIUS, BASE_THICKNESS, 0.0, 0.0))

    # ---- outer wall, base edge up to the rim -----------------------------
    r_top = OUTER_TOP_DIAMETER / 2.0
    z_top = NEST_DEPTH + BASE_THICKNESS
    n_outer = 14
    for i in range(1, n_outer + 1):
        t = i / float(n_outer)
        s = math.sin(t * math.pi / 2.0) ** 0.9
        r = BASE_RADIUS + (r_top - BASE_RADIUS) * s
        z = z_top * t
        tex_w = 1.0 - 0.35 * t
        wave_w = 0.0
        p.append((r, z, tex_w, wave_w))

    # ---- rim, outer lip over to inner lip --------------------------------
    r_inner_top = INNER_TOP_DIAMETER / 2.0
    p.append((r_top - 0.4, z_top + 0.6, 0.55, 0.5))
    p.append((r_top - (r_top - r_inner_top) * 0.5, z_top + 1.0, 0.30, 1.0))
    p.append((r_inner_top + 0.4, z_top + 0.6, 0.55, 0.5))

    # ---- inner wall, rim down to the cavity floor ------------------------
    n_inner = 10
    z_lip = z_top + 0.6
    z_fillet = BASE_THICKNESS + 1.5
    for i in range(1, n_inner + 1):
        t = i / float(n_inner)
        s = t * t * (3.0 - 2.0 * t)
        r = r_inner_top + (FLOOR_RADIUS + 4.0 - r_inner_top) * s
        z = z_lip + (z_fillet - z_lip) * t
        tex_w = 1.0 - 0.5 * t
        wave_w = 0.0
        p.append((r, z, tex_w, wave_w))

    p.append((FLOOR_RADIUS, BASE_THICKNESS + 0.6, 0.2, 0.0))
    p.append((0.0, BASE_THICKNESS, 0.0, 0.0))

    return p


def displace(r, z, th, tex_w, wave_w):
    """Apply texture/wave displacement to a profile point."""
    r_displacement = TEXTURE_AMPLITUDE * tex_w * math.cos(wave_w * th)
    z_displacement = TEXTURE_Z_PITCH * z * math.sin(wave_w * th)
    new_r = r + r_displacement
    new_z = z + z_displacement
    return (new_r, new_z)


def _frand(rng, lo, hi):
    """Return a random float in [lo, hi)."""
    return lo + rng.random() * (hi - lo)


def _irregular(rng, value, irregularity):
    """Apply random variation to a value."""
    delta = value * irregularity
    return value + _frand(rng, -delta, delta)


def generate_sticks(rng):
    """Create a list of stick definitions."""
    sticks = []
    z_top = NEST_DEPTH + BASE_THICKNESS

    # Outer sticks: full height range, inverse length gradation
    for i in range(STICK_COUNT_OUTER):
        base_z = _frand(rng, BASE_THICKNESS, z_top)
        theta = (2.0 * math.pi * i / STICK_COUNT_OUTER
                 + _frand(rng, -0.3, 0.3) * STICK_IRREGULARITY)
        z_norm = 1.0 - (base_z / z_top)
        length = _irregular(rng,
                            STICK_LENGTH_MIN + (STICK_LENGTH_MAX - STICK_LENGTH_MIN) * z_norm,
                            STICK_IRREGULARITY)
        thick = _irregular(rng,
                           _frand(rng, STICK_THICK_MIN, STICK_THICK_MAX),
                           STICK_IRREGULARITY)

        lean = math.pi / 2
        around_base = (2.0 * math.pi * i / STICK_COUNT_OUTER)
        around = around_base + math.pi / 2 + _frand(rng, -0.1, 0.1)

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

    # Inner sticks
    for i in range(STICK_COUNT_INNER):
        base_z = _frand(rng, BASE_THICKNESS + 1.0, z_top - 2.0)
        theta = (2.0 * math.pi * i / STICK_COUNT_INNER
                 + _frand(rng, -0.3, 0.3) * STICK_IRREGULARITY)
        z_norm = base_z / z_top
        length = _irregular(rng,
                            STICK_LENGTH_MIN * 0.5 + (STICK_LENGTH_MAX * 0.7 - STICK_LENGTH_MIN * 0.5) * z_norm,
                            STICK_IRREGULARITY)
        thick = _irregular(rng,
                           _frand(rng, STICK_THICK_MIN * 0.8, STICK_THICK_MAX * 0.9),
                           STICK_IRREGULARITY)

        lean = math.pi / 2
        around_base = math.pi * 2.0 * i / STICK_COUNT_INNER
        around = around_base + math.pi / 2 + _frand(rng, -0.1, 0.1)

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

    return sticks
