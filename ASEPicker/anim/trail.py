import maya.cmds as cmds
try:
    from PySide2 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui
from functools import partial
import os

PLUGIN_FILE_NAME = "hyper_trail_plugin"
PLUGIN_NODE_TYPE = "hyperTrailMesh" 
SHADER_NAME = "HyperTrailShader"
SG_NAME = "HyperTrailSG"

class TrailManager(object):
    _instance = None
    _job_id = None
    _active_mode = False
    _ontop_enabled = False

    def __init__(self):
        if TrailManager._instance: return
        TrailManager._instance = self

    @staticmethod
    def get_instance():
        if not TrailManager._instance: TrailManager._instance = TrailManager()
        return TrailManager._instance

    def _ensure_loaded(self):
        if cmds.pluginInfo(PLUGIN_FILE_NAME, q=True, loaded=True): return True
        
        # Get absolute directory and FORCE forward slashes for Maya
        current_dir = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
        plugin_path = f"{current_dir}/{PLUGIN_FILE_NAME}.py"
        
        # Maya requires the .py extension. The file is encrypted, so it is safe!
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
        # Fallback to name-based lookup for reliability
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
        # Robust method: Find group via connections
        trail_node = self._find_trail_node_from_obj(obj)
        if trail_node:
            # Trace: hyperTrailMesh.outputMesh -> mesh.inMesh -> Transform
            conns = cmds.listConnections(f"{trail_node}.outputMesh", s=False, d=True, type="mesh")
            if conns:
                parents = cmds.listRelatives(conns[0], p=True)
                if parents: return parents[0]
        
        # Fallback: Name prediction
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

    def _apply_ontop_to_group(self, grp, state):
        if not grp or not cmds.objExists(grp):
            return

        shapes = cmds.listRelatives(grp, shapes=True, fullPath=True) or []
        for shape in shapes:
            cmds.displaySurface(shape, xRay=0)
            self._set_bool_attr_if_exists(shape, "alwaysDrawOnTop", state)
            self._set_bool_attr_if_exists(shape, "doubleSided", not state)
            self._set_attr_if_exists(shape, "materialBlend", 0)

            if cmds.objExists(SHADER_NAME):
                cmds.setAttr(f"{SHADER_NAME}.outTransparency", 0.0, 0.0, 0.0, type="double3")

            if not cmds.attributeQuery("hyperTrailOnTop", node=shape, exists=True):
                cmds.addAttr(shape, longName="hyperTrailOnTop", attributeType="bool")
            cmds.setAttr(f"{shape}.hyperTrailOnTop", int(state))

    def _ontop_state_from_scene(self):
        for grp in self._all_trail_groups():
            shapes = cmds.listRelatives(grp, shapes=True, fullPath=True) or []
            for shape in shapes:
                if cmds.attributeQuery("hyperTrailOnTop", node=shape, exists=True):
                    if cmds.getAttr(f"{shape}.hyperTrailOnTop"):
                        return True
        return self._ontop_enabled

    def hide_all_trails(self):
        # FIX: Replaced bare try/except with settable check — works on all OS
        grps = cmds.ls("Trail_*_Mesh", type="transform")
        for g in grps:
            if cmds.getAttr(f"{g}.visibility", settable=True):
                cmds.setAttr(f"{g}.visibility", 0)

    def show_all_trails(self):
        # FIX: Replaced bare try/except with settable check — works on all OS
        grps = cmds.ls("Trail_*_Mesh", type="transform")
        for g in grps:
            if cmds.getAttr(f"{g}.visibility", settable=True):
                cmds.setAttr(f"{g}.visibility", 1)

    def delete_trail(self):
        sel = cmds.ls(sl=True)
        if not sel: return
        for obj in sel:
            # Explicitly delete Plugin Node AND Group to ensure clean removal
            trail = self._find_trail_node_from_obj(obj)
            grp = self._get_safe_name(obj)
            
            if trail and cmds.objExists(trail): cmds.delete(trail)
            if cmds.objExists(grp): cmds.delete(grp)
        print("Trail deleted.")

    def create_or_toggle(self, force_create=False, default_frames=None):
        if not self._ensure_loaded(): return
        
        sel = cmds.ls(sl=True)
        if not sel: return
        
        for obj in sel:
            # Prevent self-selection errors
            if "Trail_" in obj and "_Mesh" in obj: continue

            # Use robust finder
            existing_grp = self._find_trail_grp(obj)
            
            if existing_grp:
                # Exists -> Toggle Visibility
                if force_create:
                    # In Active Mode, just ensure it's visible. 
                    # Don't toggle off if already on.
                    if not cmds.getAttr(f"{existing_grp}.visibility"):
                        cmds.setAttr(f"{existing_grp}.visibility", 1)
                else:
                    is_vis = cmds.getAttr(f"{existing_grp}.visibility")
                    cmds.setAttr(f"{existing_grp}.visibility", 0 if is_vis else 1)
            else:
                # Missing -> Create
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

    def set_attr(self, attr, val):
        for obj in cmds.ls(sl=True):
            trail = self._find_trail_node_from_obj(obj)
            if trail: cmds.setAttr(f"{trail}.{attr}", val)

    def set_colors(self, pre, post):
        for obj in cmds.ls(sl=True):
            trail = self._find_trail_node_from_obj(obj)
            if trail:
                cmds.setAttr(f"{trail}.colorPre", *pre, type="double3")
                cmds.setAttr(f"{trail}.colorPost", *post, type="double3")

    def set_pre_post(self, val):
        for obj in cmds.ls(sl=True):
            trail = self._find_trail_node_from_obj(obj)
            if trail:
                cmds.setAttr(f"{trail}.preFrame", val)
                cmds.setAttr(f"{trail}.postFrame", val)

    def link_active_camera(self):
        import maya.api.OpenMayaUI as omui
        view = omui.M3dView.active3dView()
        cam_dag = view.getCamera()
        cam_name = cam_dag.partialPathName()
        
        for obj in cmds.ls(sl=True):
            trail = self._find_trail_node_from_obj(obj)
            if trail:
                cmds.connectAttr(f"{cam_name}.worldMatrix[0]", f"{trail}.cameraMatrix", f=True)
        print(f"Linked trails to camera: {cam_name}")

    def set_camera_space(self):
        self.set_attr("trailMode", 1)
        self.link_active_camera()

    def delete_all_trails(self):
        # Delete by Plugin Node Type
        trails = cmds.ls(type=PLUGIN_NODE_TYPE)
        if trails: cmds.delete(trails)
        
        # Delete by Group Naming Convention (Cleanup)
        groups = cmds.ls("Trail_*_Mesh", type="transform")
        if groups: cmds.delete(groups)
        
        print("All trails deleted.")

    def create_context_menu(self):
        parent_win = QtWidgets.QApplication.activeWindow()
        menu = QtWidgets.QMenu(parent_win)
        menu.setStyleSheet("""
            QMenu { background-color: #2A2A2A; color: #E0E0E0; border: 1px solid #444444; border-radius: 6px; padding: 4px 0px; }
            /* Increased left padding from 20px to 32px to make room for the checkbox */
            QMenu::item { padding: 6px 20px 6px 32px; background-color: transparent; margin: 0px 4px; border-radius: 4px; }
            QMenu::item:selected { background-color: #444444; color: white; }
            QMenu::separator { height: 1px; background: #444444; margin: 4px 8px; }
            
            /* Add custom checkbox indicator visuals */
            QMenu::indicator { width: 12px; height: 12px; left: 10px; border: 1px solid #666; border-radius: 2px; background: #111; }
            QMenu::indicator:checked { background-color: #4CAF50; border: 1px solid #4CAF50; }
        """)
        
        act = menu.addAction("Active Mode")
        act.setCheckable(True)
        act.setChecked(self._active_mode)
        act.triggered.connect(self.toggle_active_mode)
        
        is_ontop, is_spacing, is_taper, is_speed = self._ontop_state_from_scene(), False, False, False
        sel = cmds.ls(sl=True)
        current_width = 0.3 # Default
        
        if sel:
            # Check Current Width and new upgrades
            trail_node = self._find_trail_node_from_obj(sel[0])
            if trail_node:
                current_width = cmds.getAttr(f"{trail_node}.width")
                if cmds.attributeQuery("spacingMode", node=trail_node, exists=True):
                    is_spacing = cmds.getAttr(f"{trail_node}.spacingMode")
                if cmds.attributeQuery("taper", node=trail_node, exists=True):
                    is_taper = cmds.getAttr(f"{trail_node}.taper")
                if cmds.attributeQuery("speedColors", node=trail_node, exists=True):
                    is_speed = cmds.getAttr(f"{trail_node}.speedColors")
        
        # --- MENU ACTIONS ---
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

        # --- WIDTH SLIDER ---
        # Using a QWidgetAction to insert a custom slider layout
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
        slider.setRange(1, 100) # 0.01 to 1.00
        slider.setValue(int(current_width * 100))
        slider.setFixedWidth(100)
        
        # Label to show live value
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
        # --------------------

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





