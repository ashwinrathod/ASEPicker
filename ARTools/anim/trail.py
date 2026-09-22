# ARTools/anim/trail.py
import maya.cmds as cmds
from PySide6 import QtWidgets, QtCore, QtGui
from functools import partial
import os

PLUGIN_FILE_NAME = "hyper_trail_plugin"
PLUGIN_NODE_TYPE = "hyperTrailMesh" 
SHADER_NAME = "HyperTrailShader"
SG_NAME = "HyperTrailSG"
SCULPT_LOCATOR_SIZE_MULT = 4.0

class TrailManager(object):
    _instance = None
    _job_id = None
    _active_mode = False
    _ontop_enabled = False

    def __init__(self):
        if TrailManager._instance: return
        TrailManager._instance = self
        
        self._sculpt_mode = False
        self._sculpt_jobs = []
        self._sculpt_groups = []
        self._sculpt_cache = {}
        self._cached_key_times = set()
        
        # High-speed independent timer for flawless live UI updates
        self._sculpt_timer = QtCore.QTimer()
        self._sculpt_timer.timeout.connect(self._sculpt_tick)

    @staticmethod
    def get_instance():
        if not TrailManager._instance: TrailManager._instance = TrailManager()
        return TrailManager._instance

    def _ensure_loaded(self):
        if cmds.pluginInfo(PLUGIN_FILE_NAME, q=True, loaded=True): return True
        current_dir = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
        plugin_path = f"{current_dir}/{PLUGIN_FILE_NAME}.py"
        cmds.loadPlugin(plugin_path)
        return True

    def _get_safe_name(self, obj):
        short_name = obj.split("|")[-1]
        clean = short_name.replace(":", "_")
        return f"Trail_{clean}_Mesh"

    def _find_trail_node_from_obj(self, obj):
        if cmds.attributeQuery("message", n=obj, ex=True):
            conns = cmds.listConnections(f"{obj}.message", type=PLUGIN_NODE_TYPE)
            if conns: return conns[0]
        grp_name = self._get_safe_name(obj)
        if cmds.objExists(grp_name):
            shapes = cmds.listRelatives(grp_name, s=True)
            if shapes:
                conns = cmds.listConnections(f"{shapes[0]}.inMesh", type=PLUGIN_NODE_TYPE)
                if conns: return conns[0]
        return None

    def _assign_shader(self, obj):
        if not cmds.objExists(SHADER_NAME):
            cmds.shadingNode("surfaceShader", asShader=True, name=SHADER_NAME)
            cmds.setAttr(f"{SHADER_NAME}.outColor", 1, 1, 1, type="double3") 
        
        if not cmds.objExists(SG_NAME):
            cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=SG_NAME)
            cmds.connectAttr(f"{SHADER_NAME}.outColor", f"{SG_NAME}.surfaceShader")
            
        grp = self._get_safe_name(obj)
        if cmds.objExists(grp):
            shapes = cmds.listRelatives(grp, s=True)
            if shapes:
                cmds.sets(shapes[0], forceElement=SG_NAME)
                cmds.setAttr(f"{shapes[0]}.displayColors", True)
                cmds.setAttr(f"{shapes[0]}.displayColorChannel", "Ambient+Diffuse", type="string")
                cmds.setAttr(f"{shapes[0]}.materialBlend", 0)
                self._set_attr_if_exists(shapes[0], "doubleSided", True) 

    def _find_trail_grp(self, obj):
        trail_node = self._find_trail_node_from_obj(obj)
        if trail_node:
            conns = cmds.listConnections(f"{trail_node}.outputMesh", s=False, d=True, type="mesh")
            if conns:
                parents = cmds.listRelatives(conns[0], p=True)
                if parents: return parents[0]
        grp_name = self._get_safe_name(obj)
        if cmds.objExists(grp_name): return grp_name
        return None

    def _all_trail_groups(self):
        return cmds.ls("Trail_*_Mesh", type="transform") or []

    def _set_attr_if_exists(self, node, attr, value):
        if cmds.objExists(node) and cmds.attributeQuery(attr, node=node, exists=True):
            if cmds.getAttr(f"{node}.{attr}", settable=True):
                cmds.setAttr(f"{node}.{attr}", value)
                return True
        return False

    def _set_bool_attr_if_exists(self, node, attr, state):
        return self._set_attr_if_exists(node, attr, int(state))

    def _link_camera_to_trail(self, trail_node):
        import maya.api.OpenMayaUI as omui
        try:
            view = omui.M3dView.active3dView()
            cam_dag = view.getCamera()
            cam_name = cam_dag.partialPathName()
            target_plug = f"{cam_name}.worldMatrix[0]"
            dest_plug = f"{trail_node}.cameraMatrix"
            conns = cmds.listConnections(dest_plug, s=True, d=False, plugs=True)
            if not conns or conns[0] != target_plug:
                cmds.connectAttr(target_plug, dest_plug, force=True)
        except: pass

    def _apply_ontop_to_group(self, grp, state):
        if not grp or not cmds.objExists(grp): return

        trail_node = None
        shapes = cmds.listRelatives(grp, shapes=True, fullPath=True) or []
        for shape in shapes:
            conns = cmds.listConnections(f"{shape}.inMesh", type=PLUGIN_NODE_TYPE)
            if conns:
                trail_node = conns[0]
                break

        if trail_node:
            if not cmds.attributeQuery("onTop", node=trail_node, exists=True):
                cmds.addAttr(trail_node, longName="onTop", attributeType="bool")
            cmds.setAttr(f"{trail_node}.onTop", state)
            if state: self._link_camera_to_trail(trail_node)

        for shape in shapes:
            cmds.displaySurface(shape, xRay=0)
            self._set_bool_attr_if_exists(shape, "alwaysDrawOnTop", 0)
            self._set_bool_attr_if_exists(shape, "doubleSided", True)
            if not cmds.attributeQuery("hyperTrailOnTop", node=shape, exists=True):
                cmds.addAttr(shape, longName="hyperTrailOnTop", attributeType="bool")
            cmds.setAttr(f"{shape}.hyperTrailOnTop", int(state))

    def _ontop_state_from_scene(self):
        for grp in self._all_trail_groups():
            shapes = cmds.listRelatives(grp, shapes=True, fullPath=True) or []
            for shape in shapes:
                if cmds.attributeQuery("hyperTrailOnTop", node=shape, exists=True):
                    if cmds.getAttr(f"{shape}.hyperTrailOnTop"): return True
        return self._ontop_enabled

    def hide_all_trails(self):
        for g in cmds.ls("Trail_*_Mesh", type="transform"):
            if cmds.getAttr(f"{g}.visibility", settable=True):
                cmds.setAttr(f"{g}.visibility", 0)

    def show_all_trails(self):
        for g in cmds.ls("Trail_*_Mesh", type="transform"):
            if cmds.getAttr(f"{g}.visibility", settable=True):
                cmds.setAttr(f"{g}.visibility", 1)

    def delete_trail(self):
        sel = cmds.ls(sl=True)
        if not sel: return
        for obj in sel:
            trail = self._find_trail_node_from_obj(obj)
            grp = self._get_safe_name(obj)
            if trail and cmds.objExists(trail): cmds.delete(trail)
            if cmds.objExists(grp): cmds.delete(grp)

    # =========================================================================
    # REFINED 3D ARC SCULPTOR ENGINE 
    # =========================================================================
    def toggle_sculpt_mode(self, state):
        self._sculpt_mode = state
        if state:
            self._build_sculpt_proxies()
            self._sculpt_timer.start(30)
        else:
            self._sculpt_timer.stop()
            self._clear_sculpt_proxies()

    def _sample_matrix_safe(self, plug_path, t):
        # Same fix already applied in hyper_trail_plugin.py's update_neighbors_live:
        # under Parallel/Serial Evaluation Manager, per-frame matrix queries can
        # silently return the cached current-time value instead of the real
        # value at frame t. Force DG mode for the sample, then restore.
        prev_mode = cmds.evaluationManager(query=True, mode=True)[0]
        if prev_mode != "off":
            cmds.evaluationManager(mode="off")

        matrix_values = cmds.getAttr(plug_path, time=t)

        if prev_mode != "off":
            cmds.evaluationManager(mode=prev_mode)

        return matrix_values

    def _build_sculpt_proxies(self):
        self._clear_sculpt_proxies()
        sel = cmds.ls(sl=True)
        if not sel: return
        
        import maya.api.OpenMaya as om
        self._sculpt_cache = {}
        is_ontop = self._ontop_enabled or self._ontop_state_from_scene()
        
        for obj in sel:
            trail_node = self._find_trail_node_from_obj(obj)
            if not trail_node: continue

            grp_name = self._get_safe_name(obj).replace("_Mesh", "_SculptGrp")
            if cmds.objExists(grp_name): cmds.delete(grp_name)
            grp = cmds.createNode("transform", name=grp_name)
            self._sculpt_groups.append(grp)
            
            for attr in ["tx","ty","tz","rx","ry","rz","sx","sy","sz"]:
                cmds.setAttr(f"{grp}.{attr}", lock=True)
            
            times = cmds.keyframe(obj, at=["translate"], q=True, tc=True) or []
            if not times: continue
            times = sorted(list(set(times)))
            self._cached_key_times = set(times)
            
            parent = cmds.listRelatives(obj, p=True, f=True)
            parent_node = parent[0] if parent else None
            
            for t in times:
                loc = cmds.spaceLocator(name=f"SculptProxy_{int(t)}")[0]
                cmds.parent(loc, grp)
                
                shape = cmds.listRelatives(loc, s=True)[0]
                cmds.setAttr(f"{shape}.overrideEnabled", 1)
                cmds.setAttr(f"{shape}.overrideColor", 17)
                
                # Native display override for "On Top" visual priority
                if cmds.attributeQuery("alwaysDrawOnTop", node=shape, exists=True):
                    cmds.setAttr(f"{shape}.alwaysDrawOnTop", 1 if is_ontop else 0)
                
                # Set initial World Position securely (No camera distortion)
                wm_list = self._sample_matrix_safe(f"{obj}.worldMatrix[0]", t)
                wm = om.MMatrix(wm_list)
                real_pos = (wm[12], wm[13], wm[14])
                cmds.xform(loc, ws=True, t=real_pos)
                
                self._sculpt_cache[loc] = {
                    "ctrl": obj, 
                    "time": t, 
                    "parent_node": parent_node,
                    "trail_node": trail_node
                }
                
                # Lock unneeded channels so you can only Translate
                for attr in ["rx","ry","rz","sx","sy","sz"]:
                    cmds.setAttr(f"{loc}.{attr}", lock=True, keyable=False)
                    
                # Bind the native ScriptJob to track interactive viewport dragging
                for axis in ["x", "y", "z"]:
                    plug = f"{loc}.t{axis}"
                    job = cmds.scriptJob(ac=[plug, partial(self._on_proxy_moved, loc)], protected=True)
                    self._sculpt_jobs.append(job)
        
        self._sculpt_tick()
        cmds.select(sel)

    def _sculpt_tick(self):
        """Live QTimer Loop: Updates visibility & scale during scrubs, catches new keys instantly."""
        if not self._sculpt_cache: return

        # 1. Dynamic Keyframe Check: Rebuild if you hit 'S' or deleted a key!
        ctrl = list(self._sculpt_cache.values())[0]["ctrl"]
        if not cmds.objExists(ctrl): return
        
        current_keys = cmds.keyframe(ctrl, at=["translate"], q=True, tc=True) or []
        current_keys = set(current_keys)
        
        if current_keys != self._cached_key_times:
            # Safely rebuild proxies since keyframes changed
            self._build_sculpt_proxies()
            return

        # 2. Live Scrubbing Update (Visibility & Taper Scale ONLY)
        cur_t = cmds.currentTime(q=True)

        for loc, data in self._sculpt_cache.items():
            if not cmds.objExists(loc): continue
            t = data["time"]
            trail_node = data["trail_node"]
            if not cmds.objExists(trail_node): continue

            pre = cmds.getAttr(f"{trail_node}.preFrame")
            post = cmds.getAttr(f"{trail_node}.postFrame")
            width = cmds.getAttr(f"{trail_node}.width")
            is_all = (pre == 0 and post == 0)
            is_taper = cmds.getAttr(f"{trail_node}.taper") if cmds.attributeQuery("taper", node=trail_node, exists=True) else False

            # Visibility check (If "All" is active, it stays visible. Otherwise check window bounds)
            if is_all or (cur_t - pre <= t <= cur_t + post):
                cmds.setAttr(f"{loc}.visibility", 1)

                # Taper scaling: mirrors the plugin's own Key Dot math exactly
                # (linear falloff with a 0.25 floor -- no smoothstep), and
                # scales with the trail's actual width instead of a fixed size.
                if is_taper:
                    dist = abs(t - cur_t)
                    max_d = max(pre, post) if max(pre, post) > 0 else 1.0
                    fade = max(0.25, 1.0 - (dist / float(max_d)))
                else:
                    fade = 1.0

                shape = cmds.listRelatives(loc, s=True)[0]
                base_scale = width * fade * SCULPT_LOCATOR_SIZE_MULT
                cmds.setAttr(f"{shape}.localScaleX", base_scale)
                cmds.setAttr(f"{shape}.localScaleY", base_scale)
                cmds.setAttr(f"{shape}.localScaleZ", base_scale)

            else:
                cmds.setAttr(f"{loc}.visibility", 0)

    def _clear_sculpt_proxies(self):
        for job in getattr(self, "_sculpt_jobs", []):
            if cmds.scriptJob(exists=job): cmds.scriptJob(kill=job, force=True)
        self._sculpt_jobs = []
        
        for grp in getattr(self, "_sculpt_groups", []):
            if cmds.objExists(grp): cmds.delete(grp)
        self._sculpt_groups = []
        self._sculpt_cache = {}
        self._cached_key_times = set()

    def _on_proxy_moved(self, loc):
        if not cmds.objExists(loc): return
        
        data = getattr(self, "_sculpt_cache", {}).get(loc)
        if not data: return
        
        ctrl = data["ctrl"]
        t = data["time"]
        parent_node = data["parent_node"]
        trail_node = data["trail_node"]
        if not cmds.objExists(ctrl): return

        cmds.undoInfo(openChunk=True, chunkName="ARTools_SculptProxyMove")

        import maya.api.OpenMaya as om
        
        # 1. Read the precise drag position directly
        ws_pos = cmds.xform(loc, q=True, ws=True, t=True)
        ws_pt = om.MPoint(ws_pos[0], ws_pos[1], ws_pos[2])
        
        # 2. Local Translation Offset Calculation for the Bone
        if parent_node:
            inv_mat_list = self._sample_matrix_safe(f"{parent_node}.worldInverseMatrix[0]", t)
            inv_mat = om.MMatrix(inv_mat_list)
            loc_pt = ws_pt * inv_mat
            lx, ly, lz = loc_pt.x, loc_pt.y, loc_pt.z
        else:
            lx, ly, lz = ws_pt.x, ws_pt.y, ws_pt.z
        
        # 3. Securely Overwrite the underlying Control Keyframe
        if not cmds.getAttr(f"{ctrl}.tx", lock=True):
            cmds.keyframe(ctrl, at="tx", time=(t,t), e=True, a=True, vc=lx)
        if not cmds.getAttr(f"{ctrl}.ty", lock=True):
            cmds.keyframe(ctrl, at="ty", time=(t,t), e=True, a=True, vc=ly)
        if not cmds.getAttr(f"{ctrl}.tz", lock=True):
            cmds.keyframe(ctrl, at="tz", time=(t,t), e=True, a=True, vc=lz)
            
        # 4. INSTANT TRAIL UPDATE: Inject directly into the Plugin's Array to prevent lag
        if cmds.objExists(trail_node):
            start_time = cmds.getAttr(f"{trail_node}.startTime")
            idx = int(t - start_time)
            
            sel_list = om.MSelectionList()
            sel_list.add(trail_node)
            fn_node = om.MFnDependencyNode(sel_list.getDependNode(0))
            plug = fn_node.findPlug("trailData", False)
            
            obj_data = plug.asMObject()
            if not obj_data.isNull():
                vec_array = om.MFnVectorArrayData(obj_data).array()
                if 0 <= idx < len(vec_array):
                    vec_array[idx] = om.MVector(ws_pos[0], ws_pos[1], ws_pos[2])
                    
                    # Create a new data object and push it to forcefully dirty the plug
                    new_mobj = om.MFnVectorArrayData().create(vec_array)
                    plug.setMObject(new_mobj)

        cmds.undoInfo(closeChunk=True)
        cmds.refresh(cv=True)

    def auto_smooth_arc(self):
        sel = cmds.ls(sl=True)
        if not sel: return
        
        import maya.api.OpenMaya as om
        cmds.undoInfo(openChunk=True, chunkName="ARTools_SmoothArc")
        try:
            for obj in sel:
                times = cmds.keyframe(obj, at=["translate"], q=True, tc=True)
                if not times: continue
                times = sorted(list(set(times)))
                if len(times) < 3: continue
                
                world_positions = {}
                for t in times:
                    wm_list = self._sample_matrix_safe(f"{obj}.worldMatrix[0]", t)
                    wm = om.MMatrix(wm_list)
                    world_positions[t] = om.MPoint(wm[12], wm[13], wm[14])
                
                new_positions = {}
                for i in range(1, len(times)-1):
                    t = times[i]
                    p_prev = world_positions[times[i-1]]
                    p_curr = world_positions[t]
                    p_next = world_positions[times[i+1]]
                    
                    smoothed = om.MPoint(
                        (p_prev.x + p_curr.x * 2.0 + p_next.x) / 4.0,
                        (p_prev.y + p_curr.y * 2.0 + p_next.y) / 4.0,
                        (p_prev.z + p_curr.z * 2.0 + p_next.z) / 4.0
                    )
                    new_positions[t] = smoothed
                
                parent = cmds.listRelatives(obj, p=True, f=True)
                parent_node = parent[0] if parent else None
                
                for t, ws_pt in new_positions.items():
                    if parent_node:
                        inv_mat_list = self._sample_matrix_safe(f"{parent_node}.worldInverseMatrix[0]", t)
                        inv_mat = om.MMatrix(inv_mat_list)
                        loc_pt = ws_pt * inv_mat
                        lx, ly, lz = loc_pt.x, loc_pt.y, loc_pt.z
                    else:
                        lx, ly, lz = ws_pt.x, ws_pt.y, ws_pt.z
                        
                    if not cmds.getAttr(f"{obj}.tx", lock=True):
                        cmds.keyframe(obj, at="tx", time=(t,t), e=True, a=True, vc=lx)
                    if not cmds.getAttr(f"{obj}.ty", lock=True):
                        cmds.keyframe(obj, at="ty", time=(t,t), e=True, a=True, vc=ly)
                    if not cmds.getAttr(f"{obj}.tz", lock=True):
                        cmds.keyframe(obj, at="tz", time=(t,t), e=True, a=True, vc=lz)
                        
            cmds.inViewMessage(amg="Arc Smoothed Successfully", pos="midCenter", fade=True)
            
            if getattr(self, "_sculpt_mode", False):
                self._build_sculpt_proxies()
                
        except Exception as e:
            cmds.warning(f"Failed to smooth arc: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

    # =========================================================================

    def create_or_toggle(self, force_create=False, default_frames=None):
        if not self._ensure_loaded(): return
        sel = cmds.ls(sl=True)
        if not sel: return
        for obj in sel:
            if "Trail_" in obj and "_Mesh" in obj: continue
            existing_grp = self._find_trail_grp(obj)
            if existing_grp:
                if force_create:
                    if not cmds.getAttr(f"{existing_grp}.visibility"):
                        cmds.setAttr(f"{existing_grp}.visibility", 1)
                else:
                    is_vis = cmds.getAttr(f"{existing_grp}.visibility")
                    cmds.setAttr(f"{existing_grp}.visibility", 0 if is_vis else 1)
            else:
                cmds.select(obj)
                cmds.spHyperTrail()
                self._assign_shader(obj)
                if default_frames is not None:
                    trail_node = self._find_trail_node_from_obj(obj)
                    if trail_node:
                        cmds.setAttr(f"{trail_node}.preFrame", default_frames)
                        cmds.setAttr(f"{trail_node}.postFrame", default_frames)
                if self._ontop_enabled or self._ontop_state_from_scene():
                    self._apply_ontop_to_group(self._find_trail_grp(obj), True)
                    
        # --- Restore original selection after trails are generated ---
        if sel:
            cmds.select(sel, replace=True)

    def on_selection_change(self):
        if not self._active_mode: return
        all_trails = cmds.ls("Trail_*_Mesh", type="transform")
        for t in all_trails:
            if cmds.objExists(t): cmds.setAttr(f"{t}.visibility", 0)
        sel = cmds.ls(sl=True)
        if sel:
            self.create_or_toggle(force_create=True, default_frames=10)

    def toggle_active_mode(self, *args):
        self._active_mode = not self._active_mode
        if self._active_mode:
            if self._job_id is None:
                self._job_id = cmds.scriptJob(e=["SelectionChanged", self.on_selection_change])
            self.on_selection_change()
            print("Active Mode: ON")
        else:
            if self._job_id is not None:
                cmds.scriptJob(kill=self._job_id, force=True)
                self._job_id = None
            print("Active Mode: OFF")

    def toggle_ontop(self, state):
        self._ontop_enabled = bool(state)
        for grp in self._all_trail_groups():
            self._apply_ontop_to_group(grp, state)
            
        # Dynamically update existing proxy handles
        for loc in getattr(self, "_sculpt_cache", {}).keys():
            if cmds.objExists(loc):
                shape = cmds.listRelatives(loc, s=True)[0]
                if cmds.attributeQuery("alwaysDrawOnTop", node=shape, exists=True):
                    cmds.setAttr(f"{shape}.alwaysDrawOnTop", 1 if state else 0)

    def set_attr(self, attr, val, *args):
        for obj in cmds.ls(sl=True):
            trail = self._find_trail_node_from_obj(obj)
            if trail: cmds.setAttr(f"{trail}.{attr}", val)

    def set_colors(self, pre, post, *args):
        for obj in cmds.ls(sl=True):
            trail = self._find_trail_node_from_obj(obj)
            if trail:
                cmds.setAttr(f"{trail}.colorPre", *pre, type="double3")
                cmds.setAttr(f"{trail}.colorPost", *post, type="double3")

    def set_pre_post(self, val, *args):
        for obj in cmds.ls(sl=True):
            trail = self._find_trail_node_from_obj(obj)
            if trail:
                cmds.setAttr(f"{trail}.preFrame", val)
                cmds.setAttr(f"{trail}.postFrame", val)

    def link_active_camera(self):
        import maya.api.OpenMayaUI as omui
        try:
            view = omui.M3dView.active3dView()
            cam_dag = view.getCamera()
            cam_name = cam_dag.partialPathName()
            for obj in cmds.ls(sl=True):
                trail = self._find_trail_node_from_obj(obj)
                if trail:
                    cmds.connectAttr(f"{cam_name}.worldMatrix[0]", f"{trail}.cameraMatrix", f=True)
        except: pass

    def set_camera_space(self):
        self.set_attr("trailMode", 1)
        self.link_active_camera()

    def delete_all_trails(self):
        trails = cmds.ls(type=PLUGIN_NODE_TYPE)
        if trails: cmds.delete(trails)
        groups = cmds.ls("Trail_*_Mesh", type="transform")
        if groups: cmds.delete(groups)
        self._clear_sculpt_proxies()
        print("All trails deleted.")

    def create_context_menu(self):
        parent_win = QtWidgets.QApplication.activeWindow()
        menu = QtWidgets.QMenu(parent_win)
        menu.setStyleSheet("""
            QMenu { background-color: #2A2A2A; color: #E0E0E0; border: 1px solid #444444; border-radius: 6px; padding: 4px 0px; }
            QMenu::item { padding: 6px 20px 6px 32px; background-color: transparent; margin: 0px 4px; border-radius: 4px; }
            QMenu::item:selected { background-color: #444444; color: white; }
            QMenu::separator { height: 1px; background: #444444; margin: 4px 8px; }
            QMenu::indicator { width: 12px; height: 12px; left: 10px; border: 1px solid #666; border-radius: 2px; background: #111; }
            QMenu::indicator:checked { background-color: #4CAF50; border: 1px solid #4CAF50; }
        """)
        
        act = menu.addAction("Active Mode")
        act.setCheckable(True)
        act.setChecked(self._active_mode)
        act.triggered.connect(self.toggle_active_mode)
        
        is_ontop, is_spacing, is_taper, is_speed = self._ontop_state_from_scene(), False, False, False
        sel = cmds.ls(sl=True)
        current_width = 0.3 
        
        if sel:
            trail_node = self._find_trail_node_from_obj(sel[0])
            if trail_node:
                current_width = cmds.getAttr(f"{trail_node}.width")
                if cmds.attributeQuery("spacingMode", node=trail_node, exists=True):
                    is_spacing = cmds.getAttr(f"{trail_node}.spacingMode")
                if cmds.attributeQuery("taper", node=trail_node, exists=True):
                    is_taper = cmds.getAttr(f"{trail_node}.taper")
                if cmds.attributeQuery("speedColors", node=trail_node, exists=True):
                    is_speed = cmds.getAttr(f"{trail_node}.speedColors")
        
        act_ontop = menu.addAction("On Top")
        act_ontop.setCheckable(True)
        act_ontop.setChecked(is_ontop)
        act_ontop.triggered.connect(self.toggle_ontop)
        
        act_spacing = menu.addAction("Spacing (Zebra Pattern)")
        act_spacing.setCheckable(True); act_spacing.setChecked(is_spacing)
        act_spacing.triggered.connect(partial(self.set_attr, "spacingMode", not is_spacing))
        
        act_taper = menu.addAction("Taper Ends (Comet)")
        act_taper.setCheckable(True); act_taper.setChecked(is_taper)
        act_taper.triggered.connect(partial(self.set_attr, "taper", not is_taper))
        
        act_speed = menu.addAction("Speed Colors (Velocity)")
        act_speed.setCheckable(True); act_speed.setChecked(is_speed)
        act_speed.triggered.connect(partial(self.set_attr, "speedColors", not is_speed))
        
        show_keys = False
        if sel and trail_node:
             if cmds.attributeQuery("showKeys", node=trail_node, exists=True):
                 show_keys = cmds.getAttr(f"{trail_node}.showKeys")

        act_keys = menu.addAction("Show Keys")
        act_keys.setCheckable(True)
        act_keys.setChecked(show_keys)
        act_keys.triggered.connect(partial(self.set_attr, "showKeys", not show_keys))

        menu.addSeparator()
        
        act_sculpt = menu.addAction("Sculpt Mode (Interactive Handles)")
        act_sculpt.setCheckable(True)
        act_sculpt.setChecked(getattr(self, "_sculpt_mode", False))
        act_sculpt.triggered.connect(self.toggle_sculpt_mode)

        act_smooth = menu.addAction("Auto-Smooth Arc (Laplacian)")
        act_smooth.triggered.connect(self.auto_smooth_arc)
        
        menu.addSeparator()

        m_theme = menu.addMenu("Themes")
        m_theme.addAction("Standard", partial(self.set_colors, (0,0,1), (1,1,0)))
        m_theme.addAction("Magma", partial(self.set_colors, (1,0,0), (1,0.5,0)))
        m_theme.addAction("Cyber", partial(self.set_colors, (0.5,0,1), (0,1,1)))
        m_theme.addAction("Matrix", partial(self.set_colors, (0,0.3,0), (0,1,0)))
        
        m_solid = menu.addMenu("Solid Colors")
        m_solid.addAction("Red", partial(self.set_colors, (1,0,0), (1,0,0)))
        m_solid.addAction("Green", partial(self.set_colors, (0,1,0), (0,1,0)))
        m_solid.addAction("Blue", partial(self.set_colors, (0,0,1), (0,0,1)))
        m_solid.addAction("Yellow", partial(self.set_colors, (1,1,0), (1,1,0)))
        m_solid.addAction("Cyan", partial(self.set_colors, (0,1,1), (0,1,1)))
        
        menu.addSeparator()

        m_mode = menu.addMenu("Mode")
        m_mode.addAction("World Space", partial(self.set_attr, "trailMode", 0))
        m_mode.addAction("Camera Space", self.set_camera_space)

        m_prepost = menu.addMenu("Pre - Post Frames")
        for i in [0, 5, 10, 15, 20, 35, 50]:
            m_prepost.addAction("All" if i==0 else str(i), partial(self.set_pre_post, i))

        menu.addSeparator()

        slider_act = QtWidgets.QWidgetAction(menu)
        w_widget = QtWidgets.QWidget(menu)
        w_widget.setStyleSheet("background: transparent; color: #E0E0E0;")
        w_layout = QtWidgets.QHBoxLayout(w_widget)
        w_layout.setContentsMargins(15, 4, 15, 4)
        
        lbl = QtWidgets.QLabel("Width: ")
        w_layout.addWidget(lbl)
        
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setStyleSheet("""
            QSlider::groove:horizontal { border: 1px solid #444; height: 4px; background: #111; border-radius: 2px; }
            QSlider::handle:horizontal { background: #555; width: 12px; margin: -4px 0; border-radius: 6px; border: 1px solid #777;}
            QSlider::handle:horizontal:hover { background: #4CAF50; border: 1px solid #FFF;}
        """)
        slider.setRange(1, 100) 
        slider.setValue(int(current_width * 100))
        slider.setFixedWidth(100)
        
        val_lbl = QtWidgets.QLabel(f"{current_width:.2f}")
        w_layout.addWidget(slider)
        w_layout.addWidget(val_lbl)
        
        def on_slide(val):
            f_val = val / 100.0
            self.set_attr("width", f_val)
            val_lbl.setText(f"{f_val:.2f}")
            
        slider.valueChanged.connect(on_slide)
        slider_act.setDefaultWidget(w_widget)
        menu.addAction(slider_act)

        m_style = menu.addMenu("Line Style")
        m_style.addAction("Solid ______", partial(self.set_attr, "lineStyle", 0))
        m_style.addAction("Dash _ _ _ ", partial(self.set_attr, "lineStyle", 1))
        m_style.addAction("Dot .  .  .", partial(self.set_attr, "lineStyle", 2))

        menu.addSeparator()

        menu.addAction("Hide All Trails", self.hide_all_trails)
        menu.addAction("Show All Trails", self.show_all_trails)
        menu.addAction("Delete Trail", self.delete_trail)
        menu.addAction("Delete All Trails", self.delete_all_trails)
        return menu

    def exec_context_menu(self):
        self.create_context_menu().exec_(QtGui.QCursor.pos())