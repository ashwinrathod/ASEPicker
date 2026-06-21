# ARTools/anim/logic_pose.py
from maya import cmds
from . import clipboard
from . import snapshot

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
    sel = cmds.ls(sl=True, long=True) or []
    if use_selection and sel:
        return [(s.split("|")[-1].split(":")[-1], s) for s in sel]
    return []

def copy_pose(global_space=False):
    nodes = cmds.ls(sl=True, long=True)
    if not nodes:
        cmds.warning("Nothing selected to copy.")
        return

    data = {}
    # Embed source namespace to fall back on if "Selected" mode is disabled
    ns = ""
    short_first = nodes[0].split("|")[-1]
    if ":" in short_first:
        ns = short_first.rsplit(":", 1)[0]
    data["__namespace__"] = ns

    if global_space:
        for node in nodes:
            short = node.split("|")[-1].split(":")[-1]
            matrix = cmds.xform(node, q=True, ws=True, matrix=True)
            data[short] = matrix
        clipboard.save_data(data, "pose_global")
    else:
        for node in nodes:
            short = node.split("|")[-1].split(":")[-1]
            attrs = cmds.listAttr(node, keyable=True) or []
            node_data = {}
            for attr in attrs:
                full_attr = f"{node}.{attr}"
                if cmds.objExists(full_attr):
                    node_data[attr] = cmds.getAttr(full_attr)
            data[short] = node_data
        clipboard.save_data(data, "pose_local")

def paste_pose(global_space=False, namespace=""):
    ftype = "pose_global" if global_space else "pose_local"
    data = clipboard.load_data(ftype)
    if not data:
        cmds.warning(f"No {ftype} data found.")
        return

    # Trigger fallback to original stored namespace
    if namespace is None:
        namespace = data.get("__namespace__", "")

    targets = cmds.ls(sl=True, long=True)
    if not targets and namespace:
        targets = []
        for short_name in data.keys():
            if short_name == "__namespace__": continue
            full = f"{namespace}:{short_name}"
            if cmds.objExists(full):
                targets.append(full)

    if not targets:
        cmds.warning("No targets found.")
        return

    cmds.undoInfo(openChunk=True)
    try:
        for node in targets:
            short = node.split("|")[-1].split(":")[-1]
            if short not in data or short == "__namespace__": continue
            stored_val = data[short]

            if global_space:
                try: cmds.xform(node, ws=True, matrix=stored_val)
                except: pass
            else:
                for attr, val in stored_val.items():
                    full_attr = f"{node}.{attr}"
                    if cmds.objExists(full_attr) and cmds.getAttr(full_attr, settable=True):
                        cmds.setAttr(full_attr, val)
    finally:
        cmds.undoInfo(closeChunk=True)

def reset_pose(namespace="", target_controls=None):
    snap = snapshot.load_snapshot(namespace)
    if not snap:
        from maya import cmds
        cmds.warning("Current character's snapshot is missing. Please create a snapshot in the AnimBar first!")
        return

    from maya import cmds
    
    # 1. API Mode: Reset specifically requested controls
    if target_controls is not None:
        prefix = namespace + ":" if namespace and not namespace.endswith(":") else namespace
        nodes = []
        for short in target_controls:
            full = f"{prefix}{short}"
            if cmds.objExists(full):
                nodes.append(full)
            elif cmds.objExists(short):
                nodes.append(short)
                
        if not nodes:
            cmds.warning("[ARTools] Selected shapes have no valid controls to reset!")
            return
            
    # 2. Native Mode: Reset standard Maya Selection
    else:
        nodes = cmds.ls(sl=True, long=True)
        if not nodes: return

    # 3. Apply the Snapshot Data
    for node in nodes:
        short = node.split("|")[-1].split(":")[-1]
        info = snap["controls"].get(short)
        if info:
            defaults = info.get("defaults", {})
            for attr, val in defaults.items():
                try: cmds.setAttr(f"{node}.{attr}", val)
                except: pass

