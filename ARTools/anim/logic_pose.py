# ARTools/anim/logic_pose.py
from . import clipboard
from . import snapshot

import mathutils
from ..blender_host import selected_object_names, select_objects, object_by_name, get_property, set_property

def _get_matrix_world(b_obj):
    if hasattr(b_obj, "matrix_world"):
        return b_obj.matrix_world.copy()
    return b_obj.id_data.matrix_world @ b_obj.matrix.copy()

def _set_matrix_world(b_obj, mat):
    if hasattr(b_obj, "matrix_world"):
        b_obj.matrix_world = mat
    else:
        b_obj.matrix = b_obj.id_data.matrix_world.inverted_safe() @ mat

def _mirror_attributes(content, rules):
    """Maps attributes across axes using snapshot rule arrays."""
    t_rules = rules.get("translate", [[0, 1.0], [1, 1.0], [2, 1.0]])
    r_rules = rules.get("rotate", [[0, 1.0], [1, 1.0], [2, 1.0]])
    
    # Legacy Snapshot Support
    if t_rules and isinstance(t_rules[0], (int, float)):
        t_rules = [[0, t_rules[0]], [1, t_rules[1]], [2, t_rules[2]]]
        r_rules = [[0, r_rules[0]], [1, r_rules[1]], [2, r_rules[2]]]
        
    mirrored_content = {}
    axis_names = ["X", "Y", "Z"]
    attr_names_short = ["x", "y", "z"]
    
    for attr, val in content.items():
        is_trans = False; is_rot = False; axis_idx = 0
        if attr in ("translateX", "tx"): is_trans = True; axis_idx = 0
        elif attr in ("translateY", "ty"): is_trans = True; axis_idx = 1
        elif attr in ("translateZ", "tz"): is_trans = True; axis_idx = 2
        elif attr in ("rotateX", "rx"): is_rot = True; axis_idx = 0
        elif attr in ("rotateY", "ry"): is_rot = True; axis_idx = 1
        elif attr in ("rotateZ", "rz"): is_rot = True; axis_idx = 2
        
        if is_trans or is_rot:
            rule_set = t_rules if is_trans else r_rules
            mapped_idx, mult = rule_set[axis_idx]
            
            final_val = val * mult
            target_attr = attr
            
            # Reconstruct attribute name with new mapped axis
            if "translate" in attr: target_attr = "translate" + axis_names[mapped_idx]
            elif "rotate" in attr: target_attr = "rotate" + axis_names[mapped_idx]
            elif "t" in attr: target_attr = "t" + attr_names_short[mapped_idx]
            elif "r" in attr: target_attr = "r" + attr_names_short[mapped_idx]
            
            mirrored_content[target_attr] = final_val
        else:
            mirrored_content[attr] = val # Pass through
            
    return mirrored_content

def get_targets(use_selection=True):
        sel = selected_object_names() if use_selection else []
        if sel:
            return [(s.split(":")[-1], s) for s in sel]
        return []

def copy_pose(global_space=False):
        nodes = selected_object_names()
        
        if not nodes:
            print("[ARTools] Nothing selected to copy.")
            return

        data = {}
        ns = ""
        short_first = nodes[0].split(":")[-1]
        if ":" in nodes[0]:
            ns = nodes[0].rsplit(":", 1)[0]
        data["__namespace__"] = ns

        if global_space:
            for node in nodes:
                short = node.split(":")[-1]
                b_obj = object_by_name(node)
                if b_obj:
                    # Safely get matrix world
                    b_mat = _get_matrix_world(b_obj)
                    # Flatten Blender's 4x4 matrix into a 16-float list for JSON compatibility
                    mat = [val for row in b_mat for val in row]
                    data[short] = mat
            clipboard.save_data(data, "pose_global")
        else:
            for node in nodes:
                short = node.split(":")[-1]
                b_obj = object_by_name(node)
                if b_obj:
                    node_data = {}
                    # Fetch default transforms PLUS custom attributes
                    attrs_to_save = ["tx", "ty", "tz", "rx", "ry", "rz", "rw", "rqx", "rqy", "rqz", "sx", "sy", "sz"]
                    for k in b_obj.keys():
                        if not k.startswith("_"): attrs_to_save.append(k)
                        
                    for attr in attrs_to_save:
                        val = get_property(b_obj, attr, None)
                        if val is not None:
                            node_data[attr] = val
                    data[short] = node_data
            clipboard.save_data(data, "pose_local")

