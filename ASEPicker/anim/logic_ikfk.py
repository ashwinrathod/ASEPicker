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
    """
    RIG IS IN IK. We snap FK controls to match the IK pose.
    Uses Top-Down Matrix Evaluation to prevent hierarchy twisting.
    """
    fk_ctrls = [_resolve(x, ns) for x in chain.get("fk_ctrls", [])]
    bones = [_resolve(x, ns) for x in chain.get("bones", [])]
    sw_node, sw_attr = _resolve(chain["switch"]["node"], ns), chain["switch"]["attr"]
    attr_path = f"{sw_node}.{sw_attr}"

    if not fk_ctrls or not bones or not cmds.objExists(attr_path): 
        cmds.warning("[ASEPicker] Missing FK controls, Bones, or Switch Attr.")
        return

    cmds.undoInfo(openChunk=True)
    cmds.refresh(suspend=True) # <--- MAGIC: FREEZE THE SCREEN!
    try:
        # 1. Capture the exact World Matrices of the IK pose
        target_matrices = [cmds.xform(b, q=True, ws=True, matrix=True) for b in bones]

        # 2. FLIP THE SWITCH (Restores native FK alignments)
        cmds.setAttr(attr_path, chain["switch"]["fk_val"])
        if key: cmds.setKeyframe(attr_path)

        # 3. TOP-DOWN EVALUATION
        for ctrl, bone, goal_mat in zip(fk_ctrls, bones, target_matrices):
            if not cmds.objExists(ctrl) or not cmds.objExists(bone): continue

            # Calculate exact offset of control relative to the bone
            c_mat = om.MMatrix(cmds.xform(ctrl, q=True, ws=True, matrix=True))
            b_mat = om.MMatrix(cmds.xform(bone, q=True, ws=True, matrix=True))
            offset = c_mat * b_mat.inverse()

            # Apply offset to the target goal
            target_c_mat = offset * om.MMatrix(goal_mat)

            # Safely apply via temp locator (respects locked channels)
            temp_loc = cmds.spaceLocator()[0]
            cmds.xform(temp_loc, ws=True, matrix=list(target_c_mat))
            cmds.matchTransform(ctrl, temp_loc, pos=True, rot=True)
            
            # FK controls strictly rely on parent translation, so zero it out
            for axis in ["tx", "ty", "tz"]:
                if not cmds.getAttr(f"{ctrl}.{axis}", lock=True):
                    cmds.setAttr(f"{ctrl}.{axis}", 0.0)

            if key: cmds.setKeyframe(ctrl, at=["rotate", "translate"])
            cmds.delete(temp_loc)
            
            # The math evaluates in the background, but the screen stays frozen!
            cmds.refresh() 

        if key: cmds.filterCurve(fk_ctrls, filter="euler")

    except Exception as e:
        cmds.warning(f"[ASEPicker] IK->FK Snap Error: {e}")
    finally:
        cmds.refresh(suspend=False) # <--- MAGIC: UNFREEZE THE SCREEN!
        cmds.refresh(force=True)    # <--- MAGIC: INSTANTLY DRAW FINAL POSE!
        cmds.undoInfo(closeChunk=True)


def switch_to_ik(chain, ns, key=True):
    """
    RIG IS IN FK. We snap IK and PV controls to match the FK pose.
    """
    ik_ctrl = _resolve(chain.get("ik_ctrl", ""), ns)
    pv_ctrl = _resolve(chain.get("pv_ctrl", ""), ns)
    bones = [_resolve(x, ns) for x in chain.get("bones", [])]
    sw_node, sw_attr = _resolve(chain["switch"]["node"], ns), chain["switch"]["attr"]
    attr_path = f"{sw_node}.{sw_attr}"

    if not ik_ctrl or len(bones) < 3 or not cmds.objExists(attr_path): 
        cmds.warning("[ASEPicker] Missing IK Control, Bones, or Switch Attr.")
        return

    cmds.undoInfo(openChunk=True)
    cmds.refresh(suspend=True) # <--- MAGIC: FREEZE THE SCREEN!
    try:
        # 1. Capture the exact World Matrices/Positions of the FK pose
        wrist_goal_mat = cmds.xform(bones[-1], q=True, ws=True, matrix=True)
        shoulder_pos = om.MVector(cmds.xform(bones[0], q=True, ws=True, t=True))
        elbow_pos = om.MVector(cmds.xform(bones[1], q=True, ws=True, t=True))
        wrist_pos = om.MVector(cmds.xform(bones[-1], q=True, ws=True, t=True))

        # 2. FLIP THE SWITCH
        cmds.setAttr(attr_path, chain["switch"]["ik_val"])
        if key: cmds.setKeyframe(attr_path)

        # 3. Snap IK Wrist using Matrix Offset
        c_mat = om.MMatrix(cmds.xform(ik_ctrl, q=True, ws=True, matrix=True))
        b_mat = om.MMatrix(cmds.xform(bones[-1], q=True, ws=True, matrix=True))
        offset = c_mat * b_mat.inverse()
        target_mat = offset * om.MMatrix(wrist_goal_mat)

        temp_loc = cmds.spaceLocator()[0]
        cmds.xform(temp_loc, ws=True, matrix=list(target_mat))
        cmds.matchTransform(ik_ctrl, temp_loc, pos=True, rot=True)
        if key: cmds.setKeyframe(ik_ctrl, at=["translate", "rotate"])
        cmds.delete(temp_loc)
        
        cmds.refresh()

        # 4. Snap Pole Vector using Triangulation against the captured FK positions
        if pv_ctrl:
            AC = wrist_pos - shoulder_pos
            AB = elbow_pos - shoulder_pos
            
            if AC.length() > 0.001:
                proj = AB * (AC.normal())
                center = shoulder_pos + (AC.normal() * proj)
                pv_dir = (elbow_pos - center).normal()
                
                if pv_dir.length() > 0.001:
                    dist = (elbow_pos - shoulder_pos).length() * 1.5
                    pv_final_pos = elbow_pos + (pv_dir * dist)
                    
                    temp_pv_loc = cmds.spaceLocator()[0]
                    cmds.xform(temp_pv_loc, ws=True, t=(pv_final_pos.x, pv_final_pos.y, pv_final_pos.z))
                    cmds.matchTransform(pv_ctrl, temp_pv_loc, pos=True, rot=False)
                    cmds.delete(temp_pv_loc)
                    if key: cmds.setKeyframe(pv_ctrl, at=["translate"])

        if key: cmds.filterCurve([ik_ctrl], filter="euler")

    except Exception as e:
        cmds.warning(f"[ASEPicker] FK->IK Snap Error: {e}")
    finally:
        cmds.refresh(suspend=False) # <--- MAGIC: UNFREEZE THE SCREEN!
        cmds.refresh(force=True)    # <--- MAGIC: INSTANTLY DRAW FINAL POSE!
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