def mirror_pose(namespace, mode="swap", pivot=None, offset_nodes=None):
    """
    mode: 'swap', 'l2r', 'r2l'
    If items are selected, it acts as 'Push' (Selected -> Partner).
    If nothing selected, it performs the global 'mode' (Swap/L2R/R2L) on everything.
    """
    pivot_offset = 0.0
    if pivot:
        p_node = cmds.ls(pivot, long=True) or cmds.ls(f"*:{pivot}", long=True) or cmds.ls(f"*{pivot}*", long=True)
        if p_node:
            pivot_offset = cmds.xform(p_node[0], q=True, ws=True, t=True)[0] * 2.0
    
    snap = snapshot.load_snapshot(namespace)
    if not snap:
        cmds.warning("No snapshot found.")
        return

    nodes = cmds.ls(sl=True, long=True)
    is_selection_mode = bool(nodes)
    
    if not nodes and namespace:
        # No selection -> Global Mirror on all controls
        nodes = cmds.ls(f"{namespace}:*", type="transform", long=True)

    if not nodes: return

    # Start Undo Chunk
    cmds.refresh(suspend=True)
    current_eval_mode = cmds.evaluationManager(q=True, mode=True)[0]
    if current_eval_mode != "off": cmds.evaluationManager(mode='off')
    cmds.undoInfo(openChunk=True)
    
    try:
        prefix = namespace + ":" if namespace and not namespace.endswith(":") else namespace
        
        # 1. READ ALL VALUES FIRST (Buffer)
        buffer_data = {}
        controls_to_read = set()
        
        for node in nodes:
            short = node.split("|")[-1].split(":")[-1]
            info = snap["controls"].get(short)
            if not info: continue
            
            # If selection mode: Source is ME. I need MY values.
            if is_selection_mode:
                controls_to_read.add(short)
            else:
                # Global Swap mode: I need my PARTNER'S values to overwrite me.
                # Or my own values if I am source.
                controls_to_read.add(short)
                if info.get("mirror"):
                    controls_to_read.add(info["mirror"])

        for short in controls_to_read:
            full = f"{prefix}{short}"
            if cmds.objExists(full):
                attrs = cmds.listAttr(full, keyable=True) or []
                vals = {}
                for a in attrs:
                    try: vals[a] = cmds.getAttr(f"{full}.{a}")
                    except: pass
                buffer_data[short] = vals

        # 2. APPLY PHASE
        # A. Pre-calculate all destination nodes to find our roots
        dst_nodes = set()
        for node in nodes:
            short = node.split("|")[-1].split(":")[-1]
            info = snap["controls"].get(short)
            if not info: continue
            side = info.get("side", "Center")
            partner_short = info.get("mirror")
            
            if is_selection_mode:
                if side == "Center": dst_nodes.add(node)
                elif partner_short: dst_nodes.add(f"{prefix}{partner_short}")
            else:
                dst_nodes.add(node)

        # B. Apply values
        for node in nodes:
            short = node.split("|")[-1].split(":")[-1]
            info = snap["controls"].get(short)
            if not info: continue

            side = info.get("side", "Center")
            partner_short = info.get("mirror")
            
            # --- SELECTION MODE LOGIC (Push) ---
            if is_selection_mode:
                # I am the Source. My partner is Destination.
                # If Center, I am both.
                if side == "Center":
                    src_short = short
                    dst_full = node
                else:
                    if not partner_short: continue
                    src_short = short
                    dst_full = f"{prefix}{partner_short}"
                    
                # We apply Src values TO Dst.
                # We need rules. Rules are stored on Source (if Left) or Destination?
                # Snapshot stores rules on Left side usually.
                # If I am Right side source, I need rules from Left side (Destination).
                
                # Retrieve rules from the Left/Center node definition
                if side == "Left" or side == "Center":
                    rules_node_info = info
                else:
                    # I am Right. My partner is Left. Get rules from partner.
                    rules_node_info = snap["controls"].get(partner_short)
                
            # --- GLOBAL MODE LOGIC (Swap/Directional) ---
            else:
                # I am the Destination. I need values FROM Source.
                dst_full = node
                
                if side == "Center":
                    src_short = short
                    rules_node_info = info
                elif mode == "l2r":
                    if side == "Left": continue # Left unchanged
                    src_short = partner_short # Right gets Left
                    rules_node_info = snap["controls"].get(partner_short) # Rules on Left
                elif mode == "r2l":
                    if side == "Right": continue # Right unchanged
                    src_short = partner_short # Left gets Right
                    rules_node_info = info # Rules on Left
                else: # SWAP
                    src_short = partner_short
                    # Rules always on Left or Center
                    if side == "Left":
                        rules_node_info = info
                    else:
                        rules_node_info = snap["controls"].get(partner_short)

            if not src_short or not dst_full or not cmds.objExists(dst_full): continue
            
            # Get Values
            vals = buffer_data.get(src_short)
            if not vals: continue

            # Get Rules
            if not rules_node_info: rules_node_info = info # Fallback
            rules = rules_node_info.get("mirror_rules", {})
            t_mult = rules.get("translate", [1,1,1])
            r_mult = rules.get("rotate", [1,1,1])

            # Apply
            if offset_nodes is None: offset_nodes = []
            
            # Map the buffer values to the correct axes and multipliers!
            mapped_vals = _mirror_attributes(vals, rules)
            
            for attr, final_val in mapped_vals.items():
                # Pivot offset logic (only applies to X translation usually)
                if attr in ("translateX", "tx") and pivot_offset != 0.0 and short in offset_nodes:
                    final_val += pivot_offset
                
                try: cmds.setAttr(f"{dst_full}.{attr}", final_val)
                except: pass
    
    except Exception as e:
        print(f"[ARTools] Mirror Error: {e}")
    finally:
        cmds.undoInfo(closeChunk=True)
        if current_eval_mode != "off": cmds.evaluationManager(mode=current_eval_mode)
        cmds.refresh(suspend=False)
        cmds.refresh(force=True)

