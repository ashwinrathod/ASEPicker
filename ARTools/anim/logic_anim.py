# ARTools/anim/logic_anim.py
from maya import cmds
from collections import defaultdict
import maya.mel as mel
import maya.api.OpenMaya as om
from . import clipboard
from . import snapshot

def get_time_range():
    """Returns (start, end) if range selected, else (None, None)."""
    try:
        gPlayBackSlider = mel.eval('$tmpVar=$gPlayBackSlider')
        if cmds.timeControl(gPlayBackSlider, q=True, rangeVisible=True):
            highlight = cmds.timeControl(gPlayBackSlider, q=True, rangeArray=True)
            if highlight and (highlight[1] - highlight[0]) > 1:
                return (highlight[0], highlight[1] - 1)
    except:
        pass
    return (None, None)

def _get_dominant_tangent(types):
    """Helper to decide best tangent type for world space transfer."""
    if not types: return "auto"
    if "step" in types: return "step" # Priority 1: Blocking
    if all(x == "linear" for x in types): return "linear" # Priority 2: Mechanical
    return "auto" # Fallback: Allow Maya to smooth new values

def copy_anim(global_space=False, custom_range=None):
    """
    Saves animation data to clipboard.
    Global: Saves World Matrix + Tangent Types.
    Local: Saves Exact Attribute Values + Tangent Angles & Weights.
    """
    nodes = cmds.ls(sl=True, long=True)
    if not nodes: return

    if custom_range:
        start, end = custom_range
    else:
        start, end = get_time_range()

    file_name = "anim_global" if global_space else "anim_local"
    data = {}
    
    ns = ""
    short_first = nodes[0].split("|")[-1]
    if ":" in short_first:
        ns = short_first.rsplit(":", 1)[0]
    data["__namespace__"] = ns

    if global_space:
        # --- Copy World Space (Matrix + Tangent Type) ---
        sel_list = om.MSelectionList()
        time_batch = {}
        
        for node in nodes:
            sel_list.add(node)
            node_idx = sel_list.length() - 1
            short = node.split("|")[-1].split(":")[-1]
            data[short] = {} 

            curves = cmds.keyframe(node, at=["translate", "rotate"], q=True, name=True) or []
            node_times = set()
            if curves:
                if start is not None:
                    times = cmds.keyframe(curves, q=True, time=(start, end)) or []
                else:
                    times = cmds.keyframe(curves, q=True) or []
                for t in times: node_times.add(t)
            
            for t in node_times:
                if t not in time_batch: time_batch[t] = []
                
                # We can only copy Tangent Type for world (Stepped, Spline, etc.)
                itt = cmds.keyTangent(node, time=(t,t), q=True, itt=True) or []
                ott = cmds.keyTangent(node, time=(t,t), q=True, ott=True) or []
                
                # Use dominant tangent to avoid artifacts (e.g. one Linear channel breaking Flow)
                t_in = _get_dominant_tangent(itt)
                t_out = _get_dominant_tangent(ott)
                
                time_batch[t].append((node_idx, short, t_in, t_out))

        sorted_times = sorted(time_batch.keys())
        for t_val in sorted_times:
            time_obj = om.MTime(t_val)
            context = om.MDGContext(time_obj)

            for node_idx, short, t_in, t_out in time_batch[t_val]:
                m_obj = sel_list.getDependNode(node_idx)
                fn_node = om.MFnDependencyNode(m_obj)
                
                plug_wm = fn_node.findPlug("worldMatrix", False).elementByLogicalIndex(0)
                m_obj_mat = plug_wm.asMObject(context)
                fn_mat = om.MFnMatrixData(m_obj_mat)
                
                data[short][str(t_val)] = {
                    "m": list(fn_mat.matrix()),
                    "ti": t_in,
                    "to": t_out
                }
        
        clipboard.save_data(data, file_name)

    else:
        # --- Copy Local Space (Exact Tangent Matching) ---
        # [Existing Local Copy code remains unchanged...]
        for node in nodes:
            short = node.split("|")[-1].split(":")[-1]
            anim_data = {}
            
            attrs = cmds.listAttr(node, keyable=True) or []
            
            for attr in attrs:
                full_attr = "{}.{}".format(node, attr)
                
                if not cmds.keyframe(full_attr, q=True, keyframeCount=True):
                    continue
                
                kwargs = {}
                if start is not None: kwargs['time'] = (start, end)
                
                times = cmds.keyframe(full_attr, q=True, **kwargs) or []
                if not times: continue
                
                values = cmds.keyframe(full_attr, q=True, valueChange=True, **kwargs) or []
                
                itt = cmds.keyTangent(full_attr, q=True, itt=True, **kwargs) or []
                ott = cmds.keyTangent(full_attr, q=True, ott=True, **kwargs) or []
                ia  = cmds.keyTangent(full_attr, q=True, ia=True, **kwargs) or []
                oa  = cmds.keyTangent(full_attr, q=True, oa=True, **kwargs) or []
                wt  = cmds.keyTangent(full_attr, q=True, wt=True, **kwargs) or []
                iw  = cmds.keyTangent(full_attr, q=True, iw=True, **kwargs) or []
                ow  = cmds.keyTangent(full_attr, q=True, ow=True, **kwargs) or []

                anim_data[attr] = {
                    'times': times, 'values': values,
                    'itt': itt, 'ott': ott,
                    'ia': ia, 'oa': oa, 
                    'iw': iw, 'ow': ow, 
                    'wt': wt
                }
            
            if anim_data:
                data[short] = anim_data
                
        clipboard.save_data(data, file_name)
    
    cmds.inViewMessage(amg="Animation Copied", pos="midCenter", fade=True)

