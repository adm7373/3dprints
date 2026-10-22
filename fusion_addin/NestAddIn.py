"""
Fusion add-in: builds an editable native model of the Wingspan bird's nest.

The nest is a solid of revolution.  A closed profile sketch is drawn on the
XZ plane and revolved 360 degrees about the Z axis, which gives a fully
editable parametric body (edit the sketch, or drive it from the Fusion
User Parameters).

The same profile math is shared with the standalone STL generator through
`nest_profile.py`, so both outputs describe the same object.

The add-in is set to "run on startup": it creates a new design, builds the
nest, exports STL + STEP next to the script, and leaves the document open in
Fusion so you can inspect and edit it.
"""

import adsk.core
import adsk.fusion
import os
import sys
import traceback

# Make sure the shared profile module next to this file can be imported.
_ADDIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _ADDIN_DIR not in sys.path:
    sys.path.append(_ADDIN_DIR)

import nest_profile

# Where the exported files are written.  None -> ~/3dprints_exports.
EXPORT_DIR = None

# Name given to the created design and body.
DESIGN_NAME = "Wingspan Bird Nest"
BODY_NAME = "Nest"

# Base file names used for the exports.
STL_NAME = "wingspan_bird_nest_fusion.stl"
STEP_NAME = "wingspan_bird_nest_fusion.step"


def _log_file_path():
    """Return the path of the add-in's log file."""
    return os.path.join(_output_dir(), "nest_addin.log")


def _log(msg):
    """Write a line to Fusion's text command log and to the log file."""
    try:
        adsk.logMessage(msg)
    except Exception:
        pass
    try:
        path = _log_file_path()
        directory = os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(path, "a") as handle:
            handle.write(str(msg) + "\n")
    except Exception:
        pass


def _log_error(msg):
    _log("[NestAddIn] ERROR: " + msg)


MM = 0.1  # Fusion's internal length unit is cm; 1 mm = 0.1 cm


def _to_cm(mm_value):
    """Convert a millimetre value to Fusion's internal centimetres."""
    return float(mm_value) * MM


def _profile_points_mm():
    """Return the base (r, z) profile in millimetres, closed loop.

    The texture / scallop weights carried by `nest_profile` are dropped here:
    a Fusion revolve is axisymmetric and cannot carry them.
    """
    pts = nest_profile.build_profile()
    return [(float(r), float(z)) for (r, z, _tw, _ww) in pts]


def _ensure_user_parameter(params, name, value_mm, comment=""):
    """Create (or update) a Fusion User Parameter holding a millimetre value.

    Returns the UserParameter, or None on failure.
    """
    try:
        existing = params.itemByName(name)
        if existing is not None:
            # The expression is parsed in the document's default units, so
            # the unit has to be spelled out.
            existing.expression = "%g mm" % float(value_mm)
            return existing
        return params.add(name,
                          adsk.core.ValueInput.createByReal(_to_cm(value_mm)),
                          "mm",
                          comment)
    except Exception as exc:
        _log("could not set user parameter '%s': %s" % (name, exc))
        return None


