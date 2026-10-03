# ARTools/anim/trail.py
import bpy
import gpu
import mathutils
import bpy_extras.view3d_utils
from gpu_extras.batch import batch_for_shader
from PySide6 import QtWidgets, QtCore, QtGui
from functools import partial
import os
from ..blender_host import selected_object_names, object_by_name, add_timer, remove_timer, select_objects

class TrailManager(object):
    _instance = None
    _active_mode = False

    def __init__(self):
        if TrailManager._instance: return
        TrailManager._instance = self

    @staticmethod
    def get_instance():
        if not TrailManager._instance: TrailManager._instance = TrailManager()
        return TrailManager._instance

    def _ensure_loaded(self):
        HyperTrailCommands.register()
        return True

    def _get_motion_path(self, b_obj):
        if not b_obj: return None
        return getattr(b_obj, "motion_path", None)

    def hide_all_trails(self):
        print("[ARTools] Use standard Blender overlays to toggle visibility globally.")

    def show_all_trails(self):
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    with bpy.context.temp_override(window=window, area=area):
                        bpy.ops.object.paths_update_visible()
                    return
        if bpy.ops.object.paths_update_visible.poll():
            bpy.ops.object.paths_update_visible()

    def delete_trail(self):
        sel = selected_object_names()
        if not sel: return
        ARCustomTrailEngine.remove_targets(sel)
        select_objects(sel, replace=True)
        
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    with bpy.context.temp_override(window=window, area=area):
                        if bpy.context.mode == 'POSE':
                            bpy.ops.pose.paths_clear(only_selected=True)
                        else:
                            bpy.ops.object.paths_clear(only_selected=True)
                    return
                    
        if bpy.context.mode == 'POSE': bpy.ops.pose.paths_clear(only_selected=True)
        else: bpy.ops.object.paths_clear(only_selected=True)

    def delete_all_trails(self):
        ARCustomTrailEngine.disable()
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    with bpy.context.temp_override(window=window, area=area):
                        if bpy.context.mode == 'POSE':
                            bpy.ops.pose.paths_clear(only_selected=False)
                        else:
                            bpy.ops.object.paths_clear(only_selected=False)
                    print("All trails deleted.")
                    return
                    
        if bpy.context.mode == 'POSE': bpy.ops.pose.paths_clear(only_selected=False)
        else: bpy.ops.object.paths_clear(only_selected=False)
        print("All trails deleted.")

    def create_or_toggle(self, force_create=False, default_frames=None):
        if not self._ensure_loaded(): return
        sel = selected_object_names()
        if not sel: return
        
        # Only treat this as a toggle-off if every currently selected
        # control already has a trail; otherwise we're adding new ones.
        already_trailed = all(name in ARCustomTrailEngine._target_objects for name in sel)
        
        if already_trailed and not force_create:
            self.delete_trail()
        else:
            pre = default_frames if default_frames is not None else 15
            HyperTrailCommands.create_hyper_trail(sel, pre, pre)

    def toggle_active_mode(self, *args):
        self._active_mode = not self._active_mode
        if self._active_mode: print("Active Mode: ON")
        else: print("Active Mode: OFF")

    def toggle_ontop(self, state):
        print("[ARTools] OnTop is managed by Blender's Native Display mode.")

    def set_colors(self, pre, post, zebra=False):
        ARCustomTrailEngine._color_slow = pre
        ARCustomTrailEngine._color_fast = post
        ARCustomTrailEngine._is_zebra = zebra
        if ARCustomTrailEngine._is_active:
            # Re-slice the GPU batches with the new colors
            ARCustomTrailEngine.update_gpu_batches()
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

    def set_pre_post(self, val):
        sel = selected_object_names()
        if not sel: return
        HyperTrailCommands.create_hyper_trail(sel, val, val)

    def set_thickness(self, val):
        ARCustomTrailEngine._thickness = max(1.0, float(val / 10.0))
        if ARCustomTrailEngine._is_active:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

    def create_context_menu(self):
        parent_win = QtWidgets.QApplication.activeWindow()
        menu = QtWidgets.QMenu(parent_win)
        menu.setStyleSheet("""
            QMenu { background-color: #2A2A2A; color: #E0E0E0; border: 1px solid #444444; border-radius: 6px; padding: 4px 0px; }
            QMenu::item { padding: 6px 20px 6px 32px; background-color: transparent; margin: 0px 4px; border-radius: 4px; }
            QMenu::item:selected { background-color: #444444; color: white; }
            QMenu::separator { height: 1px; background: #444444; margin: 4px 8px; }
        """)
        
        lbl = menu.addAction("--- NATIVE MOTION PATHS ---")
        lbl.setEnabled(False)
        menu.addSeparator()

        m_theme = menu.addMenu("Themes (Blender 4.2+)")
        m_theme.addAction("Standard", partial(self.set_colors, (0,0,1), (1,1,0), False))
        m_theme.addAction("Magma", partial(self.set_colors, (1,0,0), (1,0.5,0), False))
        m_theme.addAction("Cyber", partial(self.set_colors, (0.5,0,1), (0,1,1), False))
        m_theme.addAction("Matrix", partial(self.set_colors, (0,0.3,0), (0,1,0), False))
        m_theme.addAction("Zebra Pattern", partial(self.set_colors, (0,0.5,1), (1,0.2,0), True))
        
        m_solid = menu.addMenu("Solid Colors")
        m_solid.addAction("Red", partial(self.set_colors, (1,0,0), (1,0,0), False))
        m_solid.addAction("Green", partial(self.set_colors, (0,1,0), (0,1,0), False))
        m_solid.addAction("Blue", partial(self.set_colors, (0,0,1), (0,0,1), False))
        m_solid.addAction("Yellow", partial(self.set_colors, (1,1,0), (1,1,0), False))
        m_solid.addAction("Cyan", partial(self.set_colors, (0,1,1), (0,1,1), False))
        
        menu.addSeparator()

        m_prepost = menu.addMenu("Pre - Post Frames")
        for i in [5, 10, 15, 20, 35, 50]:
            m_prepost.addAction(str(i), partial(self.set_pre_post, i))

        menu.addSeparator()

        slider_act = QtWidgets.QWidgetAction(menu)
        w_widget = QtWidgets.QWidget(menu)
        w_widget.setStyleSheet("background: transparent; color: #E0E0E0;")
        w_layout = QtWidgets.QHBoxLayout(w_widget)
        w_layout.setContentsMargins(15, 4, 15, 4)
        
        lbl2 = QtWidgets.QLabel("Thickness: ")
        w_layout.addWidget(lbl2)
        
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setStyleSheet("""
            QSlider::groove:horizontal { border: 1px solid #444; height: 4px; background: #111; border-radius: 2px; }
            QSlider::handle:horizontal { background: #555; width: 12px; margin: -4px 0; border-radius: 6px; border: 1px solid #777;}
            QSlider::handle:horizontal:hover { background: #4CAF50; border: 1px solid #FFF;}
        """)
        slider.setRange(1, 100) 
        slider.setValue(20)
        slider.setFixedWidth(100)
        
        val_lbl = QtWidgets.QLabel("2")
        w_layout.addWidget(slider)
        w_layout.addWidget(val_lbl)
        
        def on_slide(val):
            self.set_thickness(val)
            val_lbl.setText(str(max(1, int(val/10.0))))
            
        slider.valueChanged.connect(on_slide)
        slider_act.setDefaultWidget(w_widget)
        menu.addAction(slider_act)

        menu.addSeparator()
        menu.addAction("Delete Trail", self.delete_trail)
        menu.addAction("Delete All Trails", self.delete_all_trails)
        return menu

    def exec_context_menu(self):
        menu = self.create_context_menu()
        if menu:
            menu.exec_(QtGui.QCursor.pos())

