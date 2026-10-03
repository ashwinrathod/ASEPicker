# ARTools/anim/snapshot.py
import json
import os
import math
import base64
import bpy
import mathutils
from ..blender_host import object_by_name, selected_object_names, get_property, set_property

def _get_data_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    data_dir = os.path.join(root, "ARTools_Data", "snapshots")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return data_dir

def get_snapshot_path(namespace):
    name = namespace.replace(":", "").strip()
    if not name: name = "Global"
    return os.path.join(_get_data_dir(), f"{name}.art")

def _get_matrix_world(b_obj):
    if hasattr(b_obj, "matrix_world"):
        return b_obj.matrix_world.copy()
    return b_obj.id_data.matrix_world @ b_obj.matrix.copy()

# --- EMPIRICAL "TEST DRIVE" MIRROR ENGINE ---

def _test_drive_matrix(node, attr, delta):
    b_obj = object_by_name(node)
    if not b_obj: return None
        
    val = get_property(b_obj, attr, None)
    if val is None: return None
        
    set_property(b_obj, attr, val + delta, keyframe=False)
    bpy.context.view_layer.update()
    mat = _get_matrix_world(b_obj)
        
    set_property(b_obj, attr, val, keyframe=False)
    bpy.context.view_layer.update()
    return mat

def _get_base_matrix(node):
    b_obj = object_by_name(node)
    if b_obj: return _get_matrix_world(b_obj)
    return mathutils.Matrix()

def _get_origin(mat):
    return mat.translation.copy()

def _get_basis_vectors(mat):
    """Extracts raw orientation, completely ignoring rig scaling."""
    x = mathutils.Vector((mat[0][0], mat[1][0], mat[2][0]))
    y = mathutils.Vector((mat[0][1], mat[1][1], mat[2][1]))
    z = mathutils.Vector((mat[0][2], mat[1][2], mat[2][2]))
    
    if x.length > 0.0001: x.normalize()
    if y.length > 0.0001: y.normalize()
    if z.length > 0.0001: z.normalize()
    return x, y, z

def _get_mirrored_vector(v, plane="YZ"):
    if plane == "YZ": return mathutils.Vector((-v.x, v.y, v.z))
    elif plane == "XZ": return mathutils.Vector((v.x, -v.y, v.z))
    else: return mathutils.Vector((v.x, v.y, -v.z))

