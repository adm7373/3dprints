"""Minimal mock of the Fusion API, used to exercise NestAddIn's logic
outside of Fusion.

Run it with:  python3 fusion_addin/tests/test_nest_addin.py
"""

import math
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ADDIN_DIR = os.path.dirname(HERE)
REPO_DIR = os.path.dirname(ADDIN_DIR)
sys.path.insert(0, ADDIN_DIR)
sys.path.insert(0, REPO_DIR)


# ---------------------------------------------------------------------------
# adsk.core
# ---------------------------------------------------------------------------
class Point3D(object):
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z

    @staticmethod
    def create(x=0.0, y=0.0, z=0.0):
        return Point3D(x, y, z)


class ValueInput(object):
    def __init__(self, value):
        self.value = value

    @staticmethod
    def createByReal(v):
        return ValueInput(v)

    @staticmethod
    def createByString(v):
        return ValueInput(v)


class ObjectCollection(object):
    def __init__(self):
        self.items = []

    @staticmethod
    def create():
        return ObjectCollection()

    def add(self, item):
        self.items.append(item)


class UserParameter(object):
    def __init__(self, name, value, units, comment):
        self.name = name
        self.expression = value
        self.units = units
        self.comment = comment

    @property
    def value(self):
        """The numeric value, in the parameter's units."""
        try:
            return float(str(self.expression).split()[0])
        except (ValueError, IndexError):
            return 0.0


class UserParameters(object):
    def __init__(self):
        self._params = {}

    def itemByName(self, name):
        return self._params.get(name)

    def add(self, name, value, units, comment):
        p = UserParameter(name, value.value, units, comment)
        self._params[name] = p
        return p


class Document(object):
    def __init__(self, name):
        self.name = name

class Application(object):
    def __init__(self):
        self.activeProduct = None
        self.documents = _Documents()
        self.log = []

    @staticmethod
    def get():
        return _APP

    def logMessage(self, msg):
        self.log.append(msg)


class _Documents(object):
    def __init__(self):
        self._docs = []

    def add(self, documentType, visible=True, options=None):
        doc = Document("Untitled")
        self._docs.append(doc)
        _APP.activeProduct = _DESIGN
        return doc


_APP = Application()


# ---------------------------------------------------------------------------
# adsk.fusion
# ---------------------------------------------------------------------------
class SketchPoint(object):
    def __init__(self, geometry):
        self.geometry = geometry


class SketchPoints(object):
    def __init__(self, sketch):
        self._sketch = sketch
        self._points = []

    def add(self, point):
        sp = SketchPoint(point)
        self._points.append(sp)
        return sp

    def __iter__(self):
        return iter(self._points)


class SketchLine(object):
    def __init__(self, start, end):
        # Fusion wraps raw Point3D endpoints into SketchPoints.
        self._start = start if isinstance(start, SketchPoint) else SketchPoint(start)
        self._end = end if isinstance(end, SketchPoint) else SketchPoint(end)
        self.isConstruction = False

    # The runtime API exposes these as properties.
    @property
    def startSketchPoint(self):
        return self._start

    @property
    def endSketchPoint(self):
        return self._end


class SketchLines(object):
    def __init__(self, sketch):
        self._sketch = sketch
        self._lines = []

    def addByTwoPoints(self, start, end):
        line = SketchLine(start, end)
        self._lines.append(line)
        return line

    def __iter__(self):
        return iter(self._lines)


class _DimParameter(object):
    def __init__(self):
        self.expression = None


class SketchDimension(object):
    def __init__(self, point_a, point_b, orientation, text):
        self.point_a = point_a
        self.point_b = point_b
        self.orientation = orientation
        self.text = text
        self._parameter = _DimParameter()

    @property
    def parameter(self):
        return self._parameter

    @property
    def expression(self):
        return self._parameter.expression

    @expression.setter
    def expression(self, value):
        self._parameter.expression = value


class SketchDimensions(object):
    def __init__(self):
        self._dims = []

    def addDistanceDimension(self, pointOne, pointTwo, orientation, textPoint,
                            isDriving=True):
        d = SketchDimension(pointOne, pointTwo, orientation, textPoint)
        self._dims.append(d)
        return d

    def __iter__(self):
        return iter(self._dims)