class ARCustomTrailRaycaster(bpy.types.Operator):
    bl_idname = "anim.ar_trail_raycaster"
    bl_label = "Trail Raycaster"

    def modal(self, context, event):
        # Shut down if the trail is turned off
        if not ARCustomTrailEngine._is_active:
            return {'FINISHED'}

        # We only get events again once transform.translate has finished,
        # so seeing any event here means the drag is over.
        if HyperTrailManager._drag_active:
            HyperTrailManager._drag_active = False

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            region = context.region
            rv3d = context.region_data
            if not region or not rv3d: return {'PASS_THROUGH'}

            mouse_pos = (event.mouse_region_x, event.mouse_region_y)
            closest_obj = None
            closest_frame = None
            min_dist = 20.0 # 20-pixel grab radius
            
            orig_frame = context.scene.frame_current
            target_start = orig_frame - ARCustomTrailEngine._pre_frames
            target_end = orig_frame + ARCustomTrailEngine._post_frames

            # 1. Fire Ray and Detect Closest Bead
            for obj_name, keys in ARCustomTrailEngine._master_keys.items():
                if obj_name not in ARCustomTrailEngine._master_coords: continue
                
                for f in keys:
                    if target_start <= f <= target_end:
                        coord_3d = ARCustomTrailEngine._master_coords[obj_name].get(f)
                        if coord_3d:
                            coord_2d = bpy_extras.view3d_utils.location_3d_to_region_2d(region, rv3d, coord_3d)
                            if coord_2d:
                                dist = (mathutils.Vector(coord_2d) - mathutils.Vector(mouse_pos)).length
                                if dist < min_dist:
                                    min_dist = dist
                                    closest_obj = obj_name
                                    closest_frame = f

            # 2. Execute Hit Sequence
            if closest_obj and closest_frame is not None:
                context.scene.frame_set(closest_frame)
                
                from ..blender_host import object_by_name
                b_obj = object_by_name(closest_obj)
                if b_obj:
                    if hasattr(b_obj, "bone"):
                        # Pure Python bone selection (Zero Context Errors)
                        b_obj.id_data.select_set(True)
                        context.view_layer.objects.active = b_obj.id_data
                        for pbone in b_obj.id_data.pose.bones:
                            pbone.select = False
                        b_obj.select = True
                    else:
                        bpy.ops.object.select_all(action='DESELECT')
                        b_obj.select_set(True)
                        context.view_layer.objects.active = b_obj
                        
                # 3. Trigger native translation tool seamlessly
                if bpy.ops.transform.translate.poll():
                    HyperTrailManager._drag_active = True
                    bpy.ops.transform.translate('INVOKE_DEFAULT')
                return {'RUNNING_MODAL'} # Block native click so the control isn't deselected

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class HyperTrailManager:
    _is_in_handler = False
    _last_interaction_time = 0.0
    _timer_running = False
    _drag_active = False