def _calculate_mirror_rules(src_node, dst_node, plane="YZ", *args, **kwargs):
    """
    The Hybrid Double Engine:
    - Translation uses Physical Delta Test Drive to bypass Joint Orients & Parent Offsets.
    - Rotation uses Parity Basis Math (Locked & Perfect for all orientations).
    """
    t_rules = [[0, 1.0], [1, 1.0], [2, 1.0]]
    r_rules = [[0, 1.0], [1, 1.0], [2, 1.0]]
    
    src_rest = _get_base_matrix(src_node)
    dst_rest = _get_base_matrix(dst_node)
    
    src_x, src_y, src_z = _get_basis_vectors(src_rest)
    dst_x, dst_y, dst_z = _get_basis_vectors(dst_rest)
    dst_axes = [dst_x, dst_y, dst_z]
    src_axes = [src_x, src_y, src_z]
    
    src_parity = 1.0 if src_x.cross(src_y).dot(src_z) > 0 else -1.0
    dst_parity = 1.0 if dst_x.cross(dst_y).dot(dst_z) > 0 else -1.0
    scale_mult = src_parity * dst_parity
    
    # --- TRANSLATE MATH (Physical Delta Test Drive Engine) ---
    attrs_t = ['tx', 'ty', 'tz']

    # Each destination test-drive only depends on j, not i, so compute it
    # once up front instead of redoing it inside every i-iteration -- this
    # alone cuts the scene updates for this function in half.
    dst_deltas = []
    for j, dst_attr in enumerate(attrs_t):
        dst_mat = _test_drive_matrix(dst_node, dst_attr, 0.05)
        if dst_mat:
            dst_delta = dst_mat.translation - dst_rest.translation
            if dst_delta.length < 0.0001: dst_delta = dst_axes[j]
            else: dst_delta.normalize()
        else:
            dst_delta = dst_axes[j]
        dst_deltas.append(dst_delta)

    for i, src_attr in enumerate(attrs_t):
        # Reduced delta to 0.05 to prevent Blender IK constraints from flipping out
        src_mat = _test_drive_matrix(src_node, src_attr, 0.05)
        if src_mat:
            src_delta = src_mat.translation - src_rest.translation
            if src_delta.length < 0.0001: src_delta = src_axes[i]
            else: src_delta.normalize()
        else:
            src_delta = src_axes[i]

        if plane == "YZ": mir_delta = mathutils.Vector((-src_delta.x, src_delta.y, src_delta.z))
        elif plane == "XZ": mir_delta = mathutils.Vector((src_delta.x, -src_delta.y, src_delta.z))
        else: mir_delta = mathutils.Vector((src_delta.x, src_delta.y, -src_delta.z))

        best_axis, best_mult, best_score = i, 1.0, -9999.0
        for j, dst_delta in enumerate(dst_deltas):
            score = mir_delta.dot(dst_delta)
            if abs(score) > best_score:
                best_score = abs(score)
                best_axis = j
                best_mult = 1.0 if score > 0 else -1.0

        t_rules[i] = [best_axis, best_mult]

    # --- ROTATE MATH (Locked Parity Pseudovector Mirroring) ---
    if plane == "YZ":
        src_r_targets = [
            mathutils.Vector((src_x.x, -src_x.y, -src_x.z)),
            mathutils.Vector((src_y.x, -src_y.y, -src_y.z)),
            mathutils.Vector((src_z.x, -src_z.y, -src_z.z))
        ]
    elif plane == "XZ":
        src_r_targets = [
            mathutils.Vector((-src_x.x, src_x.y, -src_x.z)),
            mathutils.Vector((-src_y.x, src_y.y, -src_y.z)),
            mathutils.Vector((-src_z.x, src_z.y, -src_z.z))
        ]
    else:
        src_r_targets = [
            mathutils.Vector((-src_x.x, -src_x.y, src_x.z)),
            mathutils.Vector((-src_y.x, -src_y.y, src_y.z)),
            mathutils.Vector((-src_z.x, -src_z.y, src_z.z))
        ]
    
    for i in range(3):
        best_axis, best_mult, best_score = i, 1.0, -9999.0
        for j in range(3):
            score = src_r_targets[i].dot(dst_axes[j])
            if abs(score) > best_score:
                best_score = abs(score)
                best_axis = j
                best_mult = 1.0 if score > 0 else -1.0
        r_rules[i] = [best_axis, best_mult * scale_mult]

    return {"translate": t_rules, "rotate": r_rules}

def _invert_rules(rules):
    """Invert a set of [axis, mult] mirror rules (translate or rotate).

    The forward rules already describe an axis permutation ("my axis i
    drives their axis j, scaled by mult"), so the reverse mapping is just
    that permutation read backwards -- no extra Blender test-drives
    needed to mirror the other control in the same pair.
    """
    inverted = [[0, 1.0], [1, 1.0], [2, 1.0]]
    for i, (axis, mult) in enumerate(rules):
        inverted[axis] = [i, mult]
    return inverted

