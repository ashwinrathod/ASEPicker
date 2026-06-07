# ASEPicker/anim/snapshot.py
import json
import os
import math
from maya import cmds
import maya.mel as mel
import maya.api.OpenMaya as om

def _get_data_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    data_dir = os.path.join(root, "ASEPicker_Data", "snapshots")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return data_dir

def get_snapshot_path(namespace):
    name = namespace.replace(":", "").strip()
    if not name: name = "Global"
    return os.path.join(_get_data_dir(), f"{name}.json")

# --- VECTOR MATH HELPERS ---

def _get_node_axis_vector(node, axis_index):
    """
    Returns the NORMALIZED World Space vector of a node's local axis.
    axis_index: 0=X, 1=Y, 2=Z
    """
    if not cmds.objExists(node):
        return om.MVector(0, 0, 0)
            
    mat = cmds.xform(node, q=True, ws=True, matrix=True)
    vec = om.MVector(mat[axis_index*4], mat[axis_index*4+1], mat[axis_index*4+2])
        
    if vec.length() < 0.001:
        return om.MVector(0, 0, 0)
            
    return vec.normal()

def _calculate_mirror_rules(src, dst):
    """
    Dynamically maps axes and multipliers across complex rigs.
    Supports Cross-Axis mapping (e.g., TX -> TY), Behavioral Symmetry, and Negative Scale.
    Returns: [mapped_axis_index, multiplier] for X, Y, Z
    """
    rules = {
        "translate": [[0, 1.0], [1, 1.0], [2, 1.0]],
        "rotate": [[0, 1.0], [1, 1.0], [2, 1.0]]
    }
    
    # 1. Detect if the Destination uses a Left-Handed Coordinate System (Negative Scale)
    def get_parity(node):
        mat = cmds.xform(node, q=True, ws=True, matrix=True)
        x = om.MVector(mat[0], mat[1], mat[2])
        y = om.MVector(mat[4], mat[5], mat[6])
        z = om.MVector(mat[8], mat[9], mat[10])
        # If X cross Y points same direction as Z, it's Right-Handed (+1). Else Left-Handed (-1).
        return 1.0 if ((x ^ y) * z) > 0 else -1.0
        
    parity_src = get_parity(src)
    parity_dst = get_parity(dst)
    parity_mult = parity_src * parity_dst # Will be -1.0 if one side is negatively scaled
    
    for i in range(3): 
        v_src = _get_node_axis_vector(src, i)
        
        # --- TRANSLATION MATCHING (Polar Vector Mirroring) ---
        # Theoretical target translation vector (Flip World X)
        t_target = om.MVector(-v_src.x, v_src.y, v_src.z) 
        
        best_t_axis = i
        best_t_dot = 0.0
        for j in range(3): 
            v_dst = _get_node_axis_vector(dst, j)
            dot = t_target * v_dst
            if abs(dot) > abs(best_t_dot):
                best_t_dot = dot
                best_t_axis = j
                
        t_mult = 1.0
        if best_t_dot < -0.3: t_mult = -1.0
        elif best_t_dot > 0.3: t_mult = 1.0
        else:
            best_t_axis = i
            t_mult = 1.0 if (i != 0) else -1.0
            
        rules["translate"][i] = [best_t_axis, t_mult]
        
        # --- ROTATION MATCHING (Pseudovector Mirroring) ---
        # Theoretical target rotation axis (World X stays, World Y and Z flip)
        r_target = om.MVector(v_src.x, -v_src.y, -v_src.z)
        
        best_r_axis = i
        best_r_dot = 0.0
        for j in range(3): 
            v_dst = _get_node_axis_vector(dst, j)
            dot = r_target * v_dst
            if abs(dot) > abs(best_r_dot):
                best_r_dot = dot
                best_r_axis = j
                
        r_mult = 1.0
        if best_r_dot < -0.3: r_mult = -1.0
        elif best_r_dot > 0.3: r_mult = 1.0
        else:
            best_r_axis = i
            r_mult = 1.0
            
        # If destination has negative scale, its internal rotations spin backward.
        # We multiply by parity_mult to natively correct the final applied value!
        rules["rotate"][i] = [best_r_axis, r_mult * parity_mult]

    return rules

def _find_mirror_partner(short, known_names):
    """
    Robust string matching to find Left/Right partner.
    Returns (partner_name, side) or (None, "Center").
    """
    # Patterns: (LeftToken, RightToken)
    # We check Prefix (L_), Suffix (_L), and Middle (_L_) explicitly.
    
    pairs = [
        ("Left", "Right"), 
        ("left", "right"),
        ("Lf", "Rt"),
        ("lf", "rt"),
        ("L", "R"),
        ("l", "r")
    ]
    
    # 1. Check Prefix (e.g. "L_Hand")
    for l, r in pairs:
        # Check Left -> Right
        prefix_l = f"{l}_"
        prefix_r = f"{r}_"
        if short.startswith(prefix_l):
            cand = prefix_r + short[len(prefix_l):]
            if cand in known_names: return cand, "Left"
        
        # Check Right -> Left
        if short.startswith(prefix_r):
            cand = prefix_l + short[len(prefix_r):]
            if cand in known_names: return cand, "Right"

    # 2. Check Suffix (e.g. "Hand_L")
    for l, r in pairs:
        # Check Left -> Right
        suffix_l = f"_{l}"
        suffix_r = f"_{r}"
        if short.endswith(suffix_l):
            cand = short[:-len(suffix_l)] + suffix_r
            if cand in known_names: return cand, "Left"
            
        # Check Right -> Left
        if short.endswith(suffix_r):
            cand = short[:-len(suffix_r)] + suffix_l
            if cand in known_names: return cand, "Right"

    # 3. Check Middle (e.g. "Arm_L_FK")
    for l, r in pairs:
        mid_l = f"_{l}_"
        mid_r = f"_{r}_"
        if mid_l in short:
            cand = short.replace(mid_l, mid_r)
            if cand in known_names: return cand, "Left"
        
        if mid_r in short:
            cand = short.replace(mid_r, mid_l)
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
        cmds.warning(f"[ASEPicker] No controls found for namespace '{namespace}'.")
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
        print(f"[ASEPicker] Snapshot Error: {e}")
    finally:
        cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)

    # Save
    data = { "namespace": namespace, "controls": final_controls }
    path = get_snapshot_path(namespace)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"[ASEPicker] Snapshot saved: {path}")
    except Exception as e:
        print(f"[ASEPicker] Save Error: {e}")
        
    return data

def load_snapshot(namespace):
    path = get_snapshot_path(namespace)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return None