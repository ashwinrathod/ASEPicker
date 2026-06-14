# ASEPicker/anim/logic_ikfk.py
from maya import cmds
import maya.api.OpenMaya as om
import uuid

def _resolve(node, ns):
    """Safely applies the namespace if the node doesn't already have it."""
    if not node: return ""
    if ns and not node.startswith(f"{ns}:"): return f"{ns}:{node}"
    return node

# =====================================================================
# THE MATCHING ENGINE (NOW WITH VIEWPORT SUSPENSION)
# =====================================================================

def switch_to_fk(chain, ns, key=True):
    fk_ctrls = [_resolve(x, ns) for x in chain.get("fk_ctrls", [])]
    bones = [_resolve(x, ns) for x in chain.get("bones", [])]
    sw_node, sw_attr = _resolve(chain["switch"]["node"], ns), chain["switch"]["attr"]
    attr_path = f"{sw_node}.{sw_attr}"

    if not fk_ctrls or not bones or not cmds.objExists(attr_path): 
        cmds.warning("[ASEPicker] Missing FK controls, Bones, or Switch Attr.")
        return

    cmds.undoInfo(openChunk=True)
    cmds.refresh(suspend=True)
    try:
        # 1. Capture exact World Matrices
        target_matrices = [cmds.xform(b, q=True, ws=True, matrix=True) for b in bones]

        # 2. FLIP THE SWITCH
        cmds.setAttr(attr_path, chain["switch"]["fk_val"])
        if key: cmds.setKeyframe(attr_path)

        # 3. NATIVE DAG EVALUATION (Scale & Mirror Safe)
        for ctrl, bone, goal_mat in zip(fk_ctrls, bones, target_matrices):
            if not cmds.objExists(ctrl) or not cmds.objExists(bone): continue

            loc_b = cmds.spaceLocator()[0]
            loc_c = cmds.spaceLocator()[0]
            
            # Snap locators to current FK state
            cmds.matchTransform(loc_b, bone, pos=True, rot=True)
            cmds.matchTransform(loc_c, ctrl, pos=True, rot=True)
            
            # Parent to create safe offset
            cmds.parent(loc_c, loc_b)
            
            # Move bone locator to IK target
            cmds.xform(loc_b, ws=True, matrix=goal_mat)
            
            # Snap control back to the carried locator
            cmds.matchTransform(ctrl, loc_c, pos=True, rot=True)
            cmds.delete(loc_b)
            
            for axis in ["tx", "ty", "tz"]:
                if not cmds.getAttr(f"{ctrl}.{axis}", lock=True):
                    cmds.setAttr(f"{ctrl}.{axis}", 0.0)

            if key: cmds.setKeyframe(ctrl, at=["rotate", "translate"])
            cmds.refresh() 

        if key: cmds.filterCurve(fk_ctrls, filter="euler")

    except Exception as e:
        cmds.warning(f"[ASEPicker] IK->FK Snap Error: {e}")
    finally:
        cmds.refresh(suspend=False)
        cmds.refresh(force=True)
        cmds.undoInfo(closeChunk=True)


