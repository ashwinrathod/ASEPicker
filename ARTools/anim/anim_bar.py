# ARTools/anim/anim_bar.py
from PySide6 import QtWidgets, QtCore, QtGui

from maya import cmds
from functools import partial
from . import logic_pose
from . import logic_anim
from . import snapshot
from . import clipboard
from . import fake_parent
from . import logic_ikfk
from .trail import TrailManager
import os

class AnimBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        for widget in QtWidgets.QApplication.topLevelWidgets():
            if widget.objectName() == "AnimBar" and widget != self:
                try:
                    widget.close()
                    widget.deleteLater()
                except Exception: pass
        
        from ARTools import security
        
        io_check = security.enforce_license("animbar", parent_window=parent)
        
        if not io_check or getattr(io_check, "_ase_secure_stamp", "") != "JAY_SHREE_KRISHNA_1986":
            cmds.warning("[ARTools] License Invalid. AnimBar aborted.")
            self.deleteLater()
            return
        
        QtWidgets.QWidget.__init__(self, parent)

        self.setObjectName("AnimBar")
        
        # --- NEW: BORDERLESS & TRANSLUCENT ---
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        base_layout = QtWidgets.QVBoxLayout(self)
        base_layout.setContentsMargins(10, 10, 10, 10) # Drop shadow padding
        
        self.bg_frame = QtWidgets.QFrame(self)
        self.bg_frame.setObjectName("AnimBarFrame")
        base_layout.addWidget(self.bg_frame)
        
        layout = QtWidgets.QBoxLayout(QtWidgets.QBoxLayout.LeftToRight, self.bg_frame)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        
        self._separators = []
        
        # --- NEW: DRAG HANDLE & CLOSE BUTTON ---
        self.btn_drag = QtWidgets.QLabel(" ⋮⋮ ")
        self.btn_drag.setCursor(QtCore.Qt.SizeAllCursor)
        self.btn_drag.setObjectName("DragHandle")
        layout.addWidget(self.btn_drag)
        
        # --- NEW: Preferences Button ---
        self.btn_prefs = QtWidgets.QPushButton("⚙")
        self.btn_prefs.setFixedSize(22, 22)
        self.btn_prefs.setObjectName("LicenseBtn")
        self.btn_prefs.setToolTip("ARTools Preferences")
        self.btn_prefs.clicked.connect(self.show_preferences)
        layout.addWidget(self.btn_prefs)
        
        self.btn_license = QtWidgets.QPushButton("🔑")
        self.btn_license.setFixedSize(22, 22)
        self.btn_license.setObjectName("LicenseBtn")
        self.btn_license.setToolTip("License Status")
        self.btn_license.clicked.connect(self.show_license_status)
        layout.addWidget(self.btn_license)
        
        self.btn_close = QtWidgets.QPushButton("×")
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setObjectName("CloseBtn")
        self.btn_close.clicked.connect(self.close)
        layout.addWidget(self.btn_close)
        
        self._add_sep(layout)

        # --- 1. Snapshot / Reset / Mirror ---
        self.btn_snap = self._icon_btn("anim_snap", "Snapshot (L: Auto-Detect, R: Add/Fix)", self._on_snapshot)
        self.btn_snap.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.btn_snap.customContextMenuRequested.connect(self._menu_snapshot)
        self.btn_reset = self._icon_btn("anim_reset", "Reset Pose", self._on_reset)

        self._add_sep(layout)

        mirror_tooltip = "Mirror Pose\nShift+Click: Select Mirror (Add)\nAlt+Click: Select Mirror (Replace)"
        self.btn_mirror = self._icon_btn("anim_mirror", mirror_tooltip, self._on_mirror)
        self.btn_mirror.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.btn_mirror.customContextMenuRequested.connect(partial(self._menu_mirror))
        self.btn_space = self._icon_btn("anim_space", "Space Switcher", self._on_space_click)
        
        # --- NEW: Fake Parent Tool ---
        fake_parent_tip = "Fake Parent\nCapture: Select Parent -> Child\nApply: Click (Shift+Click to Bake)"
        self.btn_fake_parent = self._icon_btn("fakeParent", fake_parent_tip, self._on_fake_parent)
        self.fake_parent_manager = fake_parent.FakeParentManager(self.btn_fake_parent)

        layout.addWidget(self.btn_snap)
        layout.addWidget(self.btn_reset)
        layout.addWidget(self.btn_mirror)

        self._add_sep(layout)

        layout.addWidget(self.btn_space)
        layout.addWidget(self.btn_fake_parent)
        
        self._add_sep(layout)

        # --- 2. Pose (Local & World) ---
        self.btn_pl = self._icon_btn("anim_copy_pose", "Pose Local (L: Copy, R: Menu)", partial(logic_pose.copy_pose, False))
        self._setup_context_menu(self.btn_pl, "pose_local", 
            copy_cmd=partial(logic_pose.copy_pose, False), 
            paste_cmd=partial(logic_pose.paste_pose, False, self._get_paste_ns())
        )

        self.btn_pw = self._icon_btn("anim_copy_world_pose", "Pose World (L: Copy, R: Menu)", partial(logic_pose.copy_pose, True))
        self._setup_context_menu(self.btn_pw, "pose_global", 
            copy_cmd=partial(logic_pose.copy_pose, True), 
            paste_cmd=partial(logic_pose.paste_pose, True, self._get_paste_ns())
        )

        layout.addWidget(self.btn_pl)
        layout.addWidget(self.btn_pw)

        self._add_sep(layout)

        # --- 3. Anim (Local & World) ---
        self.btn_al = self._icon_btn("anim_copy_anim", "Anim Local (L: Copy, R: Menu)", partial(logic_anim.copy_anim, False))
        self._setup_context_menu(self.btn_al, "anim_local", 
            copy_cmd=partial(logic_anim.copy_anim, False), 
            paste_cmd=None,
            paste_dict={
                "Paste Anim (Original Time)": partial(logic_anim.paste_anim, False, self._get_paste_ns(), "original"),
                "Paste Anim (Current Time)": partial(logic_anim.paste_anim, False, self._get_paste_ns(), "current")
            }
        )

        self.btn_aw = self._icon_btn("anim_copy_world_anim", "Anim World (L: Copy, R: Menu)", partial(logic_anim.copy_anim, True))
        self._setup_context_menu(self.btn_aw, "anim_global", 
            copy_cmd=partial(logic_anim.copy_anim, True), 
            paste_cmd=None,
            paste_dict={
                "Paste Anim (Original Time)": partial(logic_anim.paste_anim, True, self._get_paste_ns(), "original"),
                "Paste Anim (Current Time)": partial(logic_anim.paste_anim, True, self._get_paste_ns(), "current")
            }
        )

        layout.addWidget(self.btn_al)
        layout.addWidget(self.btn_aw)
        
        self._add_sep(layout)

        # --- 4. IK/FK Tools ---
        # Pressing the IK button snaps to FK and turns the rig to IK.
        self.btn_to_ik = self._icon_btn("ik_mode", "Switch to IK (Snap IK to FK)", partial(self._match_chain, "to_ik"))
        
        # Pressing the FK button snaps to IK and turns the rig to FK.
        self.btn_to_fk = self._icon_btn("fk_mode", "Switch to FK (Snap FK to IK)", partial(self._match_chain, "to_fk"))

        self._add_ikfk_menu(self.btn_to_ik, "to_ik")
        self._add_ikfk_menu(self.btn_to_fk, "to_fk")

        layout.addWidget(self.btn_to_ik)
        layout.addWidget(self.btn_to_fk)

        self._add_sep(layout)

        # --- 5 Motion Trail Button (ARTools >> trail) ---
        self.btn_motion_trail = self._icon_btn("trail_icon", "Toggle Motion Trail(s)", partial(TrailManager.get_instance().create_or_toggle))
        self.btn_motion_trail.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.btn_motion_trail.customContextMenuRequested.connect(self._handle_trail_menu_request)
        layout.addWidget(self.btn_motion_trail)

        self._add_sep(layout)

        # --- 6. Curve Dynamics Engine (Compact) ---
        self.btn_overlap = self._icon_btn("overlap", "Auto-Overlap Physics Engine", self._on_overlap_click)
        layout.addWidget(self.btn_overlap)

        self.btn_dynamics = self._icon_btn("anim_curves", "Toggle Curve Dynamics", self._toggle_dynamics_panel)
        layout.addWidget(self.btn_dynamics)

        self.btn_palette = self._icon_btn("palette_icon", "Toggle Floating Palette", self._toggle_palette)
        self.btn_palette.setText("🎨")
        layout.addWidget(self.btn_palette)

        from .anim_sliders import CompactDynamicsWidget, FloatingSliderPalette
        self.dynamics_panel = CompactDynamicsWidget(self)
        self.dynamics_panel.setVisible(False) # Hidden by default so it stays clean!
        
        self.floating_palette = FloatingSliderPalette(self)
        self.floating_palette.hide()
        layout.addWidget(self.dynamics_panel)

        layout.addStretch()

        # --- NEW: MODERN CSS STYLING ---
        self.setStyleSheet("""
            #AnimBarFrame {
                background-color: rgba(30, 32, 36, 245);
                border: 1px solid #454A50;
                border-radius: 14px;
            }
            #DragHandle { color: #666; font-size: 22px; font-weight: bold; }
            #CloseBtn { background: transparent; color: #888; font-size: 22px; font-weight: bold; border-radius: 11px; }
            #CloseBtn:hover { background: #E07267; color: white; }
            #LicenseBtn { background: transparent; color: #888; font-size: 13px; border-radius: 11px; }
            #LicenseBtn:hover { background: #4CAF50; color: white; }
            QPushButton { background: transparent; border-radius: 6px; }
            QPushButton:hover { background: rgba(79, 184, 167, 70); border: 1px solid rgba(79, 184, 167, 150); }
            QPushButton:pressed { background: rgba(79, 184, 167, 120); }
        """)
        self._old_pos = None

        # --- NEW: UI Sync Engine & Context Highlighting ---
        self.ui_sync_job = cmds.scriptJob(e=["SelectionChanged", self._update_ikfk_buttons], protected=True)
        self.tab_poll_timer = QtCore.QTimer(self)
        self.tab_poll_timer.timeout.connect(self._poll_picker_state)
        self.tab_poll_timer.start(1000) # Check Picker state once per second
        self._last_chain_count = -1
        self._update_ikfk_buttons()

    def _add_sep(self, layout):
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line)
        if not hasattr(self, '_separators'): self._separators = []
        self._separators.append(line)

    def _on_orientation_changed(self, orientation):
        is_vertical = (orientation == QtCore.Qt.Vertical)
        if is_vertical:
            self.layout().setDirection(QtWidgets.QBoxLayout.TopToBottom)
            for sep in getattr(self, '_separators', []):
                sep.setFrameShape(QtWidgets.QFrame.HLine)
        else:
            self.layout().setDirection(QtWidgets.QBoxLayout.LeftToRight)
            for sep in getattr(self, '_separators', []):
                sep.setFrameShape(QtWidgets.QFrame.VLine)

        # Remove maximum constraints and let Qt dynamically calculate the drag bounds
        self.setMaximumWidth(16777215)
        self.setMaximumHeight(16777215)
        self.updateGeometry()

    # --- NEW: BORDERLESS WINDOW DRAGGING ---
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if hasattr(self, "_old_pos") and self._old_pos is not None:
            delta = event.globalPos() - self._old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self._old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._old_pos = None
    # ---------------------------------------

    def _poll_picker_state(self):
        try:
            from ARTools import main
            win = main._app_instance.window if hasattr(main, "_app_instance") and main._app_instance else None
            char_tab = win.main_tabs.currentWidget() if win else None
            chains = getattr(char_tab, "ikfk_chains", []) if char_tab else []
        except Exception:
            chains = []
            
        if len(chains) != self._last_chain_count:
            self._last_chain_count = len(chains)
            self._update_ikfk_buttons()

    def _update_ikfk_buttons(self, *args):
        try:
            from ARTools import main
            win = main._app_instance.window if hasattr(main, "_app_instance") and main._app_instance else None
            char_tab = win.main_tabs.currentWidget() if win else None
            chains = getattr(char_tab, "ikfk_chains", []) if char_tab else []
        except Exception:
            chains = []

        # 1. Base Disabled State (Greys out if no Picker or no chains)
        if not chains:
            self.btn_to_ik.setEnabled(False)
            self.btn_to_fk.setEnabled(False)
            self.btn_to_ik.setToolTip("Disabled: No IK/FK chains configured in the active Picker Tab.")
            self.btn_to_fk.setToolTip("Disabled: No IK/FK chains configured in the active Picker Tab.")
            self.btn_to_ik.setStyleSheet("")
            self.btn_to_fk.setStyleSheet("")
            return

        # 2. Base Enabled State
        self.btn_to_ik.setEnabled(True)
        self.btn_to_fk.setEnabled(True)
        self.btn_to_ik.setToolTip("Switch to IK (Snap IK to FK)")
        self.btn_to_fk.setToolTip("Switch to FK (Snap FK to IK)")

        # 3. Context-Aware Highlighting Engine
        from maya import cmds
        sel = cmds.ls(sl=True) or []
        
        highlight_ik = False
        highlight_fk = False

        if sel:
            sel_shorts = [s.split("|")[-1].split(":")[-1] for s in sel]
            
            for chain in chains:
                ik_ctrl = chain.get("ik_ctrl", "").split("|")[-1].split(":")[-1]
                pv_ctrl = chain.get("pv_ctrl", "").split("|")[-1].split(":")[-1]
                fk_ctrls = [x.split("|")[-1].split(":")[-1] for x in chain.get("fk_ctrls", [])]
                bones = [x.split("|")[-1].split(":")[-1] for x in chain.get("bones", [])]

                for s in sel_shorts:
                    # If an IK component is selected, illuminate the "Switch to FK" button
                    if s and (s == ik_ctrl or s == pv_ctrl):
                        highlight_fk = True 
                    # If an FK component is selected, illuminate the "Switch to IK" button
                    if s and (s in fk_ctrls or s in bones):
                        highlight_ik = True 

        # 4. Apply Dynamic Styles
        highlight_style = "background: rgba(79, 184, 167, 100); border: 2px solid #4CAF50;"
        
        self.btn_to_ik.setStyleSheet(highlight_style if highlight_ik else "")
        self.btn_to_fk.setStyleSheet(highlight_style if highlight_fk else "")

    def _icon_btn(self, icon_name, tip, func):
        btn = QtWidgets.QPushButton()
        btn.setToolTip(tip)
        btn.clicked.connect(partial(func))
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.setFlat(True)
        btn.setFixedSize(38, 38)
        
        # --- NEW: Robust Icon Pathing ---
        current_dir = os.path.dirname(os.path.abspath(__file__)) # anim folder
        root_dir = os.path.dirname(current_dir) # ARTools folder
        icons_dir = os.path.join(root_dir, "icons")
        
        path_svg = os.path.join(icons_dir, f"{icon_name}.svg")
        path_png = os.path.join(icons_dir, f"{icon_name}.png")
        
        if os.path.exists(path_svg):
            btn.setIcon(QtGui.QIcon(path_svg))
            btn.setIconSize(QtCore.QSize(28, 28))
        elif os.path.exists(path_png):
            btn.setIcon(QtGui.QIcon(path_png))
            btn.setIconSize(QtCore.QSize(28, 28))
        else:
            btn.setText(icon_name[:2].upper())
                
        return btn

    def _setup_context_menu(self, btn, file_type, copy_cmd=None, paste_cmd=None, paste_dict=None):
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        
        def show_menu(pos, *args, **kwargs):
            from ARTools.preferences import PrefManager
            prefs = PrefManager()
            menu = QtWidgets.QMenu(self)

            menu.setStyleSheet("""
                QMenu { background-color: #2A2A2A; color: #E0E0E0; border: 1px solid #444444; border-radius: 6px; padding: 4px 0px; }
                QMenu::item { padding: 6px 20px 6px 32px; background-color: transparent; margin: 0px 4px; border-radius: 4px; }
                QMenu::item:selected { background-color: #444444; color: white; }
                QMenu::separator { height: 1px; background: #444444; margin: 4px 8px; }
                QMenu::indicator { width: 12px; height: 12px; left: 10px; border: 1px solid #666; border-radius: 2px; background: #111; }
                QMenu::indicator:checked { background-color: #4CAF50; border: 1px solid #4CAF50; }
            """)
            
            # --- Selection Toggle (Native Checkable Action) ---
            act_sel = menu.addAction("Apply to Selected")
            act_sel.setCheckable(True)
            act_sel.setChecked(prefs.get("animbar_paste_selected") or False)
            def on_toggle(checked):
                prefs.set("animbar_paste_selected", checked)
            act_sel.toggled.connect(on_toggle)
            menu.addSeparator()

            # 1. Select
            menu.addAction("Select Stored Controls", partial(self._select_stored, file_type))
            menu.addSeparator()

            # 2. Copy
            if copy_cmd:
                label = "Copy Anim" if "anim" in file_type else "Copy Pose"
                menu.addAction(label, copy_cmd)

            # 3. Paste
            if paste_cmd:
                label = "Paste Anim" if "anim" in file_type else "Paste Pose"
                menu.addAction(label, paste_cmd)
            
            if paste_dict:
                for label, func in paste_dict.items():
                    if label == "----------------":
                        menu.addSeparator()
                    else:
                        menu.addAction(label, func)

            menu.exec_(btn.mapToGlobal(pos))
            
        btn.customContextMenuRequested.connect(partial(show_menu))

    def _get_paste_ns(self):
        """Resolves namespace dynamically based on user toggle preference."""
        from ARTools.preferences import PrefManager
        if PrefManager().get("animbar_paste_selected"):
            sel = cmds.ls(sl=True)
            if sel and ":" in sel[0]:
                return sel[0].split("|")[-1].rsplit(":", 1)[0]
            return ""
        return None

    def _add_ikfk_menu(self, btn, mode):
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        def show_menu(pos, *args, **kwargs):
            menu = QtWidgets.QMenu(self)
            
            # --- Time Mode Selection ---
            current_time = getattr(self, "_space_time_mode", "Current Frame")
            time_menu = menu.addMenu(f"⏱️ Time Mode: {current_time}")
            def set_time(m): self._space_time_mode = m
            for m in ["Current Frame", "Time Slider Selection", "Entire Time Slider"]:
                act = time_menu.addAction(m)
                act.setCheckable(True)
                if m == current_time: act.setChecked(True)
                act.triggered.connect(partial(set_time, m))
                
            # --- Bake Mode Selection ---
            current_bake = getattr(self, "_space_bake_mode", "Existing Keys Only")
            bake_menu = menu.addMenu(f"🔑 Bake Mode: {current_bake}")
            def set_bake(b): self._space_bake_mode = b
            for b in ["Existing Keys Only", "Bake Every Frame", "Bake on 2s"]:
                act = bake_menu.addAction(b)
                act.setCheckable(True)
                if b == current_bake: act.setChecked(True)
                act.triggered.connect(partial(set_bake, b))
                
            menu.addSeparator()
            menu.addAction("Match (Keyframe)", partial(self._match_chain, mode, key=True))
            menu.addAction("Match (No Key)", partial(self._match_chain, mode, key=False))
            menu.exec_(btn.mapToGlobal(pos))
        btn.customContextMenuRequested.connect(partial(show_menu))

    def _select_stored(self, file_type):
        data = clipboard.load_data(file_type)
        if not data: return
        from maya import cmds
        ns = self._get_ns()
        targets = []
        for short in data.keys():
            full = f"{ns}:{short}" if ns else short
            if cmds.objExists(full):
                targets.append(full)
        if targets:
            cmds.select(targets, replace=True)

    def _get_ns(self):
        try:
            from ARTools.api import get_namespace
            return get_namespace()
        except Exception:
            return ""

    def show_license_status(self, *args):
        from ARTools import security
        security.show_license_status_ui(self)
    
    def show_preferences(self, *args):
        from ARTools.preferences import PrefsWindow
        if not hasattr(self, "_prefs_win") or not self._prefs_win.isVisible():
            self._prefs_win = PrefsWindow(self)
            self._prefs_win.show()
        else:
            self._prefs_win.raise_()
            self._prefs_win.activateWindow()
    
    def _menu_snapshot(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.addAction("Add / Fix Selected Controls", self._on_snapshot_fix)
        menu.exec_(self.btn_snap.mapToGlobal(pos))

    def _on_snapshot_fix(self):
        sel = cmds.ls(sl=True, long=True)
        if not sel:
            cmds.warning("[ARTools] Please select controls to Add/Fix.")
            return
        snapshot.fix_or_add_controls(self._get_ns(), sel)

    def _on_snapshot(self, *args, **kwargs):
        snapshot.create_character_snapshot(self._get_ns())
        try:
            from ARTools import main
            win = main._app_instance.window
            if hasattr(win, "_update_status"):
                win._update_status()
        except Exception:
            pass

    def _on_reset(self, *args, **kwargs):
        cmds.undoInfo(openChunk=True, chunkName="ARTools_ResetPose")
        try:
            logic_pose.reset_pose(self._get_ns())
        finally:
            cmds.undoInfo(closeChunk=True)

    def _on_mirror(self, *args, **kwargs):
        mods = QtWidgets.QApplication.keyboardModifiers()
        ns = self._get_ns()
        if mods & QtCore.Qt.ShiftModifier:
            logic_pose.select_mirror_controls(ns, add=True)
        elif mods & QtCore.Qt.AltModifier:
            logic_pose.select_mirror_controls(ns, add=False)
        else:
            logic_pose.mirror_pose(ns, mode="swap")

    def _menu_mirror(self, pos, *args, **kwargs):
        menu = QtWidgets.QMenu(self)
        menu.addAction("Mirror Animation (Swap)", partial(logic_anim.mirror_anim, namespace=self._get_ns(), mode="swap"))
        menu.addSeparator()
        menu.addAction("Mirror from Pivot...", partial(self._show_pivot_dialog))
        menu.addAction("Mirror Planes...", partial(self._show_planes_dialog))
        
        menu.exec_(self.btn_mirror.mapToGlobal(pos))

    def _match_chain(self, target_mode, key=True, *args, **kwargs):
        try:
            from ARTools import main
            win = main._app_instance.window
            char_tab = win.main_tabs.currentWidget()
            if not char_tab: return
        except Exception:
            return
            
        chains = getattr(char_tab, "ikfk_chains", [])
        if not chains:
            from maya import cmds
            cmds.warning("[ARTools] No IK/FK Chains configured. Add them in the Rig Settings tab.")
            return

        from maya import cmds
        sel = cmds.ls(sl=True)
        ns = self._get_ns()

        chains_to_process = []
        if not sel:
            chains_to_process = chains
        else:
            for chain in chains:
                nodes = [chain.get("ik_ctrl", ""), chain.get("pv_ctrl", ""), chain.get("sw_node", "")] + chain.get("fk_ctrls", [])
                nodes = [n.split("|")[-1].split(":")[-1] for n in nodes if n]
                found = False
                for s in sel:
                    short_s = s.split("|")[-1].split(":")[-1]
                    if short_s in nodes:
                        chains_to_process.append(chain)
                        found = True
                        break

        if not chains_to_process:
            cmds.warning("[ARTools] Selection does not match any configured IK/FK chain.")
            return

        formatted_chains = []
        for chain_data in chains_to_process:
            chain = {
                "ik_ctrl": chain_data.get("ik_ctrl", ""),
                "pv_ctrl": chain_data.get("pv_ctrl", ""),
                "fk_ctrls": chain_data.get("fk_ctrls", []),
                "bones": chain_data.get("bones", []),
                "switch": {
                    "node": chain_data.get("sw_node", ""),
                    "attr": chain_data.get("sw_attr", ""),
                    "ik_val": chain_data.get("ik_val", 1.0),
                    "fk_val": chain_data.get("fk_val", 0.0)
                }
            }
            formatted_chains.append(chain)

        time_mode = getattr(self, "_space_time_mode", "Current Frame")
        bake_mode = getattr(self, "_space_bake_mode", "Existing Keys Only")

        # Route securely to the new concurrent batch processor
        logic_ikfk.batch_switch(formatted_chains, target_mode, ns, key, time_mode, bake_mode)

    def _on_overlap_click(self, *args):
        from . import simulation
        if getattr(self, "_overlap_win", None) is None or not self._overlap_win.isVisible():
            self._overlap_win = simulation.launch_overlap_engine(self)
        else:
            self._overlap_win.raise_()
            self._overlap_win.activateWindow()
    
    def _on_motion_trail(self, *args):
        from ARTools.trail import TrailManager
        TrailManager.get_instance().create_or_toggle()

    def show_trail_menu(self):
        menu = TrailManager.get_instance().create_context_menu()
        menu.exec_(QtGui.QCursor.pos())

    def _handle_trail_menu_request(self, pos):
        TrailManager.get_instance().exec_context_menu()
    
    def _on_delete_selected_trails(self):
        TrailManager.get_instance().delete_trail()

    def _toggle_dynamics_panel(self, *args):
        if hasattr(self, "dynamics_panel"):
            is_vis = self.dynamics_panel.isVisible()
            self.dynamics_panel.setVisible(not is_vis)
            
            if getattr(self, "bg_frame", None) and self.bg_frame.layout():
                self.bg_frame.layout().setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
            self.layout().setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
            
            self.resize(0, 0)
            if self.window(): self.window().resize(0, 0)

    def _set_pivot_from_selection(self, field):
        sel = cmds.ls(sl=True)
        if sel:
            field.setText(sel[0])

    def _add_targets_from_selection(self, list_widget):
        sel = cmds.ls(sl=True)
        if sel:
            list_widget.addItems([s.split("|")[-1].split(":")[-1] for s in sel])
    
    def _on_space_click(self, *args, **kwargs):
        sel = cmds.ls(sl=True)
        if not sel:
            return

        # 1. Helpers (Expanded Keywords for Global/Orient)
        keywords = ["space", "parent", "follow", "ref", "isolate", "world", "local", "global", "orient", "dyn"]
        
        def _get_space_attrs(node):
            # Returns list of (attr_name)
            found = []
            if not node: return found
            # Get all keyable attributes
            attrs = cmds.listAttr(node, k=True) or []
            for a in attrs:
                # 1. Must match a keyword (e.g. "Follow", "Space", "Global")
                if not any(k in a.lower() for k in keywords):
                    continue

                # 2. Must be Enum OR Numeric (Float/Int)
                is_valid_type = False
                
                # Check Enum
                if cmds.attributeQuery(a, node=node, enum=True):
                    is_valid_type = True
                else:
                    # Check Numeric
                    typ = cmds.attributeQuery(a, node=node, attributeType=True)
                    if typ in ["long", "short", "byte", "float", "double", "doubleLinear", "doubleAngle"]:
                        is_valid_type = True
                
                if is_valid_type:
                    found.append(a)
            return found

        # 2. Find the "Hub" node
        hub_node = None
        hub_attrs = []
        
        # Check selection first
        for s in sel:
            attrs = _get_space_attrs(s)
            if attrs:
                hub_node = s
                hub_attrs = attrs
                break
        
        # If not in selection, check connections
        if not hub_node:
            for s in sel:
                conns = cmds.listConnections(s, destination=True, source=True) or []
                conns = list(set(conns))
                for c in conns:
                    if cmds.nodeType(c) in ["transform", "network", "locator"]:
                        attrs = _get_space_attrs(c)
                        if attrs:
                            hub_node = c
                            hub_attrs = attrs
                            break
                if hub_node: break

        # 3. Build Menu
        menu = QtWidgets.QMenu(self)
        
        # --- NEW: Time Mode Selection ---
        current_mode = getattr(self, "_space_time_mode", "Current Frame")
        mode_menu = menu.addMenu(f"⏱️ Time Mode: {current_mode}")
        
        def set_mode(m):
            self._space_time_mode = m
        
        for m in ["Current Frame", "Time Slider Selection", "Entire Time Slider"]:
            act = mode_menu.addAction(m)
            act.setCheckable(True)
            if m == current_mode:
                act.setChecked(True)
            act.triggered.connect(partial(set_mode, m))

        current_bake = getattr(self, "_space_bake_mode", "Existing Keys Only")
        bake_menu = menu.addMenu(f"🔑 Bake Mode: {current_bake}")
        
        def set_bake(b):
            self._space_bake_mode = b
            
        for b in ["Existing Keys Only", "Bake Every Frame", "Bake on 2s"]:
            act = bake_menu.addAction(b)
            act.setCheckable(True)
            if b == current_bake:
                act.setChecked(True)
            act.triggered.connect(partial(set_bake, b))

        menu.addSeparator()
        # --------------------------------
        
        if hub_node and hub_attrs:
            # Title
            lbl = QtWidgets.QLabel("  Hub: " + hub_node.split(":")[-1] + "  ")
            lbl.setStyleSheet("font-weight: bold; color: #ccc; background-color: #444;")
            act = QtWidgets.QWidgetAction(menu)
            act.setDefaultWidget(lbl)
            menu.addAction(act)
            menu.addSeparator()

            # Create a Sub-Menu for EACH attribute found
            for attr in hub_attrs:
                full_attr = "{}.{}".format(hub_node, attr)
                sub = menu.addMenu(attr)
                
                current_val = cmds.getAttr(full_attr)

                # A. ENUM ATTRIBUTES (Standard Dropdowns)
                if cmds.attributeQuery(attr, node=hub_node, enum=True):
                    enum_str = cmds.attributeQuery(attr, node=hub_node, listEnum=True)[0]
                    options = enum_str.split(":")
                    for i, opt in enumerate(options):
                        # Handle "Name=Value" format if present
                        val = i
                        label = opt
                        if "=" in opt:
                            parts = opt.split("=")
                            label = parts[0]
                            try: val = int(parts[1])
                            except: pass
                        
                        mark = " [x] " if abs(current_val - val) < 0.001 else "     "
                        sub.addAction(mark + label, partial(self._set_space, full_attr, val, sel))

                # B. NUMERIC ATTRIBUTES (Your "Follow 1-10" case)
                else:
                    # Get Min/Max to define the range
                    min_v = 0
                    max_v = 1
                    if cmds.attributeQuery(attr, node=hub_node, minExists=True):
                        min_v = int(cmds.attributeQuery(attr, node=hub_node, minimum=True)[0])
                    if cmds.attributeQuery(attr, node=hub_node, maxExists=True):
                        max_v = int(cmds.attributeQuery(attr, node=hub_node, maximum=True)[0])
                    
                    # Safety: If range is huge or unset, clamp to 0-10
                    if max_v - min_v > 20: 
                        max_v = min_v + 10

                    # Generate items
                    for i in range(min_v, max_v + 1):
                        mark = " [x] " if abs(current_val - i) < 0.001 else "     "
                        sub.addAction(f"{mark}Value {i}", partial(self._set_space, full_attr, i, sel))

        else:
            menu.addAction("No Space Attributes Found").setEnabled(False)

        menu.exec_(QtGui.QCursor.pos())

    def _on_fake_parent(self, *args, **kwargs):
        mods = QtWidgets.QApplication.keyboardModifiers()
        self.fake_parent_manager.toggle(mods)
    
    def _set_space(self, attr_path, value, target_nodes, *args, **kwargs):
        # 1. Time Range Setup
        mode = getattr(self, "_space_time_mode", "Current Frame")
        start_t = end_t = cmds.currentTime(q=True)
        is_range = False
        
        if mode == "Time Slider Selection":
            import maya.mel as mel
            try:
                a_time_slider = mel.eval('$tmpVar=$gPlayBackSlider')
                if cmds.timeControl(a_time_slider, q=True, rangeVisible=True):
                    tr = cmds.timeControl(a_time_slider, q=True, rangeArray=True)
                    if tr and (tr[1] - tr[0]) > 1:
                        start_t = tr[0]
                        end_t = tr[1] - 1
                        is_range = True
                    else:
                        cmds.warning("[ARTools] No time range selected. Falling back to Current Frame.")
                else:
                    cmds.warning("[ARTools] No time range selected. Falling back to Current Frame.")
            except: pass
        
        elif mode == "Entire Time Slider":
            start_t = cmds.playbackOptions(q=True, minTime=True)
            end_t = cmds.playbackOptions(q=True, maxTime=True)
            is_range = True

        bake_mode = getattr(self, "_space_bake_mode", "Existing Keys Only")
        frames = []
        
        if not is_range:
            frames = [float(start_t)]
        elif bake_mode == "Existing Keys Only":
            key_times = cmds.keyframe(target_nodes, q=True, time=(start_t, end_t)) or []
            if key_times:
                frames = sorted(list(set([float(t) for t in key_times])))
            else:
                frames = [float(start_t)]
        elif bake_mode == "Bake on 2s":
            frames = [float(f) for f in range(int(start_t), int(end_t) + 1, 2)]
        else:
            frames = [float(f) for f in range(int(start_t), int(end_t) + 1)]

        cmds.undoInfo(openChunk=True, chunkName="ARTools_SpaceSwitch")
        
        # 2. Suspend Evaluation for Speed
        if is_range:
            cmds.refresh(suspend=True)
            current_eval_mode = cmds.evaluationManager(q=True, mode=True)[0]
            if current_eval_mode != "off": cmds.evaluationManager(mode='off')
            import maya.mel as mel
            main_pane = mel.eval('global string $gMainPane; $tmp = $gMainPane;') 
            if main_pane and cmds.paneLayout(main_pane, exists=True):
                cmds.paneLayout(main_pane, edit=True, manage=False)

        try:
            # 3. Capture World States and Tangents
            world_states = {} 
            for f in frames:
                if is_range: cmds.currentTime(f)
                
                f_data = {}
                for node in target_nodes:
                    if not cmds.objExists(node) or cmds.nodeType(node) == "network": continue
                    m = cmds.xform(node, q=True, ws=True, m=True)
                    
                    tangents = {}
                    for attr in ["translate", "rotate"]:
                        for axis in ["X", "Y", "Z"]:
                            plug = f"{node}.{attr}{axis}"
                            if cmds.keyframe(plug, q=True, time=(f, f), keyframeCount=True):
                                itt = cmds.keyTangent(plug, q=True, time=(f, f), itt=True)
                                ott = cmds.keyTangent(plug, q=True, time=(f, f), ott=True)
                                if itt and ott:
                                    tangents[plug] = (itt[0], ott[0])
                    
                    f_data[node] = (m, tangents)
                world_states[f] = f_data

            # 4. Apply Space, Snap Back, and Restore Tangents
            temp_loc = cmds.spaceLocator(name="ARTools_SpaceSwitch_TempLoc")[0]
            for f in frames:
                if is_range: cmds.currentTime(f)
                
                if cmds.getAttr(attr_path, settable=True):
                    cmds.setAttr(attr_path, value)
                    if is_range or cmds.autoKeyframe(q=True, state=True) or cmds.keyframe(attr_path, q=True, keyframeCount=True):
                        cmds.setKeyframe(attr_path)

                for node, (m, tangents) in world_states[f].items():
                    cmds.xform(temp_loc, ws=True, m=m)
                    
                    if not cmds.getAttr(node + ".tx", l=True):
                        cmds.matchTransform(node, temp_loc, pos=True)
                    if not cmds.getAttr(node + ".rx", l=True):
                        cmds.matchTransform(node, temp_loc, rot=True)
                    
                    if is_range or cmds.autoKeyframe(q=True, state=True) or cmds.keyframe(node, at=["translate", "rotate"], q=True, keyframeCount=True):
                        cmds.setKeyframe(node, at=["translate", "rotate"])
                        
                    for plug, (itt, ott) in tangents.items():
                        if cmds.keyframe(plug, q=True, time=(f, f), keyframeCount=True):
                            cmds.keyTangent(plug, time=(f, f), itt=itt, ott=ott)
            
            if cmds.objExists(temp_loc):
                cmds.delete(temp_loc)

            # 5. Euler Filter Cleanup
            if is_range:
                for node in target_nodes:
                    if cmds.objExists(node):
                        rot_curves = [f"{node}.rotate{x}" for x in "XYZ"]
                        valid_rot = [c for c in rot_curves if cmds.objExists(c) and not cmds.getAttr(c, lock=True)]
                        if valid_rot:
                            try: cmds.filterCurve(valid_rot)
                            except: pass

        except Exception as e:
            cmds.warning(f"[ARTools] Space Switch Error: {e}")
        finally:
            if is_range:
                if current_eval_mode != "off": cmds.evaluationManager(mode=current_eval_mode)
                if main_pane and cmds.paneLayout(main_pane, exists=True):
                    cmds.paneLayout(main_pane, edit=True, manage=True)
                cmds.refresh(suspend=False)
                cmds.refresh(force=True)
                
            cmds.undoInfo(closeChunk=True)
            
            if is_range: cmds.inViewMessage(amg=f"Space Switch Baked ({len(frames)} frames)", pos="midCenter", fade=True)
            else: cmds.inViewMessage(amg="Space Switched", pos="midCenter", fade=True)

    def _mirror_plane(self, plane, is_anim=False):
        nodes = cmds.ls(sl=True, long=True)
        if not nodes: return
        cmds.undoInfo(openChunk=True)
        
        t_mult = [-1, 1, 1] if plane == "YZ" else ([1, -1, 1] if plane == "XZ" else [1, 1, -1])
        r_mult = [1, -1, -1] if plane == "YZ" else ([-1, 1, -1] if plane == "XZ" else [-1, -1, 1])

        for node in nodes:
            for attr, mult in zip(["translateX", "translateY", "translateZ"], t_mult):
                full_attr = f"{node}.{attr}"
                if mult == -1 and cmds.objExists(full_attr) and cmds.getAttr(full_attr, settable=True):
                    if is_anim and cmds.keyframe(full_attr, query=True, keyframeCount=True):
                        cmds.scaleKey(full_attr, valueScale=-1.0, valuePivot=0.0)
                    else:
                        val = cmds.getAttr(full_attr)
                        cmds.setAttr(full_attr, val * -1)
            
            for attr, mult in zip(["rotateX", "rotateY", "rotateZ"], r_mult):
                full_attr = f"{node}.{attr}"
                if mult == -1 and cmds.objExists(full_attr) and cmds.getAttr(full_attr, settable=True):
                    if is_anim and cmds.keyframe(full_attr, query=True, keyframeCount=True):
                        cmds.scaleKey(full_attr, valueScale=-1.0, valuePivot=0.0)
                    else:
                        val = cmds.getAttr(full_attr)
                        cmds.setAttr(full_attr, val * -1)
                    
        cmds.undoInfo(closeChunk=True)

    def _show_pivot_dialog(self, *args, **kwargs):
        if hasattr(self, "_pivot_dlg") and self._pivot_dlg:
            self._pivot_dlg.close()
            
        self._pivot_dlg = QtWidgets.QDialog(self)
        self._pivot_dlg.setWindowTitle("Mirror from Pivot")
        self._pivot_dlg.setMinimumWidth(350)
        self._pivot_dlg.setModal(False)
        
        layout = QtWidgets.QVBoxLayout(self._pivot_dlg)
        
        # 1. Radios (Pose vs Anim)
        grp_mode = QtWidgets.QButtonGroup(self._pivot_dlg)
        rad_pose = QtWidgets.QRadioButton("Pose")
        rad_anim = QtWidgets.QRadioButton("Animation")
        rad_pose.setChecked(True)
        grp_mode.addButton(rad_pose)
        grp_mode.addButton(rad_anim)
        r_mode = QtWidgets.QHBoxLayout()
        r_mode.addWidget(rad_pose)
        r_mode.addWidget(rad_anim)
        layout.addLayout(r_mode)
        
        # 2. Pivot Selection
        r_pivot = QtWidgets.QHBoxLayout()
        r_pivot.addWidget(QtWidgets.QLabel("Select desire Pivot control/object:"))
        txt_pivot = QtWidgets.QLineEdit()
        sel = cmds.ls(sl=True)
        if sel: txt_pivot.setText(sel[0])
        btn_piv_add = QtWidgets.QPushButton("Add Selected")
        btn_piv_add.clicked.connect(partial(self._set_pivot_from_selection, txt_pivot))
        r_pivot.addWidget(txt_pivot)
        r_pivot.addWidget(btn_piv_add)
        layout.addLayout(r_pivot)
        
        # 3. Scalable Box for Unfollow/Global
        layout.addWidget(QtWidgets.QLabel("Add unfollow or Global Controls:"))
        list_targets = QtWidgets.QListWidget()
        list_targets.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        if sel: list_targets.addItems([s.split("|")[-1].split(":")[-1] for s in sel])
        layout.addWidget(list_targets)
        
        r_list_btns = QtWidgets.QHBoxLayout()
        btn_targ_add = QtWidgets.QPushButton("Add Selected")
        btn_targ_add.clicked.connect(partial(self._add_targets_from_selection, list_targets))
        btn_targ_clr = QtWidgets.QPushButton("Clear box")
        btn_targ_clr.clicked.connect(list_targets.clear)
        r_list_btns.addWidget(btn_targ_add)
        r_list_btns.addWidget(btn_targ_clr)
        layout.addLayout(r_list_btns)
        
        # 4. Actions
        r_action = QtWidgets.QHBoxLayout()
        btn_mirror = QtWidgets.QPushButton("Mirror")
        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_cancel.clicked.connect(self._pivot_dlg.close)
        
        def on_mirror():
            p_text = txt_pivot.text().strip()
            t_text = [list_targets.item(i).text() for i in range(list_targets.count())]
            if rad_pose.isChecked():
                logic_pose.mirror_pose(namespace=self._get_ns(), mode="swap", pivot=p_text, offset_nodes=t_text)
            else:
                logic_anim.mirror_anim(namespace=self._get_ns(), mode="swap", pivot=p_text, offset_nodes=t_text)
                
        btn_mirror.clicked.connect(on_mirror)
        r_action.addWidget(btn_mirror)
        r_action.addWidget(btn_cancel)
        layout.addLayout(r_action)
        
        self._pivot_dlg.show()

    def _show_planes_dialog(self, *args, **kwargs):
        if hasattr(self, "_planes_dlg") and self._planes_dlg:
            self._planes_dlg.close()
            
        self._planes_dlg = QtWidgets.QDialog(self)
        self._planes_dlg.setWindowTitle("Mirror Planes")
        self._planes_dlg.setMinimumWidth(250)
        self._planes_dlg.setModal(False)
        
        layout = QtWidgets.QVBoxLayout(self._planes_dlg)
        
        # Mode
        grp_mode = QtWidgets.QButtonGroup(self._planes_dlg)
        rad_pose = QtWidgets.QRadioButton("Pose")
        rad_anim = QtWidgets.QRadioButton("Animation")
        rad_pose.setChecked(True)
        grp_mode.addButton(rad_pose)
        grp_mode.addButton(rad_anim)
        r_mode = QtWidgets.QHBoxLayout()
        r_mode.addWidget(rad_pose)
        r_mode.addWidget(rad_anim)
        layout.addLayout(r_mode)
        
        # Planes
        grp_plane = QtWidgets.QButtonGroup(self._planes_dlg)
        rad_yz = QtWidgets.QRadioButton("YZ Plane (Flip X)")
        rad_xz = QtWidgets.QRadioButton("XZ Plane (Flip Y)")
        rad_xy = QtWidgets.QRadioButton("XY Plane (Flip Z)")
        rad_yz.setChecked(True)
        grp_plane.addButton(rad_yz)
        grp_plane.addButton(rad_xz)
        grp_plane.addButton(rad_xy)
        
        layout.addWidget(rad_yz)
        layout.addWidget(rad_xz)
        layout.addWidget(rad_xy)
        
        # Actions
        r_action = QtWidgets.QHBoxLayout()
        btn_mirror = QtWidgets.QPushButton("Mirror")
        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_cancel.clicked.connect(self._planes_dlg.close)
        
        def on_mirror():
            is_anim = rad_anim.isChecked()
            plane = "YZ"
            if rad_xz.isChecked(): plane = "XZ"
            elif rad_xy.isChecked(): plane = "XY"
            self._mirror_plane(plane, is_anim)
            
        btn_mirror.clicked.connect(on_mirror)
        r_action.addWidget(btn_mirror)
        r_action.addWidget(btn_cancel)
        layout.addLayout(r_action)
        
        self._planes_dlg.show()

    def _toggle_palette(self, *args):
        if self.floating_palette.isVisible():
            self.floating_palette.hide()
            self.btn_palette.setStyleSheet("")
        else:
            self.floating_palette.show()
            self.btn_palette.setStyleSheet("background: rgba(79, 184, 167, 100); border: 2px solid #4CAF50;")

    def _sync_palette_pos(self):
        if hasattr(self, "floating_palette") and self.floating_palette.isVisible():
            geo = self.geometry()
            self.floating_palette.move(geo.x(), geo.y() + geo.height() + 5)

    # ==========================================
    # WINDOW EVENT MANAGEMENT (MERGED & CYTHON-SAFE)
    # ==========================================
    def showEvent(self, event):
        # 1. Cython-safe parent call
        QtWidgets.QWidget.showEvent(self, event)
        
        # 2. Load Window Position Memory
        try:
            from ARTools.preferences import PrefManager
            prefs = PrefManager()
            x = prefs.get("animbar_x")
            y = prefs.get("animbar_y")
            if x is not None and y is not None and x != -9999 and y != -9999:
                self.move(x, y)
        except Exception: 
            pass

        # 3. Auto-Rotation Engine (For Toolbars)
        parent_tb = self.parentWidget()
        while parent_tb and not isinstance(parent_tb, QtWidgets.QToolBar):
            parent_tb = parent_tb.parentWidget()
            
        if parent_tb and not getattr(self, "_dock_connected", False):
            parent_tb.orientationChanged.connect(self._on_orientation_changed)
            self._dock_connected = True
            self._on_orientation_changed(parent_tb.orientation())

    def closeEvent(self, event):
        # 1. Save Window Position Memory
        try:
            from ARTools.preferences import PrefManager
            prefs = PrefManager()
            prefs.set("animbar_x", self.x())
            prefs.set("animbar_y", self.y())
        except Exception: 
            pass
        
        # 2. Safely kill the Maya scriptJobs and Timers without warnings
        job_id = getattr(self, "script_job_id", None)
        if job_id:
            import maya.cmds as cmds
            try:
                if cmds.scriptJob(exists=job_id): cmds.scriptJob(kill=job_id, force=True)
            except Exception: pass
            self.script_job_id = None
            
        sync_job = getattr(self, "ui_sync_job", None)
        if sync_job:
            import maya.cmds as cmds
            try:
                if cmds.scriptJob(exists=sync_job): cmds.scriptJob(kill=sync_job, force=True)
            except Exception: pass
            self.ui_sync_job = None
            
        if hasattr(self, "tab_poll_timer"):
            self.tab_poll_timer.stop()
        
        # 3. Cython-safe parent call (No super!)
        QtWidgets.QWidget.closeEvent(self, event)