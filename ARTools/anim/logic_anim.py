# ARTools/anim/logic_anim.py
import bpy
import mathutils
import math
from collections import defaultdict
from . import clipboard
from . import snapshot
from ..blender_host import selected_object_names, object_by_name, get_property, set_property

def _get_matrix_world(b_obj):
    if hasattr(b_obj, "matrix_world"):
        return b_obj.matrix_world.copy()
    return b_obj.id_data.matrix_world @ b_obj.matrix.copy()

def _set_matrix_world(b_obj, mat):
    if hasattr(b_obj, "matrix_world"):
        b_obj.matrix_world = mat
    else:
        b_obj.matrix = b_obj.id_data.matrix_world.inverted_safe() @ mat

def _bone_prefix(b_obj):
    """PoseBone F-Curves live on the Armature's action, prefixed with
    pose.bones["Name"]. — plain Objects use no prefix at all."""
    if isinstance(b_obj, bpy.types.PoseBone):
        return f'pose.bones["{b_obj.name}"].'
    return ""

def _anim_data(b_obj):
    """PoseBones have no animation_data of their own; it lives on the
    Object that owns them (b_obj.id_data)."""
    return b_obj.id_data.animation_data

def _get_fcurves(anim_data):
    if not anim_data or not anim_data.action:
        return []
    if hasattr(anim_data.action, "fcurves"):
        return anim_data.action.fcurves
    if hasattr(anim_data, "action_slot"):
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(anim_data.action, anim_data.action_slot)
        if cb and hasattr(cb, "fcurves"):
            return cb.fcurves
    return []

def get_time_range():
    scene = bpy.context.scene
    if scene.use_preview_range:
        return (scene.frame_preview_start, scene.frame_preview_end)
    return (None, None)

def _get_dominant_tangent(types):
    return "auto"

def copy_anim(global_space=False, custom_range=None):
    nodes = selected_object_names()
    if not nodes: return

    if custom_range:
        start, end = custom_range
    else:
        start, end = get_time_range()

    file_name = "anim_global" if global_space else "anim_local"
    data = {}
    
    ns = ""
    short_first = nodes[0].split(":")[-1]
    if ":" in nodes[0]:
        ns = nodes[0].rsplit(":", 1)[0]
    data["__namespace__"] = ns

    scene = bpy.context.scene
    orig_frame = scene.frame_current

    if global_space:
        frames_to_sample = set()
        for node in nodes:
            b_obj = object_by_name(node)
            anim_data = _anim_data(b_obj) if b_obj else None
            fcurves = _get_fcurves(anim_data)
            for fc in fcurves:
                for kp in fc.keyframe_points:
                    if start is not None:
                        if start <= kp.co.x <= end:
                            frames_to_sample.add(int(kp.co.x))
                    else:
                        frames_to_sample.add(int(kp.co.x))
        
        if not frames_to_sample and start is not None:
            frames_to_sample = set(range(int(start), int(end) + 1))
        
        sorted_frames = sorted(list(frames_to_sample))
        
        for node in nodes:
            short = node.split(":")[-1]
            data[short] = {}

        for f in sorted_frames:
            scene.frame_set(f)
            for node in nodes:
                short = node.split(":")[-1]
                b_obj = object_by_name(node)
                if b_obj:
                    b_mat = _get_matrix_world(b_obj)
                    mat = [val for row in b_mat for val in row]
                    data[short][str(f)] = { "m": mat, "ti": "auto", "to": "auto" }
        
        scene.frame_set(orig_frame)
        clipboard.save_data(data, file_name)

    else:
        for node in nodes:
            short = node.split(":")[-1]
            b_obj = object_by_name(node)
            if not b_obj: continue
            b_anim = _anim_data(b_obj)
            prefix = _bone_prefix(b_obj)
            fcurves = _get_fcurves(b_anim)
            if not fcurves:
                continue
                
            anim_data = {}
            for fc in fcurves:
                if not fc.data_path.startswith(prefix): continue
                attr = fc.data_path[len(prefix):]
                if attr == "location": attr = ["tx", "ty", "tz"][fc.array_index]
                elif attr == "rotation_euler": attr = ["rx", "ry", "rz"][fc.array_index]
                elif attr == "rotation_quaternion": attr = ["rw", "rqx", "rqy", "rqz"][fc.array_index]
                elif attr == "scale": attr = ["sx", "sy", "sz"][fc.array_index]
                elif attr.startswith('["') and attr.endswith('"]'): attr = attr[2:-2]
                
                times = []
                values = []
                
                for kp in fc.keyframe_points:
                    if start is not None and not (start <= kp.co.x <= end):
                        continue
                    times.append(kp.co.x)
                    values.append(kp.co.y)
                    
                if times:
                    anim_data[attr] = {
                        'times': times, 'values': values
                    }
            
            if anim_data:
                data[short] = anim_data
                
        clipboard.save_data(data, file_name)
    
    print("[ARTools] Animation Copied")