def _build_sketch(app, design, root):
    """Create the closed XZ profile sketch and return it (or None)."""
    pts_mm = _profile_points_mm()

    # The XZ plane: local X -> global X, local Y -> global Z.
    xz = root.xZConstructionPlane
    sketch = root.sketches.add(xz)
    sketch.name = "NestProfile"

    # Create one sketch point per profile vertex, then connect them with
    # lines.  Sharing the points makes the loop topologically closed.
    #
    # The profile is authored in global (r, z) and converted into sketch
    # space, so the code does not depend on the XZ plane's local axis
    # orientation.
    sketch_points = []
    for (r, z) in pts_mm:
        world = adsk.core.Point3D.create(_to_cm(r), 0.0, _to_cm(z))
        local = sketch.modelToSketchSpace(world)
        sp = sketch.sketchPoints.add(local)
        sketch_points.append(sp)

    # The typed curve collections live under `sketchCurves`.
    line_collection = sketch.sketchCurves.sketchLines

    # Build the FULL closed profile loop: every segment, including the
    # last one which lies on the revolve axis ((0, base_thickness) -> (0, 0)).
    # Fusion can handle a profile whose boundary touches the axis along a
    # segment — the axis segment maps to itself when revolved, generating
    # no surface — so the closed region revolves into a valid solid.
    profile_lines = []
    n = len(sketch_points)
    for i in range(n):
        a = sketch_points[i]
        b = sketch_points[(i + 1) % n]
        line = line_collection.addByTwoPoints(a, b)
        if line is None:
            _log_error("failed to create profile segment %d" % i)
            return None
        profile_lines.append(line)

    _log("sketch created with %d points and %d lines" %
         (len(sketch_points), len(profile_lines)))

    # The helper gets its own endpoints so that it does not share a point
    # with the profile.  Sharing points makes Fusion treat the helper as
    # part of the profile loop, which breaks the revolve.
    helpers = []
    z_top = nest_profile.NEST_DEPTH + nest_profile.BASE_THICKNESS
    r_top = nest_profile.OUTER_TOP_DIAMETER / 2.0

    axis_world = adsk.core.Point3D.create(0.0, 0.0, _to_cm(z_top))
    axis_point = sketch.sketchPoints.add(sketch.modelToSketchSpace(axis_world))

    rim_world = adsk.core.Point3D.create(_to_cm(r_top), 0.0, _to_cm(z_top))
    rim_point = sketch.sketchPoints.add(sketch.modelToSketchSpace(rim_world))

    h = line_collection.addByTwoPoints(axis_point, rim_point)
    if h is not None:
        h.isConstruction = True
        helpers.append(h)

    # Return the points paired with their profile coordinates so the
    # dimension code can pick them by geometry instead of by index.
    pairs = [(sketch_points[i], pts_mm[i][0], pts_mm[i][1]) for i in range(n)]
    return sketch, pairs, helpers, profile_lines


def _line_point(line, which):
    """Return a line's start or end point.

    Fusion exposes `startSketchPoint` / `endSketchPoint` as methods in some
    API versions and as properties in others, so both are handled.
    """
    name = "startSketchPoint" if which == "start" else "endSketchPoint"
    attr = getattr(line, name)
    if callable(attr):
        return attr()
    return attr


def _set_expression(dimension, expression):
    """Bind a sketch dimension to a Fusion expression.

    `SketchDimension` is not itself a `Parameter`, so the expression has
    to be applied to the dimension's underlying model parameter.
    """
    try:
        parameter = dimension.parameter
        if parameter is not None:
            parameter.expression = expression
            return True
    except Exception as exc:
        _log("could not set parameter expression '%s': %s" % (expression, exc))

    # Older API versions expose the expression directly on the dimension.
    try:
        dimension.expression = expression
        return True
    except Exception as exc:
        _log("could not set dimension expression '%s': %s" % (expression, exc))
        return False


def _pick(pairs, r_mm, z_mm, tol_mm=1e-3):
    """Return the sketch point whose profile coordinate matches (r, z)."""
    best = None
    best_d = None
    for (sp, pr, pz) in pairs:
        d = ((pr - r_mm) ** 2 + (pz - z_mm) ** 2) ** 0.5
        if best_d is None or d < best_d:
            best_d = d
            best = sp
    if best is None or best_d > tol_mm:
        return None
    return best


