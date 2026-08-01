# ARTools/anim/logic_ikfk.py
from maya import cmds
import maya.api.OpenMaya as om
import uuid

def _resolve(node, ns):
    """Safely applies the namespace, automatically cleaning old hardcoded namespaces."""
    if not node: return ""
    
    # --- 1: Strip any hardcoded namespace just in case the user saved it wrong previously! ---
    clean_node = node.split(":")[-1]
    if ns: return f"{ns}:{clean_node}"
    return clean_node

# =====================================================================
# THE BATCH MATCHING ENGINE (CONCURRENT, HIGHSPEED, TANGENT-SAFE)
# =====================================================================

def batch_switch(chains, target_mode, ns, key=True, time_mode="Current Frame", bake_mode="Existing Keys Only"):
    import maya.mel as mel
    
    # 1. Resolve all nodes and gather Master Keylist Targets
    all_nodes = set()
    resolved_chains = []
    for chain in chains:
        ik_ctrl = _resolve(chain.get("ik_ctrl", ""), ns)
        pv_ctrl = _resolve(chain.get("pv_ctrl", ""), ns)
        fk_ctrls = [_resolve(x, ns) for x in chain.get("fk_ctrls", [])]
        bones = [_resolve(x, ns) for x in chain.get("bones", [])]
        
        sw_node = _resolve(chain["switch"]["node"], ns)
        sw_attr = chain["switch"]["attr"].split(".")[-1]
        attr_path = f"{sw_node}.{sw_attr}"
        
        # Validate Chain Completeness
        if target_mode == "to_ik":
            if not ik_ctrl or len(bones) < 3 or not cmds.objExists(attr_path): continue
            all_nodes.update([ik_ctrl])
            if pv_ctrl: all_nodes.add(pv_ctrl)
            all_nodes.update(fk_ctrls)
        else:
            if not fk_ctrls or not bones or not cmds.objExists(attr_path): continue
            all_nodes.update(fk_ctrls)
            all_nodes.update([ik_ctrl])
            if pv_ctrl: all_nodes.add(pv_ctrl)
            
        all_nodes.add(sw_node)
        
        resolved_chains.append({
            "ik_ctrl": ik_ctrl, "pv_ctrl": pv_ctrl, "fk_ctrls": fk_ctrls, "bones": bones,
            "sw_node": sw_node, "sw_attr": sw_attr, "attr_path": attr_path,
            "ik_val": chain["switch"]["ik_val"], "fk_val": chain["switch"]["fk_val"]
        })
        
    if not resolved_chains: return
    valid_nodes = [n for n in all_nodes if cmds.objExists(n)]
    
    # 2. Time Range Setup
    start_t = end_t = cmds.currentTime(q=True)
    is_range = False
    
    if time_mode == "Time Slider Selection":
        try:
            a_time_slider = mel.eval('$tmpVar=$gPlayBackSlider')
            if cmds.timeControl(a_time_slider, q=True, rangeVisible=True):
                tr = cmds.timeControl(a_time_slider, q=True, rangeArray=True)
                if tr and (tr[1] - tr[0]) > 1:
                    start_t, end_t = tr[0], tr[1] - 1
                    is_range = True
        except: pass
    elif time_mode == "Entire Time Slider":
        start_t = cmds.playbackOptions(q=True, minTime=True)
        end_t = cmds.playbackOptions(q=True, maxTime=True)
        is_range = True

    # 3. Master Keylist Generation
    frames = []
    if not is_range:
        frames = [float(start_t)]
    elif bake_mode == "Existing Keys Only":
        key_times = cmds.keyframe(valid_nodes, q=True, time=(start_t, end_t)) or []
        if key_times: frames = sorted(list(set([float(t) for t in key_times])))
        else: frames = [float(start_t)]
    elif bake_mode == "Bake on 2s":
        frames = [float(f) for f in range(int(start_t), int(end_t) + 1, 2)]
    else:
        frames = [float(f) for f in range(int(start_t), int(end_t) + 1)]

    # 4. Tangent Caching Engine
    tangent_cache = {} 
    if key and is_range:
        for f in frames:
            tangent_cache[f] = {}
            for node in valid_nodes:
                for attr in ["translate", "rotate"]:
                    for axis in ["X", "Y", "Z"]:
                        plug = f"{node}.{attr}{axis}"
                        if cmds.keyframe(plug, q=True, time=(f, f), keyframeCount=True):
                            itt = cmds.keyTangent(plug, q=True, time=(f, f), itt=True)
                            ott = cmds.keyTangent(plug, q=True, time=(f, f), ott=True)
                            if itt and ott: tangent_cache[f][plug] = (itt[0], ott[0])

    # 5. Core Execution Loop
    cmds.undoInfo(openChunk=True, chunkName="ARTools_IKFKBake")
    
    if is_range:
        cmds.refresh(suspend=True)
        current_eval_mode = cmds.evaluationManager(q=True, mode=True)[0]
        if current_eval_mode != "off": cmds.evaluationManager(mode='off')
        main_pane = mel.eval('global string $gMainPane; $tmp = $gMainPane;') 
        if main_pane and cmds.paneLayout(main_pane, exists=True):
            cmds.paneLayout(main_pane, edit=True, manage=False)

    try:
        for f in frames:
            if is_range: cmds.currentTime(f)
            
            for chain in resolved_chains:
                if target_mode == "to_ik": _process_ik_frame(chain, key, is_range)
                else: _process_fk_frame(chain, key, is_range)
                    
            # Restore Preserved Tangents
            if key and is_range and f in tangent_cache:
                for plug, (itt, ott) in tangent_cache[f].items():
                    if cmds.keyframe(plug, q=True, time=(f, f), keyframeCount=True):
                        cmds.keyTangent(plug, time=(f, f), itt=itt, ott=ott)

        # 6. Auto-Gimbal Rescue (Euler Filter)
        if key and is_range:
            for node in valid_nodes:
                rot_curves = [f"{node}.rotate{x}" for x in "XYZ"]
                valid_rot = [c for c in rot_curves if cmds.objExists(c) and not cmds.getAttr(c, lock=True)]
                if valid_rot:
                    try: cmds.filterCurve(valid_rot)
                    except: pass

    except Exception as e:
        cmds.warning(f"[ARTools] IK/FK Match Error: {e}")
    finally:
        if is_range:
            if current_eval_mode != "off": cmds.evaluationManager(mode=current_eval_mode)
            if main_pane and cmds.paneLayout(main_pane, exists=True):
                cmds.paneLayout(main_pane, edit=True, manage=True)
            cmds.refresh(suspend=False)
            cmds.refresh(force=True)
        cmds.undoInfo(closeChunk=True)
        
        if is_range: cmds.inViewMessage(amg=f"IK/FK Baked ({len(frames)} frames)", pos="midCenter", fade=True)
        else: cmds.inViewMessage(amg="IK/FK Matched", pos="midCenter", fade=True)


