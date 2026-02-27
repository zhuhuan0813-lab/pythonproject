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
        param.value = value
    except Exception:
        param = parameters.create_dimension("", "LENGTH", value)
        param.rename(name)
    return param


def get_or_create_angle_param(parameters, name, value_deg):
    try:
        param = parameters.item(name)
        param.value = value_deg
    except Exception:
        param = parameters.create_dimension("", "ANGLE", value_deg)
        param.rename(name)
    return param


def get_or_create_real_param(parameters, name, value):
    """Create or get a real (dimensionless) parameter"""
    try:
        param = parameters.item(name)
        param.value = value
    except Exception:
        param = parameters.create_real("", value)
        param.rename(name)
    return param


def build_points_and_spline(part, hsf, hb, points):
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
    # Extremum along +X
    direction_x = hsf.add_new_direction_by_coord(1.0, 0.0, 0.0)
    extremum = hsf.add_new_extremum(
        part.create_reference_from_object(spline), direction_x, 0
    )
    hb.append_hybrid_shape(extremum)

    # Translate spline so extremum -> origin
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

    return hb_post


def create_or_replace_formula(relations, name, comment, output_param, body):
    """Create or replace a formula"""
    try:
        # Try to remove existing formula
        try:
            relations.remove(name)
        except:
            pass

        # Create new formula
        formula = relations.create_formula(name, comment, output_param, body)
        return formula
    except Exception as e:
        print(f"Error creating formula {name}: {e}")
        raise


def create_sketches(part, hb_root):
    """Create sketches as in the VBScript macro"""
    try:
        # Get the XY plane for sketching
        xy_plane = part.origin_elements.plane_xy

        # Create Sketch.1 with a circle of radius 3810mm (half of rotor diameter)
        sketches = hb_root.hybrid_sketches
        sketch1 = sketches.add(xy_plane)
        sketch1.name = "Sketch.1"

        # Open sketch for editing
        factory_2d = sketch1.open_edition()

        # Create a circle at origin with radius = ROTOR_DIAMETER_MM / 2
        circle = factory_2d.create_closed_circle(0.0, 0.0, ROTOR_DIAMETER_MM / 2.0)

        # Get the origin point and set it as circle center
        geom_elements = sketch1.geometric_elements
        axis_2d = geom_elements.item("AbsoluteAxis")
        origin_pt = axis_2d.get_item("Origin")
        circle.center_point = origin_pt
        circle.report_name = 3

        # Add radius constraint
        constraints = sketch1.constraints
        circle_ref = part.create_reference_from_object(circle)
        constraint = constraints.add_mono_elt_cst(0, circle_ref)  # catCstTypeRadius = 0
        constraint.mode = 0  # catCstModeDrivingDimension = 0

        sketch1.close_edition()
        part.in_work_object = hb_root
        part.update()

        # Create Sketch.2 (empty sketch for reference)
        sketch2 = sketches.add(xy_plane)
        sketch2.name = "Sketch.2"
        factory_2d_2 = sketch2.open_edition()
        sketch2.close_edition()
        part.in_work_object = hb_root
        part.update()

        print("Sketches created successfully")

    except Exception as e:
        print(f"Warning: Could not create sketches: {e}")


