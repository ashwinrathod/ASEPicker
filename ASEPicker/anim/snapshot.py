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
    Determines if attributes need to be flipped (-1) or kept (1)
    by comparing source vs dest orientation in World Space.
    Assumes mirroring across World X Plane (YZ plane).
    """
    rules = {
        "translate": [1.0, 1.0, 1.0],
        "rotate": [1.0, 1.0, 1.0]
    }
    
    # Mirror Plane Vector (Flip X) -> (-x, y, z)
    
    axes = ["X", "Y", "Z"]
    
    for i, axis in enumerate(axes):
        # 1. Source Axis
        v_src = _get_node_axis_vector(src, i)
        
        # 2. Theoretical Mirrored Axis
        # If we mirror the source orientation across world X, where should it point?
        v_target = om.MVector(-v_src.x, v_src.y, v_src.z)
        
        # 3. Actual Dest Axis
        v_dst = _get_node_axis_vector(dst, i)
        
        # 4. Compare (Dot Product)
        # Dot 1.0 = Aligned, Dot -1.0 = Inverted
        dot = (v_target * v_dst)
        
        # --- TRANSLATE RULE ---
        # If axes align (dot > 0), translation moves same way (1.0).
        # If axes oppose (dot < 0), translation must invert (-1.0).
        t_val = 1.0 if dot > 0 else -1.0
        rules["translate"][i] = t_val
        
        # --- ROTATE RULE ---
        # Rotation logic is inverted relative to translation because the coordinate system flips.
        # If axis aligns (dot > 0), rotation value FLIPS (-1.0).
        # If axis opposes (dot < 0), rotation value STAYS (1.0).
        r_val = -1.0 if dot > 0 else 1.0
        rules["rotate"][i] = r_val

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
                t_rules = [-1.0, 1.0, 1.0]
                r_rules = [1.0, -1.0, -1.0]
            
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