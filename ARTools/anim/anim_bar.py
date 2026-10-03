# ARTools/anim/anim_bar.py
from PySide6 import QtWidgets, QtCore, QtGui

import bpy
from functools import partial
from . import logic_pose
from . import logic_anim
from . import snapshot
from . import clipboard
from . import fake_parent
from . import logic_ikfk
from .trail import TrailManager
import os
import sys
import mathutils
from ..blender_host import selected_object_names, select_objects, object_by_name, get_property, set_property, get_plug_enum_items

def _attach_owner_hwnd(qwidget, owner_hwnd):
    if sys.platform != "win32" or not owner_hwnd:
        return
    import ctypes
    qwidget.winId()  # force native handle creation
    hwnd = int(qwidget.winId())

    GWLP_HWNDPARENT = -8
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOZORDER = 0x0004
    SWP_FRAMECHANGED = 0x0020

    user32 = ctypes.windll.user32
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    user32.GetWindowLongPtrW.restype = ctypes.c_void_p
    user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]

    user32.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, owner_hwnd)

    ex_style = int(user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE))
    if ex_style & WS_EX_TOOLWINDOW:
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_TOOLWINDOW)
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)

def _raise_above_owner(qwidget, insert_after_hwnd=0):
    """Push qwidget just above insert_after_hwnd in z-order (0 = absolute
    top), without activating it (SWP_NOACTIVATE). Passing a specific hwnd
    instead of always requesting the absolute top lets two related
    windows (AnimBar + palette) be stacked in one defined pass -- Blender,
    then AnimBar, then palette -- instead of both independently demanding
    "topmost" and forcing DWM to recomposite twice in a row."""
    if sys.platform != "win32":
        return
    import ctypes
    qwidget.winId()
    hwnd = int(qwidget.winId())

    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010

    user32 = ctypes.windll.user32
    user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetWindowPos(hwnd, insert_after_hwnd, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    EVENT_SYSTEM_FOREGROUND = 0x0003
    WINEVENT_OUTOFCONTEXT = 0x0000

    # Must be kept as a WINFUNCTYPE, not a plain Python function -- Windows
    # calls into this pointer directly, so the callback object has to stay
    # alive (held on the AnimBar instance) for as long as the hook exists.
    _WinEventProcType = ctypes.WINFUNCTYPE(
        None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
        wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD
    )

class AnimBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        # Grab Blender's own window right now, before any Qt window of
        # ours is created/shown -- Blender is guaranteed to still be the
        # foreground window at this exact point, since the user just
        # triggered this from inside Blender.
        self._blender_hwnd = None
        if sys.platform == "win32":
            import ctypes
            self._blender_hwnd = ctypes.windll.user32.GetForegroundWindow()

        for widget in QtWidgets.QApplication.topLevelWidgets():
            if widget.objectName() == "AnimBar" and widget != self:
                try:
                    widget.close()
                    widget.deleteLater()
                except Exception: pass
        
        # --- FIX 1: LINK TO ARTOOLS PICKER (IF OPEN) ---
        if parent is None:
            for widget in QtWidgets.QApplication.topLevelWidgets():
                if type(widget).__name__ == "PickerWindow":
                    parent = widget
                    break
        # -----------------------------------------------
        
        from ARTools import security
        
        io_check = security.enforce_license("animbar", parent_window=parent)
        
        if not io_check or getattr(io_check, "_ase_secure_stamp", "") != "JAY_SHREE_KRISHNA_1986":
            print("[ARTools] License Invalid. AnimBar aborted.")
            self.deleteLater()
            return
        
        QtWidgets.QWidget.__init__(self, None)

        self.setObjectName("AnimBar")
        
        # --- FIX 2: STRICT TOOL FLAGS (NO GLOBAL FLOATING) ---
        # The WindowStaysOnTopHint is REMOVED so it doesn't bleed across virtual desktops.
        # We will natively parent it to Blender in showEvent() instead.
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

        self._add_sep(layout)

        # --- 7. Anim sliders ---
        self.btn_dynamics = self._icon_btn("anim_curves", "Toggle Curve Dynamics", self._toggle_dynamics_panel)
        layout.addWidget(self.btn_dynamics)

        self.btn_palette = self._icon_btn("palette_icon", "Toggle Floating Palette", self._toggle_palette)
        self.btn_palette.setText("🎨")
        layout.addWidget(self.btn_palette)

        from .anim_sliders import CompactDynamicsWidget, FloatingSliderPalette
        self.dynamics_panel = CompactDynamicsWidget(self)
        self.dynamics_panel.setVisible(False) 
        
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
        self.tab_poll_timer = QtCore.QTimer(self)
        self.tab_poll_timer.timeout.connect(self._poll_picker_state)
        self.tab_poll_timer.start(150) 
        self._last_chain_count = -1
        self._last_sel_cache = None
        self._update_ikfk_buttons()

        self._win_event_hook = None
        self._win_event_proc = None
        if sys.platform == "win32" and self._blender_hwnd:
            self._win_event_proc = _WinEventProcType(self._on_foreground_changed)
            user32 = ctypes.windll.user32
            user32.SetWinEventHook.restype = wintypes.HANDLE
            user32.SetWinEventHook.argtypes = [
                wintypes.UINT, wintypes.UINT, wintypes.HMODULE,
                _WinEventProcType, wintypes.DWORD, wintypes.DWORD, wintypes.UINT
            ]
            self._win_event_hook = user32.SetWinEventHook(
                EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
                0, self._win_event_proc, 0, 0, WINEVENT_OUTOFCONTEXT
            )

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

    def moveEvent(self, event):
        QtWidgets.QWidget.moveEvent(self, event)

    def _on_foreground_changed(self, hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
        if not self.isVisible():
            return

        self.winId()
        my_hwnd = int(self.winId())

        pal_hwnd = None
        pal_visible = hasattr(self, "floating_palette") and self.floating_palette.isVisible()
        if pal_visible:
            self.floating_palette.winId()
            pal_hwnd = int(self.floating_palette.winId())

        relevant = hwnd == self._blender_hwnd or hwnd == my_hwnd or (pal_hwnd and hwnd == pal_hwnd)
        if not relevant:
            return

        _raise_above_owner(self, 0)
        if pal_visible:
            _raise_above_owner(self.floating_palette, my_hwnd)
    
    def _get_active_chains(self):
        from ARTools import main
        app = getattr(main, "_app_instance", None)
        win = getattr(app, "window", None) if app else None
        char_tab = win.main_tabs.currentWidget() if win and hasattr(win, "main_tabs") else None
        chains = getattr(char_tab, "ikfk_chains", []) if char_tab else []
        if not chains and char_tab and hasattr(char_tab, "sub_tabs"):
            sub = char_tab.sub_tabs.currentWidget()
            chains = getattr(sub, "ikfk_chains", []) if sub else []
            if not chains:
                for idx in range(char_tab.sub_tabs.count()):
                    w = char_tab.sub_tabs.widget(idx)
                    c = getattr(w, "ikfk_chains", [])
                    if c:
                        chains = c
                        break
        if chains:
            self._cached_chains = chains
        return getattr(self, "_cached_chains", [])

    def _poll_picker_state(self):
        chains = self._get_active_chains()
        sel = tuple(selected_object_names())
        if getattr(self, "_last_sel_cache", None) != sel:
            self._last_sel_cache = sel
            self._update_ikfk_buttons()
            
        if len(chains) != getattr(self, "_last_chain_count", -1):
            self._last_chain_count = len(chains)
            self._update_ikfk_buttons()

    def _update_ikfk_buttons(self, *args):
        chains = self._get_active_chains()

        # Explicitly define complete On/Off styles to prevent Qt from caching stuck backgrounds
        off_style = """
            QPushButton { background: transparent; border-radius: 6px; border: none; }
            QPushButton:hover { background: rgba(79, 184, 167, 70); border: 1px solid rgba(79, 184, 167, 150); }
            QPushButton:pressed { background: rgba(79, 184, 167, 120); }
        """
        
        highlight_style = """
            QPushButton { background: rgba(79, 184, 167, 100); border: 2px solid #4CAF50; border-radius: 6px; }
            QPushButton:hover { background: rgba(79, 184, 167, 130); border: 2px solid #66BB6A; }
            QPushButton:pressed { background: rgba(79, 184, 167, 150); }
        """

        if not chains:
            self.btn_to_ik.setEnabled(False)
            self.btn_to_fk.setEnabled(False)
            self.btn_to_ik.setToolTip("Disabled: No IK/FK chains configured in the active Picker Tab.")
            self.btn_to_fk.setToolTip("Disabled: No IK/FK chains configured in the active Picker Tab.")
            self.btn_to_ik.setStyleSheet(off_style)
            self.btn_to_fk.setStyleSheet(off_style)
            return

        self.btn_to_ik.setEnabled(True)
        self.btn_to_fk.setEnabled(True)
        self.btn_to_ik.setToolTip("Switch to IK (Snap IK to FK)")
        self.btn_to_fk.setToolTip("Switch to FK (Snap FK to IK)")

        sel = selected_object_names()
        highlight_ik = False
        highlight_fk = False

        if sel:
            sel_shorts = [s.split(":")[-1] for s in sel]
            ns = self._get_ns()
            for chain in chains:
                ik_ctrl = chain.get("ik_ctrl", "").split(":")[-1]
                pv_ctrl = chain.get("pv_ctrl", "").split(":")[-1]
                fk_ctrls = [x.split(":")[-1] for x in chain.get("fk_ctrls", []) if x]
                bones = [x.split(":")[-1] for x in chain.get("bones", []) if x]
                sw_node = (chain.get("sw_node") or chain.get("switch", {}).get("node", "")).split(":")[-1]
                sw_attr = (chain.get("sw_attr") or chain.get("switch", {}).get("attr", "")).split(".")[-1]
                ik_val = chain.get("ik_val", chain.get("switch", {}).get("ik_val", 1.0))
                fk_val = chain.get("fk_val", chain.get("switch", {}).get("fk_val", 0.0))

                for s in sel_shorts:
                    if not s:
                        continue
                        
                    # 1. Selected FK -> Highlight IK button (Suggest switching TO IK)
                    if s in fk_ctrls:
                        highlight_ik = True
                        
                    # 2. Selected IK -> Highlight FK button (Suggest switching TO FK)
                    elif s == ik_ctrl or s == pv_ctrl:
                        highlight_fk = True
                        
                    # 3. Selected Switch node or Deformation bone -> Check state
                    elif (s == sw_node or s in bones) and sw_node and sw_attr:
                        full_sw = f"{ns}:{sw_node}" if ns and not sw_node.startswith(ns) else sw_node
                        sw_obj = object_by_name(full_sw) or object_by_name(sw_node)
                        if sw_obj:
                            val = get_property(sw_obj, sw_attr, None)
                            if val is not None:
                                if abs(val - ik_val) < 0.1:
                                    # Currently in IK mode -> Suggest switching TO FK
                                    highlight_fk = True
                                elif abs(val - fk_val) < 0.1:
                                    # Currently in FK mode -> Suggest switching TO IK
                                    highlight_ik = True

        self.btn_to_ik.setStyleSheet(highlight_style if highlight_ik else off_style)
        self.btn_to_fk.setStyleSheet(highlight_style if highlight_fk else off_style)

    def _icon_btn(self, icon_name, tip, func):
        btn = QtWidgets.QPushButton()
        btn.setToolTip(tip)
        btn.clicked.connect(partial(func))
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.setFlat(True)
        btn.setFixedSize(38, 38)
        
        current_dir = os.path.dirname(os.path.abspath(__file__)) 
        root_dir = os.path.dirname(current_dir) 
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
            
            act_sel = menu.addAction("Apply to Selected")
            act_sel.setCheckable(True)
            act_sel.setChecked(prefs.get("animbar_paste_selected") or False)
            def on_toggle(checked):
                prefs.set("animbar_paste_selected", checked)
            act_sel.toggled.connect(on_toggle)
            menu.addSeparator()

            menu.addAction("Select Stored Controls", partial(self._select_stored, file_type))
            menu.addSeparator()

            if copy_cmd:
                label = "Copy Anim" if "anim" in file_type else "Copy Pose"
                menu.addAction(label, copy_cmd)

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
        from ARTools.preferences import PrefManager
        if PrefManager().get("animbar_paste_selected"):
            sel = selected_object_names()
            if sel and ":" in sel[0]:
                return sel[0].rsplit(":", 1)[0]
            return ""
        return None

    def _add_ikfk_menu(self, btn, mode):
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        def show_menu(pos, *args, **kwargs):
            menu = QtWidgets.QMenu(self)
            
            current_time = getattr(self, "_space_time_mode", "Current Frame")
            time_menu = menu.addMenu(f"⏱️ Time Mode: {current_time}")
            def set_time(m): self._space_time_mode = m
            for m in ["Current Frame", "Time Slider Selection", "Entire Time Slider"]:
                act = time_menu.addAction(m)
                act.setCheckable(True)
                if m == current_time: act.setChecked(True)
                act.triggered.connect(partial(set_time, m))
                
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
        ns = self._get_ns()
        targets = []
        for short in data.keys():
            full = f"{ns}:{short}" if ns else short
            if object_by_name(full):
                targets.append(full)
        if targets:
            select_objects(targets, replace=True)

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
        sel = selected_object_names()
        if not sel:
            print("[ARTools] Please select controls to Add/Fix.")
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
        logic_pose.reset_pose(self._get_ns())
        
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    with bpy.context.temp_override(window=window, area=area):
                        bpy.ops.ed.undo_push(message="ARTools_ResetPose")
                    return

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
            print("[ARTools] No IK/FK Chains configured. Add them in the Rig Settings tab.")
            return

        sel = selected_object_names()
        ns = self._get_ns()

        chains_to_process = []
        if not sel:
            chains_to_process = chains
        else:
            for chain in chains:
                nodes = [chain.get("ik_ctrl", ""), chain.get("pv_ctrl", ""), chain.get("sw_node", "")] + chain.get("fk_ctrls", [])
                nodes = [n.split(":")[-1] for n in nodes if n]
                found = False
                for s in sel:
                    short_s = s.split(":")[-1]
                    if short_s in nodes:
                        chains_to_process.append(chain)
                        found = True
                        break

        if not chains_to_process:
            print("[ARTools] Selection does not match any configured IK/FK chain.")
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

        logic_ikfk.batch_switch(formatted_chains, target_mode, ns, key, time_mode, bake_mode)

    def _on_overlap_click(self, *args):
        from . import simulation
        if getattr(self, "_overlap_win", None) is None or not self._overlap_win.isVisible():
            self._overlap_win = simulation.launch_overlap_engine(self)
        else:
            self._overlap_win.raise_()
            self._overlap_win.activateWindow()
    
    def _on_motion_trail(self, *args):
        TrailManager.get_instance().create_or_toggle()

    def show_trail_menu(self):
        menu = TrailManager.get_instance().create_context_menu()
        if menu:
            menu.exec_(QtGui.QCursor.pos())

    def _handle_trail_menu_request(self, pos):
        menu = TrailManager.get_instance().create_context_menu()
        if menu:
            menu.exec_(QtGui.QCursor.pos())
    
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
        sel = selected_object_names()
        if sel: field.setText(sel[0])

    def _add_targets_from_selection(self, list_widget):
        sel = selected_object_names()
        if sel: list_widget.addItems([s.split(":")[-1] for s in sel])
    
    def _on_space_click(self, *args, **kwargs):
        sel = selected_object_names()
        if not sel: return

        keywords = ["space", "parent", "follow", "ref", "isolate", "world", "local", "global", "orient", "dyn"]
        
        def _get_space_attrs(node_name):
            found = []
            if not node_name: return found
            b_obj = object_by_name(node_name)
            if not b_obj: return found
            
            for a in b_obj.keys():
                if a.startswith("_"): continue
                if any(k in a.lower() for k in keywords):
                    found.append(a)
            
            for prop in b_obj.bl_rna.properties:
                a = prop.identifier
                if a == "rna_type" or getattr(prop, "is_hidden", False): continue
                if any(k in a.lower() for k in keywords):
                    if prop.type in ["ENUM", "INT", "FLOAT"]:
                        if a not in found: found.append(a)
            return found

        hub_node = None
        hub_attrs = []
        
        for s in sel:
            attrs = _get_space_attrs(s)
            if attrs:
                hub_node = s
                hub_attrs = attrs
                break
                
        if not hub_node:
            for s in sel:
                b_obj = object_by_name(s)
                if b_obj and b_obj.parent:
                    attrs = _get_space_attrs(b_obj.parent.name)
                    if attrs:
                        hub_node = b_obj.parent.name
                        hub_attrs = attrs
                        break
                        
        menu = QtWidgets.QMenu(self)
        
        current_mode = getattr(self, "_space_time_mode", "Current Frame")
        mode_menu = menu.addMenu(f"⏱️ Time Mode: {current_mode}")
        def set_mode(m): self._space_time_mode = m
        
        for m in ["Current Frame", "Time Slider Selection", "Entire Time Slider"]:
            act = mode_menu.addAction(m)
            act.setCheckable(True)
            if m == current_mode: act.setChecked(True)
            act.triggered.connect(partial(set_mode, m))

        current_bake = getattr(self, "_space_bake_mode", "Existing Keys Only")
        bake_menu = menu.addMenu(f"🔑 Bake Mode: {current_bake}")
        def set_bake(b): self._space_bake_mode = b
            
        for b in ["Existing Keys Only", "Bake Every Frame", "Bake on 2s"]:
            act = bake_menu.addAction(b)
            act.setCheckable(True)
            if b == current_bake: act.setChecked(True)
            act.triggered.connect(partial(set_bake, b))

        menu.addSeparator()
        
        if hub_node and hub_attrs:
            lbl = QtWidgets.QLabel("  Hub: " + hub_node.split(":")[-1] + "  ")
            lbl.setStyleSheet("font-weight: bold; color: #ccc; background-color: #444;")
            act = QtWidgets.QWidgetAction(menu)
            act.setDefaultWidget(lbl)
            menu.addAction(act)
            menu.addSeparator()

            for attr in hub_attrs:
                full_attr = f"{hub_node}.{attr}"
                sub = menu.addMenu(attr)
                current_val = get_property(object_by_name(hub_node), attr, 0)
                
                enum_items = get_plug_enum_items(full_attr)
                if enum_items:
                    for i, (identifier, label) in enumerate(enum_items):
                        val = i 
                        if isinstance(current_val, str):
                            mark = " [x] " if current_val == identifier else "     "
                            sub.addAction(mark + label, partial(self._set_space, full_attr, identifier, sel))
                        else:
                            mark = " [x] " if abs(current_val - val) < 0.001 else "     "
                            sub.addAction(mark + label, partial(self._set_space, full_attr, val, sel))
                else:
                    min_v, max_v = 0, 10
                    b_obj = object_by_name(hub_node)
                    if b_obj:
                        prop = b_obj.bl_rna.properties.get(attr)
                        if prop and hasattr(prop, "hard_min") and hasattr(prop, "hard_max"):
                            if prop.hard_min > -1000: min_v = int(prop.hard_min)
                            if prop.hard_max < 1000: max_v = int(prop.hard_max)
                    
                    if max_v - min_v > 20: max_v = min_v + 10

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
        expanded_nodes = set(target_nodes)
        try:
            from ARTools import main
            win = main._app_instance.window if hasattr(main, "_app_instance") else None
            char_tab = win.main_tabs.currentWidget() if win else None
            chains = getattr(char_tab, "ikfk_chains", []) if char_tab else []
            
            if chains:
                for chain in chains:
                    ik_ctrl = chain.get("ik_ctrl", "").split(":")[-1]
                    pv_ctrl = chain.get("pv_ctrl", "").split(":")[-1]
                    
                    if any(ik_ctrl == n.split(":")[-1] for n in target_nodes):
                        if pv_ctrl:
                            ns = target_nodes[0].rsplit(":", 1)[0] + ":" if ":" in target_nodes[0] else ""
                            full_pv = ns + pv_ctrl
                            if object_by_name(full_pv):
                                expanded_nodes.add(full_pv)
        except Exception:
            pass
        
        target_nodes = list(expanded_nodes)
        
        mode = getattr(self, "_space_time_mode", "Current Frame")
        scene = bpy.context.scene
        start_t = end_t = scene.frame_current
        is_range = False
        
        if mode == "Time Slider Selection":
            if scene.use_preview_range:
                start_t = scene.frame_preview_start
                end_t = scene.frame_preview_end
                is_range = True
        elif mode == "Entire Time Slider":
            start_t = scene.frame_start
            end_t = scene.frame_end
            is_range = True

        bake_mode = getattr(self, "_space_bake_mode", "Existing Keys Only")
        
        if not is_range:
            frames = [start_t]
        elif bake_mode == "Bake on 2s":
            frames = list(range(int(start_t), int(end_t) + 1, 2))
        else:
            frames = list(range(int(start_t), int(end_t) + 1))

        # Safely capture matrices
        world_states = {} 
        for f in frames:
            if is_range: scene.frame_set(int(f))
            
            f_data = {}
            for node in target_nodes:
                b_obj = object_by_name(node)
                if not b_obj: continue
                if hasattr(b_obj, "matrix_world"):
                    f_data[node] = b_obj.matrix_world.copy()
                else:
                    f_data[node] = b_obj.id_data.matrix_world @ b_obj.matrix.copy()
            world_states[f] = f_data

        autokey = scene.tool_settings.use_keyframe_insert_auto

        for f in frames:
            if is_range: scene.frame_set(int(f))
            
            node_name, attr_name = attr_path.split(".", 1)
            hub_obj = object_by_name(node_name)
            if hub_obj:
                set_property(hub_obj, attr_name, value, keyframe=(is_range or autokey))
            
            bpy.context.view_layer.update()

            for node, mat in world_states[f].items():
                b_obj = object_by_name(node)
                if b_obj:
                    old_loc = b_obj.location.copy()
                    old_rot_e = getattr(b_obj, "rotation_euler", mathutils.Euler()).copy()
                    old_rot_q = getattr(b_obj, "rotation_quaternion", mathutils.Quaternion()).copy()
                    old_scale = b_obj.scale.copy()
                    
                    if hasattr(b_obj, "matrix_world"):
                        b_obj.matrix_world = mat
                    else:
                        b_obj.matrix = b_obj.id_data.matrix_world.inverted_safe() @ mat
                        
                    for i in range(3):
                        if getattr(b_obj, "lock_location", [False]*3)[i]: b_obj.location[i] = old_loc[i]
                        if getattr(b_obj, "lock_scale", [False]*3)[i]: b_obj.scale[i] = old_scale[i]
                    
                    if getattr(b_obj, "rotation_mode", 'QUATERNION') == 'QUATERNION':
                        if getattr(b_obj, "lock_rotations_4d", False) or getattr(b_obj, "lock_rotation", [False]*3)[0]:
                            b_obj.rotation_quaternion = old_rot_q
                    else:
                        for i in range(3):
                            if getattr(b_obj, "lock_rotation", [False]*3)[i]: b_obj.rotation_euler[i] = old_rot_e[i]

                    if is_range or autokey:
                        b_obj.keyframe_insert(data_path="location")
                        if getattr(b_obj, "rotation_mode", 'QUATERNION') == 'QUATERNION':
                            b_obj.keyframe_insert(data_path="rotation_quaternion")
                        else:
                            b_obj.keyframe_insert(data_path="rotation_euler")
        
        if is_range: scene.frame_set(int(start_t))
        bpy.context.view_layer.update()
        
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    with bpy.context.temp_override(window=window, area=area):
                        bpy.ops.ed.undo_push(message="ARTools_SpaceSwitch")
                    return

    def _mirror_plane(self, plane, is_anim=False):
        if is_anim:
            logic_anim.mirror_anim(namespace=self._get_ns(), mode="swap")
            return
            
        import mathutils
        nodes = selected_object_names()
        if not nodes: return
        
        s = [-1.0, 1.0, 1.0] if plane == "YZ" else ([1.0, -1.0, 1.0] if plane == "XZ" else [1.0, 1.0, -1.0])
        for node in nodes:
            b_obj = object_by_name(node)
            if b_obj:
                loc, rot, scale = b_obj.matrix_world.decompose()
                loc.x *= s[0]; loc.y *= s[1]; loc.z *= s[2]
                
                if plane == "YZ":
                    rot = mathutils.Quaternion((rot.w, rot.x, -rot.y, -rot.z))
                elif plane == "XZ":
                    rot = mathutils.Quaternion((rot.w, -rot.x, rot.y, -rot.z))
                else:
                    rot = mathutils.Quaternion((rot.w, -rot.x, -rot.y, rot.z))
                
                scale.x *= s[0]; scale.y *= s[1]; scale.z *= s[2]
                
                mat = mathutils.Matrix.LocRotScale(loc, rot, scale)
                b_obj.matrix_world = mat
                b_obj.keyframe_insert(data_path="location")
                b_obj.keyframe_insert(data_path="rotation_euler")
                b_obj.keyframe_insert(data_path="rotation_quaternion")
                
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    with bpy.context.temp_override(window=window, area=area):
                        bpy.ops.ed.undo_push(message="ARTools_MirrorPlane")
                    return

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
            self.btn_palette.setStyleSheet("background: transparent; border: none;")
        else:
            self.floating_palette.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
            self.floating_palette.show()
            
            # --- Native OS link to Blender ---
            # Owned directly off Blender's HWND (same owner as the AnimBar
            # itself), so it keeps working even if the AnimBar is closed
            # later, and only ever stays above Blender -- never above
            # unrelated applications.
            _attach_owner_hwnd(self.floating_palette, self._blender_hwnd)
            # -----------------------------------
            
            self.floating_palette.raise_()
            self.floating_palette.activateWindow()
            self.btn_palette.setStyleSheet("background: rgba(79, 184, 167, 100); border: 2px solid #4CAF50;")

    # ==========================================
    # WINDOW EVENT MANAGEMENT (MERGED & CYTHON-SAFE)
    # ==========================================
    def showEvent(self, event):
        QtWidgets.QWidget.showEvent(self, event)
        
        # --- Native OS window linking (Windows only) ---
        # Owning the AnimBar off Blender's HWND keeps it above Blender's
        # own window at all times, without ever floating above unrelated
        # applications the way Qt.WindowStaysOnTopHint does.
        _attach_owner_hwnd(self, self._blender_hwnd)

        # Load Window Position Memory
        try:
            from ARTools.preferences import PrefManager
            prefs = PrefManager()
            x = prefs.get("animbar_x")
            y = prefs.get("animbar_y")
            if x is not None and y is not None and x != -9999 and y != -9999:
                self.move(x, y)
        except Exception: 
            pass

    def closeEvent(self, event):
        # 1. Save Window Position Memory
        try:
            from ARTools.preferences import PrefManager
            prefs = PrefManager()
            prefs.set("animbar_x", self.x())
            prefs.set("animbar_y", self.y())
        except Exception: 
            pass
        
        # 2. Safely kill Timers
        if hasattr(self, "tab_poll_timer"):
            self.tab_poll_timer.stop()

        # 2b. Unhook the WinEvent hook
        if sys.platform == "win32" and getattr(self, "_win_event_hook", None):
            ctypes.windll.user32.UnhookWinEvent(self._win_event_hook)
            self._win_event_hook = None
        
        # 3. Close the Floating Palette so it doesn't linger orphaned
        if hasattr(self, "floating_palette"):
            self.floating_palette.close()
        
        # 4. Cython-safe parent call (No super!)
        QtWidgets.QWidget.closeEvent(self, event)