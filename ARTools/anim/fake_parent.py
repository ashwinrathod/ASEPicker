# ARTools/anim/fake_parent.py
import bpy
import mathutils
from PySide6 import QtCore
from ..blender_host import object_by_name, selected_object_names, add_timer, remove_timer
import math

class FakeParentManager:
    def __init__(self, button):
        self.button = button
        self.parent_node = None
        self.children_data = {}
        self.is_armed = False
        
    def toggle(self, modifiers=0):
        is_shift = bool(modifiers & QtCore.Qt.ShiftModifier)
        if self.is_active():
            self.apply(bake=is_shift)
        else:
            self.capture()
            
    def is_active(self):
        return self.parent_node is not None and len(self.children_data) > 0
        
    def _get_matrix(self, node):
        b_obj = object_by_name(node)
        if b_obj:
            if hasattr(b_obj, "matrix_world"):
                return b_obj.matrix_world.copy()
            else:
                return b_obj.id_data.matrix_world @ b_obj.matrix.copy()
        return mathutils.Matrix()
        
    def _set_matrix(self, node, mat):
        b_obj = object_by_name(node)
        if b_obj:
            if hasattr(b_obj, "matrix_world"):
                b_obj.matrix_world = mat
            else:
                # Convert target world matrix back to armature local space for the bone
                b_obj.matrix = b_obj.id_data.matrix_world.inverted_safe() @ mat

    def _safe_undo_push(self, message):
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    with bpy.context.temp_override(window=window, area=area):
                        bpy.ops.ed.undo_push(message=message)
                    return

    def capture(self):
        sel = selected_object_names()
        if len(sel) < 2:
            print("[ARTools] Fake Parent: Select the Parent first, then one or more Children.")
            return
            
        self.parent_node = sel[0]
        self.children_data = {}
        
        # Calculate Offset: LocalOffset = ParentWorld.inverse @ ChildWorld
        p_inv = self._get_matrix(self.parent_node).inverted()
        for child in sel[1:]:
            c_mat = self._get_matrix(child)
            offset = p_inv @ c_mat
            self.children_data[child] = offset
            
        self._set_active_ui(True)
        
        if getattr(self, "is_armed", False):
            remove_timer(self.on_selection_changed)
            
        self.is_armed = True
        add_timer(self.on_selection_changed, interval=0.5)
        print(f"[ARTools] Fake Parent Armed. Parent: {self.parent_node.split(':')[-1]}")
        
    def apply(self, bake=False):
        if not self.is_active(): return
        
        if bake:
            self._bake_timeline()
        else:
            p_mat = self._get_matrix(self.parent_node)
            autokey = bpy.context.scene.tool_settings.use_keyframe_insert_auto
            
            for child, offset in self.children_data.items():
                b_obj = object_by_name(child)
                if b_obj:
                    new_mat = p_mat @ offset
                    self._set_matrix(child, new_mat)
                    if autokey:
                        b_obj.keyframe_insert(data_path="location")
                        if hasattr(b_obj, "rotation_mode") and b_obj.rotation_mode == 'QUATERNION':
                            b_obj.keyframe_insert(data_path="rotation_quaternion")
                        else:
                            b_obj.keyframe_insert(data_path="rotation_euler")
                        
            self._safe_undo_push("ARTools_FakeParent")
            print("[ARTools] Fake Parent Applied")
    
    def _bake_timeline(self):
        scene = bpy.context.scene
        start_t = end_t = scene.frame_current
        
        if scene.use_preview_range:
            start_t = scene.frame_preview_start
            end_t = scene.frame_preview_end
        else:
            start_t = scene.frame_start
            end_t = scene.frame_end
            
        frames = [float(f) for f in range(int(start_t), int(end_t) + 1)]
        
        for f in frames:
            scene.frame_set(int(f))
            p_mat = self._get_matrix(self.parent_node)
            for child, offset in self.children_data.items():
                b_obj = object_by_name(child)
                if b_obj:
                    new_mat = p_mat @ offset
                    self._set_matrix(child, new_mat)
                    b_obj.keyframe_insert(data_path="location")
                    if hasattr(b_obj, "rotation_mode") and b_obj.rotation_mode == 'QUATERNION':
                        b_obj.keyframe_insert(data_path="rotation_quaternion")
                    else:
                        b_obj.keyframe_insert(data_path="rotation_euler")
                    
        # Dynamic Euler Filter to prevent Gimbal Flips across the newly baked range
        for child in self.children_data.keys():
            b_obj = object_by_name(child)
            if not b_obj: continue
            
            # Secure animation data routing for PoseBones
            anim_host = b_obj.id_data if hasattr(b_obj, "id_data") else b_obj
            if not anim_host.animation_data or not anim_host.animation_data.action:
                continue
                
            rot_path = b_obj.path_from_id("rotation_euler") if hasattr(b_obj, "path_from_id") else "rotation_euler"
            
            for fc in anim_host.animation_data.action.fcurves:
                if fc.data_path == rot_path:
                    prev_y = None
                    for kp in sorted(fc.keyframe_points, key=lambda k: k.co.x):
                        if prev_y is not None:
                            diff = kp.co.y - prev_y
                            if abs(diff) > math.pi:
                                offset_val = round(diff / (2 * math.pi)) * 2 * math.pi
                                kp.co.y -= offset_val
                                kp.handle_left.y -= offset_val
                                kp.handle_right.y -= offset_val
                        prev_y = kp.co.y
                    fc.update()
                    
        self._safe_undo_push("ARTools_FakeParentBake")
        print(f"[ARTools] Fake Parent Baked ({len(frames)} Frames)")
            
    def on_selection_changed(self):
        if not self.is_active(): return 0.5
        sel = selected_object_names()
        
        # Rule: Any foreign selection wipes the tool
        if not sel:
            self.clear()
            return 0.5
            
        valid_nodes = set(self.children_data.keys())
        valid_nodes.add(self.parent_node)
        
        for s in sel:
            if s not in valid_nodes:
                self.clear()
                return 0.5
        return 0.5
                
    def clear(self):
        self.parent_node = None
        self.children_data = {}
        if getattr(self, "is_armed", False):
            remove_timer(self.on_selection_changed)
            self.is_armed = False
        self._set_active_ui(False)
        
    def _set_active_ui(self, is_active):
        if not self.button: return
        if is_active:
            self.button.setStyleSheet("background: rgba(79, 184, 167, 100); border: 2px solid #4CAF50;")
        else:
            self.button.setStyleSheet("background: transparent; border: none;")