def paste_anim(global_space=False, namespace="", paste_method="replace"):
    ftype = "anim_global" if global_space else "anim_local"
    data = clipboard.load_data(ftype)
    if not data: 
        cmds.warning("No animation data found.")
        return

    if namespace is None:
        namespace = data.get("__namespace__", "")

    targets = cmds.ls(sl=True, long=True)
    if not targets and namespace:
        for short in data.keys():
            if short == "__namespace__": continue
            full = f"{namespace}:{short}" if namespace else short
            if cmds.objExists(full): targets.append(full)
    if not targets: 
        cmds.warning("No targets found.")
        return

    # Calculate Time Offset
    time_offset = 0.0
    if paste_method == "current":
        first_frame = 99999999.0
        if global_space:
            for k, d in data.items():
                if k == "__namespace__": continue
                frames = [float(f_str) for f_str in d.keys()]
                if frames: first_frame = min(first_frame, min(frames))
        else:
            for k, d in data.items():
                if k == "__namespace__": continue
                for attr_data in d.values():
                    if isinstance(attr_data, dict) and 'times' in attr_data:
                        t_list = attr_data['times']
                        if t_list: first_frame = min(first_frame, t_list[0])
                    elif isinstance(attr_data, list) and attr_data:
                        first_frame = min(first_frame, attr_data[0][0])
        
        current_time = cmds.currentTime(q=True)
        if first_frame < 99999990.0: 
            time_offset = current_time - first_frame

    # --- SPEED PREP ---
    cmds.undoInfo(openChunk=True)
    
    # 1. Freeze Viewport
    cmds.refresh(suspend=True)
    
    # 2. Freeze Panel UI (prevents timeline redraw)
    main_pane = mel.eval('global string $gMainPane; $tmp = $gMainPane;') 
    if main_pane and cmds.paneLayout(main_pane, exists=True):
        cmds.paneLayout(main_pane, edit=True, manage=False)

    # 3. Disable Evaluation Manager (CRITICAL FOR SPEED)
    # This stops Maya from calculating deformations when we change time
    current_eval_mode = cmds.evaluationManager(q=True, mode=True)[0]
    if current_eval_mode != "off":
        cmds.evaluationManager(mode='off')

    try:
        if global_space:
            # --- WORLD SPACE (Direct Matrix + Key) ---
            # Group data by frame to minimize time changes
            frame_map = {}
            for node in targets:
                short = node.split("|")[-1].split(":")[-1]
                if short in data and short != "__namespace__":
                    for t_str, content in data[short].items():
                        t = float(t_str)
                        if t not in frame_map: frame_map[t] = []
                        if isinstance(content, dict):
                            frame_map[t].append((node, content["m"], content.get("ti", "auto"), content.get("to", "auto")))
                        else:
                            frame_map[t].append((node, content, "auto", "auto"))
            
            sorted_frames = sorted(frame_map.keys())
            if sorted_frames:
                # Clear keys first (range)
                min_t = sorted_frames[0] + time_offset
                max_t = sorted_frames[-1] + time_offset
                for node in targets:
                    cmds.cutKey(node, time=(min_t, max_t), at=["translate", "rotate"], clear=True)

                # Set Keys Frame by Frame
                for t in sorted_frames:
                    target_t = t + time_offset
                    cmds.currentTime(target_t) # Fast now because Eval Manager is OFF
                    
                    for node, mat, ti, to in frame_map[t]:
                        cmds.xform(node, ws=True, matrix=mat)
                        cmds.setKeyframe(node, at=["translate", "rotate"])
                        cmds.keyTangent(node, at=["translate", "rotate"], time=(target_t, target_t), itt=ti, ott=to)
                
                # Cleanup
                for node in targets:
                    rot_curves = [f"{node}.rotate{x}" for x in "XYZ"]
                    valid_rot = [c for c in rot_curves if cmds.objExists(c) and not cmds.getAttr(c, lock=True)]
                    if valid_rot:
                        try: cmds.filterCurve(valid_rot)
                        except: pass
                    
                    # Remove weights to prevent overshoot on baked keys
                    all_curves = rot_curves + [f"{node}.translate{x}" for x in "XYZ"]
                    cmds.keyTangent(all_curves, edit=True, weightedTangents=False)

        else:
            # --- LOCAL SPACE (Data-Only) ---
            # Already fast (no timeline scrubbing), but benefits from suspended refresh
            for node in targets:
                short = node.split("|")[-1].split(":")[-1]
                if short not in data or short == "__namespace__": continue
                node_data = data[short]
                rot_attrs_touched = False
                
                for attr, curve_data in node_data.items():
                    full_attr = f"{node}.{attr}"
                    if not cmds.objExists(full_attr): continue
                    if not cmds.getAttr(full_attr, settable=True): continue
                    if cmds.getAttr(full_attr, lock=True): continue

                    if isinstance(curve_data, dict):
                        times = curve_data.get('times', [])
                        values = curve_data.get('values', [])
                        itt = curve_data.get('itt', [])
                        ott = curve_data.get('ott', [])
                        wt = curve_data.get('wt', [])
                        ia = curve_data.get('ia', [])
                        oa = curve_data.get('oa', [])
                        iw = curve_data.get('iw', [])
                        ow = curve_data.get('ow', [])
                    else:
                        times = [p[0] for p in curve_data]
                        values = [p[1] for p in curve_data]
                        itt = ott = wt = ia = oa = iw = ow = []

                    if not times: continue
                    target_times = [t + time_offset for t in times]
                    
                    min_t = min(target_times)
                    max_t = max(target_times)
                    cmds.cutKey(full_attr, time=(min_t, max_t), clear=True)

                    # Batch key setting isn't easily possible with varying values, 
                    # but since we don't scrub time, this loop is fast.
                    for i, t in enumerate(target_times):
                        cmds.setKeyframe(full_attr, time=(t,t), value=values[i])
                        
                        if itt and ott:
                            # Apply Tangents
                            try:
                                c_itt = itt[i] if i < len(itt) else "auto"
                                c_ott = ott[i] if i < len(ott) else "auto"
                                c_wt = wt[i] if i < len(wt) else False
                                
                                cmds.keyTangent(full_attr, time=(t,t), itt=c_itt, ott=c_ott)
                                
                                if c_wt:
                                    c_ia = ia[i] if i < len(ia) else 0
                                    c_oa = oa[i] if i < len(oa) else 0
                                    c_iw = iw[i] if i < len(iw) else 1
                                    c_ow = ow[i] if i < len(ow) else 1
                                    cmds.keyTangent(full_attr, time=(t,t), edit=True, weightedTangents=True)
                                    cmds.keyTangent(full_attr, time=(t,t), edit=True, absolute=True, 
                                                    ia=c_ia, oa=c_oa, iw=c_iw, ow=c_ow)
                                else:
                                    cmds.keyTangent(full_attr, time=(t,t), edit=True, weightedTangents=False)
                            except: pass
                    
                    if "rotate" in attr: rot_attrs_touched = True

                if rot_attrs_touched:
                    rot_curves = [f"{node}.rotate{x}" for x in "XYZ" if cmds.objExists(f"{node}.rotate{x}")]
                    valid = [c for c in rot_curves if not cmds.getAttr(c, lock=True)]
                    if valid:
                        try: cmds.filterCurve(valid)
                        except: pass

    except Exception as e:
        cmds.warning(f"Paste Error: {e}")
    finally:
        # --- RESTORE ---
        if current_eval_mode != "off":
            cmds.evaluationManager(mode=current_eval_mode)
        
        main_pane = mel.eval('global string $gMainPane; $tmp = $gMainPane;')
        if main_pane and cmds.paneLayout(main_pane, exists=True):
            cmds.paneLayout(main_pane, edit=True, manage=True)
            
        cmds.refresh(suspend=False)
        cmds.refresh(force=True)
        cmds.undoInfo(closeChunk=True)
        cmds.inViewMessage(amg="Animation Pasted", pos="midCenter", fade=True)