def paste_anim(global_space=False, namespace="", paste_method="replace"):
    ftype = "anim_global" if global_space else "anim_local"
    data = clipboard.load_data(ftype)
    if not data: 
        print("No animation data found.")
        return

    if namespace is None:
        namespace = data.get("__namespace__", "")

    targets = selected_object_names()
    if not targets and namespace:
        for short in data.keys():
            if short == "__namespace__": continue
            full = f"{namespace}:{short}" if namespace else short
            if object_by_name(full): targets.append(full)
    if not targets: 
        print("No targets found.")
        return

    time_offset = 0.0
    scene = bpy.context.scene
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
        
        if first_frame < 99999990.0: 
            time_offset = scene.frame_current - first_frame

    orig_frame = scene.frame_current
    
    if global_space:
        frame_map = {}
        for node in targets:
            short = node.split(":")[-1]
            if short in data and short != "__namespace__":
                for t_str, content in data[short].items():
                    t = float(t_str)
                    if t not in frame_map: frame_map[t] = []
                    mat = content.get("m") if isinstance(content, dict) else content
                    frame_map[t].append((node, mat))
        
        sorted_frames = sorted(frame_map.keys())
        if sorted_frames:
            for t in sorted_frames:
                target_t = t + time_offset
                scene.frame_set(int(target_t))
                
                for node, mat_data in frame_map[t]:
                    b_obj = object_by_name(node)
                    if b_obj:
                        mat = mathutils.Matrix([mat_data[0:4], mat_data[4:8], mat_data[8:12], mat_data[12:16]])
                        _set_matrix_world(b_obj, mat)
                        b_obj.keyframe_insert(data_path="location")
                        b_obj.keyframe_insert(data_path="rotation_euler")
                        b_obj.keyframe_insert(data_path="rotation_quaternion")
    else:
        for node in targets:
            short = node.split(":")[-1]
            if short not in data or short == "__namespace__": continue
            node_data = data[short]
            b_obj = object_by_name(node)
            if not b_obj: continue
            
            for attr, curve_data in node_data.items():
                if isinstance(curve_data, dict):
                    times = curve_data.get('times', [])
                    values = curve_data.get('values', [])
                else:
                    continue
                    
                if not times: continue
                target_times = [t + time_offset for t in times]
                
                for i, t in enumerate(target_times):
                    scene.frame_set(int(t))
                    set_property(b_obj, attr, values[i], keyframe=True)
                    
    for node in targets:
        b_obj = object_by_name(node)
        if not b_obj: continue
        anim_host = b_obj.id_data if hasattr(b_obj, "id_data") else b_obj
        if not anim_host.animation_data: continue
        fcurves = _get_fcurves(anim_host.animation_data)
        for fc in fcurves:
            prev_y = None
            for kp in sorted(fc.keyframe_points, key=lambda k: k.co.x):
                kp.interpolation = 'LINEAR'
                if "rotation_euler" in fc.data_path:
                    if prev_y is not None:
                        diff = kp.co.y - prev_y
                        if abs(diff) > math.pi:
                            offset_val = round(diff / (2 * math.pi)) * 2 * math.pi
                            kp.co.y -= offset_val
                            kp.handle_left.y -= offset_val
                            kp.handle_right.y -= offset_val
                    prev_y = kp.co.y
            fc.update()

    scene.frame_set(orig_frame)
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                with bpy.context.temp_override(window=window, area=area):
                    bpy.ops.ed.undo_push(message="ARTools_PasteAnim")
                break
    print("Animation Pasted")

def _legacy_mirror_anim(namespace, mode="swap", pivot=None):
    pass