class HyperTrailCommands:
    @staticmethod
    def depsgraph_update_handler(scene, depsgraph=None):
        if not ARCustomTrailEngine._is_active: return
        if bpy.context.screen and bpy.context.screen.is_animation_playing: return
        
        # 1. Strict Filter: Completely ignore selection changes and viewport panning
        if depsgraph:
            is_relevant = False
            for update in depsgraph.updates:
                if not (update.is_updated_transform or update.is_updated_geometry):
                    continue
                if isinstance(update.id, bpy.types.Object):
                    # Check if object itself moved
                    if update.id.name in ARCustomTrailEngine._target_objects:
                        is_relevant = True
                        break
                    # If it's a rig, check if our target bones belong to it
                    if update.id.type == 'ARMATURE':
                        from ..blender_host import object_by_name
                        for obj_name in ARCustomTrailEngine._target_objects:
                            b_obj = object_by_name(obj_name)
                            if b_obj and hasattr(b_obj, "bone") and b_obj.id_data.name == update.id.name:
                                is_relevant = True
                                break
            if not is_relevant:
                return

        # 2. Position Filter: on armatures, Blender flags a transform update
        # even for pure selection changes, so confirm something actually
        # moved before doing any work.
        if not ARCustomTrailEngine.any_target_moved():
            return

        # 3. Zero-lag live injection
        ARCustomTrailEngine.update_live_frame()
        
        # 2. Debouncer for full timeline sync (Catches parent movements/deleted keys)
        import time
        HyperTrailManager._last_interaction_time = time.time()
        if not HyperTrailManager._timer_running:
            bpy.app.timers.register(HyperTrailCommands.debounced_timer, first_interval=0.2)
            HyperTrailManager._timer_running = True

    @staticmethod
    def debounced_timer():
        import time
        if time.time() - HyperTrailManager._last_interaction_time < 0.15:
            return 0.1

        # Never rebuild mid-drag: scrubbing the timeline here would reset
        # the control to its last keyframed value before the drag is confirmed.
        if HyperTrailManager._drag_active:
            return 0.1

        HyperTrailManager._timer_running = False
        # Silently rebuild the master cache in the background
        ARCustomTrailEngine.build_master_cache()
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        return None

    @staticmethod
    def frame_change_handler(scene, depsgraph=None):
        if not ARCustomTrailEngine._is_active: return
        # Re-slice the visual trail window instantly (Zero lag scrubbing)
        ARCustomTrailEngine.update_gpu_batches()
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

    @staticmethod
    def create_hyper_trail(sel_names, pre=15, post=15):
        ARCustomTrailEngine._pre_frames = pre
        ARCustomTrailEngine._post_frames = post
        for obj_name in sel_names:
            if obj_name not in ARCustomTrailEngine._target_objects:
                ARCustomTrailEngine._target_objects.append(obj_name)

        from ..blender_host import object_by_name
        for obj_name in sel_names:
            b_obj = object_by_name(obj_name)
            if not b_obj: continue
            is_pose = hasattr(b_obj, "bone")
            if is_pose and getattr(b_obj, "motion_path", None) and bpy.ops.pose.paths_clear.poll():
                bpy.ops.pose.paths_clear(only_selected=False)
            elif not is_pose and getattr(b_obj, "motion_path", None) and bpy.ops.object.paths_clear.poll():
                bpy.ops.object.paths_clear(only_selected=False)

        ARCustomTrailEngine.build_master_cache()
        
        # Start Raycaster safely in the 3D Viewport context
        was_active = ARCustomTrailEngine._is_active
        ARCustomTrailEngine.enable()

        if not was_active:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type != 'VIEW_3D':
                        continue
                    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                    if not region:
                        continue
                    with bpy.context.temp_override(window=window, area=area, region=region):
                        if bpy.ops.anim.ar_trail_raycaster.poll():
                            bpy.ops.anim.ar_trail_raycaster('INVOKE_DEFAULT')
                        else:
                            print("[ARTools] Raycaster did not start: poll() failed.")
                    break

    @staticmethod
    def register():
        if not hasattr(bpy.types, "ANIM_OT_ar_trail_raycaster"):
            bpy.utils.register_class(ARCustomTrailRaycaster)
            
        if HyperTrailCommands.depsgraph_update_handler not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(HyperTrailCommands.depsgraph_update_handler)
        if HyperTrailCommands.frame_change_handler not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(HyperTrailCommands.frame_change_handler)

    @staticmethod
    def unregister():
        if hasattr(bpy.types, "ANIM_OT_ar_trail_raycaster"):
            bpy.utils.unregister_class(ARCustomTrailRaycaster)
            
        if HyperTrailCommands.depsgraph_update_handler in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(HyperTrailCommands.depsgraph_update_handler)
        if HyperTrailCommands.frame_change_handler in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.remove(HyperTrailCommands.frame_change_handler)

