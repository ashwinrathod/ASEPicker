# ARTools/anim/snapshot.py
import json
import os
import math
import base64
from maya import cmds
import maya.mel as mel
import maya.api.OpenMaya as om

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

# --- EMPIRICAL "TEST DRIVE" MIRROR ENGINE ---

def _test_drive_matrix(node, attr, delta):
    locked = cmds.getAttr(f"{node}.{attr}", lock=True)
    if locked: return None
    try:
        val = cmds.getAttr(f"{node}.{attr}")
        cmds.setAttr(f"{node}.{attr}", val + delta)
        # Force DG evaluation by querying World Space Matrix
        mat_list = cmds.xform(node, q=True, ws=True, matrix=True)
        cmds.setAttr(f"{node}.{attr}", val) # Revert instantly
        return om.MMatrix(mat_list)
    except:
        return None

def _get_base_matrix(node):
    mat_list = cmds.xform(node, q=True, ws=True, matrix=True)
    return om.MMatrix(mat_list)

def _get_origin(mat):
    return om.MVector(mat[12], mat[13], mat[14])

def _get_basis_vectors(mat):
    """Extracts raw orientation, completely ignoring rig scaling."""
    x = om.MVector(mat[0], mat[1], mat[2])
    y = om.MVector(mat[4], mat[5], mat[6])
    z = om.MVector(mat[8], mat[9], mat[10])
    
    # Normalize to prevent scale from ruining the math
    if x.length() > 0.0001: x.normalize()
    if y.length() > 0.0001: y.normalize()
    if z.length() > 0.0001: z.normalize()
    return x, y, z

def _get_mirrored_vector(v, plane="YZ"):
    if plane == "YZ": return om.MVector(-v.x, v.y, v.z)
    elif plane == "XZ": return om.MVector(v.x, -v.y, v.z)
    else: return om.MVector(v.x, v.y, -v.z)

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
        
        # ENGINE 1: Normalized Basis Extraction
        src_x, src_y, src_z = _get_basis_vectors(src_rest)
        dst_x, dst_y, dst_z = _get_basis_vectors(dst_rest)
        dst_axes = [dst_x, dst_y, dst_z]
        src_axes = [src_x, src_y, src_z]
        
        # ENGINE 2: Handedness Parity Check (Locked for Rotation)
        src_parity = 1.0 if ((src_x ^ src_y) * src_z) > 0 else -1.0
        dst_parity = 1.0 if ((dst_x ^ dst_y) * dst_z) > 0 else -1.0
        scale_mult = src_parity * dst_parity
        
        # --- TRANSLATE MATH (Physical Delta Test Drive Engine) ---
        attrs_t = ['tx', 'ty', 'tz']
        for i, src_attr in enumerate(attrs_t):
            # Test drive Source physically
            src_mat = _test_drive_matrix(src_node, src_attr, 1.0)
            if src_mat:
                src_delta = om.MVector(src_mat[12]-src_rest[12], src_mat[13]-src_rest[13], src_mat[14]-src_rest[14])
                if src_delta.length() < 0.0001: src_delta = src_axes[i] # Fallback if locked
                else: src_delta.normalize()
            else:
                src_delta = src_axes[i] # Fallback

            mir_delta = om.MVector(-src_delta.x, src_delta.y, src_delta.z) if plane == "YZ" else (om.MVector(src_delta.x, -src_delta.y, src_delta.z) if plane == "XZ" else om.MVector(src_delta.x, src_delta.y, -src_delta.z))

            best_axis, best_mult, best_score = i, 1.0, -9999.0
            for j, dst_attr in enumerate(attrs_t):
                # Test drive Destination physically
                dst_mat = _test_drive_matrix(dst_node, dst_attr, 1.0)
                if dst_mat:
                    dst_delta = om.MVector(dst_mat[12]-dst_rest[12], dst_mat[13]-dst_rest[13], dst_mat[14]-dst_rest[14])
                    if dst_delta.length() < 0.0001: dst_delta = dst_axes[j] # Fallback
                    else: dst_delta.normalize()
                else:
                    dst_delta = dst_axes[j] # Fallback

                score = mir_delta * dst_delta
                if abs(score) > best_score:
                    best_score = abs(score)
                    best_axis = j
                    best_mult = 1.0 if score > 0 else -1.0
                    
            t_rules[i] = [best_axis, best_mult]

        # --- ROTATE MATH (Locked Parity Pseudovector Mirroring) ---
        src_r_targets = [
            om.MVector(src_x.x, -src_x.y, -src_x.z) if plane == "YZ" else (om.MVector(-src_x.x, src_x.y, -src_x.z) if plane == "XZ" else om.MVector(-src_x.x, -src_x.y, src_z.z)),
            om.MVector(src_y.x, -src_y.y, -src_y.z) if plane == "YZ" else (om.MVector(-src_y.x, src_y.y, -src_y.z) if plane == "XZ" else om.MVector(-src_y.x, -src_y.y, src_z.z)),
            om.MVector(src_z.x, -src_z.y, -src_z.z) if plane == "YZ" else (om.MVector(-src_z.x, src_z.y, -src_z.z) if plane == "XZ" else om.MVector(-src_z.x, -src_z.y, src_z.z))
        ]
        
        for i in range(3):
            best_axis, best_mult, best_score = i, 1.0, -9999.0
            for j in range(3):
                score = src_r_targets[i] * dst_axes[j]
                if abs(score) > best_score:
                    best_score = abs(score)
                    best_axis = j
                    best_mult = 1.0 if score > 0 else -1.0
            r_rules[i] = [best_axis, best_mult * scale_mult]

        return {"translate": t_rules, "rotate": r_rules}

