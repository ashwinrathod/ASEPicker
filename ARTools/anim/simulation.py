# ARTools/anim/simulation.py
from PySide6 import QtWidgets, QtCore, QtGui
import maya.cmds as cmds
import maya.api.OpenMaya as om
import math
import json
import os

class TargetItemWidget(QtWidgets.QWidget):
    def __init__(self, name, parent=None):
        super(TargetItemWidget, self).__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        self.lbl = QtWidgets.QLabel(name)
        self.lbl.setStyleSheet("color: #E8EEF2; font-weight: bold;")
        
        self.btn_mute = QtWidgets.QPushButton("Mute")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setFixedWidth(50)
        self.btn_mute.setStyleSheet("""
            QPushButton { background: #2A353D; border: 1px solid #3A454D; border-radius: 4px; padding: 4px; color: #FFF; }
            QPushButton:checked { background: #C5534A; color: white; border: 1px solid #A03A3A; }
        """)
        
        layout.addWidget(self.lbl)
        layout.addWidget(self.btn_mute)

class OverlapPhysicsSolver:
    def __init__(self):
        self.preview_layer = "ARTools_Overlap_Preview"

    def _apply_wind(self, frame, wind_dir, turbulence):
        speed = math.sqrt(wind_dir[0]**2 + wind_dir[1]**2 + wind_dir[2]**2)
        if speed < 0.001:
            return om.MVector(0, 0, 0)
            
        freq = speed * 0.5
        noise_x = math.sin(frame * 0.2 * freq) * turbulence * speed
        noise_y = math.cos(frame * 0.15 * freq) * turbulence * speed
        noise_z = math.sin(frame * 0.25 * freq) * turbulence * speed
        
        scalar = 0.1
        return om.MVector((wind_dir[0] + noise_x) * scalar, (wind_dir[1] + noise_y) * scalar, (wind_dir[2] + noise_z) * scalar)

    def clear_preview(self):
        if cmds.objExists(self.preview_layer):
            cmds.delete(self.preview_layer)

    def run_simulation(self, target_chains, colliders, params, bake_target=None, step=1):
        if not target_chains:
            cmds.warning("[ARTools] No unmuted target chains loaded for simulation.")
            return

        cmds.undoInfo(openChunk=True, chunkName="ARTools_Simulate")

        start = int(cmds.playbackOptions(q=True, minTime=True))
        end = int(cmds.playbackOptions(q=True, maxTime=True))

        flat_controls = []
        for chain in target_chains:
            for c in chain:
                if c not in flat_controls:
                    flat_controls.append(c)

        spring = ((params.get("spring", 30) / 100.0) ** 1.5) * 0.5 
        drag_val = params.get("drag", 85) / 100.0
        drag = 1.0 - ((1.0 - drag_val) ** 2.0)
        base_weight = ((params.get("weight", 10) / 20.0) ** 1.5) + 0.1     
        
        raw_grav = params.get("gravity", 0.0)
        grav_sign = 1.0 if raw_grav >= 0 else -1.0
        gravity_force = grav_sign * ((abs(raw_grav) / 100.0) ** 2.5) * 1.5 
        
        col_thick = params.get("col_thick", 1.5)
        col_bounce = params.get("col_bounce", 0.0)
        respect_keys = params.get("respect_keys", True)
        
        use_wind = params.get("use_wind", False)
        wind_dir = params.get("wind_dir", [1.0, 0.0, 0.0])

        target_layer = self.preview_layer
        if bake_target == "Base Animation":
            target_layer = None
            self.clear_preview()
        elif bake_target == "Current AnimLayer":
            target_layer = None
            all_layers = cmds.ls(type="animLayer") or []
            for layer in all_layers:
                if cmds.animLayer(layer, query=True, selected=True):
                    target_layer = layer
                    break
            self.clear_preview()
        elif bake_target == "New AnimLayer":
            target_layer = cmds.animLayer("ARTools_Dynamics", override=True)
            self.clear_preview()
        else:
            self.clear_preview()
            cmds.animLayer(self.preview_layer, override=True)

        if target_layer and not cmds.objExists(target_layer):
            cmds.animLayer(target_layer, override=True)

        if target_layer:
            for ctl in flat_controls:
                for axis in ["rx", "ry", "rz"]:
                    plug = f"{ctl}.{axis}"
                    if cmds.objExists(plug) and cmds.getAttr(plug, settable=True):
                        cmds.animLayer(target_layer, edit=True, attribute=plug)

        anim_cache = {}
        for ctl in flat_controls:
            anim_cache[ctl] = {}
            ctl_keys = set()
            for axis in ["rx", "ry", "rz"]:
                plug = f"{ctl}.{axis}"
                if cmds.objExists(plug):
                    keys = cmds.keyframe(plug, q=True, time=(start, end)) or []
                    ctl_keys.update([int(k) for k in keys])
            
            ctl_keys.add(start)
            
            for f in range(start, end + 1):
                rx = cmds.getAttr(f"{ctl}.rx", time=f) if cmds.objExists(f"{ctl}.rx") else 0.0
                ry = cmds.getAttr(f"{ctl}.ry", time=f) if cmds.objExists(f"{ctl}.ry") else 0.0
                rz = cmds.getAttr(f"{ctl}.rz", time=f) if cmds.objExists(f"{ctl}.rz") else 0.0
                
                future_keys = [k for k in ctl_keys if k >= f]
                dist = (min(future_keys) - f) if future_keys else 9999
                
                anim_cache[ctl][f] = {
                    "rot": (rx, ry, rz),
                    "is_key": (f in ctl_keys),
                    "dist_to_key": dist
                }

        if bake_target:
            for ctl in flat_controls:
                for axis in ["rx", "ry", "rz"]:
                    plug = f"{ctl}.{axis}"
                    if cmds.objExists(plug) and cmds.getAttr(plug, settable=True):
                        if target_layer:
                            layer_curves = cmds.animLayer(target_layer, query=True, animCurves=True) or []
                            plug_curves = cmds.keyframe(plug, query=True, name=True) or []
                            curves_to_cut = list(set(plug_curves) & set(layer_curves))
                            if curves_to_cut:
                                cmds.cutKey(curves_to_cut, time=(start, end), clear=True)
                        else:
                            cmds.cutKey(plug, time=(start, end), clear=True)

        states = {}
        cmds.currentTime(start)
        
        for chain in target_chains:
            total_depth = max(1, len(chain))
            sel_list = om.MSelectionList()
            for ctl in chain:
                sel_list.add(ctl)
                
            for i, ctl in enumerate(chain):
                if ctl in states: 
                    continue 
                
                dag_path = sel_list.getDagPath(i)
                fn_transform = om.MFnTransform(dag_path)
                
                rx, ry, rz = anim_cache[ctl][start]["rot"]
                if cmds.getAttr(f"{ctl}.rx", settable=True): cmds.setAttr(f"{ctl}.rx", rx)
                if cmds.getAttr(f"{ctl}.ry", settable=True): cmds.setAttr(f"{ctl}.ry", ry)
                if cmds.getAttr(f"{ctl}.rz", settable=True): cmds.setAttr(f"{ctl}.rz", rz)
                
                w_mat = om.MMatrix(cmds.xform(ctl, q=True, ws=True, matrix=True))
                base_pos = om.MVector(w_mat[12], w_mat[13], w_mat[14])
                
                child_pos = None
                if i < len(chain) - 1:
                    next_ctl = chain[i+1]
                    cw_mat = om.MMatrix(cmds.xform(next_ctl, q=True, ws=True, matrix=True))
                    c_pos = om.MVector(cw_mat[12], cw_mat[13], cw_mat[14])
                    if (c_pos - base_pos).length() > 0.001:
                        child_pos = c_pos
                
                if not child_pos:
                    if i > 0:
                        prev_ctl = chain[i-1]
                        pw_mat = om.MMatrix(cmds.xform(prev_ctl, q=True, ws=True, matrix=True))
                        prev_pos = om.MVector(pw_mat[12], pw_mat[13], pw_mat[14])
                        extrapolated_vec = base_pos - prev_pos
                        if extrapolated_vec.length() > 0.001:
                            child_pos = base_pos + extrapolated_vec
                    if not child_pos:
                        child_pos = base_pos + (om.MVector(w_mat[0], w_mat[1], w_mat[2]).normal() * 5.0)
                    
                bone_vec = child_pos - base_pos
                length = bone_vec.length()
                local_aim = bone_vec * w_mat.inverse()
                
                depth_ratio = i / float(total_depth)
                local_mass = max(0.1, base_weight * (1.0 - (depth_ratio * 0.5)))
                
                spring_base = ((params.get("spring", 30) / 100.0) ** 1.5) * 0.5
                root_pin = params.get("root_stiff", 50) / 100.0
                local_spring = spring_base + (spring_base * (root_pin * 10.0) * (1.0 - depth_ratio))
                
                states[ctl] = {
                    "sim_tip": child_pos,
                    "vel": om.MVector(0, 0, 0),
                    "local_spring": local_spring,
                    "length": length,
                    "local_aim": local_aim,
                    "local_mass": local_mass,
                    "can_x": cmds.objExists(f"{ctl}.rx") and cmds.getAttr(f"{ctl}.rx", settable=True),
                    "can_y": cmds.objExists(f"{ctl}.ry") and cmds.getAttr(f"{ctl}.ry", settable=True),
                    "can_z": cmds.objExists(f"{ctl}.rz") and cmds.getAttr(f"{ctl}.rz", settable=True),
                    "ro_order": (cmds.getAttr(f"{ctl}.rotateOrder") + 1) if cmds.objExists(f"{ctl}.rotateOrder") else 1
                }

        col_dags = []
        col_sel = om.MSelectionList()
        for c in colliders:
            if cmds.objExists(c):
                shapes = cmds.listRelatives(c, shapes=True, fullPath=True, type="mesh") or []
                if cmds.nodeType(c) == "mesh": shapes.append(c)

                live_shapes = []
                for shape in shapes:
                    if not cmds.getAttr(f"{shape}.intermediateObject"):
                        live_shapes.append(shape)

                if live_shapes:
                    col_sel.add(live_shapes[0])
                    col_dags.append(col_sel.getDagPath(col_sel.length() - 1))

        auto_key_state = cmds.autoKeyframe(q=True, state=True)
        if auto_key_state: cmds.autoKeyframe(state=False)
        
        cmds.refresh(suspend=True)
        current_eval = cmds.evaluationManager(q=True, mode=True)[0]
        if current_eval != "off": cmds.evaluationManager(mode="off")
        
        for f in range(start, end + 1):
            cmds.currentTime(f)
            current_wind = self._apply_wind(f, wind_dir, 0.5) if use_wind else om.MVector(0,0,0)

            for chain in target_chains:
                for ctl in chain:
                    state = states[ctl]
                    
                    rx, ry, rz = anim_cache[ctl][f]["rot"]
                    if state["can_x"]: cmds.setAttr(f"{ctl}.rx", rx)
                    if state["can_y"]: cmds.setAttr(f"{ctl}.ry", ry)
                    if state["can_z"]: cmds.setAttr(f"{ctl}.rz", rz)
                    
                    w_mat = om.MMatrix(cmds.xform(ctl, q=True, ws=True, matrix=True))
                    base_pos = om.MVector(w_mat[12], w_mat[13], w_mat[14])
                    target_tip = base_pos + (state["local_aim"] * w_mat)
                    
                    is_key = anim_cache[ctl][f]["is_key"]
                    
                    if f == start:
                        state["sim_tip"] = target_tip
                        state["vel"] = om.MVector(0, 0, 0)
                        
                        if f % step == 0 or f == start or f == end:
                            k_args = {"time": (f, f)}
                            if target_layer: k_args["animLayer"] = target_layer
                            if state["can_x"]: cmds.setKeyframe(f"{ctl}.rx", **k_args)
                            if state["can_y"]: cmds.setKeyframe(f"{ctl}.ry", **k_args)
                            if state["can_z"]: cmds.setKeyframe(f"{ctl}.rz", **k_args)
                        continue 
                    
                    diff = target_tip - state["sim_tip"]
                    force = diff * state["local_spring"]
                    force.y -= gravity_force 
                    if use_wind: force += current_wind

                    state["vel"] = (state["vel"] + (force / state["local_mass"])) * drag
                    
                    if respect_keys and is_key:
                        state["vel"] += (target_tip - state["sim_tip"]) * 0.5
                    elif respect_keys:
                        dist_f = anim_cache[ctl][f]["dist_to_key"]
                        blend_frames = 6.0 
                        if dist_f <= blend_frames:
                            pull = 1.0 - (dist_f / blend_frames)
                            pull = pull * pull 
                            state["vel"] += (target_tip - state["sim_tip"]) * (pull * 0.3)
                            state["vel"] *= (1.0 - (pull * 0.1))

                    state["sim_tip"] += state["vel"]
                    
                    sim_vec = state["sim_tip"] - base_pos
                    if sim_vec.length() > 0.0001:
                        sim_vec = sim_vec.normal() * state["length"]
                        state["sim_tip"] = base_pos + sim_vec
                        
                    if col_dags:
                        for dag in col_dags:
                            if dag.hasFn(om.MFn.kMesh):
                                fn_mesh = om.MFnMesh(dag)
                                if fn_mesh.numPolygons > 0:
                                    pt = om.MPoint(state["sim_tip"])
                                    closest_pt, face_idx = fn_mesh.getClosestPoint(pt, om.MSpace.kWorld)
                                    normal = om.MVector(fn_mesh.getClosestNormal(pt, om.MSpace.kWorld)[0])
                                    
                                    vec = om.MVector(pt) - om.MVector(closest_pt)
                                    dist = vec.length()
                                    dot = (vec.x * normal.x) + (vec.y * normal.y) + (vec.z * normal.z)
                                    
                                    if dot < 0.0 or dist < col_thick:
                                        if dot < 0.0:
                                            target_safe = om.MVector(closest_pt) + (normal * col_thick)
                                        else:
                                            target_safe = state["sim_tip"] + (normal * (col_thick - dist))
                                        
                                        correction = target_safe - state["sim_tip"]
                                        clamp_multiplier = 0.85 if dot < 0.0 else 0.25
                                        max_shift = state["length"] * clamp_multiplier
                                        
                                        if correction.length() > max_shift:
                                            correction = correction.normal() * max_shift
                                            
                                        state["sim_tip"] += correction
                                        
                                        vel_dot = (state["vel"].x * normal.x) + (state["vel"].y * normal.y) + (state["vel"].z * normal.z)
                                        if vel_dot < 0.0:
                                            v_normal = normal * vel_dot
                                            v_tangent = state["vel"] - v_normal
                                            
                                            active_bounce = col_bounce if abs(vel_dot) > 0.5 else 0.0
                                            col_frict = 1.0 - (params.get("col_frict", 30) / 100.0)
                                            state["vel"] = (v_normal * -active_bounce) + (v_tangent * col_frict)
                    
                    current_aim = (target_tip - base_pos).normal()
                    sim_aim = (state["sim_tip"] - base_pos).normal()
                    
                    if current_aim.length() > 0.0001 and sim_aim.length() > 0.0001:
                        world_quat = om.MQuaternion(current_aim, sim_aim)
                        
                        t_mat = om.MTransformationMatrix(w_mat)
                        t_mat.rotateBy(world_quat, om.MSpace.kWorld)
                        new_w_mat = t_mat.asMatrix()
                        
                        parent_inv = om.MMatrix(cmds.getAttr(f"{ctl}.parentInverseMatrix[0]"))
                        local_mat = new_w_mat * parent_inv
                        local_t_mat = om.MTransformationMatrix(local_mat)
                        
                        local_t_mat.reorderRotation(state["ro_order"])
                        euler = local_t_mat.rotation(False)
                        
                        rx, ry, rz = math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z)
                    
                        if state["can_x"]: cmds.setAttr(f"{ctl}.rx", rx)
                        if state["can_y"]: cmds.setAttr(f"{ctl}.ry", ry)
                        if state["can_z"]: cmds.setAttr(f"{ctl}.rz", rz)

                    if f % step == 0 or f == end:
                        k_args = {"time": (f, f)}
                        if target_layer: k_args["animLayer"] = target_layer
                        if state["can_x"]: cmds.setKeyframe(f"{ctl}.rx", **k_args)
                        if state["can_y"]: cmds.setKeyframe(f"{ctl}.ry", **k_args)
                        if state["can_z"]: cmds.setKeyframe(f"{ctl}.rz", **k_args)

        if params.get("do_smooth", False) and bake_target:
            for ctl in flat_controls:
                for axis in ["rx", "ry", "rz"]:
                    plug = f"{ctl}.{axis}"
                    if cmds.objExists(plug):
                        crvs = cmds.keyframe(plug, q=True, name=True)
                        if crvs:
                            cmds.filterCurve(crvs, filter="euler")
                            cmds.filterCurve(crvs, filter="butterworth")

        if current_eval != "off": cmds.evaluationManager(mode=current_eval)
        if auto_key_state: cmds.autoKeyframe(state=True)
        cmds.refresh(suspend=False)
        cmds.refresh(force=True)
        
        cmds.undoInfo(closeChunk=True)

class OverlapWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(OverlapWindow, self).__init__(parent)
        self.setWindowTitle("Auto-Overlap Physics Engine")
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setMinimumWidth(380)
        self.solver = OverlapPhysicsSolver()
        self.build_ui()
        self.apply_styles()

    def build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # --- 0. TARGET CONTROLS ---
        grp_targets = QtWidgets.QGroupBox("Target Chains")
        lay_targets = QtWidgets.QVBoxLayout(grp_targets)
        
        self.list_targets = QtWidgets.QListWidget()
        self.list_targets.setMinimumHeight(100)
        self.list_targets.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.list_targets.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list_targets.customContextMenuRequested.connect(self._show_target_menu)
        lay_targets.addWidget(self.list_targets)
        
        row_tgt_btns = QtWidgets.QHBoxLayout()
        btn_add_tgt = QtWidgets.QPushButton("Add Selected")
        btn_add_tgt.clicked.connect(self._add_target)
        btn_rem_tgt = QtWidgets.QPushButton("Remove")
        btn_rem_tgt.clicked.connect(self._remove_target)
        btn_clr_tgt = QtWidgets.QPushButton("Clear")
        btn_clr_tgt.clicked.connect(self.list_targets.clear)
        
        row_tgt_btns.addWidget(btn_add_tgt)
        row_tgt_btns.addWidget(btn_rem_tgt)
        row_tgt_btns.addWidget(btn_clr_tgt)
        lay_targets.addLayout(row_tgt_btns)
        layout.addWidget(grp_targets, 1)

        # --- PRESETS QUICK-SET ---
        grp_presets = QtWidgets.QGroupBox("Material Presets")
        lay_presets = QtWidgets.QHBoxLayout(grp_presets)
        
        self.rad_tail = QtWidgets.QRadioButton("Tail / Fleshy")
        self.rad_hair = QtWidgets.QRadioButton("Hair")
        self.rad_cloth = QtWidgets.QRadioButton("Cloth")
        self.rad_metal = QtWidgets.QRadioButton("Heavy Metal")
        self.rad_tail.setChecked(True)
        
        lay_presets.addWidget(self.rad_tail)
        lay_presets.addWidget(self.rad_hair)
        lay_presets.addWidget(self.rad_cloth)
        lay_presets.addWidget(self.rad_metal)
        layout.addWidget(grp_presets)
        
        self.rad_tail.clicked.connect(lambda: self._apply_preset(50, 30, 85, 10, 0, 30))
        self.rad_hair.clicked.connect(lambda: self._apply_preset(10, 15, 92, 5, 15, 10))
        self.rad_cloth.clicked.connect(lambda: self._apply_preset(0, 5, 98, 2, 30, 60))
        self.rad_metal.clicked.connect(lambda: self._apply_preset(90, 80, 99, 50, 80, 10))

        # --- 1. SLIDERS (PHYSICS) ---
        grp_phys = QtWidgets.QGroupBox("Physics Parameters")
        lay_phys = QtWidgets.QVBoxLayout(grp_phys)
        
        self.sl_root, self.val_root = self._add_slider_row(lay_phys, "Root Pinning", 0, 100, 50)
        self.sl_spring, self.val_spring = self._add_slider_row(lay_phys, "Spring (Stiffness)", 1, 100, 30)
        self.sl_drag, self.val_drag = self._add_slider_row(lay_phys, "Drag (Damping)", 1, 99, 85)
        self.sl_mass, self.val_mass = self._add_slider_row(lay_phys, "Weight (Mass)", 1, 100, 10)
        self.sl_grav, self.val_grav = self._add_slider_row(lay_phys, "Gravity", -100, 100, 0)
        
        layout.addWidget(grp_phys)

        # --- 2. WIND ENGINE ---
        grp_wind = QtWidgets.QGroupBox("Wind Engine (Turbulence)")
        lay_wind = QtWidgets.QHBoxLayout(grp_wind)
        self.chk_wind = QtWidgets.QCheckBox("Enable Wind")
        lay_wind.addWidget(self.chk_wind)
        
        self.sp_wx = QtWidgets.QDoubleSpinBox(); self.sp_wx.setRange(-100, 100); self.sp_wx.setValue(1.0)
        self.sp_wy = QtWidgets.QDoubleSpinBox(); self.sp_wy.setRange(-100, 100); self.sp_wy.setValue(0.0)
        self.sp_wz = QtWidgets.QDoubleSpinBox(); self.sp_wz.setRange(-100, 100); self.sp_wz.setValue(0.0)
        
        lay_wind.addWidget(QtWidgets.QLabel("X:")); lay_wind.addWidget(self.sp_wx)
        lay_wind.addWidget(QtWidgets.QLabel("Y:")); lay_wind.addWidget(self.sp_wy)
        lay_wind.addWidget(QtWidgets.QLabel("Z:")); lay_wind.addWidget(self.sp_wz)
        layout.addWidget(grp_wind)

        # --- 3. COLLIDERS ---
        grp_col = QtWidgets.QGroupBox("Proxy Colliders")
        lay_col = QtWidgets.QVBoxLayout(grp_col)
        self.list_colliders = QtWidgets.QListWidget()
        self.list_colliders.setMinimumHeight(60)
        self.list_colliders.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        lay_col.addWidget(self.list_colliders)
        
        self.sl_thick, self.val_thick = self._add_slider_row(lay_col, "Radius (Padding)", 0, 100, 15)
        self.sl_frict, self.val_frict = self._add_slider_row(lay_col, "Surface Friction", 0, 100, 30)
        self.sl_bounce, self.val_bounce = self._add_slider_row(lay_col, "Bounce", 0, 100, 0)
        
        btn_add_col = QtWidgets.QPushButton("Add Selected")
        btn_add_col.clicked.connect(self._add_colliders)
        btn_rem_col = QtWidgets.QPushButton("Remove")
        btn_rem_col.clicked.connect(self._remove_collider)
        btn_clr_col = QtWidgets.QPushButton("Clear")
        btn_clr_col.clicked.connect(self.list_colliders.clear)
        
        row_col_btns = QtWidgets.QHBoxLayout()
        row_col_btns.addWidget(btn_add_col)
        row_col_btns.addWidget(btn_rem_col)
        row_col_btns.addWidget(btn_clr_col)
        lay_col.addLayout(row_col_btns)
        layout.addWidget(grp_col, 1)

        # --- 4. BAKE SETTINGS ---
        grp_bake = QtWidgets.QGroupBox("Bake Settings")
        lay_bake = QtWidgets.QVBoxLayout(grp_bake)
        
        self.chk_respect_keys = QtWidgets.QCheckBox("Magnetic Poses (Flow seamlessly into existing keys)")
        self.chk_respect_keys.setChecked(True)
        lay_bake.addWidget(self.chk_respect_keys)
        
        self.chk_smooth = QtWidgets.QCheckBox("Post-Bake Smoothing (Euler + Butterworth)")
        self.chk_smooth.setChecked(True)
        lay_bake.addWidget(self.chk_smooth)
        
        row_bake = QtWidgets.QHBoxLayout()
        self.combo_target = QtWidgets.QComboBox()
        self.combo_target.addItems(["Current AnimLayer", "New AnimLayer", "Base Animation"])
        self.combo_step = QtWidgets.QComboBox()
        self.combo_step.addItems(["Default (1s)", "2s", "4s"])
        row_bake.addWidget(QtWidgets.QLabel("Target:"))
        row_bake.addWidget(self.combo_target, 1)
        row_bake.addWidget(QtWidgets.QLabel("Step:"))
        row_bake.addWidget(self.combo_step)
        lay_bake.addLayout(row_bake)
        layout.addWidget(grp_bake)

        # --- 5. ACTION BUTTONS ---
        row_actions = QtWidgets.QHBoxLayout()
        self.btn_preview = QtWidgets.QPushButton("PREVIEW")
        self.btn_preview.setObjectName("ActionBtn")
        self.btn_preview.clicked.connect(self.on_preview)
        
        self.btn_bake = QtWidgets.QPushButton("BAKE")
        self.btn_bake.setObjectName("ActionBtn")
        self.btn_bake.clicked.connect(self.on_bake)
        
        self.btn_clear = QtWidgets.QPushButton("CLEAR")
        self.btn_clear.setObjectName("DangerBtn")
        self.btn_clear.clicked.connect(self.on_clear)

        row_actions.addWidget(self.btn_preview)
        row_actions.addWidget(self.btn_bake)
        row_actions.addWidget(self.btn_clear)
        layout.addLayout(row_actions)

        # --- 6. PRESET MANAGEMENT (SAVE/LOAD STATE) ---
        row_presets_io = QtWidgets.QHBoxLayout()
        btn_save_preset = QtWidgets.QPushButton("💾 Save Preset")
        btn_load_preset = QtWidgets.QPushButton("📂 Load Preset")
        
        btn_save_preset.clicked.connect(self._save_preset)
        btn_load_preset.clicked.connect(self._load_preset)
        
        row_presets_io.addWidget(btn_save_preset)
        row_presets_io.addWidget(btn_load_preset)
        layout.addLayout(row_presets_io)

    def _add_slider_row(self, parent_layout, name, min_val, max_val, default):
        row = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel(name)
        lbl.setFixedWidth(100)
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        val_lbl = QtWidgets.QLabel(str(default))
        val_lbl.setFixedWidth(30)
        
        slider.valueChanged.connect(lambda v, l=val_lbl: l.setText(str(v)))
        row.addWidget(lbl)
        row.addWidget(slider)
        row.addWidget(val_lbl)
        parent_layout.addLayout(row)
        return slider, val_lbl

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #1E2024; color: #E8EEF2; }
            QGroupBox { border: 1px solid #3A454D; border-radius: 6px; margin-top: 10px; font-weight: bold; color: #8F9CA6; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QSlider::groove:horizontal { border: 1px solid #111; height: 6px; background: #111; border-radius: 3px; }
            QSlider::handle:horizontal { background: #4FB8A7; width: 14px; margin: -4px 0; border-radius: 7px; border: 1px solid #000; }
            QListWidget { background: #151A1E; border: 1px solid #3A454D; border-radius: 4px; }
            QPushButton { background: #2A353D; border: 1px solid #3A454D; border-radius: 4px; padding: 6px; color: #FFF; font-weight: bold; }
            QPushButton:hover { background: #34434E; }
            #ActionBtn { background: #2E8C74; }
            #ActionBtn:hover { background: #39A188; }
            #DangerBtn { background: #C5534A; }
            #DangerBtn:hover { background: #D32F2F; }
        """)

    def _show_target_menu(self, pos):
        item = self.list_targets.itemAt(pos)
        if item:
            menu = QtWidgets.QMenu(self)
            rename_action = menu.addAction("Rename Chain")
            action = menu.exec(self.list_targets.mapToGlobal(pos))
            if action == rename_action:
                widget = self.list_targets.itemWidget(item)
                new_name, ok = QtWidgets.QInputDialog.getText(self, "Rename", "New Name:", text=widget.lbl.text())
                if ok and new_name:
                    widget.lbl.setText(new_name)

    def _add_target(self):
        sel = cmds.ls(sl=True)
        if sel:
            controls = sorted(sel, key=lambda x: len(cmds.ls(x, long=True)[0].split("|")))
            name = f"Chain ({controls[0].split(':')[-1]})"
            
            item = QtWidgets.QListWidgetItem(self.list_targets)
            widget = TargetItemWidget(name)
            item.setSizeHint(widget.sizeHint())
            
            self.list_targets.addItem(item)
            self.list_targets.setItemWidget(item, widget)
            item.setData(QtCore.Qt.UserRole, controls)
        else:
            cmds.warning("[ARTools] Please select controls to add a target chain.")

    def _remove_target(self):
        for item in self.list_targets.selectedItems():
            self.list_targets.takeItem(self.list_targets.row(item))

    def _save_preset(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Global Preset", "", "JSON Files (*.json)")
        if path:
            chains_data = []
            for i in range(self.list_targets.count()):
                item = self.list_targets.item(i)
                widget = self.list_targets.itemWidget(item)
                chains_data.append({
                    "name": widget.lbl.text(),
                    "muted": widget.btn_mute.isChecked(),
                    "controls": item.data(QtCore.Qt.UserRole)
                })
                
            colliders_data = [self.list_colliders.item(i).text() for i in range(self.list_colliders.count())]
            
            params_data = {
                "root_stiff": self.sl_root.value(),
                "spring": self.sl_spring.value(),
                "drag": self.sl_drag.value(),
                "mass": self.sl_mass.value(),
                "gravity": self.sl_grav.value(),
                "use_wind": self.chk_wind.isChecked(),
                "wind_x": self.sp_wx.value(),
                "wind_y": self.sp_wy.value(),
                "wind_z": self.sp_wz.value(),
                "col_thick": self.sl_thick.value(),
                "col_frict": self.sl_frict.value(),
                "col_bounce": self.sl_bounce.value(),
                "respect_keys": self.chk_respect_keys.isChecked(),
                "do_smooth": self.chk_smooth.isChecked(),
                "bake_target": self.combo_target.currentIndex(),
                "bake_step": self.combo_step.currentIndex()
            }
            
            preset_data = {
                "chains": chains_data,
                "colliders": colliders_data,
                "params": params_data
            }
            
            with open(path, 'w') as f:
                json.dump(preset_data, f, indent=4)
            cmds.inViewMessage(amg=f"Global Preset saved to {os.path.basename(path)}", pos="midCenter", fade=True)

    def _load_preset(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Global Preset", "", "JSON Files (*.json)")
        if path and os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
            
            self.list_targets.clear()
            self.list_colliders.clear()
            
            for chain_data in data.get("chains", []):
                item = QtWidgets.QListWidgetItem(self.list_targets)
                widget = TargetItemWidget(chain_data.get("name", "Chain"))
                if chain_data.get("muted", False):
                    widget.btn_mute.setChecked(True)
                    
                item.setSizeHint(widget.sizeHint())
                self.list_targets.addItem(item)
                self.list_targets.setItemWidget(item, widget)
                item.setData(QtCore.Qt.UserRole, chain_data.get("controls", []))
                
            self.list_colliders.addItems(data.get("colliders", []))
            
            params = data.get("params", {})
            if params:
                self.sl_root.setValue(params.get("root_stiff", 50))
                self.sl_spring.setValue(params.get("spring", 30))
                self.sl_drag.setValue(params.get("drag", 85))
                self.sl_mass.setValue(params.get("mass", 10))
                self.sl_grav.setValue(params.get("gravity", 0))
                
                self.chk_wind.setChecked(params.get("use_wind", False))
                self.sp_wx.setValue(params.get("wind_x", 1.0))
                self.sp_wy.setValue(params.get("wind_y", 0.0))
                self.sp_wz.setValue(params.get("wind_z", 0.0))
                
                self.sl_thick.setValue(params.get("col_thick", 15))
                self.sl_frict.setValue(params.get("col_frict", 30))
                self.sl_bounce.setValue(params.get("col_bounce", 0))
                
                self.chk_respect_keys.setChecked(params.get("respect_keys", True))
                self.chk_smooth.setChecked(params.get("do_smooth", True))
                
                self.combo_target.setCurrentIndex(params.get("bake_target", 0))
                self.combo_step.setCurrentIndex(params.get("bake_step", 0))
            
            cmds.inViewMessage(amg="Global Preset successfully loaded", pos="midCenter", fade=True)

    def _get_active_chains(self):
        chains = []
        for i in range(self.list_targets.count()):
            item = self.list_targets.item(i)
            widget = self.list_targets.itemWidget(item)
            if not widget.btn_mute.isChecked():
                chains.append(item.data(QtCore.Qt.UserRole))
        return chains

    def _apply_preset(self, root, spring, drag, mass, gravity, frict):
        self.sl_root.setValue(root)
        self.sl_spring.setValue(spring)
        self.sl_drag.setValue(drag)
        self.sl_mass.setValue(mass)
        self.sl_grav.setValue(gravity)
        self.sl_frict.setValue(frict)

    def _get_params(self):
        return {
            "root_stiff": self.sl_root.value(),
            "spring": self.sl_spring.value(),
            "drag": self.sl_drag.value(),
            "weight": self.sl_mass.value(),
            "gravity": self.sl_grav.value(),
            "use_wind": self.chk_wind.isChecked(),
            "wind_dir": [self.sp_wx.value(), self.sp_wy.value(), self.sp_wz.value()],
            "col_thick": self.sl_thick.value() / 10.0,
            "col_frict": self.sl_frict.value(),
            "col_bounce": self.sl_bounce.value() / 100.0,
            "respect_keys": self.chk_respect_keys.isChecked(),
            "do_smooth": self.chk_smooth.isChecked()
        }

    def _get_colliders(self):
        return [self.list_colliders.item(i).text() for i in range(self.list_colliders.count())]

    def _add_colliders(self):
        sel = cmds.ls(sl=True)
        if sel: self.list_colliders.addItems(sel)

    def _remove_collider(self):
        for item in self.list_colliders.selectedItems():
            self.list_colliders.takeItem(self.list_colliders.row(item))

    def on_preview(self):
        self.solver.run_simulation(self._get_active_chains(), self._get_colliders(), self._get_params(), bake_target="Preview")

    def on_bake(self):
        target = self.combo_target.currentText()
        step_text = self.combo_step.currentText()
        step = 2 if "2s" in step_text else 4 if "4s" in step_text else 1
        
        self.solver.run_simulation(self._get_active_chains(), self._get_colliders(), self._get_params(), bake_target=target, step=step)
        cmds.inViewMessage(amg=f"Physics Baked to {target}", pos="midCenter", fade=True)

    def on_clear(self):
        self.solver.clear_preview()
        cmds.inViewMessage(amg="Preview Cleared", pos="midCenter", fade=True)

    def closeEvent(self, event):
        self.list_targets.clear()
        super(OverlapWindow, self).closeEvent(event)

def launch_overlap_engine(parent=None):
    win = OverlapWindow(parent)
    win.show()
    return win