def paste_pose(global_space=False, namespace=""):
        ftype = "pose_global" if global_space else "pose_local"
        data = clipboard.load_data(ftype)
        if not data:
            print(f"[ARTools] No {ftype} data found.")
            return

        if namespace is None:
            namespace = data.get("__namespace__", "")
        
        targets = selected_object_names()
        if not targets and namespace:
            for short_name in data.keys():
                if short_name == "__namespace__": continue
                full = f"{namespace}:{short_name}" if namespace else short_name
                if object_by_name(full):
                    targets.append(full)

        if not targets:
            print("[ARTools] No targets found.")
            return

        for node in targets:
            short = node.split(":")[-1]
            if short not in data or short == "__namespace__": continue
            stored_val = data[short]
            b_obj = object_by_name(node)
            if not b_obj: continue

            if global_space:
                mat = mathutils.Matrix([stored_val[0:4], stored_val[4:8], stored_val[8:12], stored_val[12:16]])
                _set_matrix_world(b_obj, mat)
                b_obj.keyframe_insert(data_path="location")
                b_obj.keyframe_insert(data_path="rotation_euler")
                b_obj.keyframe_insert(data_path="rotation_quaternion")
            else:
                for attr, val in stored_val.items():
                    set_property(b_obj, attr, val, keyframe=True)

def reset_pose(namespace="", target_controls=None):
        snap = snapshot.load_snapshot(namespace)
        if not snap:
            print("[ARTools] Current character's snapshot is missing. Please create a snapshot in the AnimBar first!")
            return
        
        if target_controls is not None:
            prefix = namespace + ":" if namespace and not namespace.endswith(":") else namespace
            nodes = []
            for short in target_controls:
                full = f"{prefix}{short}"
                if object_by_name(full):
                    nodes.append(full)
                elif object_by_name(short):
                    nodes.append(short)
                    
            if not nodes:
                print("[ARTools] Selected shapes have no valid controls to reset!")
                return
        else:
            nodes = selected_object_names()
            if not nodes: return

        for node in nodes:
            short = node.split(":")[-1]
            info = snap["controls"].get(short)
            if info:
                defaults = info.get("defaults", {})
                b_obj = object_by_name(node)
                if b_obj:
                    for attr, val in defaults.items():
                        set_property(b_obj, attr, val, keyframe=True)

