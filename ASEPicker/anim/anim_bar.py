# ASEPicker/anim/anim_bar.py
try:
    from PySide2 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui

from maya import cmds
from functools import partial
from . import logic_pose
from . import logic_anim
from . import snapshot
from . import clipboard
from . import logic_ikfk
from .trail import TrailManager
import os

class AnimBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(AnimBar, self).__init__(parent)
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
        
        self.btn_close = QtWidgets.QPushButton("×")
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setObjectName("CloseBtn")
        self.btn_close.clicked.connect(self.close)
        layout.addWidget(self.btn_close)
        
        self._add_sep(layout)

        # --- 1. Snapshot / Reset / Mirror ---
        self.btn_snap = self._icon_btn("anim_snap", "Snapshot Character (Auto-Detect Mirror)", self._on_snapshot)
        self.btn_reset = self._icon_btn("anim_reset", "Reset Pose", self._on_reset)

        self._add_sep(layout)

        mirror_tooltip = "Mirror Pose\nShift+Click: Select Mirror (Add)\nAlt+Click: Select Mirror (Replace)"
        self.btn_mirror = self._icon_btn("anim_mirror", mirror_tooltip, self._on_mirror)
        self.btn_mirror.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.btn_mirror.customContextMenuRequested.connect(self._menu_mirror)
        self.btn_space = self._icon_btn("anim_space", "Space Switcher", self._on_space_click)

        layout.addWidget(self.btn_snap)
        layout.addWidget(self.btn_reset)
        layout.addWidget(self.btn_mirror)

        self._add_sep(layout)

        layout.addWidget(self.btn_space)
        
        self._add_sep(layout)

        # --- 2. Pose (Local & World) ---
        self.btn_pl = self._icon_btn("anim_copy_pose", "Pose Local (L: Copy, R: Menu)", lambda *a: logic_pose.copy_pose(False))
        self._setup_context_menu(self.btn_pl, "pose_local", 
            copy_cmd=lambda: logic_pose.copy_pose(False), 
            paste_cmd=lambda: logic_pose.paste_pose(False, self._get_paste_ns())
        )

        self.btn_pw = self._icon_btn("anim_copy_world_pose", "Pose World (L: Copy, R: Menu)", lambda *a: logic_pose.copy_pose(True))
        self._setup_context_menu(self.btn_pw, "pose_global", 
            copy_cmd=lambda: logic_pose.copy_pose(True), 
            paste_cmd=lambda: logic_pose.paste_pose(True, self._get_paste_ns())
        )

        layout.addWidget(self.btn_pl)
        layout.addWidget(self.btn_pw)

        self._add_sep(layout)

        # --- 3. Anim (Local & World) ---
        self.btn_al = self._icon_btn("anim_copy_anim", "Anim Local (L: Copy, R: Menu)", lambda *a: logic_anim.copy_anim(False))
        self._setup_context_menu(self.btn_al, "anim_local", 
            copy_cmd=lambda: logic_anim.copy_anim(False), 
            paste_cmd=None,
            paste_dict={
                "Paste Anim (Original Time)": lambda: logic_anim.paste_anim(False, self._get_paste_ns(), "original"),
                "Paste Anim (Current Time)": lambda: logic_anim.paste_anim(False, self._get_paste_ns(), "current")
            }
        )

        self.btn_aw = self._icon_btn("anim_copy_world_anim", "Anim World (L: Copy, R: Menu)", lambda *a: logic_anim.copy_anim(True))
        self._setup_context_menu(self.btn_aw, "anim_global", 
            copy_cmd=lambda: logic_anim.copy_anim(True), 
            paste_cmd=None,
            paste_dict={
                "Paste Anim (Original Time)": lambda: logic_anim.paste_anim(True, self._get_paste_ns(), "original"),
                "Paste Anim (Current Time)": lambda: logic_anim.paste_anim(True, self._get_paste_ns(), "current")
            }
        )

        layout.addWidget(self.btn_al)
        layout.addWidget(self.btn_aw)
        
        self._add_sep(layout)

        # --- 4. IK/FK Tools ---
        # Pressing the IK button snaps to FK and turns the rig to IK.
        self.btn_to_ik = self._icon_btn("ik_mode", "Switch to IK (Snap IK to FK)", lambda *a: self._match_chain("to_ik"))
        
        # Pressing the FK button snaps to IK and turns the rig to FK.
        self.btn_to_fk = self._icon_btn("fk_mode", "Switch to FK (Snap FK to IK)", lambda *a: self._match_chain("to_fk"))
        
        self._add_ikfk_menu(self.btn_to_ik, "to_ik")
        self._add_ikfk_menu(self.btn_to_fk, "to_fk")

        layout.addWidget(self.btn_to_ik)
        layout.addWidget(self.btn_to_fk)

        self._add_sep(layout)

        # --- 5 Motion Trail Button (ASEPicker >> trail) ---
        # Fixed: Updated to call 'create_or_toggle' (new name)
        self.btn_motion_trail = self._icon_btn("trail_icon", "Toggle Motion Trail(s)", lambda *a: TrailManager.get_instance().create_or_toggle())
        self.btn_motion_trail.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.btn_motion_trail.customContextMenuRequested.connect(lambda pos: TrailManager.get_instance().exec_context_menu())
        layout.addWidget(self.btn_motion_trail)

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
            QPushButton { background: transparent; border-radius: 6px; }
            QPushButton:hover { background: rgba(79, 184, 167, 70); border: 1px solid rgba(79, 184, 167, 150); }
            QPushButton:pressed { background: rgba(79, 184, 167, 120); }
        """)
        self._old_pos = None

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
    
    def _icon_btn(self, icon_name, tip, func):
        btn = QtWidgets.QPushButton()
        btn.setToolTip(tip)
        btn.clicked.connect(func)
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.setFlat(True)
        btn.setFixedSize(38, 38)
        
        # --- NEW: Robust Icon Pathing ---
        current_dir = os.path.dirname(os.path.abspath(__file__)) # anim folder
        root_dir = os.path.dirname(current_dir) # ASEPicker folder
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
        
        def show_menu(pos):
            from ASEPicker.preferences import PrefManager
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
            menu.addAction("Select Stored Controls", lambda: self._select_stored(file_type))
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
            
        btn.customContextMenuRequested.connect(show_menu)

    def _get_paste_ns(self):
        """Resolves namespace dynamically based on user toggle preference."""
        from ASEPicker.preferences import PrefManager
        if PrefManager().get("animbar_paste_selected"):
            sel = cmds.ls(sl=True)
            if sel and ":" in sel[0]:
                return sel[0].split("|")[-1].rsplit(":", 1)[0]
            return ""
        return None

    def _add_ikfk_menu(self, btn, mode):
        # Simplified menu: No Human/Animal toggle. 
        # Chain type is decided by the chain data itself.
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        def show_menu(pos):
            menu = QtWidgets.QMenu(self)
            menu.addAction("Match (Keyframe)", lambda: self._match_chain(mode, key=True))
            menu.addAction("Match (No Key)", lambda: self._match_chain(mode, key=False))
            menu.exec_(btn.mapToGlobal(pos))
        btn.customContextMenuRequested.connect(show_menu)

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
            from ASEPicker.api import get_namespace
            return get_namespace()
        except Exception:
            return ""

    def _on_snapshot(self):
        snapshot.create_character_snapshot(self._get_ns())
        try:
            from ASEPicker import main
            win = main._app_instance.window
            if hasattr(win, "_update_status"):
                win._update_status()
        except Exception:
            pass

    def _on_reset(self):
        logic_pose.reset_pose(self._get_ns())

    def _on_mirror(self):
        mods = QtWidgets.QApplication.keyboardModifiers()
        ns = self._get_ns()
        if mods & QtCore.Qt.ShiftModifier:
            logic_pose.select_mirror_controls(ns, add=True)
        elif mods & QtCore.Qt.AltModifier:
            logic_pose.select_mirror_controls(ns, add=False)
        else:
            logic_pose.mirror_pose(ns, mode="swap")

    def _menu_mirror(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.addAction("Mirror Animation (Swap)", lambda: logic_anim.mirror_anim(namespace=self._get_ns(), mode="swap"))
        menu.addSeparator()
        menu.addAction("Mirror from Pivot...", self._show_pivot_dialog)
        menu.addAction("Mirror Planes...", self._show_planes_dialog)
        
        menu.exec_(self.btn_mirror.mapToGlobal(pos))

    def _match_chain(self, target_mode, key=True):
        try:
            from ASEPicker import main
            win = main._app_instance.window
            char_tab = win.main_tabs.currentWidget()
            if not char_tab: return
        except Exception:
            return
            
        chains = getattr(char_tab, "ikfk_chains", [])
        if not chains:
            from maya import cmds
            cmds.warning("[ASEPicker] No IK/FK Chains configured. Add them in the Rig Settings tab.")
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
            cmds.warning("[ASEPicker] Selection does not match any configured IK/FK chain.")
            return

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

            # Route securely to logic_ikfk (The redundant attribute flip is safely removed from here)
            if target_mode == "to_ik":
                logic_ikfk.switch_to_ik(chain, ns, key=key)
            elif target_mode == "to_fk":
                logic_ikfk.switch_to_fk(chain, ns, key=key)

    def _on_motion_trail(self, *args):
        from ASEPicker.trail import TrailManager
        TrailManager.get_instance().create_or_toggle()

    def show_trail_menu(self):
        menu = TrailManager.get_instance().create_context_menu()
        menu.exec_(QtGui.QCursor.pos())

    def _on_delete_selected_trails(self):
        TrailManager.get_instance().delete_trail()

    def _on_space_click(self):
        sel = cmds.ls(sl=True)
        if not sel:
            return

        # 1. Helpers
        keywords = ["space", "parent", "follow", "ref", "isolate", "world", "local"]
        
        def _get_space_attrs(node):
            # Returns list of (attr_name)
            found = []
            if not node: return found
            # Get all keyable attributes
            attrs = cmds.listAttr(node, k=True) or []
            for a in attrs:
                # 1. Must match a keyword (e.g. "Follow", "Space")
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

    def _set_space(self, attr_path, value, target_nodes):
        # 1. Record World Transforms for ALL selected nodes (Hand, PV, etc.)
        world_states = {}
        for node in target_nodes:
            if not cmds.objExists(node): continue
            # Skip the hub node itself if it's just a settings loc/network node (optional safety)
            if cmds.nodeType(node) == "network": continue
            
            t = cmds.xform(node, q=True, ws=True, t=True)
            r = cmds.xform(node, q=True, ws=True, ro=True)
            world_states[node] = (t, r)

        # 2. Switch Space
        if cmds.getAttr(attr_path, settable=True):
            cmds.setAttr(attr_path, value)

        # 3. Restore Transforms (Snap Back)
        for node, (t, r) in world_states.items():
            if not cmds.getAttr(node + ".tx", l=True):
                cmds.move(t[0], t[1], t[2], node, ws=True)
            
            if not cmds.getAttr(node + ".rx", l=True):
                cmds.rotate(r[0], r[1], r[2], node, ws=True)

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

    def _show_pivot_dialog(self):
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
        btn_piv_add.clicked.connect(lambda: txt_pivot.setText(cmds.ls(sl=True)[0] if cmds.ls(sl=True) else txt_pivot.text()))
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
        btn_targ_add.clicked.connect(lambda: list_targets.addItems([s.split("|")[-1].split(":")[-1] for s in cmds.ls(sl=True)]))
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

    def _show_planes_dialog(self):
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
    
    # ==========================================
    # WINDOW EVENT MANAGEMENT (MERGED & CYTHON-SAFE)
    # ==========================================
    def showEvent(self, event):
        # 1. Cython-safe parent call
        QtWidgets.QWidget.showEvent(self, event)
        
        # 2. Load Window Position Memory
        try:
            from ASEPicker.preferences import PrefManager
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
            from ASEPicker.preferences import PrefManager
            prefs = PrefManager()
            prefs.set("animbar_x", self.x())
            prefs.set("animbar_y", self.y())
        except Exception: 
            pass
            
        # 2. Safely kill the Maya scriptJob without warnings
        job_id = getattr(self, "script_job_id", None) # Change if your variable is different!
        if job_id:
            import maya.cmds as cmds
            if cmds.scriptJob(exists=job_id):
                cmds.scriptJob(kill=job_id, force=True)
            self.script_job_id = None
            
        # 3. Cython-safe parent call (No super!)
        QtWidgets.QWidget.closeEvent(self, event)