def postprocess_scale_translate_rotate(part, hsf, relations, parameters, hb_post, hb_root, origin_point):
    """Complete transformation with full parameterization"""

    # Radial axis line (origin -> half diameter as end length)
    direction_y = hsf.add_new_direction_by_coord(0.0, 1.0, 0.0)
    axis_line = hsf.add_new_line_pt_dir(
        part.create_reference_from_object(origin_point),
        direction_y,
        0.0,
        ROTOR_DIAMETER_MM / 2.0,
        False,
    )
    hb_root.append_hybrid_shape(axis_line)
    part.update()

    # Link axis line length to parameter
    try:
        create_or_replace_formula(
            relations,
            "Formula.1",
            "",
            axis_line.length,
            "`旋翼直径`/2mm"
        )
        print("✓ Axis line linked to 旋翼直径")
    except Exception as e:
        print(f"✗ Failed to link axis line: {e}")

    # Mid point along the radial axis
    mid_point = hsf.add_new_point_on_curve_from_percent(
        part.create_reference_from_object(axis_line),
        MID_SPAN_RATIO,
        False,
    )
    hb_root.append_hybrid_shape(mid_point)
    part.update()

    # Link mid point ratio to parameter
    try:
        create_or_replace_formula(
            relations,
            "Formula.2",
            "",
            mid_point.ratio,
            "`翼中所在位置比例`"
        )
        print("✓ Mid point ratio linked to 翼中所在位置比例")
    except Exception as e:
        print(f"✗ Failed to link mid point ratio: {e}")

    # Tip point at end of axis
    tip_point = hsf.add_new_point_on_curve_from_percent(
        part.create_reference_from_object(axis_line),
        1.0,
        False,
    )
    hb_root.append_hybrid_shape(tip_point)
    part.update()

    # === ROOT SECTION (528) ===
    root_curve = hb_post.hybrid_shapes.item("NACA64-528就绪")

    # Scale
    scale_528 = hsf.add_new_hybrid_scaling(
        part.create_reference_from_object(root_curve),
        part.create_reference_from_object(origin_point),
        ROOT_CHORD_MM / 99.0,
    )
    scale_528.volume_result = False
    hb_root.append_hybrid_shape(scale_528)
    part.update()

    # Link scale to parameter
    try:
        create_or_replace_formula(
            relations,
            "Formula.3",
            "",
            scale_528.ratio,
            "`翼根弦长`/99mm"
        )
        print("✓ Root scale linked to 翼根弦长")
    except Exception as e:
        print(f"✗ Failed to link root scale: {e}")

    # Rotate
    rotate_528 = hsf.add_new_empty_rotate()
    rotate_528.elem_to_rotate = part.create_reference_from_object(scale_528)
    rotate_528.axis = part.create_reference_from_object(axis_line)
    rotate_528.volume_result = False
    rotate_528.rotation_type = 0
    rotate_528.angle_value = ROOT_TWIST_DEG
    hb_root.append_hybrid_shape(rotate_528)
    part.update()

    # Link rotation angle to parameter
    try:
        create_or_replace_formula(
            relations,
            "Formula.4",
            "",
            rotate_528.angle,
            "`翼根扭转角`"
        )
        print("✓ Root twist linked to 翼根扭转角")
    except Exception as e:
        print(f"✗ Failed to link root twist: {e}")

    # === MID SECTION (118) ===
    mid_curve = hb_post.hybrid_shapes.item("NACA64-118就绪")

    # Translate
    translate_118 = hsf.add_new_empty_translate()
    translate_118.elem_to_translate = part.create_reference_from_object(mid_curve)
    translate_118.vector_type = 1
    translate_118.first_point = part.create_reference_from_object(origin_point)
    translate_118.second_point = part.create_reference_from_object(mid_point)
    translate_118.volume_result = False
    hb_root.append_hybrid_shape(translate_118)
    part.update()

    # Link translation distance
    try:
        create_or_replace_formula(
            relations,
            "Formula.5",
            "",
            translate_118.distance,
            "`旋翼直径`*`翼中所在位置比例`/2mm"
        )
        print("✓ Mid translate linked to parameters")
    except Exception as e:
        print(f"✗ Failed to link mid translate: {e}")

    # Scale
    scale_118 = hsf.add_new_hybrid_scaling(
        part.create_reference_from_object(translate_118),
        part.create_reference_from_object(mid_point),
        MID_CHORD_MM / 99.0,
    )
    scale_118.volume_result = False
    hb_root.append_hybrid_shape(scale_118)
    part.update()

    # Link scale
    try:
        create_or_replace_formula(
            relations,
            "Formula.6",
            "",
            scale_118.ratio,
            "`翼中弦长`/99mm"
        )
        print("✓ Mid scale linked to 翼中弦长")
    except Exception as e:
        print(f"✗ Failed to link mid scale: {e}")

    # Rotate
    rotate_118 = hsf.add_new_empty_rotate()
    rotate_118.elem_to_rotate = part.create_reference_from_object(scale_118)
    rotate_118.axis = part.create_reference_from_object(axis_line)
    rotate_118.volume_result = False
    rotate_118.rotation_type = 0
    rotate_118.angle_value = MID_TWIST_DEG
    hb_root.append_hybrid_shape(rotate_118)
    part.update()

    # Link rotation
    try:
        create_or_replace_formula(
            relations,
            "Formula.7",
            "",
            rotate_118.angle,
            "`翼中扭转角`"
        )
        print("✓ Mid twist linked to 翼中扭转角")
    except Exception as e:
        print(f"✗ Failed to link mid twist: {e}")

    # === TIP SECTION (208) ===
    tip_curve = hb_post.hybrid_shapes.item("NACA64-208就绪")

    # Translate
    translate_208 = hsf.add_new_empty_translate()
    translate_208.elem_to_translate = part.create_reference_from_object(tip_curve)
    translate_208.vector_type = 1
    translate_208.first_point = part.create_reference_from_object(origin_point)
    translate_208.second_point = part.create_reference_from_object(tip_point)
    translate_208.volume_result = False
    hb_root.append_hybrid_shape(translate_208)
    part.update()

    # Link translation
    try:
        create_or_replace_formula(
            relations,
            "Formula.8",
            "",
            translate_208.distance,
            "`旋翼直径`/2mm"
        )
        print("✓ Tip translate linked to 旋翼直径")
    except Exception as e:
        print(f"✗ Failed to link tip translate: {e}")

    # Scale
    scale_208 = hsf.add_new_hybrid_scaling(
        part.create_reference_from_object(translate_208),
        part.create_reference_from_object(tip_point),
        TIP_CHORD_MM / 99.0,
    )
    scale_208.volume_result = False
    hb_root.append_hybrid_shape(scale_208)
    part.update()

    # Link scale
    try:
        create_or_replace_formula(
            relations,
            "Formula.9",
            "",
            scale_208.ratio,
            "`翼尖弦长`/99mm"
        )
        print("✓ Tip scale linked to 翼尖弦长")
    except Exception as e:
        print(f"✗ Failed to link tip scale: {e}")

    # Rotate
    rotate_208 = hsf.add_new_empty_rotate()
    rotate_208.elem_to_rotate = part.create_reference_from_object(scale_208)
    rotate_208.axis = part.create_reference_from_object(axis_line)
    rotate_208.volume_result = False
    rotate_208.rotation_type = 0
    rotate_208.angle_value = TIP_TWIST_DEG
    hb_root.append_hybrid_shape(rotate_208)
    part.update()

    # Link rotation
    try:
        create_or_replace_formula(
            relations,
            "Formula.10",
            "",
            rotate_208.angle,
            "`翼尖扭转角`"
        )
        print("✓ Tip twist linked to 翼尖扭转角")
    except Exception as e:
        print(f"✗ Failed to link tip twist: {e}")

    print("\n" + "=" * 50)
    print("PARAMETERIZATION COMPLETE")
    print("=" * 50)
    print("All geometric features are now linked to parameters.")
    print("Modify the parameters in CATIA to update the model!")
    print("=" * 50)