def mirror_pose(namespace, mode="swap", pivot=None, offset_nodes=None):
        if offset_nodes is None: offset_nodes = []
        pivot_offset = 0.0
        
        if pivot:
            p_node = object_by_name(pivot)
            if p_node:
                pivot_offset = _get_matrix_world(p_node).translation.x * 2.0
        
        snap = snapshot.load_snapshot(namespace)
        if not snap:
            print("[ARTools] No snapshot found.")
            return

        nodes = selected_object_names()
        is_selection_mode = bool(nodes)
        
        if not nodes and namespace:
            prefix = namespace + ":" if namespace and not namespace.endswith(":") else namespace
            for short in snap["controls"].keys():
                full = f"{prefix}{short}"
                if object_by_name(full):
                    nodes.append(full)

        if not nodes: return

        prefix = namespace + ":" if namespace and not namespace.endswith(":") else namespace
        buffer_data = {}
        controls_to_read = set()
        
        for node in nodes:
            short = node.split(":")[-1]
            info = snap["controls"].get(short)
            if not info: continue
            
            controls_to_read.add(short)
            if not is_selection_mode and info.get("mirror"):
                controls_to_read.add(info["mirror"])

        for short in controls_to_read:
            full = f"{prefix}{short}"
            b_obj = object_by_name(full)
            if b_obj:
                attrs = ["tx", "ty", "tz", "rx", "ry", "rz", "rw", "rqx", "rqy", "rqz", "sx", "sy", "sz"]
                for k in b_obj.keys():
                    if not k.startswith("_"): attrs.append(k)
                vals = {}
                for a in attrs:
                    val = get_property(b_obj, a, None)
                    if val is not None:
                        vals[a] = val
                buffer_data[short] = vals

        dst_nodes = set()
        for node in nodes:
            short = node.split(":")[-1]
            info = snap["controls"].get(short)
            if not info: continue
            side = info.get("side", "Center")
            partner_short = info.get("mirror")
            
            if is_selection_mode:
                if side == "Center": dst_nodes.add(node)
                elif partner_short: dst_nodes.add(f"{prefix}{partner_short}")
            else:
                dst_nodes.add(node)

        for node in nodes:
            short = node.split(":")[-1]
            info = snap["controls"].get(short)
            if not info: continue

            side = info.get("side", "Center")
            partner_short = info.get("mirror")
            
            if is_selection_mode:
                if side == "Center":
                    src_short = short
                    dst_full = node
                else:
                    if not partner_short: continue
                    src_short = short
                    dst_full = f"{prefix}{partner_short}"
                    
                if side == "Left" or side == "Center":
                    rules_node_info = info
                else:
                    rules_node_info = snap["controls"].get(partner_short)
            else:
                dst_full = node
                if side == "Center":
                    src_short = short
                    rules_node_info = info
                elif mode == "l2r":
                    if side == "Left": continue
                    src_short = partner_short
                    rules_node_info = snap["controls"].get(partner_short)
                elif mode == "r2l":
                    if side == "Right": continue
                    src_short = partner_short
                    rules_node_info = info
                else:
                    src_short = partner_short
                    if side == "Left":
                        rules_node_info = info
                    else:
                        rules_node_info = snap["controls"].get(partner_short)

            if not src_short or not dst_full or not object_by_name(dst_full): continue
            
            vals = buffer_data.get(src_short)
            if not vals: continue

            if not rules_node_info: rules_node_info = info
            rules = rules_node_info.get("mirror_rules", {})

            mapped_vals = _mirror_attributes(vals, rules)
            dst_b_obj = object_by_name(dst_full)
            
            for attr, final_val in mapped_vals.items():
                if attr in ("translateX", "tx") and pivot_offset != 0.0 and short in offset_nodes:
                    final_val += pivot_offset
                set_property(dst_b_obj, attr, final_val, keyframe=True)

def select_mirror_controls(namespace, add=False):
        snap = snapshot.load_snapshot(namespace)
        if not snap: return

        nodes = selected_object_names()
        mirror_nodes = []
        
        prefix = namespace + ":" if namespace and not namespace.endswith(":") else namespace

        for node in nodes:
            short = node.split(":")[-1]
            info = snap["controls"].get(short)
            if info:
                partner = info.get("mirror")
                if partner:
                    full_partner = f"{prefix}{partner}"
                    if object_by_name(full_partner):
                        mirror_nodes.append(full_partner)
        
        if mirror_nodes:
            if add:
                new_sel = list(set(nodes + mirror_nodes))
                select_objects(new_sel, replace=True)
            else:
                select_objects(mirror_nodes, replace=True)

def get_pose_data(global_space=False, use_selection=True):
        nodes = selected_object_names() if use_selection else []
        if not nodes:
            return {}

        data = {}
        if global_space:
            for node in nodes:
                short = node.split(":")[-1]
                b_obj = object_by_name(node)
                if b_obj:
                    b_mat = _get_matrix_world(b_obj)
                    mat = [val for row in b_mat for val in row]
                    data[short] = mat
        else:
            for node in nodes:
                short = node.split(":")[-1]
                b_obj = object_by_name(node)
                if b_obj:
                    node_data = {}
                    attrs_to_save = ["tx", "ty", "tz", "rx", "ry", "rz", "rw", "rqx", "rqy", "rqz", "sx", "sy", "sz"]
                    for k in b_obj.keys():
                        if not k.startswith("_"): attrs_to_save.append(k)
                    for attr in attrs_to_save:
                        val = get_property(b_obj, attr, None)
                        if val is not None:
                            node_data[attr] = val
                    data[short] = node_data
        return data

