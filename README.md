# Wingspan Bird's Nest

A 3D-printable bird's nest for holding egg tokens during a game of
[Wingspan](https://boardgamegeek.com/boardgame/266192/wingspan).

![preview](preview.png)

## Files

| File | Purpose |
|---|---|
| `generate_nest.py` | Parametric generator (pure Python stdlib, no dependencies) |
| `wingspan_bird_nest.stl` | Binary STL, print-ready |
| `wingspan_bird_nest_ascii.stl` | ASCII STL for inspection |
| `render_preview.py` | Tiny stdlib renderer that produces `preview.png` |

## Dimensions

* Outer diameter at rim: **70 mm**
* Inner diameter at rim: **60 mm**
* Cavity depth: **28 mm**
* Base thickness: **3 mm**
* Overall height: **33.6 mm**
* Flat base: **60 mm** across, so it doesn't tip

All dimensions are millimetres. Edit the constants at the top of
`generate_nest.py` to change them, then re-run:

```sh
python3 generate_nest.py
```

## Printing

* 3 perimeters, 20-30% infill
* No supports needed — it prints upright, base down
* At 0.15 mm layer height, expect roughly 6-8 hours on a typical FDM printer
* A brim is a good idea: the base is only 3 mm thick and the rim is wide

## How it works

The nest is a **solid of revolution**. A closed profile curve in the
(r, z) half-plane is swept around the Z axis, which guarantees the
result is watertight without any boolean operations. The profile is:

```
flat underside -> up the outer wall -> over the scalloped rim
                -> down the inner wall -> flat cavity floor -> back to the axis
```

Two displacement functions add the detail on top of that base shape:

* **Woven texture** — a radial sine wave in Z, modulated by a cosine in
  theta, so the ribs look like bundled twigs.
* **Rim scallop** — a cosine in theta applied only to the three rim
  profile points, giving the wavy edge.

The generator runs a manifold check on every run: each directed edge of the
mesh must be used exactly once, which is what "closed solid" means. It
prints `Manifold: OK` when the mesh is valid.