def apply_library_item(anim_data, settings, target_ns=""):
    if "data" in anim_data and isinstance(anim_data["data"], dict):
        anim_data = anim_data["data"]

    if not target_ns or target_ns in ["-", "Selected", "None"]:
        target_ns = anim_data.get("__namespace__", "")

    mirror = settings.get("mirror", False)
    mirror_mode = settings.get("mirror_mode", "swap")
    paste_method = settings.get("paste_method", "Replace")
    paste_time = settings.get("paste_time", "original")
    
    start_opt = settings.get("start_frame", 0)
    end_opt = settings.get("end_frame", 0)
    use_range = (start_opt != 0 or end_opt != 0)

    is_world = False
    for node_content in anim_data.values():
        if isinstance(node_content, dict) and node_content:
            first_key = next(iter(node_content), "")
            if first_key.replace('.', '', 1).isdigit() or (first_key.startswith('-') and first_key[1:].replace('.', '', 1).isdigit()):
                is_world = True; break
            else:
                is_world = False; break

    scene = bpy.context.scene
    offset = 0
    if paste_time == "current":
        first_frame = None
        if is_world:
            for k, frames in anim_data.items():
                if k == "__namespace__": continue
                for f_str in frames.keys():
                    if f_str.replace('.', '', 1).isdigit() or (f_str.startswith('-') and f_str[1:].replace('.', '', 1).isdigit()):
                        t = float(f_str)
                        if first_frame is None or t < first_frame: first_frame = t
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
            offset = scene.frame_current - first_frame

    orig_frame = scene.frame_current
    animated_nodes = []
    resolved_nodes = {}
    
    for node_name in anim_data.keys():
        if node_name == "__namespace__": continue
        full_node = f"{target_ns}:{node_name}" if target_ns else node_name
        if not object_by_name(full_node):
            if object_by_name(node_name): full_node = node_name
            else: continue
        resolved_nodes[node_name] = full_node
        animated_nodes.append(full_node)

    if not resolved_nodes:
        print("[ARTools] Apply aborted: No matching controls found.")
        return

    if is_world:
        frame_batches = {}
        for short, full_node in resolved_nodes.items():
            node_data = anim_data[short]
            for t_str, content in node_data.items():
                if t_str.replace('.', '', 1).isdigit() or (t_str.startswith('-') and t_str[1:].replace('.', '', 1).isdigit()):
                    t_raw = float(t_str)
                    if use_range and (t_raw < start_opt or t_raw > end_opt): continue
                    if t_raw not in frame_batches: frame_batches[t_raw] = []
                    
                    mat = content.get("m") if isinstance(content, dict) else content
                    if mat:
                        frame_batches[t_raw].append((full_node, mat))
        
        sorted_frames = sorted(frame_batches.keys())

        for t in sorted_frames:
            final_time = t + offset
            scene.frame_set(int(final_time))
            
            batch = frame_batches[t]
            for full_node, mat_data in batch:
                b_obj = object_by_name(full_node)
                if b_obj:
                    mat = mathutils.Matrix([mat_data[0:4], mat_data[4:8], mat_data[8:12], mat_data[12:16]])
                    _set_matrix_world(b_obj, mat)
                    b_obj.keyframe_insert(data_path="location")
                    b_obj.keyframe_insert(data_path="rotation_euler")
                    b_obj.keyframe_insert(data_path="rotation_quaternion")
    else:
        for short, full_node in resolved_nodes.items():
            node_data = anim_data[short]
            b_obj = object_by_name(full_node)
            if not b_obj: continue
            
            for attr, curve_data in node_data.items():
                if isinstance(curve_data, dict):
                    times = curve_data.get('times', [])
                    values = curve_data.get('values', [])
                elif isinstance(curve_data, list):
                    times = [p[0] for p in curve_data]
                    values = [p[1] for p in curve_data]
                else: continue

                if not times: continue
                target_times = [t + offset for t in times]

                for idx, t in enumerate(target_times):
                    orig_t = times[idx]
                    if use_range and (orig_t < start_opt or orig_t > end_opt): continue

                    scene.frame_set(int(t))
                    set_property(b_obj, attr, values[idx], keyframe=True)

    scene.frame_set(orig_frame)

    if mirror and animated_nodes:
        from ..blender_host import select_objects
        select_objects(animated_nodes, replace=True)
        mirror_anim(target_ns, mirror_mode)
        select_objects(animated_nodes, replace=True)

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                with bpy.context.temp_override(window=window, area=area):
                    bpy.ops.ed.undo_push(message="ARTools_LibraryApply")
                break
    print("[ARTools] Animation Applied.")

def apply_mixed_pose(target_data, base_data, mix=1.0):
    pass

def calculate_mirror_data(data, namespace=""):
    return data