def _add_dimensions(app, design, sketch, pairs, helpers):
    """Add driving dimensions driven by Fusion User Parameters."""
    dims = sketch.sketchDimensions

    added = 0

    def horizontal_dim(point_a, point_b, expression, text_offset):
        """Dimension the horizontal distance between two sketch points."""
        ga = point_a.geometry
        gb = point_b.geometry
        text = adsk.core.Point3D.create((ga.x + gb.x) / 2.0 + text_offset,
                                        (ga.y + gb.y) / 2.0 + text_offset)
        d = dims.addDistanceDimension(
            point_a, point_b,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            text)
        if d is not None:
            if _set_expression(d, expression):
                return 1
            return 0
        return 0

    # --- Rim radius (half of the outer diameter) ----------------------------
    # Measured on the construction reference line at rim height, so the
    # dimension is a true horizontal distance.
    if helpers:
        helper = helpers[0]
        p_axis = _line_point(helper, "start")
        p_rim = _line_point(helper, "end")
        added += horizontal_dim(p_axis, p_rim, "rim_diameter / 2", 1.0)
        axis_top_pt = p_axis
    else:
        axis_top_pt = None

    # --- Flat base radius ----------------------------------------------------
    base_pt = _pick(pairs, nest_profile.BASE_RADIUS, 0.0)
    axis_bot_pt = _pick(pairs, 0.0, 0.0)
    if base_pt is not None and axis_bot_pt is not None:
        added += horizontal_dim(axis_bot_pt, base_pt, "base_radius", -1.0)

    # --- Base thickness (vertical, underside -> cavity floor) ---------------
    floor_pt = _pick(pairs, 0.0, nest_profile.BASE_THICKNESS)
    if floor_pt is not None and axis_bot_pt is not None:
        ga = axis_bot_pt.geometry
        gb = floor_pt.geometry
        text = adsk.core.Point3D.create(ga.x - 1.5, (ga.y + gb.y) / 2.0)
        d = dims.addDistanceDimension(
            axis_bot_pt, floor_pt,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            text)
        if d is not None:
            if _set_expression(d, "base_thickness"):
                added += 1

    # --- Cavity depth (cavity floor -> rim) ---------------------------------
    if floor_pt is not None and axis_top_pt is not None:
        ga = floor_pt.geometry
        gb = axis_top_pt.geometry
        text = adsk.core.Point3D.create(ga.x - 2.5, (ga.y + gb.y) / 2.0)
        d = dims.addDistanceDimension(
            floor_pt, axis_top_pt,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            text)
        if d is not None:
            if _set_expression(d, "cavity_depth"):
                added += 1

    _log("added %d driving dimensions" % added)
    return added


def _add_revolve_axis(root):
    """Return the model's Z construction axis (the revolve axis)."""
    try:
        axis = root.zConstructionAxis
        if axis is None:
            _log_error("no Z construction axis available")
            return None
        return axis
    except Exception as exc:
        _log_error("could not get the Z construction axis: %s" % exc)
        return None