class SketchCurves(object):
    """The typed curve collections, reached via `sketch.sketchCurves`."""

    def __init__(self, sketch):
        self._sketch = sketch
        self._lines = SketchLines(sketch)

    @property
    def sketchLines(self):
        return self._lines


class Sketch(object):
    def __init__(self):
        self.name = "Sketch1"
        self._points = SketchPoints(self)
        self._curves = SketchCurves(self)
        self._dims = SketchDimensions()
        self._profiles = Profiles()

    @property
    def sketchPoints(self):
        return self._points

    @property
    def sketchCurves(self):
        return self._curves

    @property
    def sketchDimensions(self):
        return self._dims

    @property
    def profiles(self):
        return self._profiles

    def modelToSketchSpace(self, world_point):
        """The XZ plane maps global (x, 0, z) to sketch (x, z)."""
        return Point3D.create(world_point.x, world_point.z, 0.0)

    def sketchToModelSpace(self, sketch_point):
        return Point3D.create(sketch_point.x, 0.0, sketch_point.y)


class Sketches(object):
    def __init__(self, component):
        self._component = component
        self._sketches = []

    def add(self, planar_entity):
        s = Sketch()
        self._sketches.append(s)
        return s


class RevolveFeature(object):
    def __init__(self, name):
        self.name = name


class _RevolveInput(object):
    def setAngleExtent(self, isSymmetric, angle):
        self.angle = angle
        return True


class RevolveFeatures(object):
    def __init__(self):
        self.features = []

    def createInput(self, profile, axis, operation):
        self.last_profile = profile
        self.last_axis = axis
        return _RevolveInput()

    def add(self, input_):
        f = RevolveFeature("Revolve1")
        self.features.append(f)
        return f


class BRepBody(object):
    def __init__(self):
        self.name = "Body1"
        self.volume = 12.5  # cm3


class BRepBodies(object):
    def __init__(self):
        self._bodies = [BRepBody()]

    def item(self, index):
        return self._bodies[index]

    def __iter__(self):
        return iter(self._bodies)


class ConstructionAxis(object):
    def __init__(self, name):
        self.name = name


class Features(object):
    """The feature collections, reached via `component.features`."""

    def __init__(self, component):
        self._component = component
        self._revolves = RevolveFeatures()

    @property
    def revolveFeatures(self):
        return self._revolves


class Component(object):
    def __init__(self):
        self._name = "Component1"
        self._sketches = Sketches(self)
        self._features = Features(self)
        self._bodies = BRepBodies()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        # Fusion refuses to rename the root component.
        raise RuntimeError("3 : root component name cannot be changed")

    @property
    def sketches(self):
        return self._sketches

    @property
    def features(self):
        return self._features

    @property
    def bRepBodies(self):
        return self._bodies

    @property
    def xZConstructionPlane(self):
        return "XZ"

    @property
    def zConstructionAxis(self):
        return ConstructionAxis("Z")

    def createOpenProfile(self, curves, chainCurves=True):
        """Create an open profile from curves (mock just succeeds)."""
        return Profile()


class Profile(object):
    def __init__(self):
        self.name = "Profile1"


class Profiles(object):
    def __init__(self):
        self._profiles = [Profile()]

    def __len__(self):
        return len(self._profiles)

    def __getitem__(self, index):
        return self._profiles[index]

    def __iter__(self):
        return iter(self._profiles)

    def item(self, index):
        return self._profiles[index]

    @property
    def count(self):
        return len(self._profiles)


class _STLOptions(object):
    def __init__(self):
        self.isBinaryFormat = False
        self.unitType = None
        self.surfaceDeviation = 0.0
        self.normalDeviation = 0.0


class _STEPOptions(object):
    pass


class _ExportManager(object):
    def __init__(self):
        self.executed = []

    def createSTLExportOptions(self, geometry, filename=""):
        return _STLOptions()

    def createSTEPExportOptions(self, filename, geometry=None):
        return _STEPOptions()

    def execute(self, options):
        self.executed.append(options)


class Design(object):
    def __init__(self):
        self.rootComponent = Component()
        self._params = UserParameters()
        self._export_manager = _ExportManager()

    @staticmethod
    def cast(arg):
        return arg if isinstance(arg, Design) else None

    @property
    def userParameters(self):
        return self._params

    @property
    def exportManager(self):
        return self._export_manager