def apply_library_pose(data, namespace="", mirror=False, mix=1.0, show_ui=True):
        if not data: return
        
        if not namespace or namespace in ["-", "Selected", "None"]:
            namespace = data.get("__namespace__", "")

        ns_prefix = namespace + ":" if namespace and not namespace.endswith(":") else namespace
        
        snap = None
        if mirror:
            snap = snapshot.load_snapshot(namespace)
            if not snap and show_ui:
                print(f"[ARTools] Warning: No snapshot found for namespace '{namespace}'. Mirroring disabled.")
                mirror = False
        
        applied_count = 0
        for short_name, content in data.items():
            if short_name == "__namespace__": continue
            
            target_short = short_name
            apply_content = content
            
            if mirror and snap:
                info = snap["controls"].get(short_name)
                if info:
                    if info.get("mirror"):
                        target_short = info.get("mirror")
                    
                    if isinstance(content, dict):
                        rules_node_info = info
                        side = info.get("side", "Center")
                        if side == "Right" and info.get("mirror"):
                            partner_info = snap["controls"].get(info.get("mirror"))
                            if partner_info: rules_node_info = partner_info

                        rules = rules_node_info.get("mirror_rules", {})
                        apply_content = _mirror_attributes(content, rules)

            full_node = f"{ns_prefix}{target_short}"
            b_obj = object_by_name(full_node)
            if not b_obj: continue
            
            applied_count += 1

            if isinstance(apply_content, list) and len(apply_content) == 16:
                mat = mathutils.Matrix([apply_content[0:4], apply_content[4:8], apply_content[8:12], apply_content[12:16]])
                _set_matrix_world(b_obj, mat)
                b_obj.keyframe_insert(data_path="location")
                b_obj.keyframe_insert(data_path="rotation_euler")
                b_obj.keyframe_insert(data_path="rotation_quaternion")
            elif isinstance(apply_content, dict):
                for attr, val in apply_content.items():
                    set_property(b_obj, attr, val, keyframe=True)
        
        if show_ui:
            if applied_count == 0:
                print("[ARTools] Apply aborted: No matching controls found in scene.")
            else:
                print("[ARTools] Pose Applied.")

def apply_mixed_pose(target_data, base_data, mix=1.0):
        if not target_data or not base_data: return
        mix = max(0.0, min(1.0, mix))
        
        if mix >= 0.99:
            apply_library_pose(target_data, show_ui=False) 
            return

        for short, t_val in target_data.items():
            if short not in base_data: continue
            b_val = base_data[short]
            
            b_obj = object_by_name(short)
            if not b_obj: continue

            if isinstance(t_val, dict) and isinstance(b_val, dict):
                for attr, t_float in t_val.items():
                    if attr not in b_val: continue
                    b_float = b_val[attr]
                    val = b_float + (t_float - b_float) * mix
                    set_property(b_obj, attr, val, keyframe=True)

            elif isinstance(t_val, list) and isinstance(b_val, list):
                if len(t_val) == 16 and len(b_val) == 16:
                    mixed_m = []
                    for i in range(16):
                        mixed_m.append(b_val[i] + (t_val[i] - b_val[i]) * mix)
                    mat = mathutils.Matrix([mixed_m[0:4], mixed_m[4:8], mixed_m[8:12], mixed_m[12:16]])
                    _set_matrix_world(b_obj, mat)
                    b_obj.keyframe_insert(data_path="location")
                    b_obj.keyframe_insert(data_path="rotation_euler")
                    b_obj.keyframe_insert(data_path="rotation_quaternion")

def calculate_mirror_data(data, namespace=""):
    from . import snapshot
    snap = snapshot.load_snapshot(namespace)
    if not snap:
        return data

    mirrored_data = {}
    
    for short_name, content in data.items():
        target_short = short_name
        apply_content = content
        
        info = snap["controls"].get(short_name)
        if info:
            if info.get("mirror"):
                target_short = info.get("mirror")
            
            if isinstance(content, dict):
                rules_node_info = info
                side = info.get("side", "Center")
                
                if side == "Right" and info.get("mirror"):
                    partner_info = snap["controls"].get(info.get("mirror"))
                    if partner_info: rules_node_info = partner_info

                rules = rules_node_info.get("mirror_rules", {})
                apply_content = _mirror_attributes(content, rules)
        
        mirrored_data[target_short] = apply_content
        
    return mirrored_data