class ARCustomTrailEngine:
    _handle = None
    _shader = None
    _is_active = False
    
    _thickness = 3.0
    _color_slow = (0.0, 0.5, 1.0)
    _color_fast = (1.0, 0.2, 0.0)
    _is_zebra = False
    _pre_frames = 15
    _post_frames = 15
    _target_objects = []
    
    _master_coords = {}
    _master_keys = {}
    _gpu_batches = {}

    @classmethod
    def enable(cls):
        if cls._is_active: return
        cls._shader = gpu.shader.from_builtin('SMOOTH_COLOR')
        cls._handle = bpy.types.SpaceView3D.draw_handler_add(cls.draw_callback_px, (), 'WINDOW', 'POST_VIEW')
        cls._is_active = True

    @classmethod
    def disable(cls):
        if not cls._is_active: return
        bpy.types.SpaceView3D.draw_handler_remove(cls._handle, 'WINDOW')
        cls._master_coords.clear()
        cls._master_keys.clear()
        cls._gpu_batches.clear()
        cls._target_objects = []
        cls._is_active = False

    @classmethod
    def remove_targets(cls, names):
        for name in names:
            cls._target_objects = [n for n in cls._target_objects if n != name]
            cls._master_coords.pop(name, None)
            cls._master_keys.pop(name, None)
            cls._gpu_batches.pop(name, None)

        if not cls._target_objects:
            cls.disable()
        else:
            cls.update_gpu_batches()

    @classmethod
    def build_master_cache(cls):
        if not cls._target_objects: return
        scene = bpy.context.scene
        orig_frame = scene.frame_current
        start_f = int(scene.frame_start)
        end_f = int(scene.frame_end)
        
        from ..blender_host import object_by_name

        for obj_name in cls._target_objects:
            cls._master_coords[obj_name] = {}
            cls._master_keys[obj_name] = set()
            
            b_obj = object_by_name(obj_name)
            if not b_obj: continue
            
            anim_obj = b_obj.id_data if hasattr(b_obj, "bone") else b_obj
            if anim_obj.animation_data and anim_obj.animation_data.action:
                action = anim_obj.animation_data.action
                path_prefix = b_obj.path_from_id() if hasattr(b_obj, "path_from_id") else ""
                fcurves_list = []
                
                if hasattr(action, "fcurves"):
                    fcurves_list.extend(action.fcurves)
                elif hasattr(action, "slots") and hasattr(action, "layers"):
                    for slot in action.slots:
                        for layer in action.layers:
                            for strip in layer.strips:
                                cb = strip.channelbag(slot)
                                if cb and hasattr(cb, "fcurves"):
                                    fcurves_list.extend(cb.fcurves)
                                    
                for fc in fcurves_list:
                    if path_prefix and not fc.data_path.startswith(path_prefix): continue
                    for kf in fc.keyframe_points:
                        cls._master_keys[obj_name].add(int(kf.co[0]))
        
        # Frame iteration loop (Fast Python Evaluation)
        for f in range(start_f, end_f + 1):
            scene.frame_set(f)
            bpy.context.view_layer.update()
            
            for obj_name in cls._target_objects:
                b_obj = object_by_name(obj_name)
                if not b_obj: continue
                
                if hasattr(b_obj, "bone"):
                    mat = b_obj.id_data.matrix_world @ b_obj.matrix
                else:
                    mat = b_obj.matrix_world
                    
                cls._master_coords[obj_name][f] = mat.translation.copy()
                
        scene.frame_set(orig_frame)
        cls.update_gpu_batches()

    @classmethod
    def update_live_frame(cls):
        orig_frame = bpy.context.scene.frame_current
        from ..blender_host import object_by_name
        
        redraw = False
        for obj_name in cls._target_objects:
            b_obj = object_by_name(obj_name)
            if not b_obj: continue
            
            if hasattr(b_obj, "bone"):
                mat = b_obj.id_data.matrix_world @ b_obj.matrix
            else:
                mat = b_obj.matrix_world
                
            if obj_name not in cls._master_coords:
                cls._master_coords[obj_name] = {}
                
            cls._master_coords[obj_name][orig_frame] = mat.translation.copy()
            redraw = True
            
        if redraw:
            cls.update_gpu_batches()

    @classmethod
    def any_target_moved(cls):
        from ..blender_host import object_by_name
        orig_frame = bpy.context.scene.frame_current

        for obj_name in cls._target_objects:
            b_obj = object_by_name(obj_name)
            if not b_obj:
                continue

            if hasattr(b_obj, "bone"):
                mat = b_obj.id_data.matrix_world @ b_obj.matrix
            else:
                mat = b_obj.matrix_world

            last = cls._master_coords.get(obj_name, {}).get(orig_frame)
            if last is None or (mat.translation - last).length > 1e-6:
                return True

        return False
    
    @classmethod
    def update_gpu_batches(cls):
        orig_frame = bpy.context.scene.frame_current
        if not cls._shader: cls._shader = gpu.shader.from_builtin('SMOOTH_COLOR')
        
        for obj_name in cls._target_objects:
            if obj_name not in cls._master_coords: continue
            
            target_start = orig_frame - cls._pre_frames
            target_end = orig_frame + cls._post_frames
            
            coords = []
            frames = []
            keys = cls._master_keys.get(obj_name, set())
            
            # Safely slice the master cache
            for f in range(target_start, target_end + 1):
                if f in cls._master_coords[obj_name]:
                    frames.append(f)
                    coords.append(cls._master_coords[obj_name][f])
                    
            if len(coords) < 2:
                cls._gpu_batches[obj_name] = {}
                continue
                
            key_coords = []
            key_colors = []
            
            if cls._is_zebra:
                line_coords = []
                line_colors = []
                for i in range(len(coords) - 1):
                    f = frames[i]
                    c = cls._color_fast if f % 2 == 0 else cls._color_slow
                    line_coords.extend([coords[i], coords[i+1]])
                    line_colors.extend([(c[0], c[1], c[2], 1.0), (c[0], c[1], c[2], 1.0)])
                    
                    if f in keys:
                        key_coords.append(coords[i])
                        key_colors.append((1.0, 1.0, 1.0, 1.0))
                        
                if frames[-1] in keys:
                    key_coords.append(coords[-1])
                    key_colors.append((1.0, 1.0, 1.0, 1.0))
                    
                batch_line = batch_for_shader(cls._shader, 'LINES', {"pos": line_coords, "color": line_colors})
                point_colors = [line_colors[i*2] for i in range(len(coords)-1)] + [line_colors[-1]]
                batch_pts = batch_for_shader(cls._shader, 'POINTS', {"pos": coords, "color": point_colors})
                
            else:
                colors = []
                distances = [0.0]
                max_dist = 0.001
                
                for i in range(1, len(coords)):
                    dist = (coords[i] - coords[i-1]).length
                    distances.append(dist)
                    if dist > max_dist: max_dist = dist
                        
                for i in range(len(coords)):
                    speed_factor = distances[i] / max_dist 
                    r = cls._color_slow[0] + (cls._color_fast[0] - cls._color_slow[0]) * speed_factor
                    g = cls._color_slow[1] + (cls._color_fast[1] - cls._color_slow[1]) * speed_factor
                    b = cls._color_slow[2] + (cls._color_fast[2] - cls._color_slow[2]) * speed_factor
                    
                    f = frames[i]
                    if f == orig_frame:
                        colors.append((1.0, 1.0, 1.0, 1.0))
                    else:
                        dist_from_cur = abs(f - orig_frame)
                        max_f = max(1, cls._pre_frames if f < orig_frame else cls._post_frames)
                        alpha = max(0.1, 1.0 - (dist_from_cur / max_f))
                        colors.append((r, g, b, alpha))
                        
                    if f in keys:
                        key_coords.append(coords[i])
                        key_colors.append((1.0, 1.0, 1.0, 1.0))
                        
                batch_line = batch_for_shader(cls._shader, 'LINE_STRIP', {"pos": coords, "color": colors})
                batch_pts = batch_for_shader(cls._shader, 'POINTS', {"pos": coords, "color": colors})
                
            batch_keys = batch_for_shader(cls._shader, 'POINTS', {"pos": key_coords, "color": key_colors}) if key_coords else None
            
            cls._gpu_batches[obj_name] = {
                'line': batch_line,
                'points': batch_pts,
                'keys': batch_keys
            }

    @classmethod
    def draw_callback_px(cls):
        if not cls._gpu_batches: return
        
        gpu.state.blend_set('ALPHA')
        cls._shader.bind()
        
        for obj_name, batches in cls._gpu_batches.items():
            if hasattr(gpu.state, "line_width_set"):
                gpu.state.line_width_set(cls._thickness)
            if batches.get('line'): batches['line'].draw(cls._shader)
            
            if hasattr(gpu.state, "point_size_set"):
                gpu.state.point_size_set(cls._thickness * 1.5)
            if batches.get('points'): batches['points'].draw(cls._shader)
            
            if hasattr(gpu.state, "point_size_set"):
                gpu.state.point_size_set(cls._thickness * 3.5)
            if batches.get('keys'): batches['keys'].draw(cls._shader)
            
        gpu.state.blend_set('NONE')