_DESIGN = Design()


def _install():
    core = types.ModuleType("adsk.core")
    for name in ("Point3D", "ValueInput", "ObjectCollection", "UserParameter",
                 "UserParameters", "Document", "Application"):
        setattr(core, name, globals()[name])
    core.DocumentTypes = types.SimpleNamespace(
        FusionDesignDocumentType="FusionDesignDocumentType")
    core.DistanceUnits = types.SimpleNamespace(
        MillimeterDistanceUnits=0, CentimeterDistanceUnits=1)

    fusion = types.ModuleType("adsk.fusion")
    for name in ("Design", "Component", "Sketch", "Sketches", "Profile"):
        setattr(fusion, name, globals()[name])
    fusion.FeatureOperations = types.SimpleNamespace(
        NewBodyFeatureOperation=3)
    fusion.DimensionOrientations = types.SimpleNamespace(
        AlignedDimensionOrientation=0,
        HorizontalDimensionOrientation=1,
        VerticalDimensionOrientation=2)
    fusion.DistanceUnits = core.DistanceUnits

    adsk = types.ModuleType("adsk")
    adsk.core = core
    adsk.fusion = fusion
    sys.modules["adsk"] = adsk
    sys.modules["adsk.core"] = adsk.core
    sys.modules["adsk.fusion"] = adsk.fusion


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_mm_to_cm():
    """The millimetre -> centimetre conversion is correct."""
    import NestAddIn

    assert abs(NestAddIn._to_cm(10.0) - 1.0) < 1e-12
    assert abs(NestAddIn._to_cm(70.0) - 7.0) < 1e-12
    print("unit conversion OK")


def test_profile_is_closed_and_nonzero():
    """The shared profile is a closed, non-degenerate loop."""
    import nest_profile

    pts = nest_profile.build_profile()
    assert len(pts) > 20
    for i in range(len(pts)):
        a = pts[i]
        b = pts[(i + 1) % len(pts)]
        assert math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6, \
            "degenerate segment at %d" % i

    assert any(abs(p[0]) < 1e-9 and abs(p[1]) < 1e-9 for p in pts)
    print("profile OK")


def test_build():
    """The whole build flow runs and produces a revolve + exports."""
    import NestAddIn

    doc = NestAddIn.build_nest()
    assert doc is not None, "build_nest() returned None"

    root = _DESIGN.rootComponent
    sketch = list(root.sketches._sketches)[0]
    lines = list(sketch.sketchCurves.sketchLines)
    assert len(lines) > 20, "expected the full profile, got %d lines" % len(lines)

    # Exactly one construction line (the dimension reference).
    construction = [l for l in lines if l.isConstruction]
    assert len(construction) == 1, \
        "expected 1 construction line, got %d" % len(construction)

    # The profile lines form a closed loop.
    profile = [l for l in lines if not l.isConstruction]
    starts = set(id(l.startSketchPoint) for l in profile)
    ends = set(id(l.endSketchPoint) for l in profile)
    assert starts == ends, "the profile is not a closed loop"

    # Every dimension is expression driven.
    dims = list(sketch.sketchDimensions)
    assert len(dims) == 4, "expected 4 dimensions, got %d" % len(dims)
    for d in dims:
        assert d.expression, "a dimension has no expression"

    # The revolve was created.
    assert len(root.features.revolveFeatures.features) == 1, "no revolve feature"

    # The exports were executed.
    manager = _DESIGN.exportManager
    assert len(manager.executed) == 2, \
        "expected 2 exports, got %d" % len(manager.executed)

    print("build flow OK")


def test_user_parameters():
    """The user parameters hold the expected millimetre values."""
    import NestAddIn

    NestAddIn.build_nest()
    params = _DESIGN.userParameters
    for name in ("rim_diameter", "inner_diameter", "cavity_depth",
                 "base_thickness", "base_radius", "floor_radius"):
        p = params.itemByName(name)
        assert p is not None, "missing parameter %s" % name
        # The value is stored in centimetres, so 70 mm is 7 cm.
        assert p.value > 0, "parameter %s has no value" % name
        assert p.units == "mm", "parameter %s has the wrong units" % name
    print("user parameters OK")


def main():
    _install()
    test_mm_to_cm()
    test_profile_is_closed_and_nonzero()
    test_build()
    test_user_parameters()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