# Legacy implementation kept only for reference.
# The active runtime mirror entry point is the later `mirror_anim(...)` below.
def _legacy_mirror_anim(namespace, mode="swap", pivot=None):
    snap = snapshot.load_snapshot(namespace)
    if not snap:
        cmds.warning("No snapshot found.")
        return

    pivot_offset = 0.0
    if pivot and cmds.objExists(pivot):
        pivot_offset = cmds.xform(pivot, q=True, ws=True, t=True)[0] * 2.0

    nodes = cmds.ls(sl=True, long=True)
    is_selection_mode = bool(nodes)

    if not nodes and namespace:
        nodes = cmds.ls(f"{namespace}:*", type="transform", long=True)

    if not nodes: return
    
    start, end = get_time_range()
    prefix = namespace + ":" if namespace and not namespace.endswith(":") else namespace

    buffer_curves = {}
    controls_to_read = set()
    
    for node in nodes:
        short = node.split("|")[-1].split(":")[-1]
        info = snap["controls"].get(short)
        if not info: continue
        
        if is_selection_mode:
            controls_to_read.add(short)
        else:
            controls_to_read.add(short)
            if info.get("mirror"):
                controls_to_read.add(info["mirror"])

    for short in controls_to_read:
        full = f"{prefix}{short}"
        if not cmds.objExists(full): continue
        
        node_curves = {}
        attrs = cmds.listAttr(full, keyable=True) or []
        for attr in attrs:
            if cmds.keyframe(f"{full}.{attr}", q=True, keyframeCount=True):
                if start is not None:
                    times = cmds.keyframe(f"{full}.{attr}", q=True, time=(start, end))
                    values = cmds.keyframe(f"{full}.{attr}", q=True, valueChange=True, time=(start, end))
                else:
                    times = cmds.keyframe(f"{full}.{attr}", q=True)
                    values = cmds.keyframe(f"{full}.{attr}", q=True, valueChange=True)
                
                if times:
                    node_curves[attr] = list(zip(times, values))
        
        buffer_curves[short] = node_curves

    cmds.refresh(suspend=True)
    current_eval_mode = cmds.evaluationManager(q=True, mode=True)[0]
    if current_eval_mode != "off": cmds.evaluationManager(mode='off')
    cmds.undoInfo(openChunk=True)
    try:
        for node in nodes:
            dst_short = node.split("|")[-1].split(":")[-1]
            dst_info = snap["controls"].get(dst_short)
            if not dst_info: continue

            side = dst_info.get("side", "Center")
            partner_short = dst_info.get("mirror")
            
            src_short = None
            if is_selection_mode:
                if side == "Center":
                    src_short = dst_short
                    dst_full = node
                else:
                    if not partner_short: continue
                    src_short = dst_short
                    dst_full = f"{prefix}{partner_short}"
            else:
                dst_full = node
                if side == "Center":
                    src_short = dst_short
                elif mode == "l2r":
                    if side == "Left": continue
                    src_short = partner_short
                elif mode == "r2l":
                    if side == "Right": continue
                    src_short = partner_short
                else: 
                    src_short = partner_short

            if not src_short or src_short not in buffer_curves: continue
            if not cmds.objExists(dst_full): continue

            rules_info = dst_info if side == "Left" or side == "Center" else snap["controls"].get(partner_short)
            if not rules_info: rules_info = dst_info
            
            rules = rules_info.get("mirror_rules", {})
            t_mult = rules.get("translate", [1,1,1])
            r_mult = rules.get("rotate", [1,1,1])

            src_data = buffer_curves[src_short]
            
            for attr, keys in src_data.items():
                scale = 1.0
                if attr in ("translateX", "tx"): scale = t_mult[0]
                elif attr in ("translateY", "ty"): scale = t_mult[1]
                elif attr in ("translateZ", "tz"): scale = t_mult[2]
                elif attr in ("rotateX", "rx"): scale = r_mult[0]
                elif attr in ("rotateY", "ry"): scale = r_mult[1]
                elif attr in ("rotateZ", "rz"): scale = r_mult[2]

                if start is not None:
                    cmds.cutKey(f"{dst_full}.{attr}", time=(start, end), clear=True)
                else:
                    cmds.cutKey(f"{dst_full}.{attr}", clear=True)

                for t, v in keys:
                    val = v * scale
                    
                    if pivot_offset != 0.0 and attr in ("translateX", "tx"):
                        val += pivot_offset

                    cmds.setKeyframe(f"{dst_full}.{attr}", time=t, value=val)
    except Exception as e:
        print(f"[ARTools] Mirror Anim Error: {e}")
    finally:
        if current_eval_mode != "off": cmds.evaluationManager(mode=current_eval_mode)
        cmds.refresh(suspend=False)
        cmds.undoInfo(closeChunk=True)