class PoseBlender(object):
        def __init__(self, target_data, global_space=False):
            self.items = [] 
            self.global_space = global_space
            
            selection = selected_object_names()
            valid_nodes_map = {}
            if selection:
                for node in selection:
                    short = node.split(":")[-1]
                    valid_nodes_map[short] = node

            if not self.global_space:
                for short, attrs in target_data.items():
                    full_node = None
                    if selection:
                        if short not in valid_nodes_map: continue
                        full_node = valid_nodes_map[short]
                    else:
                        if object_by_name(short): full_node = short
                    
                    if not full_node: continue
                    b_obj = object_by_name(full_node)
                    if not b_obj: continue
                    
                    for attr, target_val in attrs.items():
                        start_val = get_property(b_obj, attr, None)
                        if start_val is not None:
                            diff = target_val - start_val
                            self.items.append((b_obj, attr, start_val, diff))
            else:
                for short, target_matrix in target_data.items():
                    full_node = None
                    if selection:
                        if short not in valid_nodes_map: continue
                        full_node = valid_nodes_map[short]
                    else:
                        if object_by_name(short): full_node = short
                    
                    if not full_node: continue
                    b_obj = object_by_name(full_node)
                    if not b_obj: continue
                    
                    b_mat = _get_matrix_world(b_obj)
                    start_matrix = [val for row in b_mat for val in row]
                    self.items.append((b_obj, start_matrix, target_matrix))

        def update(self, mix):
            mix = max(0.0, min(1.0, mix))
            
            if not self.global_space:
                for b_obj, attr, start, diff in self.items:
                    val = start + (diff * mix)
                    set_property(b_obj, attr, val, keyframe=True)
            else:
                for b_obj, start_m, target_m in self.items:
                    new_m = []
                    for i in range(16):
                        val = start_m[i] + (target_m[i] - start_m[i]) * mix
                        new_m.append(val)
                    mat = mathutils.Matrix([new_m[0:4], new_m[4:8], new_m[8:12], new_m[12:16]])
                    _set_matrix_world(b_obj, mat)
                    b_obj.keyframe_insert(data_path="location")
                    b_obj.keyframe_insert(data_path="rotation_euler")
                    b_obj.keyframe_insert(data_path="rotation_quaternion")

        def get_blender(target_data, global_space=False):
            return PoseBlender(target_data, global_space)

        def mirror_plane(plane, namespace=""):
            nodes = selected_object_names()
            if not nodes: return
            s = [-1.0, 1.0, 1.0] if plane == "YZ" else ([1.0, -1.0, 1.0] if plane == "XZ" else [1.0, 1.0, -1.0])
            for node in nodes:
                b_obj = object_by_name(node)
                if b_obj:
                    loc, rot, scale = _get_matrix_world(b_obj).decompose()
                    loc.x *= s[0]; loc.y *= s[1]; loc.z *= s[2]
                    
                    if plane == "YZ":
                        rot = mathutils.Quaternion((rot.w, rot.x, -rot.y, -rot.z))
                    elif plane == "XZ":
                        rot = mathutils.Quaternion((rot.w, -rot.x, rot.y, -rot.z))
                    else:
                        rot = mathutils.Quaternion((rot.w, -rot.x, -rot.y, rot.z))
                    
                    scale.x *= s[0]; scale.y *= s[1]; scale.z *= s[2]
                    
                    mat = mathutils.Matrix.LocRotScale(loc, rot, scale)
                    _set_matrix_world(b_obj, mat)
                    b_obj.keyframe_insert(data_path="location")
                    b_obj.keyframe_insert(data_path="rotation_euler")
                    b_obj.keyframe_insert(data_path="rotation_quaternion")