def _find_mirror_partner(short, known_names):
    """
    Robust string matching to find Left/Right partner using the Custom Dictionary.
    Returns (partner_name, side) or (None, "Center").
    """
    from ARTools.preferences import PrefManager
    pairs = PrefManager().get_mirror_pairs_list()
    
    for l_str, r_str in pairs:
        if l_str in short:
            cand = short.replace(l_str, r_str)
            if cand in known_names: return cand, "Left"
        if r_str in short:
            cand = short.replace(r_str, l_str)
            if cand in known_names: return cand, "Right"

    return None, "Center"

def create_character_snapshot(namespace):
    if namespace is None: namespace = ""
    ns_prefix = f"{namespace}:" if namespace and not namespace.endswith(":") else namespace
    
    short_to_long = {}
    control_list = []
    
    # 1. Gather ALL controls directly from the Rig in the Maya scene
    search_pattern = f"{ns_prefix}*" if ns_prefix else "*"
    all_transforms = cmds.ls(search_pattern, type="transform", long=True) or []
    
    for node in all_transforms:
        # A standard control is a transform with a NURBS curve shape
        shapes = cmds.listRelatives(node, shapes=True, type="nurbsCurve")
        if shapes:
            short = node.split("|")[-1].split(":")[-1]
            short_to_long[short] = node
            control_list.append(short)

    if not control_list:
        cmds.warning(f"[ARTools] No controls found for namespace '{namespace}'.")
        return None

    final_controls = {}
    known_set = set(control_list)

    gMainProgressBar = mel.eval('$tmp = $gMainProgressBar')
    cmds.progressBar(gMainProgressBar, edit=True, beginProgress=True, isInterruptable=True, status='Snapshotting...', maxValue=len(control_list))

    try:
        for short in control_list:
            if cmds.progressBar(gMainProgressBar, query=True, isCancelled=True): break
            cmds.progressBar(gMainProgressBar, edit=True, step=1)

            full_node = short_to_long[short]
            
            # A. Identification
            partner, side = _find_mirror_partner(short, known_set)
            
            # B. Center Fallback Check
            if side == "Center":
                # Check position to verify if it's truly center
                pos = cmds.xform(full_node, q=True, ws=True, rp=True)
                if pos[0] > 0.01: side = "Left"
                elif pos[0] < -0.01: side = "Right"
                # Even if off-center, if no partner found, it acts as Center (self-mirroring) or Orphan.

            # C. Capture Defaults
            defaults = {}
            keyable = cmds.listAttr(full_node, keyable=True) or []
            for attr in keyable:
                full_attr = f"{full_node}.{attr}"
                if cmds.objExists(full_attr) and not cmds.getAttr(full_attr, lock=True):
                    defaults[attr] = cmds.getAttr(full_attr)

            # D. Calculate Rules
            t_rules = [1.0, 1.0, 1.0]
            r_rules = [1.0, 1.0, 1.0]

            if side == "Center":
                # Standard Center behavior: Translate X flips, Rot Y/Z flip
                t_rules = [[0, -1.0], [1, 1.0], [2, 1.0]]
                r_rules = [[0, 1.0], [1, -1.0], [2, -1.0]]
            
            elif partner and partner in short_to_long:
                # Calculate precise vector math against partner
                dst_node = short_to_long[partner]
                rules = _calculate_mirror_rules(full_node, dst_node)
                t_rules = rules["translate"]
                r_rules = rules["rotate"]

            final_controls[short] = {
                "defaults": defaults,
                "side": side,
                "mirror": partner,
                "mirror_rules": {
                    "translate": t_rules,
                    "rotate": r_rules
                }
            }

    except Exception as e:
        print(f"[ARTools] Snapshot Error: {e}")
    finally:
        cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)

    # Save
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
        cmds.warning("[ARTools] Current namespace's snapshot is not available.")
        return

    short_to_long = {}
    for node in selected_controls:
        short = node.split("|")[-1].split(":")[-1]
        short_to_long[short] = node

    known_set = set(snap_data["controls"].keys())
    known_set.update(short_to_long.keys())

    for short, full_node in short_to_long.items():
        partner, side = _find_mirror_partner(short, known_set)
        
        if side == "Center":
            pos = cmds.xform(full_node, q=True, ws=True, rp=True)
            if pos[0] > 0.01: side = "Left"
            elif pos[0] < -0.01: side = "Right"

        defaults = {}
        keyable = cmds.listAttr(full_node, keyable=True) or []
        for attr in keyable:
            full_attr = f"{full_node}.{attr}"
            if cmds.objExists(full_attr) and not cmds.getAttr(full_attr, lock=True):
                defaults[attr] = cmds.getAttr(full_attr)

        t_rules = [1.0, 1.0, 1.0]
        r_rules = [1.0, 1.0, 1.0]

        if side == "Center":
            t_rules = [[0, -1.0], [1, 1.0], [2, 1.0]]
            r_rules = [[0, 1.0], [1, -1.0], [2, -1.0]]
        elif partner:
            dst_node = partner
            if partner in short_to_long:
                dst_node = short_to_long[partner]
            else:
                dst_node = f"{ns_prefix}{partner}"
            
            if cmds.objExists(dst_node):
                rules = _calculate_mirror_rules(full_node, dst_node)
                t_rules = rules["translate"]
                r_rules = rules["rotate"]

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
    
    cmds.inViewMessage(amg=f"Snapshot Fixed/Added {len(selected_controls)} controls", pos="midCenter", fade=True)