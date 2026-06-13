# ASEPicker/library/saver.py
from PySide6 import QtWidgets, QtGui, QtCore
IS_PYSIDE2 = False

from maya import cmds
import maya.mel as mel
import maya.api.OpenMaya as om
import maya.OpenMayaUI as omui
import os
import tempfile
import getpass
import shutil
import glob
from . import core
from ASEPicker.anim import logic_anim, clipboard
from ASEPicker import preferences

# Try to import shiboken for safety checks (Support Maya 2023-2026+)
try:
    from shiboken6 import isValid, wrapInstance
except ImportError:
    try:
        from shiboken2 import isValid, wrapInstance
    except ImportError:
        def isValid(widget):
            try:
                # Fallback for PySide/Qt if shiboken is completely missing
                import shiboken
                return shiboken.isValid(widget)
            except:
                # Absolute fallback: assume valid if we can't check
                return True
        wrapInstance = None

# GLOBAL VARIABLE TO KEEP WINDOW ALIVE
_saver_instance = None

# -------------------------------------------------------------------------
# CUSTOM WIDGET: HOVER PREVIEW LABEL
# -------------------------------------------------------------------------
class HoverPreviewLabel(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super(HoverPreviewLabel, self).__init__(parent)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setMouseTracking(True)
        
        self._frames = []
        self._idx = 0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._advance_frame)
        self._timer.setInterval(42)

    def set_sequence(self, pixmaps, fps=24):
        self.stop_playback()
        self._frames = pixmaps
        self._idx = 0
        if fps > 0: self._timer.setInterval(int(1000.0 / fps))
        if self._frames: self.set_frame(0)

    def set_placeholder(self):
        self.stop_playback()
        self._frames = []
        pix = QtGui.QPixmap(600, 450)
        pix.fill(QtGui.QColor("#111"))
        p = QtGui.QPainter(pix)
        p.setPen(QtGui.QPen(QtGui.QColor("#444")))
        font = p.font()
        font.setPointSize(20)
        p.setFont(font)
        p.drawText(pix.rect(), QtCore.Qt.AlignCenter, "No Capture")
        p.end()
        if isValid(self):
            self.setPixmap(pix)

    def set_frame(self, index):
        if not self._frames or not isValid(self): return
        pix = self._frames[index]
        scaled = pix.scaled(self.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.setPixmap(scaled)

    def enterEvent(self, event):
        if len(self._frames) > 1: self._timer.start()
        super(HoverPreviewLabel, self).enterEvent(event)

    def leaveEvent(self, event):
        self.stop_playback()
        if self._frames: self.set_frame(0)
        super(HoverPreviewLabel, self).leaveEvent(event)

    def _advance_frame(self):
        if not self._frames: return
        self._idx = (self._idx + 1) % len(self._frames)
        self.set_frame(self._idx)

    def stop_playback(self):
        self._timer.stop()

    def resizeEvent(self, event):
        if self._frames: self.set_frame(self._idx)
        super(HoverPreviewLabel, self).resizeEvent(event)

# -------------------------------------------------------------------------
# MAIN WINDOW
# -------------------------------------------------------------------------
class ModernSaver(QtWidgets.QDialog):
    def __init__(self, method="local", ns="", mode="anim", prefill=None, lock_method=True, parent=None):
        super(ModernSaver, self).__init__(parent)
        
        # --- LICENSE ENFORCEMENT FRONT DOOR ---
        from ASEPicker import security
        if hasattr(security, '__file__') and security.__file__.endswith(('.py', '.pyc', '.pyw')):
            import maya.cmds as cmds
            cmds.warning("[ASEPicker] Security tampering detected. Saver aborted.")
            self.deleteLater()
            return

        io_check = security.enforce_license(self)
        if not io_check or getattr(io_check, "_ase_secure_stamp", "") != "JAY_SHREE_KRISHNA_1986":
            import maya.cmds as cmds
            cmds.warning("[ASEPicker] License Invalid. Saver aborted.")
            self.deleteLater()
            return
        # --------------------------------------

        self.lock_method = lock_method

        # 1. High-DPI Scaling
        self.scale = self.get_dpi_scale()
        self.old_pos = None

        # 2. Window Setup
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground) 

        self.method = method
        self.target_ns = ns
        self.mode = mode
        self.prefill_data = prefill
        self.prefill_version = ""

        self.temp_dir = os.path.join(tempfile.gettempdir(), "ase_lib_temp_capture")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

        self.callback_id = None
        self.captured_sequence = False
        self.fps_val = 24.0
        self.current_capture_files = []
        self.using_old_preview = False
        
        # --- LIBRARY SETUP CHECK ---
        active_lib = preferences.Prefs.active_library()
        libs = preferences.Prefs.library_paths()
        
        # Force Create if Empty
        if active_lib in libs:
            path = libs[active_lib]
            if not os.path.exists(path):
                QtWidgets.QMessageBox.warning(self, "Path Missing", 
                    f"Library '{active_lib}' path is missing:\n{path}\n\nPlease select a valid library or create new.")
                preferences.Prefs.remove_library_path(active_lib)
                libs = preferences.Prefs.library_paths()
                active_lib = ""

        # Force Create if Empty
        if not libs:
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("Setup")
            msg.setText("No Library Found.\nPlease create one to save items.")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
            if msg.exec_() == QtWidgets.QMessageBox.Cancel:
                return 

            path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Library Folder")
            if path:
                name, ok = QtWidgets.QInputDialog.getText(self, "Library Name", "Enter Name:", text="MyLibrary")
                if ok and name:
                    preferences.Prefs.add_library_path(name, path)
                    preferences.Prefs.set_active_library(name)
                    libs = preferences.Prefs.library_paths()
                    active_lib = name
        
        if not libs:
            print("[ASEPicker] No library configured. Saver closed.")
            return

        # Fallback if active was deleted but others exist
        if not active_lib or active_lib not in libs:
            active_lib = sorted(list(libs.keys()))[0]
            preferences.Prefs.set_active_library(active_lib)

        # Assign instance variables required
        self.all_libs = libs
        self.active_lib_name = active_lib

        # Core Init
        root = libs.get(active_lib)
        self.library_core = core.LibraryCore(root)
        
        # 3. Initial Data
        self.current_path = "" 
        self.current_user = getpass.getuser()

        # 4. Build & Style
        self.build_ui()
        self.apply_styles()

        # 5. Apply Pre-filled data if replacing
        if self.prefill_data:
            self._apply_prefill()

        # 6. Initialize
        self.update_live_stats(None) 
        self.register_callback()

        self.set_placeholder_image()
        self.update_old_preview_button()

        self.resize(int(900 * self.scale), int(580 * self.scale))
        self.center_window()
        
        if self.mode == "pose":
            self.update_header()
            self.rb_range_timeline.setEnabled(False)
            self.rb_range_whole.setEnabled(False)
            self.rb_range_timeline.setChecked(False) 
            if hasattr(self, "lbl_range"): self.lbl_range.setText("Range: Current Frame")
        else:
            self.update_header()

    def get_dpi_scale(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if not screen: return 1.0
        dpi = screen.logicalDotsPerInch()
        return max(1.0, dpi / 96.0)

    def update_core_path(self, lib_name):
        path = self.all_libs.get(lib_name, "")
        root_arg = path if path else None
        self.library_core = core.LibraryCore(root_arg)

    def update_header(self):
        if hasattr(self, "header_label"):
            action = "Save Pose" if self.mode == "pose" else "Save Animation"
            method = "World" if self.method == "world" else "Local"
            self.header_label.setText(f"{action}  |  {self.active_lib_name}")
            self.header_label.setToolTip(f"{action} ({method})")

    # -------------------------------------------------------------------------
    # LIVE MAYA CONNECTION
    # -------------------------------------------------------------------------
    def register_callback(self):
        self.callback_id = om.MEventMessage.addEventCallback("SelectionChanged", self.update_live_stats)

    def closeEvent(self, event):
        if self.callback_id:
            om.MMessage.removeCallback(self.callback_id)
            self.callback_id = None
        super(ModernSaver, self).closeEvent(event)

    def _apply_prefill(self):
        data = self.prefill_data
        if not data: return
        
        # 1. Fill Name
        if "name" in data:
            self.inp_name.setText(data["name"])
        
        # 2. Fill Location (and update button text)
        if "path" in data:
            self.set_current_path(data["path"])
        
        self.prefill_version = data.get("version", "")
            
        # 3. Sync Method (Local/World)
        meth = data.get("method", self.method)
        if meth == "world": self.rb_world.setChecked(True)
        else: self.rb_local.setChecked(True)
        self.update_version_ui()
        self.update_old_preview_button()

    def update_live_stats(self, client_data):
        if not isValid(self):
            return

        # 1. Stats
        sel = cmds.ls(sl=True)
        count = len(sel) if sel else 0
        
        # 2. FPS
        fps_map = {"game": "15fps", "film": "24fps", "pal": "25fps", "ntsc": "30fps", "show": "48fps", "palf": "50fps", "ntscf": "60fps"}
        raw_fps = cmds.currentUnit(query=True, time=True)
        fps_label = fps_map.get(raw_fps, raw_fps)

        self.fps_val = 24.0
        if "fps" in fps_label:
             val_str = fps_label.replace("fps", "")
             if val_str.replace(".", "").isdigit():
                 self.fps_val = float(val_str)

        # 3. Time Range Logic (FIXED)
        start, end = 0, 0
        
        # Determine Mode: Timeline vs Whole
        use_timeline = True
        if hasattr(self, "rb_range_whole") and self.rb_range_whole.isChecked():
            use_timeline = False

        if use_timeline:
            # A. ACTIVE TIMELINE
            highlighted = False
            gPlayBackSlider = mel.eval('$tmpVar=$gPlayBackSlider')
            if cmds.timeControl(gPlayBackSlider, q=True, rangeVisible=True):
                highlight = cmds.timeControl(gPlayBackSlider, q=True, rangeArray=True)
                if highlight and (highlight[1] - highlight[0]) > 1:
                    start = highlight[0]
                    end = highlight[1] - 1
                    highlighted = True
            
            if not highlighted:
                # Use Playback Range
                start = cmds.playbackOptions(q=True, min=True)
                end = cmds.playbackOptions(q=True, max=True)
        else:
            # B. WHOLE ANIMATION (Selected Objects)
            key_times = []
            sel_nodes = cmds.ls(sl=True) or []
            
            for n in sel_nodes:
                times = cmds.keyframe(n, q=True, tc=True) or []
                if times: key_times.extend(times)
                
            if key_times:
                start = min(key_times)
                end = max(key_times)
            else:
                # Fallback if no keys on selection
                start = cmds.playbackOptions(q=True, min=True)
                end = cmds.playbackOptions(q=True, max=True)

        # Update Labels safely
        if hasattr(self, "lbl_sel_count") and isValid(self.lbl_sel_count): 
            self.lbl_sel_count.setText(f"Selected: {count}")
            
        if hasattr(self, "lbl_fps") and isValid(self.lbl_fps): 
            self.lbl_fps.setText(f"FPS: {fps_label}")
            
        if hasattr(self, "lbl_range") and isValid(self.lbl_range): 
            self.lbl_range.setText(f"Range: {int(start)} - {int(end)}")
        
        self.control_count = count
        self.start_frame = int(start)
        self.end_frame = int(end)

    # -------------------------------------------------------------------------
    # UI BUILD
    # -------------------------------------------------------------------------
    def build_ui(self):
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0,0,0,0)
        
        self.bg_frame = QtWidgets.QFrame()
        self.bg_frame.setObjectName("BgFrame")
        self.main_layout.addWidget(self.bg_frame)

        self.content_layout = QtWidgets.QHBoxLayout(self.bg_frame)
        self.content_layout.setContentsMargins(int(15*self.scale), int(15*self.scale), int(15*self.scale), int(15*self.scale))
        self.content_layout.setSpacing(int(20*self.scale))

        # --- LEFT ZONE: VIEWER (55%) ---
        self.left_container = QtWidgets.QWidget()
        self.left_layout = QtWidgets.QVBoxLayout(self.left_container)
        self.left_layout.setContentsMargins(0,0,0,0)
        self.left_layout.setSpacing(0)
        
        self.img_frame = QtWidgets.QFrame()
        self.img_frame.setObjectName("ImageContainer")
        self.img_frame_layout = QtWidgets.QVBoxLayout(self.img_frame)
        self.img_frame_layout.setContentsMargins(0,0,0,0)
        
        self.img_lbl = HoverPreviewLabel()
        self.img_frame_layout.addWidget(self.img_lbl)

        self.capture_mode_widget = QtWidgets.QWidget()
        self.capture_mode_widget.setFixedHeight(int(32 * self.scale))
        self.capture_mode_widget.setObjectName("CaptureModeBar")
        self.capture_mode_layout = QtWidgets.QHBoxLayout(self.capture_mode_widget)
        self.capture_mode_layout.setContentsMargins(int(10 * self.scale), 0, int(10 * self.scale), 0)
        self.capture_mode_layout.setSpacing(int(6 * self.scale))

        self.capture_view_group = QtWidgets.QButtonGroup(self)
        self.btn_view_active = QtWidgets.QPushButton("ACTIVE VIEW")
        self.btn_view_layout = QtWidgets.QPushButton("VIEW LAYOUT")
        for btn in (self.btn_view_active, self.btn_view_layout):
            btn.setObjectName("CaptureModeBtn")
            btn.setCheckable(True)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            self.capture_view_group.addButton(btn)
            self.capture_mode_layout.addWidget(btn)
        self.btn_view_active.setChecked(True)
        self.capture_mode_layout.addStretch(1)
        
        self.overlay_widget = QtWidgets.QWidget()
        self.overlay_widget.setFixedHeight(int(42 * self.scale))
        self.overlay_widget.setObjectName("OverlayBar")
        self.overlay_layout = QtWidgets.QHBoxLayout(self.overlay_widget)
        self.overlay_layout.setContentsMargins(int(10 * self.scale), 0, int(10 * self.scale), 0)
        self.overlay_layout.setSpacing(int(10 * self.scale))
        
        self.btn_capture = QtWidgets.QPushButton("CAPTURE")
        self.btn_capture.setObjectName("OverlayTextBtn")
        self.btn_capture.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_capture.clicked.connect(self.capture_snapshot)
        
        self.btn_ignore = QtWidgets.QPushButton("IGNORE")
        self.btn_ignore.setObjectName("OverlayTextBtn")
        self.btn_ignore.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_ignore.clicked.connect(self.ignore_snapshot)

        self.btn_use_old = QtWidgets.QPushButton("USE OLD")
        self.btn_use_old.setObjectName("OverlayTextBtn")
        self.btn_use_old.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_use_old.clicked.connect(self.use_old_snapshot)
        
        self.btn_cancel = QtWidgets.QPushButton("CANCEL")
        self.btn_cancel.setObjectName("OverlayTextBtn_Cancel")
        self.btn_cancel.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.close)

        self.overlay_layout.addWidget(self.btn_capture)
        self.overlay_layout.addWidget(self.btn_ignore)
        self.overlay_layout.addWidget(self.btn_use_old)
        self.overlay_layout.addWidget(self.btn_cancel)
        
        self.img_frame_layout.addWidget(self.capture_mode_widget)
        self.img_frame_layout.addWidget(self.overlay_widget)
        self.left_layout.addWidget(self.img_frame)
        self.content_layout.addWidget(self.left_container, 55)

        # --- RIGHT ZONE: INSPECTOR (45%) ---
        self.right_container = QtWidgets.QWidget()
        self.right_layout = QtWidgets.QVBoxLayout(self.right_container)
        self.right_layout.setContentsMargins(5, 5, 5, 5)
        self.right_layout.setSpacing(int(12 * self.scale))

        self.header_label = QtWidgets.QLabel("SAVE TO LIBRARY")
        self.header_label.setObjectName("HeaderLabel")
        self.header_label.setAlignment(QtCore.Qt.AlignCenter)
        self.right_layout.addWidget(self.header_label)

        grp_lib = QtWidgets.QGroupBox("Target Library")
        lay_lib = QtWidgets.QVBoxLayout(grp_lib)
        lay_lib.setContentsMargins(10, 15, 10, 10)
        self.combo_lib = QtWidgets.QComboBox()
        lib_keys = sorted(list(self.all_libs.keys()))
        self.combo_lib.addItems(lib_keys)
        idx = self.combo_lib.findText(self.active_lib_name)
        if idx >= 0: self.combo_lib.setCurrentIndex(idx)
        self.combo_lib.currentIndexChanged.connect(self.on_lib_change)
        lay_lib.addWidget(self.combo_lib)
        self.right_layout.addWidget(grp_lib)

        grp_name = QtWidgets.QGroupBox("Name")
        lay_name = QtWidgets.QVBoxLayout(grp_name)
        lay_name.setContentsMargins(10, 15, 10, 10)
        self.inp_name = QtWidgets.QLineEdit()
        self.inp_name.setPlaceholderText("Enter Item Name...")
        self.inp_name.textChanged.connect(self._on_name_changed)
        lay_name.addWidget(self.inp_name)
        self.right_layout.addWidget(grp_name)

        grp_version = QtWidgets.QGroupBox("Version")
        lay_version = QtWidgets.QVBoxLayout(grp_version)
        lay_version.setContentsMargins(10, 15, 10, 10)
        lay_version.setSpacing(6)
        self.combo_version_action = QtWidgets.QComboBox()
        self.combo_version_action.currentIndexChanged.connect(lambda *_: self.update_old_preview_button())
        self.lbl_version_hint = QtWidgets.QLabel("")
        self.lbl_version_hint.setWordWrap(True)
        self.lbl_version_hint.setStyleSheet("color: #8FA1AC;")
        lay_version.addWidget(self.combo_version_action)
        lay_version.addWidget(self.lbl_version_hint)
        self.right_layout.addWidget(grp_version)

        # --- LOCATION ---
        grp_cat = QtWidgets.QGroupBox("Location")
        lay_cat = QtWidgets.QHBoxLayout(grp_cat)
        lay_cat.setContentsMargins(10, 15, 10, 10)
        lay_cat.setSpacing(5)
        
        self.btn_path = QtWidgets.QPushButton("Root")
        self.btn_path.setObjectName("LocBtn")
        self.btn_path.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_path.clicked.connect(self.show_path_menu)
        
        self.btn_new = QtWidgets.QPushButton("+")
        self.btn_new.setObjectName("AddBtn")
        self.btn_new.setFixedSize(int(24*self.scale), int(24*self.scale))
        self.btn_new.setToolTip("Create New Folder")
        self.btn_new.clicked.connect(self.create_new_folder)
        
        self.btn_open_loc = QtWidgets.QPushButton()
        self.btn_open_loc.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirOpenIcon))
        self.btn_open_loc.setObjectName("OpenBtn")
        self.btn_open_loc.setFixedSize(int(24*self.scale), int(24*self.scale))
        self.btn_open_loc.setToolTip("Open Current Location in OS")
        self.btn_open_loc.clicked.connect(self.open_current_location)
        
        lay_cat.addWidget(self.btn_path)
        lay_cat.addWidget(self.btn_new)
        lay_cat.addWidget(self.btn_open_loc)
        self.right_layout.addWidget(grp_cat)

        # --- SETTINGS ---
        grp_set = QtWidgets.QGroupBox("Settings")
        lay_set = QtWidgets.QVBoxLayout(grp_set)
        lay_set.setContentsMargins(10, 15, 10, 10)
        lay_set.setSpacing(10)
        
        self.rb_group = QtWidgets.QButtonGroup(self)
        row_method = QtWidgets.QHBoxLayout()
        self.rb_local = QtWidgets.QRadioButton("Local Space")
        self.rb_world = QtWidgets.QRadioButton("World Space")
        self.rb_group.addButton(self.rb_local)
        self.rb_group.addButton(self.rb_world)
        if self.method == "world": self.rb_world.setChecked(True)
        else: self.rb_local.setChecked(True)
        self.rb_local.setEnabled(not self.lock_method)
        self.rb_world.setEnabled(not self.lock_method)
        row_method.addWidget(self.rb_local)
        row_method.addWidget(self.rb_world)
        lay_set.addLayout(row_method)
        
        lay_set.addWidget(self._label("Time Range:"))
        self.rb_range_group = QtWidgets.QButtonGroup(self)
        row_time = QtWidgets.QHBoxLayout()
        
        self.rb_range_timeline = QtWidgets.QRadioButton("Timeline")
        self.rb_range_timeline.setChecked(True)
        self.rb_range_timeline.toggled.connect(lambda *args: self.update_live_stats(None))
        
        self.rb_range_whole = QtWidgets.QRadioButton("Whole Animation")
        self.rb_range_whole.toggled.connect(lambda *args: self.update_live_stats(None))
        
        self.rb_range_group.addButton(self.rb_range_timeline)
        self.rb_range_group.addButton(self.rb_range_whole)
        
        row_time.addWidget(self.rb_range_timeline)
        row_time.addWidget(self.rb_range_whole)
        lay_set.addLayout(row_time)

        row_opts = QtWidgets.QHBoxLayout()
        row_opts.addWidget(self._label("Step:"))
        self.sb_step = QtWidgets.QSpinBox()
        self.sb_step.setRange(1, 10)
        self.sb_step.setValue(1)
        row_opts.addWidget(self.sb_step)
        
        row_opts.addWidget(self._label("Pad:"))
        self.sb_padding = QtWidgets.QSpinBox()
        self.sb_padding.setRange(1, 8)
        self.sb_padding.setValue(4)
        row_opts.addWidget(self.sb_padding)
        lay_set.addLayout(row_opts)
        self.right_layout.addWidget(grp_set)

        self.stats_frame = QtWidgets.QFrame()
        self.stats_frame.setObjectName("StatsFrame")
        self.stats_layout = QtWidgets.QVBoxLayout(self.stats_frame)
        self.stats_layout.setSpacing(2) 
        self.stats_layout.setContentsMargins(10, 10, 10, 10)
        self.stats_layout.setAlignment(QtCore.Qt.AlignVCenter)
        
        self.lbl_target_ns = QtWidgets.QLabel(f"Target: {self.target_ns if self.target_ns else '(Auto)'}")
        self.lbl_target_ns.setObjectName("LiveStat_Highlight") 
        self.lbl_sel_count = QtWidgets.QLabel("Selected: 0")
        self.lbl_sel_count.setObjectName("LiveStat")
        self.lbl_fps = QtWidgets.QLabel("FPS: 24fps")
        self.lbl_fps.setObjectName("LiveStat")
        self.lbl_range = QtWidgets.QLabel("Range: 1 - 100")
        self.lbl_range.setObjectName("LiveStat")
        
        self.stats_layout.addWidget(self.lbl_target_ns)
        self.stats_layout.addWidget(self.lbl_sel_count)
        self.stats_layout.addWidget(self.lbl_fps)
        self.stats_layout.addWidget(self.lbl_range)
        self.right_layout.addWidget(self.stats_frame, 1)
        
        row_note = QtWidgets.QHBoxLayout()
        row_note.addWidget(self._label("Note:"))
        self.inp_note = QtWidgets.QPlainTextEdit()
        self.inp_note.setPlaceholderText("...")
        self.inp_note.setFixedHeight(int(30 * self.scale))
        row_note.addWidget(self.inp_note)
        self.right_layout.addLayout(row_note)

        self.btn_save = QtWidgets.QPushButton("SAVE")
        self.btn_save.setObjectName("SaveBtn")
        self.btn_save.setFixedHeight(int(40 * self.scale))
        self.btn_save.clicked.connect(self.do_save)
        self.right_layout.addWidget(self.btn_save)

        self.content_layout.addWidget(self.right_container, 45)
        self.set_current_path("")

    def _label(self, text):
        lbl = QtWidgets.QLabel(text)
        f = lbl.font()
        f.setPointSize(int(9 * self.scale))
        lbl.setFont(f)
        return lbl

    def _on_name_changed(self, *_):
        self.update_version_ui()
        self.update_old_preview_button()

    def update_version_ui(self):
        if not hasattr(self, "combo_version_action"):
            return

        name = self.inp_name.text().strip() if hasattr(self, "inp_name") else ""
        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
        versions = self.library_core.list_item_versions(self.current_path, safe_name) if safe_name else []
        preferred = self.prefill_version if self.prefill_version in versions else (versions[-1] if versions else "V1")
        next_version = "V{0}".format(self.library_core._version_number(versions[-1]) + 1 if versions else 1)

        self.combo_version_action.blockSignals(True)
        self.combo_version_action.clear()

        if versions:
            self.combo_version_action.addItem("Replace {0}".format(preferred), ("replace", preferred))
            self.combo_version_action.addItem("Create {0}".format(next_version), ("new_version", next_version))
            self.lbl_version_hint.setText("Available: {0}".format(", ".join(versions)))
        else:
            self.combo_version_action.addItem("Create V1", ("replace", "V1"))
            self.lbl_version_hint.setText("New item. First save will create V1.")

        self.combo_version_action.blockSignals(False)

    # -------------------------------------------------------------------------
    # NEW PATH SYSTEM
    # -------------------------------------------------------------------------
    def set_current_path(self, path):
        self.current_path = path
        if path == "":
            self.btn_path.setText("Library Root")
        else:
            display = path.replace("/", " > ")
            if len(display) > 25: display = "..." + display[-22:]
            self.btn_path.setText(display)
        self.btn_path.setToolTip(path if path else "Library Root")
        self.update_version_ui()
        self.update_old_preview_button()

    def show_path_menu(self):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #2A2A2A; color: #EEE; border: 1px solid #555; }
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background: #444; }
        """)
        
        act_root = menu.addAction("Root")
        act_root.triggered.connect(lambda *_: self.set_current_path(""))
        menu.addSeparator()
        
        structure = self.library_core.get_structure()
        
        def _build(parent_menu, struct, current_rel_path=""):
            for key in sorted(struct.keys()):
                this_path = os.path.join(current_rel_path, key).replace("\\", "/")
                sub = parent_menu.addMenu(key)
                
                act_sel = sub.addAction(f"Select '{key}'")
                act_sel.triggered.connect(lambda *_, p=this_path: self.set_current_path(p))
                
                sub.addSeparator()
                _build(sub, struct[key], this_path)

        _build(menu, structure)
        menu.exec_(self.btn_path.mapToGlobal(QtCore.QPoint(0, self.btn_path.height())))

    def create_new_folder(self):
        parent = self.current_path if self.current_path else ""
        parent_display = parent if parent else "Root"
        
        name, ok = QtWidgets.QInputDialog.getText(self, "New Folder", f"Create folder inside '{parent_display}':")
        if ok and name:
            safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
            if not safe_name: return
            
            new_rel = os.path.join(parent, safe_name).replace("\\", "/")
            full = os.path.join(self.library_core.data_root, new_rel)
            
            if not os.path.exists(full):
                try:
                    os.makedirs(full)
                    self.set_current_path(new_rel)
                    cmds.inViewMessage(amg=f"Created: {safe_name}", pos="midCenter", fade=True)
                except: cmds.warning("Failed.")
            else:
                cmds.warning("Exists.")

    def open_current_location(self):
        path = os.path.join(self.library_core.data_root, self.current_path if self.current_path else "")
        if os.path.exists(path):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
        else:
            cmds.warning(f"Path not found: {path}")

    def on_lib_change(self):
        self.active_lib_name = self.combo_lib.currentText()
        self.update_core_path(self.active_lib_name)
        self.update_header()
        self.set_current_path("")
        self.update_version_ui()
        self.update_old_preview_button()

    def get_active_ns_fallback(self):
        sel = cmds.ls(sl=True)
        if not sel: return ""
        if ":" in sel[0]:
            return sel[0].rsplit(":", 1)[0]
        return ""

    def apply_styles(self):
        s = self.scale
        css = f"""
        #BgFrame {{
            background-color: #12171D;
            border-radius: {12*s}px;
            border: 1px solid #29323B;
        }}
        #ImageContainer {{
            background-color: #0F1419;
            border-radius: {8*s}px;
            border: 1px solid #24303A;
        }}
        #OverlayBar {{
            background-color: rgba(12, 17, 22, 225);
            border-bottom-left-radius: {8*s}px;
            border-bottom-right-radius: {8*s}px;
            border-top: 1px solid rgba(79, 184, 167, 65);
        }}
        #CaptureModeBar {{
            background-color: rgba(14, 20, 25, 235);
            border-top: 1px solid rgba(47, 59, 69, 160);
        }}
        QGroupBox {{
            background-color: #151D24;
            border: 1px solid #27333D;
            border-radius: {7*s}px;
            margin-top: {12*s}px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: {10*s}px;
            padding: 0 {4*s}px;
            color: #90A0AA;
            font-weight: bold;
            font-size: {10*s}px;
        }}
        QLabel {{
            color: #AEB8BE;
            font-family: Segoe UI, sans-serif;
        }}
        #HeaderLabel {{
            color: #F3F6F8;
            font-size: {15*s}px;
            font-weight: bold;
            margin-bottom: {4*s}px;
            letter-spacing: 0.4px;
        }}
        QLineEdit, QComboBox, QPlainTextEdit, QSpinBox {{
            background-color: #1A232B;
            border: 1px solid #2F3B45;
            border-radius: {5*s}px;
            color: #F1F5F7;
            padding: {4*s}px;
            min-height: {20*s}px;
            font-size: {10*s}px;
        }}
        QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus {{
            border: 1px solid #4FB8A7;
            background-color: #1E2830;
        }}
        QComboBox QAbstractItemView {{
            background-color: #1A232B;
            color: #F1F5F7;
            selection-background-color: #4FB8A7;
            min-width: {200*s}px;
            padding: {3*s}px;
            outline: none;
        }}
        QRadioButton {{
            font-size: {10*s}px;
            color: #BBC5CB;
            spacing: {6*s}px;
        }}
        QRadioButton:disabled {{ color: #6F7C85; }}
        #StatsFrame {{
            background-color: #131B21;
            border: 1px solid #24303A;
            border-radius: {8*s}px;
        }}
        #LiveStat {{
            color: #91A0AA;
            font-family: Consolas, monospace;
            font-size: {15*s}px;
            font-weight: bold;
        }}
        #LiveStat_Highlight {{
            color: #4FB8A7;
            font-family: Consolas, monospace;
            font-size: {17*s}px;
            font-weight: bold;
        }}
        #SaveBtn {{
            background-color: #2E8C74;
            color: white;
            font-size: {13*s}px;
            font-weight: bold;
            border-radius: {6*s}px;
            border: none;
        }}
        #SaveBtn:hover {{ background-color: #39A188; }}
        #OverlayTextBtn {{
            background-color: transparent;
            color: #E8EEF2;
            font-weight: bold;
            font-size: {11*s}px;
            border: none;
        }}
        #OverlayTextBtn:hover {{ color: #4FB8A7; }}
        #OverlayTextBtn:disabled {{ color: #6F7C85; }}
        #CaptureModeBtn {{
            background-color: #172129;
            color: #92A1AA;
            border: 1px solid #2E3B45;
            border-radius: {5*s}px;
            padding: {3*s}px {9*s}px;
            font-size: {9*s}px;
            font-weight: bold;
        }}
        #CaptureModeBtn:hover {{ border: 1px solid #4FB8A7; color: #D9E2E7; }}
        #CaptureModeBtn:checked {{
            background-color: #244D45;
            color: #FFFFFF;
            border: 1px solid #4FB8A7;
        }}
        #OverlayTextBtn_Cancel {{
            background-color: transparent;
            color: #E8EEF2;
            font-weight: bold;
            font-size: {11*s}px;
            border: none;
        }}
        #OverlayTextBtn_Cancel:hover {{ color: #E07267; }}
        #LocBtn {{
            text-align: left;
            padding-left: {10*s}px;
            font-weight: bold;
            background-color: #182129;
            border: 1px solid #2F3B45;
            border-radius: {5*s}px;
            color: #E5EDF2;
        }}
        #LocBtn:hover {{ border: 1px solid #51616D; background-color: #202B34; }}
        #AddBtn {{
            font-weight: bold;
            color: #9FD5C7;
            font-size: 14px;
            background-color: #182129;
            border: 1px solid #2F3B45;
            border-radius: {5*s}px;
        }}
        #AddBtn:hover {{ border: 1px solid #51616D; background-color: #202B34; }}
        #OpenBtn {{
            background-color: #182129;
            border: 1px solid #2F3B45;
            border-radius: {5*s}px;
        }}
        #OpenBtn:hover {{ border: 1px solid #51616D; background-color: #202B34; }}
        """
        self.setStyleSheet(css)

    def set_placeholder_image(self):
        self.img_lbl.set_placeholder()
        self.captured_sequence = False
        self.current_capture_files = []
        self.using_old_preview = False

    def _get_existing_item_path(self):
        name = self.inp_name.text().strip()
        if not name or not self.library_core or not self.library_core.data_root:
            return ""

        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
        if not safe_name:
            return ""

        versions = self.library_core.list_item_versions(self.current_path, safe_name)
        if not versions:
            return ""

        version_data = self.combo_version_action.currentData() if hasattr(self, "combo_version_action") else None
        version_mode = version_data[0] if version_data else "replace"
        version_name = version_data[1] if version_data else ""

        if version_mode == "replace" and version_name in versions:
            source_version = version_name
        elif self.prefill_version in versions:
            source_version = self.prefill_version
        else:
            source_version = versions[-1]

        return self.library_core.get_item_path(self.current_path, safe_name, source_version)

    def _get_existing_preview_files(self):
        item_path = self._get_existing_item_path()
        if not item_path or not os.path.exists(item_path):
            return [], False

        seq_dir = os.path.join(item_path, "preview_sequence")
        seq_files = sorted(glob.glob(os.path.join(seq_dir, "*.jpg")))
        if seq_files:
            return seq_files, True

        thumb_path = os.path.join(item_path, "thumbnail.jpg")
        if os.path.exists(thumb_path):
            return [thumb_path], False

        return [], False

    def update_old_preview_button(self):
        if not hasattr(self, "btn_use_old"):
            return

        files, _ = self._get_existing_preview_files()
        has_old = bool(files)
        self.btn_use_old.setEnabled(has_old)
        self.btn_use_old.setToolTip("Use existing thumbnail/preview" if has_old else "No existing thumbnail or preview found")

    def _capture_view_mode(self):
        if hasattr(self, "btn_view_layout") and self.btn_view_layout.isChecked():
            return "layout"
        return "active"

    def _main_layout_model_panels(self):
        if wrapInstance is None:
            return []

        panels = []
        for panel in cmds.getPanel(visiblePanels=True) or []:
            if cmds.getPanel(typeOf=panel) == "modelPanel":
                control = cmds.panel(panel, q=True, control=True)
                ptr = omui.MQtUtil.findControl(control)
                if ptr:
                    widget = wrapInstance(int(ptr), QtWidgets.QWidget)
                    if widget and widget.isVisible() and widget.window().objectName() == "MayaWindow":
                        if widget.width() > 8 and widget.height() > 8:
                            pos = widget.mapToGlobal(QtCore.QPoint(0, 0))
                            panels.append({
                                "panel": panel,
                                "x": pos.x(),
                                "y": pos.y(),
                                "w": widget.width(),
                                "h": widget.height()
                            })

        panels.sort(key=lambda item: (item["y"], item["x"]))
        return panels

    def _layout_output_rects(self, panels):
        min_x = min([p["x"] for p in panels])
        min_y = min([p["y"] for p in panels])
        max_x = max([p["x"] + p["w"] for p in panels])
        max_y = max([p["y"] + p["h"] for p in panels])
        source_w = max(1, max_x - min_x)
        source_h = max(1, max_y - min_y)
        target_w, target_h = 600, 450
        
        scale_x = float(target_w) / float(source_w)
        scale_y = float(target_h) / float(source_h)

        rects = []
        for panel in panels:
            x = int(round((panel["x"] - min_x) * scale_x))
            y = int(round((panel["y"] - min_y) * scale_y))
            end_x = int(round((panel["x"] + panel["w"] - min_x) * scale_x))
            end_y = int(round((panel["y"] + panel["h"] - min_y) * scale_y))
            
            rects.append(QtCore.QRect(x, y, max(16, end_x - x), max(16, end_y - y)))
        return rects

    def _playblast_panel_frame(self, panel_name, frame, rect, output_path):
        cmds.playblast(
            completeFilename=output_path,
            forceOverwrite=True,
            format="image",
            compression="jpg",
            quality=100,
            widthHeight=(max(16, rect.width()), max(16, rect.height())),
            startTime=frame,
            endTime=frame,
            showOrnaments=False,
            viewer=False,
            percent=100,
            offScreen=True,
            clearCache=True,
            editorPanelName=panel_name
        )

    def _compose_layout_frame(self, panels, rects, frame, output_path, temp_dir):
        target_w, target_h = 600, 450
        canvas = QtGui.QPixmap(target_w, target_h)
        canvas.fill(QtGui.QColor("#0F1419"))
        painter = QtGui.QPainter(canvas)

        for i, panel in enumerate(panels):
            panel_file = os.path.join(temp_dir, "panel_{0}.jpg".format(i))
            self._playblast_panel_frame(panel["panel"], frame, rects[i], panel_file)
            if os.path.exists(panel_file):
                painter.drawPixmap(rects[i], QtGui.QPixmap(panel_file))

        painter.end()
        canvas.save(output_path, "JPG", 100)

    def _capture_layout_sequence(self, filename, frames, padding):
        panels = self._main_layout_model_panels()
        if not panels:
            return False

        rects = self._layout_output_rects(panels)
        panel_temp = os.path.join(self.temp_dir, "_layout_panel_renders")
        if os.path.exists(panel_temp):
            shutil.rmtree(panel_temp)
        os.makedirs(panel_temp)

        current_frame = cmds.currentTime(q=True)
        for frame in frames:
            cmds.currentTime(frame, edit=True)
            cmds.refresh(force=True)
            QtWidgets.QApplication.processEvents()
            frame_name = str(int(round(frame))).zfill(padding)
            self._compose_layout_frame(panels, rects, frame, "{0}.{1}.jpg".format(filename, frame_name), panel_temp)
        cmds.currentTime(current_frame, edit=True)
        cmds.refresh(force=True)
        return True

    def capture_snapshot(self):
        self.update_live_stats(None)
        if os.path.exists(self.temp_dir): shutil.rmtree(self.temp_dir)
        os.makedirs(self.temp_dir)
        
        padding = self.sb_padding.value()
        step = self.sb_step.value()
        filename = os.path.join(self.temp_dir, "capture")
        
        cmds.refresh(cv=True)
        force_single = (self.mode == "pose")
        layout_capture = (self._capture_view_mode() == "layout")
        
        if layout_capture:
            if force_single:
                frames = [cmds.currentTime(q=True)]
                self.captured_sequence = False
            else:
                frames = list(range(self.start_frame, self.end_frame + 1, step))
                self.captured_sequence = True
            layout_capture = self._capture_layout_sequence(filename, frames, padding)

        if force_single and not layout_capture:
            current_frame = cmds.currentTime(q=True)
            cmds.playblast(filename=filename, forceOverwrite=True, format="image", compression="jpg", quality=100, widthHeight=(600, 450), startTime=current_frame, endTime=current_frame, framePadding=padding, showOrnaments=False, viewer=False, percent=100, offScreen=True, clearCache=True)
            self.captured_sequence = False
        elif not layout_capture:
            if step == 1:
                cmds.playblast(filename=filename, forceOverwrite=True, format="image", compression="jpg", quality=100, widthHeight=(600, 450), startTime=self.start_frame, endTime=self.end_frame, framePadding=padding, showOrnaments=False, viewer=False, percent=100, offScreen=True, clearCache=True)
            else:
                frames_to_cap = list(range(self.start_frame, self.end_frame + 1, step))
                cmds.playblast(filename=filename, forceOverwrite=True, format="image", compression="jpg", quality=100, widthHeight=(600, 450), frame=frames_to_cap, framePadding=padding, showOrnaments=False, viewer=False, percent=100, offScreen=True, clearCache=True)
            self.captured_sequence = True

        pixmaps = []
        files = sorted(glob.glob(os.path.join(self.temp_dir, "*.jpg")))
        for f in files: pixmaps.append(QtGui.QPixmap(f))
        self.current_capture_files = files
        self.using_old_preview = False
        
        if force_single: self.img_lbl.set_sequence(pixmaps, fps=0)
        else: self.img_lbl.set_sequence(pixmaps, fps=self.fps_val)

    def ignore_snapshot(self):
        self.set_placeholder_image()

    def use_old_snapshot(self):
        files, is_sequence = self._get_existing_preview_files()
        if not files:
            self.update_old_preview_button()
            return

        pixmaps = [QtGui.QPixmap(f) for f in files if os.path.exists(f)]
        if not pixmaps:
            self.update_old_preview_button()
            return

        self.current_capture_files = []
        self.using_old_preview = True
        self.captured_sequence = False
        if is_sequence and len(pixmaps) > 1:
            self.img_lbl.set_sequence(pixmaps, fps=self.fps_val)
        else:
            self.img_lbl.set_sequence(pixmaps, fps=0)

    def center_window(self):
        screen = QtGui.QGuiApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) / 2, (screen.height() - size.height()) / 2)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_pos = QtGui.QCursor.pos()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = QtGui.QCursor.pos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = QtGui.QCursor.pos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def do_save(self):
        name = self.inp_name.text().strip()
        if not name:
            cmds.warning("Name is required!")
            return
        
        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
        existing_versions = self.library_core.list_item_versions(self.current_path, safe_name)
        version_data = self.combo_version_action.currentData() if hasattr(self, "combo_version_action") else ("replace", "V1")
        version_mode = version_data[0] if version_data else "replace"
        version_name = version_data[1] if version_data else "V1"

        if version_mode == "replace" and version_name in existing_versions:
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("Overwrite?")
            msg.setText(f"Replace {version_name} for '{safe_name}'?")
            msg.setInformativeText("Existing version data will be updated.")
            msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            msg.setStyleSheet("background-color: #222; color: #EEE;")
            if msg.exec_() != QtWidgets.QMessageBox.Yes:
                return
        
        sel = cmds.ls(sl=True)
        if not sel:
            cmds.warning("Select items.")
            return

        method = "world" if self.rb_world.isChecked() else "local"
        save_data = {}
        meta_type = "anim"
        
        if self.mode == "pose":
            from .. import logic_pose
            meta_type = "pose"
            save_data = logic_pose.get_pose_data(global_space=(method=="world"))
        else:
            try:
                self.update_live_stats(None)
                custom_range = (self.start_frame, self.end_frame)
                sel_nodes = cmds.ls(sl=True, long=True) or []
                if sel_nodes:
                    for node in sel_nodes:
                        if not cmds.keyframe(node, q=True, keyframeCount=True):
                            attrs = cmds.listAttr(node, keyable=True) or []
                            for attr in attrs:
                                try:
                                    cmds.setKeyframe(f"{node}.{attr}", time=self.start_frame)
                                    cmds.setKeyframe(f"{node}.{attr}", time=self.end_frame)
                                except: pass
                logic_anim.copy_anim(global_space=(method=="world"), custom_range=custom_range)
                save_data = clipboard.load_data("anim_global" if method == "world" else "anim_local")
            except Exception as e:
                cmds.warning(f"Anim Error: {e}")
                return

        if not save_data: return

        meta = {
            "type": meta_type,
            "method": method,
            "start": self.start_frame if meta_type == "anim" else cmds.currentTime(q=True),
            "end": self.end_frame if meta_type == "anim" else cmds.currentTime(q=True),
            "fps": self.fps_val,
            "padding": self.sb_padding.value(),
            "step": self.sb_step.value(),
            "controls": getattr(self, "control_count", len(save_data.keys())),
            "user": self.current_user,
            "note": self.inp_note.toPlainText(),
            "source_ns": self.target_ns if self.target_ns else self.get_active_ns_fallback()
        }

        old_item_path = self._get_existing_item_path()
        old_files = []
        old_is_sequence = False
        old_thumb = ""
        if self.using_old_preview:
            old_files, old_is_sequence = self._get_existing_preview_files()
            if old_item_path:
                old_thumb = os.path.join(old_item_path, "thumbnail.jpg")
                if not os.path.exists(old_thumb):
                    old_thumb = old_files[0] if old_files else ""

        files = list(self.current_capture_files)
        thumb_path = files[0] if files else (old_thumb or None)
        
        item_path = self.library_core.save_item(
            name,
            self.current_path,
            save_data,
            meta,
            thumb_path,
            None,
            version_mode=version_mode,
            version=version_name
        )
        
        if self.captured_sequence and item_path and files:
            seq_dir = os.path.join(item_path, "preview_sequence")
            if os.path.exists(seq_dir):
                try: shutil.rmtree(seq_dir)
                except: pass
            
            if not os.path.exists(seq_dir): 
                os.makedirs(seq_dir)

            for f in files: shutil.copy2(f, seq_dir)
        elif self.using_old_preview and item_path and old_files and old_is_sequence:
            seq_dir = os.path.join(item_path, "preview_sequence")
            if os.path.exists(seq_dir):
                try: shutil.rmtree(seq_dir)
                except: pass

            if not os.path.exists(seq_dir):
                os.makedirs(seq_dir)

            for f in old_files:
                shutil.copy2(f, seq_dir)
        
        cmds.inViewMessage(amg=f"Saved {meta_type.capitalize()}: {name} ({version_name})", pos="midCenter", fade=True)
        
        from . import browser
        if browser._browser_instance:
            try:
                if browser._browser_instance.isVisible(): browser._browser_instance.reload_lib()
            except: pass 
            
        self.close()

def _get_maya_window():
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == "MayaWindow":
            return widget
    return None

def LibrarySaver(method="local", ns="", mode="anim", prefill=None, lock_method=True):
    global _saver_instance
    if _saver_instance:
        try:
            _saver_instance.close()
            _saver_instance.deleteLater()
        except: pass
    
    _saver_instance = ModernSaver(method=method, ns=ns, mode=mode, prefill=prefill, lock_method=lock_method, parent=_get_maya_window())
    _saver_instance.show()
    return _saver_instance