def set_visibility(part_document, obj, show):
    selection = part_document.selection
    selection.clear()
    selection.add(obj)
    vis_props = selection.vis_properties
    vis_props = vis_props.parent
    vis_props.set_show(1 if show else 0)
    selection.clear()


def main():
    print("Starting propeller blade generation...")

    caa = catia()
    docs = caa.documents
    if docs.count == 0:
        doc = docs.add("Part")
    else:
        doc = caa.active_document

    part = doc.part
    hsf = part.hybrid_shape_factory
    parameters = part.parameters
    relations = part.relations

    # Create parameters with Chinese names
    print("\nCreating parameters...")
    get_or_create_length_param(parameters, "旋翼直径", ROTOR_DIAMETER_MM)
    get_or_create_length_param(parameters, "翼根弦长", ROOT_CHORD_MM)
    get_or_create_length_param(parameters, "翼中弦长", MID_CHORD_MM)
    get_or_create_length_param(parameters, "翼尖弦长", TIP_CHORD_MM)
    get_or_create_angle_param(parameters, "桨毂前锥角", PRE_CONE_ANGLE_DEG)
    get_or_create_angle_param(parameters, "翼根扭转角", ROOT_TWIST_DEG)
    get_or_create_angle_param(parameters, "翼中扭转角", MID_TWIST_DEG)
    get_or_create_angle_param(parameters, "翼尖扭转角", TIP_TWIST_DEG)
    get_or_create_real_param(parameters, "翼中所在位置比例", MID_SPAN_RATIO)
    print("✓ Parameters created")

    # Build structure
    print("\nBuilding structure...")
    hb_root = part.hybrid_bodies.add()
    hb_root.name = "桨叶GS"

    hb_airfoil = hb_root.hybrid_bodies.add()
    hb_airfoil.name = "翼型"

    hb_ref = hb_root.hybrid_bodies.add()
    hb_ref.name = "参考"
    origin = hsf.add_new_point_coord(0.0, 0.0, 0.0)
    hb_ref.append_hybrid_shape(origin)
    print("✓ Structure created")

    # Create airfoil sections
    print("\nCreating airfoil sections...")
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
        spline = build_points_and_spline(part, hsf, hb_section, points)
        translate_name, plane_name = name_to_mark[name]
        align_spline_and_create_plane(
            part, hsf, hb_section, spline, origin, translate_name, plane_name
        )
        print(f"✓ {name} created")

    # Apply splits
    print("\nApplying splits...")
    hb_post = apply_macro_splits(part, hsf, hb_airfoil)
    print("✓ Splits applied")

    # Create sketches
    print("\nCreating sketches...")
    create_sketches(part, hb_root)

    # Apply transformations with parameterization
    print("\nApplying transformations and creating formulas...")
    postprocess_scale_translate_rotate(part, hsf, relations, parameters, hb_post, hb_root, origin)

    # Set visibility
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

    # Final update
    part.update()
    print("\n" + "=" * 50)
    print("COMPLETE! Propeller blade model generated.")
    print("=" * 50)


if __name__ == "__main__":
    main()