def _process_fk_frame(chain, key, is_range):
    fk_ctrls = chain["fk_ctrls"]
    bones = chain["bones"]
    attr_path = chain["attr_path"]
    
    target_locs = []
    for b in bones:
        loc = cmds.spaceLocator()[0]
        cmds.matchTransform(loc, b, pos=True, rot=True)
        target_locs.append(loc)

    cmds.setAttr(attr_path, chain["fk_val"])
    if key and (is_range or cmds.autoKeyframe(q=True, state=True) or cmds.keyframe(attr_path, q=True, keyframeCount=True)): 
        cmds.setKeyframe(attr_path)

    for ctrl, bone, goal_loc in zip(fk_ctrls, bones, target_locs):
        if not cmds.objExists(ctrl) or not cmds.objExists(bone): continue

        loc_b = cmds.spaceLocator()[0]
        loc_c = cmds.spaceLocator()[0]
        
        cmds.matchTransform(loc_b, bone, pos=True, rot=True)
        cmds.matchTransform(loc_c, ctrl, pos=True, rot=True)
        cmds.parent(loc_c, loc_b)
        cmds.matchTransform(loc_b, goal_loc, pos=True, rot=True)
        cmds.matchTransform(ctrl, loc_c, pos=True, rot=True)
        cmds.delete(loc_b)
        
        for axis in ["tx", "ty", "tz"]:
            if not cmds.getAttr(f"{ctrl}.{axis}", lock=True):
                cmds.setAttr(f"{ctrl}.{axis}", 0.0)

        if key and (is_range or cmds.autoKeyframe(q=True, state=True) or cmds.keyframe(ctrl, at=["rotate", "translate"], q=True, keyframeCount=True)): 
            cmds.setKeyframe(ctrl, at=["rotate", "translate"])

    cmds.delete(target_locs)
    if not is_range and key: cmds.filterCurve(fk_ctrls, filter="euler")