def _find_mirror_partner(short, known_names):

    from ARTools.preferences import PrefManager
    pairs = PrefManager().get_mirror_pairs_list()
    segments = short.split("_")

    for l_str, r_str in pairs:
        for src, dst, side in ((l_str, r_str, "Left"), (r_str, l_str, "Right")):
            cand = None

            if src.startswith(("_", ".")) and short.endswith(src):
                # Suffix-style token ("_L", ".L") -- must end the name.
                cand = short[:-len(src)] + dst
            elif src.endswith("_") and short.startswith(src):
                # Prefix-style token ("L_") -- must start the name.
                cand = dst + short[len(src):]
            elif src in segments:
                # Free-form token ("Left", "lf") -- must be its own
                # whole underscore-delimited segment.
                idx = segments.index(src)
                cand = "_".join(segments[:idx] + [dst] + segments[idx + 1:])

            if cand and cand in known_names:
                return cand, side

    return None, "Center"

def create_character_snapshot(namespace):
    if namespace is None: namespace = ""
    
    short_to_long = {}
    control_list = []
    
    armature = bpy.data.objects.get(namespace)
    if armature and armature.type == 'ARMATURE':
        for bone in armature.pose.bones:
            short = bone.name
            short_to_long[short] = f"{armature.name}:{short}"
            control_list.append(short)
    else:
        sel = selected_object_names()
        for s in sel:
            short = s.split(":")[-1]
            short_to_long[short] = s
            control_list.append(short)

    if not control_list:
        print(f"[ARTools] No controls found for namespace '{namespace}'.")
        return None

    final_controls = {}
    known_set = set(control_list)
    mirror_rule_cache = {}

    for short in control_list:
        full_node = short_to_long[short]
        partner, side = _find_mirror_partner(short, known_set)
            
        b_obj = object_by_name(full_node)
        if not b_obj: continue
            
        if side == "Center":
            pos = _get_matrix_world(b_obj).translation
            # Tightened threshold to strictly identify Blender center bones
            if pos.x > 0.005: side = "Left"
            elif pos.x < -0.005: side = "Right"

        defaults = {}
        attrs_to_save = ["tx", "ty", "tz", "rx", "ry", "rz", "rw", "rqx", "rqy", "rqz", "sx", "sy", "sz"]
        for k in b_obj.keys():
            if not k.startswith("_"): attrs_to_save.append(k)
                
        for attr in attrs_to_save:
            val = get_property(b_obj, attr, None)
            if val is not None:
                defaults[attr] = val

        # Correct nested array defaults to prevent data corruption on isolated bones
        t_rules = [[0, 1.0], [1, 1.0], [2, 1.0]]
        r_rules = [[0, 1.0], [1, 1.0], [2, 1.0]]

        if partner and partner in short_to_long:
            dst_node = short_to_long[partner]
            pair_key = tuple(sorted((full_node, dst_node)))
            cached = mirror_rule_cache.get(pair_key)
            if cached is None:
                rules = _calculate_mirror_rules(full_node, dst_node)
                mirror_rule_cache[pair_key] = (full_node, rules)
                t_rules = rules["translate"]
                r_rules = rules["rotate"]
            elif cached[0] == full_node:
                t_rules = cached[1]["translate"]
                r_rules = cached[1]["rotate"]
            else:
                # The partner side already computed this pair -- reuse it
                # instead of re-running the test-drive engine a second time.
                t_rules = _invert_rules(cached[1]["translate"])
                r_rules = _invert_rules(cached[1]["rotate"])
        else:
            # No name-based partner exists -- this is either a true center
            # control, or one the position check above relabeled to
            # Left/Right because it sits off-axis. Either way there is no
            # partner to look up, so fall back to the self-mirror flip
            # instead of silently leaving the identity rule in place.
            t_rules = [[0, -1.0], [1, 1.0], [2, 1.0]]
            r_rules = [[0, 1.0], [1, -1.0], [2, -1.0]]

        final_controls[short] = {
            "defaults": defaults,
            "side": side,
            "mirror": partner,
            "mirror_rules": {
                "translate": t_rules,
                "rotate": r_rules
            }
        }

    data = { "namespace": namespace, "controls": final_controls }
    path = get_snapshot_path(namespace)
    
    json_str = json.dumps(data)
    encoded_bytes = base64.b64encode(json_str.encode("utf-8"))
    
    with open(path, "wb") as f:
        f.write(encoded_bytes)
        
    print(f"[ARTools] Snapshot saved: {path}")
    return data