def select_mirror_controls(namespace, add=False):
    snap = snapshot.load_snapshot(namespace)
    if not snap: return

    nodes = cmds.ls(sl=True, long=True) or []
    mirror_nodes = []
    
    prefix = namespace + ":" if namespace and not namespace.endswith(":") else namespace

    for node in nodes:
        short = node.split("|")[-1].split(":")[-1]
        info = snap["controls"].get(short)
        if info:
            partner = info.get("mirror")
            if partner:
                full_partner = f"{prefix}{partner}"
                if cmds.objExists(full_partner):
                    mirror_nodes.append(full_partner)
    
    if mirror_nodes:
        if add:
            cmds.select(mirror_nodes, add=True)
        else:
            cmds.select(mirror_nodes, replace=True)

def get_pose_data(global_space=False, use_selection=True):
    """
    Returns pose data dictionary directly for the Library Saver.
    """
    nodes = cmds.ls(sl=True, long=True) if use_selection else []
    if not nodes:
        return {}

    data = {}
    if global_space:
        for node in nodes:
            short = node.split("|")[-1].split(":")[-1]
            matrix = cmds.xform(node, q=True, ws=True, matrix=True)
            data[short] = matrix
    else:
        for node in nodes:
            short = node.split("|")[-1].split(":")[-1]
            attrs = cmds.listAttr(node, keyable=True) or []
            node_data = {}
            for attr in attrs:
                try:
                    val = cmds.getAttr(f"{node}.{attr}")
                    node_data[attr] = val
                except: pass
            data[short] = node_data
    return data