def _process_ik_frame(chain, key, is_range):
    ik_ctrl = chain["ik_ctrl"]
    pv_ctrl = chain["pv_ctrl"]
    bones = chain["bones"]
    attr_path = chain["attr_path"]
    
    goal_loc = cmds.spaceLocator()[0]
    cmds.matchTransform(goal_loc, bones[-1], pos=True, rot=True)
    
    start = om.MVector(cmds.xform(bones[0], q=True, ws=True, rp=True))
    mid = om.MVector(cmds.xform(bones[1], q=True, ws=True, rp=True))
    end = om.MVector(cmds.xform(bones[-1], q=True, ws=True, rp=True))

    cmds.setAttr(attr_path, chain["ik_val"])
    if key and (is_range or cmds.autoKeyframe(q=True, state=True) or cmds.keyframe(attr_path, q=True, keyframeCount=True)): 
        cmds.setKeyframe(attr_path)

    if cmds.objExists(ik_ctrl): cmds.getAttr(f"{ik_ctrl}.worldMatrix[0]")
    if pv_ctrl and cmds.objExists(pv_ctrl): cmds.getAttr(f"{pv_ctrl}.worldMatrix[0]")

    cmds.matchTransform(ik_ctrl, goal_loc, pos=True, rot=True)
    if cmds.objExists(ik_ctrl): cmds.getAttr(f"{ik_ctrl}.worldMatrix[0]")

    loc_b = cmds.spaceLocator()[0]
    loc_c = cmds.spaceLocator()[0]
    cmds.matchTransform(loc_b, bones[-1], pos=True, rot=True)
    cmds.matchTransform(loc_c, ik_ctrl, pos=True, rot=True)
    cmds.parent(loc_c, loc_b)
    
    cmds.matchTransform(loc_b, goal_loc, pos=True, rot=True)
    cmds.matchTransform(ik_ctrl, loc_c, pos=True, rot=True)
    cmds.delete([loc_b, goal_loc]) 
    
    if key and (is_range or cmds.autoKeyframe(q=True, state=True) or cmds.keyframe(ik_ctrl, at=["translate", "rotate"], q=True, keyframeCount=True)): 
        cmds.setKeyframe(ik_ctrl, at=["translate", "rotate"])
    
    if cmds.objExists(ik_ctrl): cmds.getAttr(f"{ik_ctrl}.worldMatrix[0]")
    if pv_ctrl and cmds.objExists(pv_ctrl): cmds.getAttr(f"{pv_ctrl}.worldMatrix[0]")

    if pv_ctrl:
        v1 = (start - mid).normal()
        v2 = (end - mid).normal()
        bisector = (v1 + v2).normal()
        pv_dir = -bisector
        
        if pv_dir.length() < 0.001: pv_dir = om.MVector(0,0,1) 
            
        current_pv = om.MVector(cmds.xform(pv_ctrl, q=True, ws=True, rp=True))
        current_dist = (current_pv - mid).length()
        if current_dist < 0.1: current_dist = 5.0
            
        pv_final_pos = mid + (pv_dir * current_dist)
        
        temp_pv = cmds.spaceLocator()[0]
        cmds.xform(temp_pv, ws=True, t=(pv_final_pos.x, pv_final_pos.y, pv_final_pos.z))
        cmds.matchTransform(pv_ctrl, temp_pv, pos=True, rot=False)
        cmds.delete(temp_pv)
        if key and (is_range or cmds.autoKeyframe(q=True, state=True) or cmds.keyframe(pv_ctrl, at=["translate"], q=True, keyframeCount=True)): 
            cmds.setKeyframe(pv_ctrl, at=["translate"])

    if not is_range and key: cmds.filterCurve([ik_ctrl], filter="euler")

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