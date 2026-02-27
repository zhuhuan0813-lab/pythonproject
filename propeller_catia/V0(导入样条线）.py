from pathlib import Path
from pycatia import catia


DAT_FILES = {
    "NAVA64-118": r"D:\PythonProject\propeller_catia\数据\NACA64-118_300.dat",
    "NAVA64-208": r"D:\PythonProject\propeller_catia\数据\NACA64-208_300.dat",
    "NAVA64-528": r"D:\PythonProject\propeller_catia\数据\NACA64-528_300.dat",
}

# Parameters
ROTOR_DIAMETER_MM = 7620.0
ROOT_CHORD_MM = 431.8
MID_CHORD_MM = 368.3
TIP_CHORD_MM = 304.8
PRE_CONE_ANGLE_DEG = 1.5
ROOT_TWIST_DEG = 40.25
MID_TWIST_DEG = 18.25
TIP_TWIST_DEG = -3.75
MID_SPAN_RATIO = 0.5
TIP_SPAN_RATIO = 0.9


def read_dat_points(path):
    points = []
    for enc in ("utf-8", "gbk", "gb2312", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                lines = f.readlines()
            break
        except UnicodeDecodeError:
            continue
    else:
        raise RuntimeError(f"cannot read dat: {path}")

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("NACA"):
            continue
        cols = line.split()
        if len(cols) >= 2:
            try:
                x = float(cols[0])
                z = float(cols[1]) if len(cols) == 2 else float(cols[2])
            except ValueError:
                continue
            points.append((x, z))

    if not points:
        raise RuntimeError(f"no points in dat: {path}")
    return points


def get_or_create_length_param(parameters, name, value):
    try:
        param = parameters.item(name)
    except Exception:
        param = parameters.create_dimension("", "LENGTH", 0.0)
        param.rename(name)
    param.value = value
    return param


def get_or_create_angle_param(parameters, name, value_deg):
    try:
        param = parameters.item(name)
    except Exception:
        param = parameters.create_dimension("", "ANGLE", 0.0)
        param.rename(name)
    param.value = value_deg
    return param


def build_spline_at_origin(part, hsf, hb, points, chord_mm, name_prefix):
    # Move the point with min x to origin (do not reorder point sequence)
    min_x, min_z = min(points, key=lambda p: p[0])
    max_x = max(p[0] for p in points)
    chord_len = max_x - min_x
    shifted = [(x - min_x, z - min_z) for x, z in points]

    # Create a sub set for points
    hb_points = hb.hybrid_bodies.add()
    hb_points.name = "点"

    # Create points at y=0 with chord scaling, leading edge at origin
    point_objs = []
    for x, z in shifted:
        pt = hsf.add_new_point_coord(x * chord_mm, 0.0, z * chord_mm)
        hb_points.append_hybrid_shape(pt)
        point_objs.append(pt)

    spline = hsf.add_new_spline()
    spline.set_spline_type(0)
    spline.set_closing(0)
    for pt in point_objs:
        ref = part.create_reference_from_object(pt)
        spline.add_point(ref)
    hb.append_hybrid_shape(spline)

    part.in_work_object = spline
    return spline


def main():
    caa = catia()
    docs = caa.documents
    if docs.count == 0:
        doc = docs.add("Part")
    else:
        doc = caa.active_document

    part = doc.part
    hsf = part.hybrid_shape_factory
    parameters = part.parameters

    # Parameters (Chinese names)
    get_or_create_length_param(parameters, "旋翼直径", ROTOR_DIAMETER_MM)
    get_or_create_length_param(parameters, "翼根弦长", ROOT_CHORD_MM)
    get_or_create_length_param(parameters, "翼中弦长", MID_CHORD_MM)
    get_or_create_length_param(parameters, "翼尖弦长", TIP_CHORD_MM)
    get_or_create_angle_param(parameters, "桨毂前锥角", PRE_CONE_ANGLE_DEG)
    get_or_create_angle_param(parameters, "翼根扭转角", ROOT_TWIST_DEG)
    get_or_create_angle_param(parameters, "翼中扭转角", MID_TWIST_DEG)
    get_or_create_angle_param(parameters, "翼尖扭转角", TIP_TWIST_DEG)
    get_or_create_length_param(parameters, "翼中所在位置比例", MID_SPAN_RATIO)
    get_or_create_length_param(parameters, "翼尖所在位置比例", TIP_SPAN_RATIO)

    # Build structure: 桨叶GS / 翼型 / NAVA64-118, NAVA64-208, NAVA64-528
    hb_root = part.hybrid_bodies.add()
    hb_root.name = "桨叶GS"

    hb_airfoil = hb_root.hybrid_bodies.add()
    hb_airfoil.name = "翼型"

    section_map = {
        "NAVA64-528": ROOT_CHORD_MM,
        "NAVA64-118": MID_CHORD_MM,
        "NAVA64-208": TIP_CHORD_MM,
    }

    for name, chord in section_map.items():
        hb_section = hb_airfoil.hybrid_bodies.add()
        hb_section.name = name

        dat_path = DAT_FILES[name]
        points = read_dat_points(dat_path)
        build_spline_at_origin(part, hsf, hb_section, points, chord, name)

    part.update()
    print("done")


if __name__ == "__main__":
    main()