def _revolve(design, root, sketch, axis, profile_lines):
    """Revolve the profile 360 degrees about the axis; return the feature."""
    try:
        if not profile_lines:
            _log_error("no profile lines found for the revolve")
            return None

        # Fusion's Revolve needs an explicit Profile object.  The sketch
        # contains a closed region bounded by the open chain plus the
        # axis segment; sketch.profiles auto-detects it.
        profiles = sketch.profiles
        if profiles.count == 0:
            _log_error("no closed profile detected in the sketch")
            return None

        collection = adsk.core.ObjectCollection.create()
        collection.add(profiles.item(0))

        input_ = root.features.revolveFeatures.createInput(
            collection, axis, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        # A full 360 degree revolve gives a closed, watertight solid.
        input_.setAngleExtent(False,
                              adsk.core.ValueInput.createByString("360 deg"))
        feature = root.features.revolveFeatures.add(input_)
        _log("revolve created: %s" % feature.name)
        return feature
    except Exception as exc:
        _log_error("revolve failed: %s" % exc)
        return None


def _export(app, design, out_dir):
    """Export the design to STL and STEP.  Returns (stl_path, step_path)."""
    stl_path = os.path.join(out_dir, STL_NAME)
    step_path = os.path.join(out_dir, STEP_NAME)

    manager = design.exportManager

    try:
        opts = manager.createSTLExportOptions(design.rootComponent, stl_path)
        if opts is not None:
            opts.isBinaryFormat = True
            opts.unitType = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
            opts.surfaceDeviation = 0.02
            opts.normalDeviation = 5.0
            manager.execute(opts)
            _log("exported STL: %s" % stl_path)
        else:
            _log_error("could not create STL export options")
    except Exception as exc:
        _log_error("STL export failed: %s" % exc)

    try:
        opts = manager.createSTEPExportOptions(step_path, design.rootComponent)
        if opts is not None:
            manager.execute(opts)
            _log("exported STEP: %s" % step_path)
        else:
            _log_error("could not create STEP export options")
    except Exception as exc:
        _log_error("STEP export failed: %s" % exc)

    return stl_path, step_path


def _output_dir():
    """Return the directory the exports are written to."""
    if EXPORT_DIR:
        return EXPORT_DIR
    return os.path.join(os.path.expanduser("~"), "3dprints_exports")


def _create_parameters(design):
    """Create the User Parameters that drive the model."""
    params = design.userParameters
    _ensure_user_parameter(params, "rim_diameter", nest_profile.OUTER_TOP_DIAMETER,
                           "Outer diameter at the rim")
    _ensure_user_parameter(params, "inner_diameter", nest_profile.INNER_TOP_DIAMETER,
                           "Inner diameter at the rim")
    _ensure_user_parameter(params, "cavity_depth", nest_profile.NEST_DEPTH,
                           "Cavity depth from the floor")
    _ensure_user_parameter(params, "base_thickness", nest_profile.BASE_THICKNESS,
                           "Thickness of the solid base")
    _ensure_user_parameter(params, "base_radius", nest_profile.BASE_RADIUS,
                           "Radius of the flat underside")
    _ensure_user_parameter(params, "floor_radius", nest_profile.FLOOR_RADIUS,
                           "Radius of the flat cavity floor")
    return params


def build_nest():
    """Create the design, build the nest, and export it.

    Returns the created document, or None if something failed.
    """
    app = adsk.core.Application.get()
    if app is None:
        _log_error("could not get the Fusion application")
        return None

    try:
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    except Exception as exc:
        _log_error("could not create a new design: %s" % exc)
        return None
    _log("created document '%s'" % doc.name)

    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        _log_error("no active Fusion design")
        return None

    root = design.rootComponent
    # The root component's name is fixed by Fusion, so the design gets its
    # name instead.
    try:
        doc.name = DESIGN_NAME
    except Exception as exc:
        _log("could not rename the document: %s" % exc)

    params = _create_parameters(design)

    sketch, pairs, helpers, profile_lines = _build_sketch(app, design, root)
    if sketch is None:
        return None

    axis = _add_revolve_axis(root)
    if axis is None:
        return None

    _add_dimensions(app, design, sketch, pairs, helpers)

    feature = _revolve(design, root, sketch, axis, profile_lines)
    if feature is None:
        return None

    # Name the resulting body.
    try:
        for body in root.bRepBodies:
            body.name = BODY_NAME
    except Exception as exc:
        _log("could not rename body: %s" % exc)

    # Report the model volume so it can be sanity-checked in the log.
    try:
        body = root.bRepBodies.item(0)
        volume_cm3 = body.volume
        _log("model volume: %.2f cm3 (%.1f mm3)" % (volume_cm3, volume_cm3 * 1000.0))
    except Exception as exc:
        _log("could not read the model volume: %s" % exc)

    out_dir = _output_dir()
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    _export(app, design, out_dir)

    return doc


# ---------------------------------------------------------------------------
# Script entry point
#
# The same module works both as an add-in (run/stop are called by Fusion)
# and as a plain script (run() is called with no arguments), so the nest
# can be rebuilt from the Scripts menu without restarting Fusion.
# ---------------------------------------------------------------------------
def run(context=None):
    """Build the nest.  Used both as an add-in and as a script."""
    try:
        _log("[NestAddIn] starting")
        build_nest()
        _log("[NestAddIn] finished")
    except Exception:
        _log_error("unhandled exception:\n" + traceback.format_exc())


def stop(context=None):
    """Called when the add-in is unloaded."""
    _log("[NestAddIn] stopped")


# __CHUNK_MARKER__