def switch_to_ik(chain, ns, key=True):
    ik_ctrl = _resolve(chain.get("ik_ctrl", ""), ns)
    pv_ctrl = _resolve(chain.get("pv_ctrl", ""), ns)
    bones = [_resolve(x, ns) for x in chain.get("bones", [])]
    sw_node, sw_attr = _resolve(chain["switch"]["node"], ns), chain["switch"]["attr"]
    attr_path = f"{sw_node}.{sw_attr}"

    if not ik_ctrl or len(bones) < 3 or not cmds.objExists(attr_path): 
        cmds.warning("[ASEPicker] Missing IK Control, Bones, or Switch Attr.")
        return

    cmds.undoInfo(openChunk=True)
    cmds.refresh(suspend=True)
    try:
        # 1. Capture exact Data
        wrist_goal_mat = cmds.xform(bones[-1], q=True, ws=True, matrix=True)
        
        start = om.MVector(cmds.xform(bones[0], q=True, ws=True, rp=True))
        mid = om.MVector(cmds.xform(bones[1], q=True, ws=True, rp=True))
        end = om.MVector(cmds.xform(bones[-1], q=True, ws=True, rp=True))

        # 2. FLIP THE SWITCH
        cmds.setAttr(attr_path, chain["switch"]["ik_val"])
        if key: cmds.setKeyframe(attr_path)

        # 3. Snap IK Wrist using DAG Offset
        loc_b = cmds.spaceLocator()[0]
        loc_c = cmds.spaceLocator()[0]
        cmds.matchTransform(loc_b, bones[-1], pos=True, rot=True)
        cmds.matchTransform(loc_c, ik_ctrl, pos=True, rot=True)
        cmds.parent(loc_c, loc_b)
        cmds.xform(loc_b, ws=True, matrix=wrist_goal_mat)
        cmds.matchTransform(ik_ctrl, loc_c, pos=True, rot=True)
        cmds.delete(loc_b)
        if key: cmds.setKeyframe(ik_ctrl, at=["translate", "rotate"])
        cmds.refresh()

        # 4. Snap PV (Bisector Method - ZERO Micro-Shifts!)
        if pv_ctrl:
            start = om.MVector(cmds.xform(bones[0], q=True, ws=True, rp=True))
            mid = om.MVector(cmds.xform(bones[1], q=True, ws=True, rp=True))
            end = om.MVector(cmds.xform(bones[-1], q=True, ws=True, rp=True))

            v1 = (start - mid).normal()
            v2 = (end - mid).normal()
            
            # The bisector of the elbow angle points INSIDE the elbow.
            # We want the PV to point OUTSIDE the elbow, so we invert it.
            bisector = (v1 + v2).normal()
            pv_dir = -bisector
            
            if pv_dir.length() < 0.001:
                pv_dir = om.MVector(0,0,1) # Fallback for perfectly straight arm
                
            # Lock the current distance so it doesn't jump forward/backward
            current_pv = om.MVector(cmds.xform(pv_ctrl, q=True, ws=True, rp=True))
            current_dist = (current_pv - mid).length()
            if current_dist < 0.1: current_dist = 5.0
                
            pv_final_pos = mid + (pv_dir * current_dist)
            
            temp_pv = cmds.spaceLocator()[0]
            cmds.xform(temp_pv, ws=True, t=(pv_final_pos.x, pv_final_pos.y, pv_final_pos.z))
            cmds.matchTransform(pv_ctrl, temp_pv, pos=True, rot=False)
            cmds.delete(temp_pv)
            if key: cmds.setKeyframe(pv_ctrl, at=["translate"])

        if key: cmds.filterCurve([ik_ctrl], filter="euler")

    except Exception as e:
        cmds.warning(f"[ASEPicker] FK->IK Snap Error: {e}")
    finally:
        cmds.refresh(suspend=False)
        cmds.refresh(force=True)
        cmds.undoInfo(closeChunk=True)

# =====================================================================
# UI HELPER: AUTO-FIND JOINTS
# =====================================================================

def find_driven_joint(ctrl):
    if not cmds.objExists(ctrl): return None
    candidates = set()
    
    parent = cmds.listRelatives(ctrl, parent=True, type="joint", fullPath=True)
    if parent: candidates.add(parent[0])
    
    children = cmds.listRelatives(ctrl, allDescendents=True, type="joint", fullPath=True)
    if children: candidates.update(children)
        
    connections = cmds.listConnections(ctrl, s=False, d=True) or []
    for node in connections:
        if cmds.nodeType(node) == "joint": candidates.add(node)
        elif "Constraint" in cmds.nodeType(node):
            targets = cmds.listConnections(node, s=False, d=True, type="joint") or []
            candidates.update(targets)
            
    if not candidates: return None
    
    try:
        src_pos = om.MVector(cmds.xform(ctrl, q=True, ws=True, rp=True))
        best = None; best_d = 999999.0
        for c in candidates:
            d = (om.MVector(cmds.xform(c, q=True, ws=True, rp=True)) - src_pos).length()
            if d < best_d: best, best_d = c, d
        return best
    except: return None

def auto_find_chain(fk_list):
    bones = []
    for fk in fk_list:
        b = find_driven_joint(fk)
        if b: bones.append(b)
    return bones