def apply_library_pose(data, namespace="", mirror=False, mix=1.0, show_ui=True):
    """
    Applies pose data from library with support for namespaces, mirroring, and UI feedback.
    show_ui: If True, shows Progress Bar and Confirmation Window.
    """
    if not data: return

    import maya.mel as mel

    ns_prefix = namespace + ":" if namespace and not namespace.endswith(":") else namespace
    
    # Pre-load snapshot if mirroring is required
    snap = None
    if mirror:
        snap = snapshot.load_snapshot(namespace)
        if not snap and show_ui:
            print(f"[ARTools] Warning: No snapshot found for namespace '{namespace}'. Mirroring disabled.")
            mirror = False

    # 1. SETUP PROGRESS BAR
    gMainProgressBar = mel.eval('$tmp = $gMainProgressBar')
    if show_ui:
        cmds.progressBar(gMainProgressBar, edit=True, beginProgress=True, isInterruptable=True, status='Applying Pose...', maxValue=len(data))
    
    cmds.refresh(suspend=True)
    current_eval_mode = cmds.evaluationManager(q=True, mode=True)[0]
    if current_eval_mode != "off": cmds.evaluationManager(mode='off')
    cmds.undoInfo(openChunk=True)
    try:
        # Suppress Script Editor during loop
        cmds.scriptEditorInfo(e=True, suppressResults=True, suppressInfo=True, suppressWarnings=True)
        
        count = 0
        for short_name, content in data.items():
            if short_name == "__namespace__": continue # NEW FILTER LINE
            # Update Progress
            if show_ui:
                if cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                    break
                cmds.progressBar(gMainProgressBar, edit=True, step=1)

            target_short = short_name
            apply_content = content
            
            # --- MIRROR LOGIC ---
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
                        # Use the new dynamic cross-axis mapping helper!
                        apply_content = _mirror_attributes(content, rules)
            # --------------------

            full_node = f"{ns_prefix}{target_short}"
            if not cmds.objExists(full_node): continue

            # Apply Global (Matrix)
            if isinstance(apply_content, list) and len(apply_content) == 16:
                try: cmds.xform(full_node, ws=True, matrix=apply_content)
                except: pass
            
            # Apply Local (Attributes)
            elif isinstance(apply_content, dict):
                for attr, val in apply_content.items():
                    try: 
                        cmds.setAttr(f"{full_node}.{attr}", val)
                    except: pass
                    
    except Exception as e:
        if show_ui: cmds.warning(f"Pose Apply Error: {e}")
    finally:
        cmds.scriptEditorInfo(e=True, suppressResults=False, suppressInfo=False, suppressWarnings=False)
        cmds.undoInfo(closeChunk=True)
        if current_eval_mode != "off": cmds.evaluationManager(mode=current_eval_mode)
        cmds.refresh(suspend=False)
        cmds.refresh(force=True)
        if show_ui:
            cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
            # CONFIRMATION WINDOW
            print("[ARTools] Pose Applied.")

def apply_mixed_pose(target_data, base_data, mix=1.0):
    """
    Blends between base_data and target_data by mix factor (0.0 - 1.0).
    """
    if not target_data or not base_data: return
    mix = max(0.0, min(1.0, mix))
    
    # If 100%, apply directly (Faster + Cleaner), but disable UI (Slider should be silent)
    if mix >= 0.99:
        apply_library_pose(target_data, show_ui=False) 
        return
        
    # ... (Rest of manual mixing logic is handled by PoseBlender usually, 
    # but strictly speaking this function is a fallback if not using Blender class.
    # We keep the old logic here just in case) ...
    
    for short, t_val in target_data.items():
        if short not in base_data: continue
        b_val = base_data[short]
        
        if isinstance(t_val, dict) and isinstance(b_val, dict):
            for attr, t_float in t_val.items():
                if attr not in b_val: continue
                b_float = b_val[attr]
                val = b_float + (t_float - b_float) * mix
                
                if cmds.objExists(short):
                    try: cmds.setAttr(f"{short}.{attr}", val)
                    except: pass
                else:
                    matches = cmds.ls(f"*:{short}", r=True) or cmds.ls(short, r=True)
                    if matches:
                        try: cmds.setAttr(f"{matches[0]}.{attr}", val)
                        except: pass

        elif isinstance(t_val, list) and isinstance(b_val, list):
            if len(t_val) == 16 and len(b_val) == 16:
                mixed_m = []
                for i in range(16):
                    mixed_m.append(b_val[i] + (t_val[i] - b_val[i]) * mix)
                if cmds.objExists(short):
                    try: cmds.xform(short, ws=True, matrix=mixed_m)
                    except: pass

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
                # Use the new dynamic cross-axis mapping helper!
                apply_content = _mirror_attributes(content, rules)
        
        mirrored_data[target_short] = apply_content
        
    return mirrored_data