import maya.cmds as cmds
import json

# -------------------------------------------------------------------------
# CORE LIBRARY APPLICATION LOGIC
# -------------------------------------------------------------------------

def apply_library_item(anim_data, settings, target_ns=""):
    """
    Applies animation data.
    OPTIMIZED: Uses batched frame updates for World Space to prevent timeline scrubbing lag.
    """
    # 0. Data Unwrap
    if "data" in anim_data and isinstance(anim_data["data"], dict):
        anim_data = anim_data["data"]

    # 1. Namespace Check
    if target_ns:
        if not cmds.namespace(exists=target_ns) and not cmds.namespace(exists=":" + target_ns):
            pass

    # 2. Extract Options
    mirror = settings.get("mirror", False)
    mirror_mode = settings.get("mirror_mode", "swap")
    paste_method = settings.get("paste_method", "Replace")
    paste_time = settings.get("paste_time", "original")
    
    start_opt = settings.get("start_frame", 0)
    end_opt = settings.get("end_frame", 0)
    use_range = (start_opt != 0 or end_opt != 0)

    # 3. Detect Data Type (World vs Local)
    is_world = False
    for node_content in anim_data.values():
        if isinstance(node_content, dict) and node_content:
            first_key = next(iter(node_content), "")
            try:
                float(first_key)
                is_world = True; break
            except ValueError:
                is_world = False; break

    # 4. Calculate Offset
    offset = 0
    if paste_time == "current":
        first_frame = None
        if is_world:
            for k, frames in anim_data.items():
                if k == "__namespace__": continue
                for f_str in frames.keys():
                    try:
                        t = float(f_str)
                        if first_frame is None or t < first_frame: first_frame = t
                    except: pass
        else:
            for k, attrs in anim_data.items():
                if k == "__namespace__": continue
                for data in attrs.values():
                    if isinstance(data, dict):
                        ts = data.get("times")
                        if ts:
                            min_t = min(ts)
                            if first_frame is None or min_t < first_frame: first_frame = min_t
                    elif isinstance(data, list):
                        for p in data:
                            if first_frame is None or p[0] < first_frame: first_frame = p[0]
        
        if first_frame is not None and first_frame < 99999990.0:
            offset = cmds.currentTime(q=True) - first_frame

    # 5. Apply Animation
    
    # --- SPEED PREP ---
    cmds.undoInfo(openChunk=True)
    gMainProgressBar = mel.eval('$tmp = $gMainProgressBar')
    cmds.progressBar(gMainProgressBar, edit=True, beginProgress=True, isInterruptable=True, 
                     status='Applying Animation...', maxValue=len(anim_data))
    
    cmds.scriptEditorInfo(e=True, suppressResults=True, suppressInfo=True, suppressWarnings=True)
    cmds.refresh(suspend=True)

    # Freeze UI Panels
    main_pane = mel.eval('global string $gMainPane; $tmp = $gMainPane;')
    if main_pane and cmds.paneLayout(main_pane, exists=True):
        cmds.paneLayout(main_pane, edit=True, manage=True)

    # Disable Eval
    current_eval_mode = cmds.evaluationManager(q=True, mode=True)[0]
    if current_eval_mode != "off":
        cmds.evaluationManager(mode='off')

    try:
        animated_nodes = []
        
        # Resolve Nodes
        resolved_nodes = {}
        for node_name in anim_data.keys():
            if node_name == "__namespace__": continue
            full_node = f"{target_ns}:{node_name}" if target_ns else node_name
            if not cmds.objExists(full_node):
                if cmds.objExists(node_name): full_node = node_name
                else: continue
            resolved_nodes[node_name] = full_node
            animated_nodes.append(full_node)

        if not resolved_nodes:
            cmds.warning("[ARTools] Apply aborted: No matching controls found.")
            return

        if is_world:
            # --- WORLD SPACE (Direct Matrix + Key) ---
            # Pre-calc Frames
            frame_batches = {}
            total_ops = 0
            
            for short, full_node in resolved_nodes.items():
                node_data = anim_data[short]
                for t_str, content in node_data.items():
                    try:
                        t_raw = float(t_str)
                        if use_range and (t_raw < start_opt or t_raw > end_opt): continue
                        
                        if t_raw not in frame_batches: frame_batches[t_raw] = []
                        
                        mat = content.get("m") if isinstance(content, dict) else content
                        if mat:
                            frame_batches[t_raw].append((full_node, mat))
                            total_ops += 1
                    except: pass
            
            sorted_frames = sorted(frame_batches.keys())
            cmds.progressBar(gMainProgressBar, edit=True, maxValue=max(1, len(sorted_frames)))

            # APPLY PER FRAME
            for i, t in enumerate(sorted_frames):
                # Update UI occasionally
                if i % 10 == 0:
                    if cmds.progressBar(gMainProgressBar, query=True, isCancelled=True): break
                    cmds.progressBar(gMainProgressBar, edit=True, step=10)
                
                final_time = t + offset
                cmds.currentTime(final_time)
                
                batch = frame_batches[t]
                for full_node, mat in batch:
                    cmds.xform(full_node, m=mat, ws=True)
                    cmds.setKeyframe(full_node, at=["translate", "rotate"])

        else:
            # --- LOCAL SPACE (Direct Data) ---
            cmds.progressBar(gMainProgressBar, edit=True, maxValue=len(resolved_nodes))
            for i, (short, full_node) in enumerate(resolved_nodes.items()):
                if i % 5 == 0:
                    if cmds.progressBar(gMainProgressBar, query=True, isCancelled=True): break
                    cmds.progressBar(gMainProgressBar, edit=True, step=5)

                node_data = anim_data[short]
                rot_attrs_touched = False
                
                for attr, curve_data in node_data.items():
                    full_attr = f"{full_node}.{attr}"
                    if not cmds.objExists(full_attr): continue
                    try:
                        if not cmds.getAttr(full_attr, settable=True): continue
                        if cmds.getAttr(full_attr, lock=True): continue
                    except: continue

                    if isinstance(curve_data, dict):
                        times = curve_data.get('times', [])
                        values = curve_data.get('values', [])
                        itt = curve_data.get('itt', [])
                        ott = curve_data.get('ott', [])
                        wt = curve_data.get('wt', [])
                        ia = curve_data.get('ia', [])
                        oa = curve_data.get('oa', [])
                        iw = curve_data.get('iw', [])
                        ow = curve_data.get('ow', [])
                    elif isinstance(curve_data, list):
                        times = [p[0] for p in curve_data]
                        values = [p[1] for p in curve_data]
                        itt = ott = wt = ia = oa = iw = ow = []
                    else: continue

                    if not times: continue
                    
                    target_times = [t + offset for t in times]
                    min_t = min(target_times)
                    max_t = max(target_times)
                    
                    if paste_method == "Replace All":
                        cmds.cutKey(full_attr, clear=True)
                    elif paste_method != "Merge":
                        cmds.cutKey(full_attr, time=(min_t, max_t), clear=True)

                    for idx, t in enumerate(target_times):
                        orig_t = times[idx]
                        if use_range and (orig_t < start_opt or orig_t > end_opt): continue

                        cmds.setKeyframe(full_attr, time=(t,t), value=values[idx])
                        
                        # Apply Tangents
                        if itt and ott:
                            try:
                                c_itt = itt[idx] if idx < len(itt) else "auto"
                                c_ott = ott[idx] if idx < len(ott) else "auto"
                                cmds.keyTangent(full_attr, time=(t,t), itt=c_itt, ott=c_ott)
                                
                                c_wt = wt[idx] if idx < len(wt) else False
                                if c_wt:
                                    c_ia = ia[idx] if idx < len(ia) else 0
                                    c_oa = oa[idx] if idx < len(oa) else 0
                                    c_iw = iw[idx] if idx < len(iw) else 1
                                    c_ow = ow[idx] if idx < len(ow) else 1
                                    
                                    cmds.keyTangent(full_attr, time=(t,t), edit=True, weightedTangents=True)
                                    cmds.keyTangent(full_attr, time=(t,t), edit=True, absolute=True, 
                                                    ia=c_ia, oa=c_oa, iw=c_iw, ow=c_ow)
                                else:
                                    cmds.keyTangent(full_attr, time=(t,t), edit=True, weightedTangents=False)
                            except: pass
                    
                    if "rotate" in attr: rot_attrs_touched = True

                if rot_attrs_touched:
                    rot_curves = [f"{full_node}.rotate{x}" for x in "XYZ" if cmds.objExists(f"{full_node}.rotate{x}")]
                    valid = [c for c in rot_curves if not cmds.getAttr(c, lock=True)]
                    if valid:
                        try: cmds.filterCurve(valid)
                        except: pass

        # 6. Mirror Logic
        if mirror and animated_nodes:
            cmds.progressBar(gMainProgressBar, edit=True, status="Mirroring Animation...", maxValue=100)
            cmds.select(animated_nodes)
            mirror_anim(target_ns, mirror_mode)
            cmds.select(animated_nodes) # restore selection

        # Restore
        cmds.scriptEditorInfo(e=True, suppressResults=False, suppressInfo=False, suppressWarnings=False)
        print("[ARTools] Animation Applied.")

    except Exception as e:
        cmds.scriptEditorInfo(e=True, suppressResults=False, suppressInfo=False, suppressWarnings=False)
        cmds.warning(f"Apply Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # --- RESTORE ---
        if current_eval_mode != "off":
            cmds.evaluationManager(mode=current_eval_mode)
        
        main_pane = mel.eval('global string $gMainPane; $tmp = $gMainPane;')
        if main_pane and cmds.paneLayout(main_pane, exists=True):
            cmds.paneLayout(main_pane, edit=True, manage=True)

        cmds.scriptEditorInfo(e=True, suppressResults=False, suppressInfo=False, suppressWarnings=False)
        cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
        cmds.refresh(suspend=False)
        cmds.refresh(force=True)
        cmds.undoInfo(closeChunk=True)

# --------------------------------------------------------------------- #
def mirror_anim(namespace="", mode="swap", pivot=None, offset_nodes=None):
    """
    Mirrors animation on selected controls.
    - Swaps Tangent Types (Auto, Spline, Linear, etc.) exactly.
    - Mirrors Tangent Angles/Weights.
    - Swaps Custom Attributes without inversion.
    - Includes Progress Bar.
    """
    if offset_nodes is None:
        offset_nodes = []
    pivot_offset = 0.0
    if pivot:
        p_node = cmds.ls(pivot, long=True) or cmds.ls(f"*:{pivot}", long=True) or cmds.ls(f"*{pivot}*", long=True)
        if p_node:
            pivot_offset = cmds.xform(p_node[0], q=True, ws=True, t=True)[0] * 2.0
            
    import maya.mel as mel
    
    selection = cmds.ls(sl=True, long=True)
    if not selection:
        cmds.warning("[ARTools] Please select controls to mirror animation.")
        return

    # 1. Load Rules and Time Range
    snap = snapshot.load_snapshot(namespace) or {"controls": {}}
    snap_ctrls = snap.get("controls", {})
    start, end = get_time_range()
    time_kwargs = {"time": (start, end)} if start is not None else {}
    offset_node_set = set(offset_nodes)
    axis_index = {"X": 0, "Y": 1, "Z": 2}
    
    # 2. Identify Pairs
    pairs = []
    processed = set()
    prefix = (namespace + ":") if namespace and not namespace.endswith(":") else namespace
    
    for node in selection:
        if node in processed: continue
        short = node.split("|")[-1].split(":")[-1]
        
        partner = None
        rules = {"translate": [1,1,1], "rotate": [1,1,1]} 
        
        if short in snap_ctrls:
            info = snap_ctrls[short]
            side = info.get("side", "Center")
            p_short = info.get("mirror")
            
            # Center controls mirror onto themselves
            if side == "Center":
                partner = node 
            elif p_short:
                partner = f"{prefix}{p_short}"
                if not cmds.objExists(partner): partner = None
            
            r_data = info.get("mirror_rules", {})
            rules["translate"] = r_data.get("translate", [1,1,1])
            rules["rotate"] = r_data.get("rotate", [1,1,1])
        
        if partner:
            pairs.append((node, partner, rules))
            processed.add(node)
            if node != partner:
                processed.add(partner)

    if not pairs:
        cmds.warning("[ARTools] No mirror partners found for selection.")
        return

    # --- PROGRESS BAR SETUP ---
    gMainProgressBar = mel.eval('$tmp = $gMainProgressBar')
    cmds.progressBar(gMainProgressBar, edit=True, beginProgress=True, 
                     isInterruptable=True, status='Reading Animation...', maxValue=len(pairs))
    progress_step = max(1, len(pairs) // 20)

    # 3. Harvest Data (Buffer All First)
    data_buffer = {}

    def get_curve_data(node):
        out = {}
        attrs = cmds.listAttr(node, k=True) or []
        for attr in attrs:
            full = f"{node}.{attr}"
            if not cmds.objExists(full):
                continue

            times = cmds.keyframe(full, q=True, tc=True, **time_kwargs) or []
            if not times:
                continue

            out[attr] = {
                "times": times,
                "values": cmds.keyframe(full, q=True, vc=True, **time_kwargs) or [],
                # Tangent Types (Strings: 'auto', 'spline', etc.)
                "itt": cmds.keyTangent(full, q=True, itt=True, **time_kwargs) or [],
                "ott": cmds.keyTangent(full, q=True, ott=True, **time_kwargs) or [],
                # Tangent Weights/Angles
                "wt": cmds.keyTangent(full, q=True, wt=True, **time_kwargs) or [],
                "ia": cmds.keyTangent(full, q=True, ia=True, **time_kwargs) or [],
                "oa": cmds.keyTangent(full, q=True, oa=True, **time_kwargs) or [],
                "iw": cmds.keyTangent(full, q=True, iw=True, **time_kwargs) or [],
                "ow": cmds.keyTangent(full, q=True, ow=True, **time_kwargs) or []
            }
        return out

    current_eval_mode = "off"
    main_pane = ""
    try:
        for i, (src, dst, _) in enumerate(pairs):
            if (i % progress_step) == 0:
                if cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                    break
                cmds.progressBar(gMainProgressBar, edit=True, progress=min(i + 1, len(pairs)))

            if src not in data_buffer:
                data_buffer[src] = get_curve_data(src)
            if src != dst and dst not in data_buffer:
                data_buffer[dst] = get_curve_data(dst)

        # 4. Apply Mirrored Data
        cmds.progressBar(gMainProgressBar, edit=True, status='Mirroring Animation...', progress=0, maxValue=len(pairs))
        
        def apply_mirrored(target_node, source_data, rules):
            tgt_short = target_node.split("|")[-1].split(":")[-1]
            offset_enabled = pivot_offset != 0.0 and tgt_short in offset_node_set

            # --- CRITICAL FIX: Safe Rule Parsing (Handles Advanced Axis Swapping) ---
            t_rules = rules.get("translate", [[0, 1.0], [1, 1.0], [2, 1.0]])
            r_rules = rules.get("rotate", [[0, 1.0], [1, 1.0], [2, 1.0]])
            
            # Normalize legacy flat numbers to the new advanced layout if needed
            if t_rules and isinstance(t_rules[0], (int, float)):
                t_rules = [[0, t_rules[0]], [1, t_rules[1]], [2, t_rules[2]]]
                r_rules = [[0, r_rules[0]], [1, r_rules[1]], [2, r_rules[2]]]

            axes_long = ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"]
            axes_short = ["tx", "ty", "tz", "rx", "ry", "rz"]

            for src_attr, data in source_data.items():
                target_attr = src_attr
                mult = 1.0

                if src_attr in axes_long or src_attr in axes_short:
                    is_rot = "rotate" in src_attr or src_attr in ["rx", "ry", "rz"]
                    is_short = src_attr in axes_short
                    
                    src_axis = -1
                    if "X" in src_attr or "x" in src_attr: src_axis = 0
                    elif "Y" in src_attr or "y" in src_attr: src_axis = 1
                    elif "Z" in src_attr or "z" in src_attr: src_axis = 2

                    if src_axis != -1:
                        active_rules = r_rules if is_rot else t_rules
                        mapped_target_axis = src_axis
                        
                        # Find the correct target axis and multiplier from the snapshot rules
                        for tgt_idx, rule in enumerate(active_rules):
                            if rule[0] == src_axis:
                                mapped_target_axis = tgt_idx
                                mult = rule[1]
                                break
                                
                        base_name = "rotate" if is_rot else "translate"
                        if is_short:
                            target_attr = f"{base_name[0]}{['x','y','z'][mapped_target_axis]}"
                        else:
                            target_attr = f"{base_name}{['X','Y','Z'][mapped_target_axis]}"

                full_attr = f"{target_node}.{target_attr}"
                if not cmds.objExists(full_attr) or cmds.getAttr(full_attr, l=True):
                    continue
                # ------------------------------------------------------------------------

                # Clear Target keys in range
                if start is not None:
                    cmds.cutKey(full_attr, time=(start, end), clear=True)
                else:
                    cmds.cutKey(full_attr, clear=True)

                times = data["times"]
                values = data["values"]
                itt = data["itt"]
                ott = data["ott"]
                wt = data["wt"]
                ia = data["ia"]
                oa = data["oa"]
                iw = data["iw"]
                ow = data["ow"]
                
                # Batch Loop
                for i, t in enumerate(times):
                    # 1. Set Value
                    val = values[i] * mult
                    
                    # Ensure pivot offset applies to the newly mapped X axis
                    if offset_enabled and target_attr in ("translateX", "tx"):
                        val += pivot_offset
                        
                    cmds.setKeyframe(full_attr, t=t, v=val)
                    
                    try:
                        # 2. Set Tangent Type explicitly (e.g. "spline", "auto")
                        cur_itt = itt[i]
                        cur_ott = ott[i]
                        cmds.keyTangent(full_attr, time=(t,t), itt=cur_itt, ott=cur_ott)
                        
                        # 3. Apply Weights/Angles
                        new_ia = ia[i] * mult
                        new_oa = oa[i] * mult
                        
                        if wt[i]:
                            # Weighted
                            cmds.keyTangent(full_attr, time=(t,t), edit=True, weightedTangents=True)
                            cmds.keyTangent(full_attr, time=(t,t), edit=True, absolute=True, 
                                          ia=new_ia, oa=new_oa, 
                                          iw=iw[i], ow=ow[i])
                        else:
                            # Non-Weighted (Fixed/Locked angles)
                            cmds.keyTangent(full_attr, time=(t,t), edit=True, weightedTangents=False,
                                          absolute=True, ia=new_ia, oa=new_oa)
                    except: 
                        pass

        cmds.refresh(suspend=True)
        current_eval_mode = cmds.evaluationManager(q=True, mode=True)[0]
        if current_eval_mode != "off":
            cmds.evaluationManager(mode='off')
        cmds.scriptEditorInfo(e=True, suppressResults=True, suppressInfo=True, suppressWarnings=True)
        main_pane = mel.eval('global string $gMainPane; $tmp = $gMainPane;')
        if main_pane and cmds.paneLayout(main_pane, exists=True):
            cmds.paneLayout(main_pane, edit=True, manage=False)
        cmds.undoInfo(openChunk=True)
        
        for i, (src, dst, rules) in enumerate(pairs):
            if (i % progress_step) == 0:
                if cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                    break
                cmds.progressBar(gMainProgressBar, edit=True, progress=min(i + 1, len(pairs)))
            
            if src == dst: # Center
                if src in data_buffer: apply_mirrored(src, data_buffer[src], rules)
            elif mode == "swap":
                if src in data_buffer: apply_mirrored(dst, data_buffer[src], rules)
                if dst in data_buffer: apply_mirrored(src, data_buffer[dst], rules)
            elif mode == "l2r" and src in data_buffer:
                apply_mirrored(dst, data_buffer[src], rules)
            elif mode == "r2l" and dst in data_buffer:
                apply_mirrored(src, data_buffer[dst], rules)

    except Exception as e:
        cmds.warning(f"[ARTools] Mirror Error: {e}")
    finally:
        cmds.undoInfo(closeChunk=True)
        if current_eval_mode != "off":
            cmds.evaluationManager(mode=current_eval_mode)
        if main_pane and cmds.paneLayout(main_pane, exists=True):
            cmds.paneLayout(main_pane, edit=True, manage=True)
        cmds.scriptEditorInfo(e=True, suppressResults=False, suppressInfo=False, suppressWarnings=False)
        cmds.refresh(suspend=False)
        cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
        cmds.refresh(force=True)