def load_snapshot(namespace):
    path = get_snapshot_path(namespace)
    if os.path.exists(path):
        with open(path, "rb") as f:
            encoded_bytes = f.read()
        json_str = base64.b64decode(encoded_bytes).decode("utf-8")
        return json.loads(json_str)
    return None

def fix_or_add_controls(namespace, selected_controls):
    if namespace is None: namespace = ""
    ns_prefix = f"{namespace}:" if namespace and not namespace.endswith(":") else namespace
    
    snap_data = load_snapshot(namespace)
    if not snap_data:
        print("[ARTools] Current namespace's snapshot is not available.")
        return

    short_to_long = {}
    for node in selected_controls:
        short = node.split(":")[-1]
        short_to_long[short] = node

    known_set = set(snap_data["controls"].keys())
    known_set.update(short_to_long.keys())
    mirror_rule_cache = {}

    for short, full_node in short_to_long.items():
        partner, side = _find_mirror_partner(short, known_set)
            
        b_obj = object_by_name(full_node)
        if not b_obj: continue
            
        if side == "Center":
            pos = _get_matrix_world(b_obj).translation
            if pos.x > 0.005: side = "Left"
            elif pos.x < -0.005: side = "Right"

        defaults = {}
        attrs_to_save = ["tx", "ty", "tz", "rx", "ry", "rz", "rw", "rqx", "rqy", "rqz", "sx", "sy", "sz"]
        for k in b_obj.keys():
            if not k.startswith("_"): attrs_to_save.append(k)
            
        for attr in attrs_to_save:
            val = get_property(b_obj, attr, None)
            if val is not None:
                defaults[attr] = val

        t_rules = [[0, 1.0], [1, 1.0], [2, 1.0]]
        r_rules = [[0, 1.0], [1, 1.0], [2, 1.0]]

        dst_node = None
        if partner:
            dst_node = partner
            if partner in short_to_long:
                dst_node = short_to_long[partner]
            else:
                dst_node = f"{ns_prefix}{partner}"
            if not object_by_name(dst_node):
                dst_node = None

        if dst_node:
            pair_key = tuple(sorted((full_node, dst_node)))
            cached = mirror_rule_cache.get(pair_key)
            if cached is None:
                rules = _calculate_mirror_rules(full_node, dst_node)
                mirror_rule_cache[pair_key] = (full_node, rules)
                t_rules = rules["translate"]
                r_rules = rules["rotate"]
            elif cached[0] == full_node:
                t_rules = cached[1]["translate"]
                r_rules = cached[1]["rotate"]
            else:
                # The partner side already computed this pair -- reuse it
                # instead of re-running the test-drive engine a second time.
                t_rules = _invert_rules(cached[1]["translate"])
                r_rules = _invert_rules(cached[1]["rotate"])
        else:
            # No usable partner on the other side -- a true center
            # control, one relabeled to Left/Right by the position check
            # above, or a named partner that doesn't exist in the scene.
            # Fall back to the self-mirror flip instead of the identity rule.
            t_rules = [[0, -1.0], [1, 1.0], [2, 1.0]]
            r_rules = [[0, 1.0], [1, -1.0], [2, -1.0]]

        snap_data["controls"][short] = {
            "defaults": defaults,
            "side": side,
            "mirror": partner,
            "mirror_rules": {
                "translate": t_rules,
                "rotate": r_rules
            }
        }

    path = get_snapshot_path(namespace)
    json_str = json.dumps(snap_data)
    encoded_bytes = base64.b64encode(json_str.encode("utf-8"))
    
    with open(path, "wb") as f:
        f.write(encoded_bytes)
    
    print(f"[ARTools] Snapshot Fixed/Added {len(selected_controls)} controls")