def mirror_anim(namespace="", mode="swap", pivot=None, offset_nodes=None):
    if offset_nodes is None: offset_nodes = []
    pivot_offset = 0.0
    
    selection = selected_object_names()
    if not selection:
        print("[ARTools] Please select controls to mirror animation.")
        return

    if pivot:
        p_node = object_by_name(pivot)
        if p_node:
            pivot_offset = _get_matrix_world(p_node).translation.x * 2.0

    snap = snapshot.load_snapshot(namespace) or {"controls": {}}
    snap_ctrls = snap.get("controls", {})
    start, end = get_time_range()
    offset_node_set = set(offset_nodes)
    
    pairs = []
    processed = set()
    prefix = (namespace + ":") if namespace and not namespace.endswith(":") else namespace
    
    for node in selection:
        if node in processed: continue
        short = node.split(":")[-1]
        
        partner = None
        rules = {"translate": [1,1,1], "rotate": [1,1,1]} 
        
        if short in snap_ctrls:
            info = snap_ctrls[short]
            side = info.get("side", "Center")
            p_short = info.get("mirror")
            
            if side == "Center":
                partner = node 
            elif p_short:
                partner = f"{prefix}{p_short}"
                if not object_by_name(partner): partner = None
            
            r_data = info.get("mirror_rules", {})
            rules["translate"] = r_data.get("translate", [1,1,1])
            rules["rotate"] = r_data.get("rotate", [1,1,1])
        
        if partner:
            pairs.append((node, partner, rules))
            processed.add(node)
            if node != partner:
                processed.add(partner)

    if not pairs:
        print("[ARTools] No mirror partners found for selection.")
        return

    data_buffer = {}

    def get_curve_data(node_name):
        out = {}
        b_obj = object_by_name(node_name)
        if not b_obj: return out
        b_anim = _anim_data(b_obj)
        prefix = _bone_prefix(b_obj)
            
        fcurves = _get_fcurves(b_anim)
        if not fcurves:
            return out
                
        for fc in fcurves:
            if not fc.data_path.startswith(prefix): continue
            attr = fc.data_path[len(prefix):]
            if attr == "location": attr = ["tx", "ty", "tz"][fc.array_index]
            elif attr == "rotation_euler": attr = ["rx", "ry", "rz"][fc.array_index]
            elif attr == "rotation_quaternion": attr = ["rw", "rqx", "rqy", "rqz"][fc.array_index]
            elif attr == "scale": attr = ["sx", "sy", "sz"][fc.array_index]
            elif attr.startswith('["') and attr.endswith('"]'): attr = attr[2:-2]
            
            times = []
            values = []
            for kp in fc.keyframe_points:
                if start is not None and not (start <= kp.co.x <= end):
                    continue
                times.append(kp.co.x)
                values.append(kp.co.y)
            if times:
                out[attr] = {"times": times, "values": values}
        return out

    for src, dst, _ in pairs:
        if src not in data_buffer:
            data_buffer[src] = get_curve_data(src)
        if src != dst and dst not in data_buffer:
            data_buffer[dst] = get_curve_data(dst)

    def apply_mirrored(target_node, source_data, rules):
        tgt_short = target_node.split(":")[-1]
        offset_enabled = pivot_offset != 0.0 and tgt_short in offset_node_set

        t_rules = rules.get("translate", [[0, 1.0], [1, 1.0], [2, 1.0]])
        r_rules = rules.get("rotate", [[0, 1.0], [1, 1.0], [2, 1.0]])
        
        if t_rules and isinstance(t_rules[0], (int, float)):
            t_rules = [[0, t_rules[0]], [1, t_rules[1]], [2, t_rules[2]]]
            r_rules = [[0, r_rules[0]], [1, r_rules[1]], [2, r_rules[2]]]

        axes_long = ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"]
        axes_short = ["tx", "ty", "tz", "rx", "ry", "rz"]

        b_obj = object_by_name(target_node)
        if not b_obj: return

        scene = bpy.context.scene

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

            times = data["times"]
            values = data["values"]
            
            for i, t in enumerate(times):
                val = values[i] * mult
                if offset_enabled and target_attr in ("translateX", "tx"):
                    val += pivot_offset
                    
                scene.frame_set(int(t))
                set_property(b_obj, target_attr, val, keyframe=True)

    orig_frame = bpy.context.scene.frame_current

    for src, dst, rules in pairs:
        if src == dst: 
            if src in data_buffer: apply_mirrored(src, data_buffer[src], rules)
        elif mode == "swap":
            if src in data_buffer: apply_mirrored(dst, data_buffer[src], rules)
            if dst in data_buffer: apply_mirrored(src, data_buffer[dst], rules)
        elif mode == "l2r" and src in data_buffer:
            apply_mirrored(dst, data_buffer[src], rules)
        elif mode == "r2l" and dst in data_buffer:
            apply_mirrored(src, data_buffer[dst], rules)
    
    bpy.context.scene.frame_set(orig_frame)
    
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                with bpy.context.temp_override(window=window, area=area):
                    bpy.ops.ed.undo_push(message="ARTools_MirrorAnim")
                break
    
    print("[ARTools] Animation Mirrored")