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



def build_points_and_spline(part, hsf, hb, points, name_prefix):
    # Points folder
    hb_points = hb.hybrid_bodies.add()
    hb_points.name = "点"

    point_objs = []
    for x, z in points:
        pt = hsf.add_new_point_coord(x, 0.0, z)
        hb_points.append_hybrid_shape(pt)
        point_objs.append(pt)

    spline = hsf.add_new_spline()
    spline.set_spline_type(0)
    spline.set_closing(0)
    for pt in point_objs:
        ref = part.create_reference_from_object(pt)
        spline.add_point(ref)
    spline.name = "Spline.1"
    hb.append_hybrid_shape(spline)

    return spline



def align_spline_and_create_plane(part, hsf, hb, spline, origin_point, translate_name, plane_name):

    # Extremum along +X (min/max depends on CATIA, use direction +X)
    direction_x = hsf.add_new_direction_by_coord(1.0, 0.0, 0.0)
    extremum = hsf.add_new_extremum(
        part.create_reference_from_object(spline), direction_x, 0
    )
    hb.append_hybrid_shape(extremum)

    # Translate spline so extremum -> origin (create new translated spline)
    spline_translate = hsf.add_new_empty_translate()
    spline_translate.elem_to_translate = part.create_reference_from_object(spline)
    spline_translate.vector_type = 1
    spline_translate.first_point = part.create_reference_from_object(extremum)
    spline_translate.second_point = part.create_reference_from_object(origin_point)
    spline_translate.name = translate_name
    hb.append_hybrid_shape(spline_translate)

    # Plane offset 99mm from YZ, referenced to the curve origin
    offset_pt = hsf.add_new_point_coord_with_reference(
        99.0, 0.0, 0.0, part.create_reference_from_object(origin_point)
    )
    hb.append_hybrid_shape(offset_pt)
    plane = hsf.add_new_plane_offset_pt(
        part.create_reference_from_object(part.origin_elements.plane_yz),
        part.create_reference_from_object(offset_pt),
    )
    plane.name = plane_name
    hb.append_hybrid_shape(plane)

    part.in_work_object = spline_translate


def apply_macro_splits(part, hsf, hb_airfoil):
    hb_528 = hb_airfoil.hybrid_bodies.item("NAVA64-528")
    hb_118 = hb_airfoil.hybrid_bodies.item("NAVA64-118")
    hb_208 = hb_airfoil.hybrid_bodies.item("NAVA64-208")

    # Create a new set under NAVA64-528 to store split results
    hb_post = hb_528.hybrid_bodies.add()
    hb_post.name = "后处理"

    # Add three offset planes (as in macro)
    yz_ref = part.create_reference_from_object(part.origin_elements.plane_yz)
    plane1 = hsf.add_new_plane_offset(yz_ref, 99.0, False)
    plane2 = hsf.add_new_plane_offset(yz_ref, 99.0, False)
    plane3 = hsf.add_new_plane_offset(yz_ref, 99.0, False)
    hb_post.append_hybrid_shape(plane1)
    hb_post.append_hybrid_shape(plane2)
    hb_post.append_hybrid_shape(plane3)

    # Split NAVA64-208 using Translate.3 and Plane.3
    translate_208 = hb_208.hybrid_shapes.item("Translate.3")
    plane_208 = hb_208.hybrid_shapes.item("Plane.3")
    split1 = hsf.add_new_hybrid_split(
        part.create_reference_from_object(translate_208),
        part.create_reference_from_object(plane_208),
        1,
    )
    split1.name = "NACA64-208就绪"
    hb_post.append_hybrid_shape(split1)
    try:
        hsf.gsm_visibility(part.create_reference_from_object(translate_208), 0)
    except Exception:
        pass

    # Split NAVA64-118 using Translate.2 and Plane.2
    translate_118 = hb_118.hybrid_shapes.item("Translate.2")
    plane_118 = hb_118.hybrid_shapes.item("Plane.2")
    split2 = hsf.add_new_hybrid_split(
        part.create_reference_from_object(translate_118),
        part.create_reference_from_object(plane_118),
        1,
    )
    split2.name = "NACA64-118就绪"
    hb_post.append_hybrid_shape(split2)
    try:
        hsf.gsm_visibility(part.create_reference_from_object(translate_118), 0)
    except Exception:
        pass

    # Split NAVA64-528 using Translate.1 and Plane.1
    translate_528 = hb_528.hybrid_shapes.item("Translate.1")
    plane_528 = hb_528.hybrid_shapes.item("Plane.1")
    split3 = hsf.add_new_hybrid_split(
        part.create_reference_from_object(translate_528),
        part.create_reference_from_object(plane_528),
        1,
    )
    split3.name = "NACA64-528就绪"
    hb_post.append_hybrid_shape(split3)
    try:
        hsf.gsm_visibility(part.create_reference_from_object(translate_528), 0)
    except Exception:
        pass


def set_visibility(part_document, obj, show):
    selection = part_document.selection
    selection.clear()
    selection.add(obj)
    vis_props = selection.vis_properties
    vis_props = vis_props.parent
    vis_props.set_show(1 if show else 0)
    selection.clear()



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

    # Build structure: 桨叶GS / 翼型 / NAVA64-118, NAVA64-208, NAVA64-528
    hb_root = part.hybrid_bodies.add()
    hb_root.name = "桨叶GS"

    hb_airfoil = hb_root.hybrid_bodies.add()
    hb_airfoil.name = "翼型"

    hb_ref = hb_root.hybrid_bodies.add()
    hb_ref.name = "参考"
    origin = hsf.add_new_point_coord(0.0, 0.0, 0.0)
    hb_ref.append_hybrid_shape(origin)

    name_to_mark = {
        "NAVA64-528": ("Translate.1", "Plane.1"),
        "NAVA64-118": ("Translate.2", "Plane.2"),
        "NAVA64-208": ("Translate.3", "Plane.3"),
    }
    for name in ("NAVA64-528", "NAVA64-118", "NAVA64-208"):
        hb_section = hb_airfoil.hybrid_bodies.add()
        hb_section.name = name

        dat_path = DAT_FILES[name]
        points = read_dat_points(dat_path)
        spline = build_points_and_spline(part, hsf, hb_section, points, name)
        translate_name, plane_name = name_to_mark[name]
        align_spline_and_create_plane(
            part, hsf, hb_section, spline, origin, translate_name, plane_name
        )

    apply_macro_splits(part, hsf, hb_airfoil)

    # Match macro visibility intent for Translate objects (final state: shown)
    try:
        hb_528 = hb_airfoil.hybrid_bodies.item("NAVA64-528")
        hb_118 = hb_airfoil.hybrid_bodies.item("NAVA64-118")
        hb_208 = hb_airfoil.hybrid_bodies.item("NAVA64-208")
        t1 = hb_528.hybrid_shapes.item("Translate.1")
        t2 = hb_118.hybrid_shapes.item("Translate.2")
        t3 = hb_208.hybrid_shapes.item("Translate.3")
        set_visibility(doc, t1, True)
        set_visibility(doc, t2, True)
        set_visibility(doc, t3, True)
    except Exception:
        pass

    part.update()
    print("done")


if __name__ == "__main__":
    main()