class PoseBlender(object):
    def __init__(self, target_data, global_space=False):
        self.items = [] 
        self.global_space = global_space
        
        # 1. Map Selection for precise targeting
        selection = cmds.ls(sl=True, long=True)
        valid_nodes_map = {}
        if selection:
            for node in selection:
                short = node.split("|")[-1].split(":")[-1]
                valid_nodes_map[short] = node

        # 2. Capture Start State & Calculate Deltas
        if not self.global_space:
            for short, attrs in target_data.items():
                # Filter: Must be in selection if selection exists
                full_node = None
                if selection:
                    if short not in valid_nodes_map: continue
                    full_node = valid_nodes_map[short]
                else:
                    if cmds.objExists(short): full_node = short
                    else:
                        matches = cmds.ls(f"*:{short}", r=True) or cmds.ls(short, r=True)
                        if matches: full_node = matches[0]
                
                if not full_node: continue
                
                for attr, target_val in attrs.items():
                    full_attr = f"{full_node}.{attr}"
                    
                    # Check if attribute exists AND is modifiable (not locked/connected)
                    if cmds.objExists(full_attr):
                        if not cmds.getAttr(full_attr, settable=True):
                            continue

                        start_val = cmds.getAttr(full_attr)
                        diff = target_val - start_val
                        self.items.append((full_node, attr, start_val, diff))

        else:
            for short, target_matrix in target_data.items():
                full_node = None
                if selection:
                    if short not in valid_nodes_map: continue
                    full_node = valid_nodes_map[short]
                else:
                    if cmds.objExists(short): full_node = short
                    else:
                        matches = cmds.ls(f"*:{short}", r=True) or cmds.ls(short, r=True)
                        if matches: full_node = matches[0]
                
                if not full_node: continue
                
                start_matrix = cmds.xform(full_node, q=True, ws=True, matrix=True)
                self.items.append((full_node, start_matrix, target_matrix))

    def update(self, mix):
        mix = max(0.0, min(1.0, mix))
        
        if not self.global_space:
            for node, attr, start, diff in self.items:
                val = start + (diff * mix)
                cmds.setAttr(f"{node}.{attr}", val)
        else:
            for node, start_m, target_m in self.items:
                new_m = []
                for i in range(16):
                    val = start_m[i] + (target_m[i] - start_m[i]) * mix
                    new_m.append(val)
                cmds.xform(node, ws=True, matrix=new_m)

    def get_blender(target_data, global_space=False):
        return PoseBlender(target_data, global_space)

    def mirror_plane(plane, namespace=""):
        from maya import cmds
        nodes = cmds.ls(sl=True, long=True)
        if not nodes: return
        cmds.undoInfo(openChunk=True)
        s = [-1.0, 1.0, 1.0] if plane == "YZ" else ([1.0, -1.0, 1.0] if plane == "XZ" else [1.0, 1.0, -1.0])
        for node in nodes:
            m = cmds.xform(node, q=True, ws=True, m=True)
            m[0] *= s[0]
            m[1] *= s[0]
            m[2] *= s[0]
            m[4] *= s[1]
            m[5] *= s[1]
            m[6] *= s[1]
            m[8] *= s[2]
            m[9] *= s[2]
            m[10] *= s[2]
            m[12] *= s[0]
            m[13] *= s[1]
            m[14] *= s[2]
            cmds.xform(node, ws=True, m=m)
        cmds.undoInfo(closeChunk=True)