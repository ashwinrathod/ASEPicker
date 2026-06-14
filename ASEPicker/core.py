# ASEPicker/core.py
from maya import cmds
import re
import copy
import uuid

class PickerCore:
    def strip_trailing_colon(self, namespace_str):
        namespace_str = (namespace_str or "").strip()
        if namespace_str.endswith(":"):
            return namespace_str[:-1]
        return namespace_str

    def list_maya_namespaces(self, include_root=True):
        ns_list = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
        ignore_list = ["UI", "shared"]
        filtered_ns = [n for n in ns_list if n not in ignore_list]
        
        if include_root and ":" not in filtered_ns:
            filtered_ns.insert(0, ":")
        elif not include_root:
            filtered_ns = [n for n in filtered_ns if n != ":"]
            
        return filtered_ns

    def strip_namespace_for_save(self, ctrl, active_ns, *args, **kwargs):
        active_ns = self.strip_trailing_colon(active_ns)
        if not active_ns: return ctrl # No active namespace, save absolute
        
        prefix = f"{active_ns}:"
        if ctrl.startswith(prefix):
            return ctrl[len(prefix):]
        else:
            return ctrl
    
    def resolve_control_names(self, controls_list, namespace_str, *args, **kwargs):
        ns_clean = self.strip_trailing_colon(namespace_str)
        resolved = []
        seen = set()

        for ctrl in controls_list:
            ctrl = str(ctrl).strip()
            if not ctrl: continue

            candidate = None
            
            # ATTEMPT 1: The Relative Match (Sub-Tab Namespace + Saved Name)
            if ns_clean:
                # If the saved control already has a colon (nested), just prepend root.
                # If it doesn't, prepend root.
                rel_test = f"{ns_clean}:{ctrl}"
                if cmds.objExists(rel_test):
                    candidate = rel_test
            
            # ATTEMPT 2: The Absolute Fallback (Different Rig / No Namespace)
            if not candidate and cmds.objExists(ctrl):
                candidate = ctrl
                
            # ATTEMPT 3: Legacy Fallback (Just in case older layouts need it)
            if not candidate and ":" in ctrl:
                short = ctrl.split(":")[-1]
                if ns_clean and cmds.objExists(f"{ns_clean}:{short}"):
                    candidate = f"{ns_clean}:{short}"

            if candidate and candidate not in seen:
                seen.add(candidate)
                resolved.append(candidate)

        return resolved
    
    def mirror_string(self, name_str):
        # Dictionary of common rigging prefix/suffix pairs
        pairs = [
            ("L_", "R_"), ("R_", "L_"),
            ("_L", "_R"), ("_R", "_L"),
            ("Left", "Right"), ("Right", "Left"),
            ("left", "right"), ("right", "left")
        ]
        
        for search, replace in pairs:
            if search in name_str:
                return name_str.replace(search, replace)
        return name_str

    def get_mirrored_controls(self, controls_list):
        mirrored_list = []
        for ctrl in controls_list:
            mirrored_list.append(self.mirror_string(ctrl))
        return mirrored_list
    
    def calculate_alignment(self, mode, shape_data):
        # --- SILENT LICENSE TRAP ---
        import sys
        if "ASEPicker.security" in sys.modules:
            from . import security
            saved = security.get_saved_license()
            if not saved: return shape_data

            if saved.startswith("OFF-"):
                chk = security.verify_offline_key(saved)
                if isinstance(chk, tuple) and not chk[0]: return shape_data
                elif not isinstance(chk, tuple) and not chk: return shape_data
            
            if saved.startswith("ONL-"):
                parts = saved.split("|")
                if len(parts) < 2: return shape_data # Allows for the new 3-part Tier format!
        # ---------------------------
        # Pure math logic, zero UI dependencies for IP protection.
        # shape_data = list of dicts: {"id": int, "x": float, "y": float, "w": float, "h": float}
        if len(shape_data) < 2:
            return shape_data

        if mode == "left":
            val = min(d["x"] - d["w"]/2.0 for d in shape_data)
            for d in shape_data: d["x"] = val + d["w"]/2.0
        elif mode == "right":
            val = max(d["x"] + d["w"]/2.0 for d in shape_data)
            for d in shape_data: d["x"] = val - d["w"]/2.0
        elif mode == "center_x":
            val = sum(d["x"] for d in shape_data) / len(shape_data)
            for d in shape_data: d["x"] = val
        elif mode == "top":
            val = min(d["y"] - d["h"]/2.0 for d in shape_data)
            for d in shape_data: d["y"] = val + d["h"]/2.0
        elif mode == "bottom":
            val = max(d["y"] + d["h"]/2.0 for d in shape_data)
            for d in shape_data: d["y"] = val - d["h"]/2.0
        elif mode == "center_y":
            val = sum(d["y"] for d in shape_data) / len(shape_data)
            for d in shape_data: d["y"] = val
        elif mode == "distribute_x":
            shape_data.sort(key=lambda d: d["x"])
            start = shape_data[0]["x"]
            end = shape_data[-1]["x"]
            step = (end - start) / (len(shape_data) - 1)
            for idx, d in enumerate(shape_data):
                d["x"] = start + (step * idx)
        elif mode == "distribute_y":
            shape_data.sort(key=lambda d: d["y"])
            start = shape_data[0]["y"]
            end = shape_data[-1]["y"]
            step = (end - start) / (len(shape_data) - 1)
            for idx, d in enumerate(shape_data):
                d["y"] = start + (step * idx)

        return shape_data
    
    def swap_side_tokens(self, name):
        if not name: return name
        patterns = [
            (r'^L_', 'R_'), (r'^R_', 'L_'),
            (r'_L_', '_R_'), (r'_R_', '_L_'),
            (r'_L$', '_R'), (r'_R$', '_L'),
            (r'^l_', 'r_'), (r'^r_', 'l_'),
            (r'_l_', '_r_'), (r'_r_', '_l_'),
            (r'_l$', '_r'), (r'_r$', '_l'),
            (r'Left', 'Right'), (r'Right', 'Left'),
            (r'left', 'right'), (r'right', 'left')
        ]
        for p, rep in patterns:
            if re.search(p, name):
                return re.sub(p, rep, name)
        return name

    def mirror_shapes_data(self, shape_data_list, direction, use_canvas_center, canvas_rect, is_copy):
        if not shape_data_list: return []
        
        result_data = copy.deepcopy(shape_data_list)
        id_map = {}
        if is_copy:
            for d in result_data:
                old_id = d.get('id', '') # matches serialize_item key
                new_id = str(uuid.uuid4())
                d['id'] = new_id
                id_map[old_id] = new_id
                
            for d in result_data:
                d['parent_links'] = [id_map[p] for p in d.get('parent_links', []) if p in id_map]
                d['child_links'] = [id_map[c] for c in d.get('child_links', []) if c in id_map]
        
        # --- NEW FIX: Always swap side names/controls when mirroring Left/Right! ---
        if direction == 'left_right':
            for d in result_data:
                d['controls'] = [self.swap_side_tokens(c) for c in d.get('controls', [])]
                d['label'] = self.swap_side_tokens(d.get('label', ''))
        
        # --- NEW FIX: 0.0 is the exact center of the Picker Canvas. 
        if use_canvas_center:
            center_x = 0.0
            center_y = 0.0
        else:
            min_x = min(d['pos'][0] - d['width']/2.0 for d in result_data)
            max_x = max(d['pos'][0] + d['width']/2.0 for d in result_data)
            min_y = min(d['pos'][1] - d['height']/2.0 for d in result_data)
            max_y = max(d['pos'][1] + d['height']/2.0 for d in result_data)
            center_x = (min_x + max_x) / 2.0
            center_y = (min_y + max_y) / 2.0
            
        for d in result_data:
            if direction == 'left_right':
                d['pos'][0] = center_x - (d['pos'][0] - center_x)
                d['rotation'] = -d.get('rotation', 0.0)
                
                # Flip Text Alignment
                align_h = d.get('text_align_h', 'center')
                if align_h == 'left': d['text_align_h'] = 'right'
                elif align_h == 'right': d['text_align_h'] = 'left'

                # Flip Round Rectangle Corners
                if d.get('type') == 'Round Rectangle':
                    tr, tl = d.get('rad_tr', 4.0), d.get('rad_tl', 4.0)
                    br, bl = d.get('rad_br', 4.0), d.get('rad_bl', 4.0)
                    d['rad_tl'], d['rad_tr'] = tr, tl
                    d['rad_bl'], d['rad_br'] = br, bl

                # Flip polygon geometry and bezier handles horizontally
                if d.get('type') == 'Polygon' and 'path_data' in d:
                    for pt in d['path_data']:
                        pt['p'][0] = -pt['p'][0]
                        pt['in'][0] = -pt['in'][0]
                        pt['out'][0] = -pt['out'][0]
                        
            elif direction == 'up_down':
                d['pos'][1] = center_y - (d['pos'][1] - center_y)
                d['rotation'] = -d.get('rotation', 0.0)
                
                # Flip Text Alignment
                align_v = d.get('text_align_v', 'center')
                if align_v == 'up': d['text_align_v'] = 'down'
                elif align_v == 'down': d['text_align_v'] = 'up'
                
                # Flip Round Rectangle Corners
                if d.get('type') == 'Round Rectangle':
                    tr, tl = d.get('rad_tr', 4.0), d.get('rad_tl', 4.0)
                    br, bl = d.get('rad_br', 4.0), d.get('rad_bl', 4.0)
                    d['rad_tl'], d['rad_bl'] = bl, tl
                    d['rad_tr'], d['rad_br'] = br, tr

                # Flip polygon geometry and bezier handles vertically
                if d.get('type') == 'Polygon' and 'path_data' in d:
                    for pt in d['path_data']:
                        pt['p'][1] = -pt['p'][1]
                        pt['in'][1] = -pt['in'][1]
                        pt['out'][1] = -pt['out'][1]
                    
        return result_data
    
    def smart_select(self, controls_list, namespace_str, mode="replace"):
        # --- SILENT LICENSE TRAP ---
        import sys
        if "ASEPicker.security" in sys.modules:
            from . import security
            saved = security.get_saved_license()
            if not saved: return

            if saved.startswith("OFF-"):
                chk = security.verify_offline_key(saved)
                if isinstance(chk, tuple) and not chk[0]: return
                elif not isinstance(chk, tuple) and not chk: return
            
            if saved.startswith("ONL-"):
                parts = saved.split("|")
                if len(parts) < 2: return  # Allows for the new 3-part Tier format!
        # -------------------------------------------------------------------------
        
        resolved = self.resolve_control_names(controls_list, namespace_str)
        
        current_selection = cmds.ls(selection=True, long=True) or []
        
        if not resolved:
            if mode == "replace" and current_selection:
                cmds.select(clear=True)
            return

        targets_selection = cmds.ls(resolved, long=True) or []
        
        # Apply Selection Modes
        if mode == "add":
            new_selection = list(dict.fromkeys(current_selection + targets_selection))
        elif mode == "replace":
            new_selection = targets_selection
        elif mode in ["mirror", "invert"]:
            new_selection = current_selection[:]
            for target in targets_selection:
                if target not in new_selection:
                    new_selection.append(target)
                else:
                    new_selection.remove(target)
        elif mode in ["deselect", "remove"]:
            new_selection = [s for s in current_selection if s not in targets_selection]
        else:
            new_selection = targets_selection

        if set(current_selection) != set(new_selection):
            cmds.select(new_selection, replace=True)