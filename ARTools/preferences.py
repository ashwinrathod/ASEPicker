# ARTools/preferences.py
import os, json, pickle
from functools import partial

from PySide6 import QtWidgets, QtGui, QtCore

class PrefManager:
    """Singleton Manager that handles saving/loading JSON to the external Data folder."""
    _instance = None
    
    def __new__(cls):
        if not cls._instance:
            cls._instance = super(PrefManager, cls).__new__(cls)
            cls._instance._init_paths()
            cls._instance.load()
        return cls._instance

    def _init_paths(self):
        self.module_dir = os.path.dirname(os.path.abspath(__file__))
        # Store ONE LEVEL UP in "ARTools_Data"
        self.data_dir = os.path.join(os.path.dirname(self.module_dir), "ARTools_Data")
        self.prefs_file = os.path.join(self.data_dir, "preferences.json")
        self.preset_file = os.path.join(self.data_dir, "presets.art")
        
        if not os.path.exists(self.data_dir):
            try: os.makedirs(self.data_dir)
            except: pass

        self.defaults = {
            "startup_mode": "Pose",
            "startup_bg_lock": False,
            "startup_hier": False,
            "grid_visible": False,
            "grid_scale": 50.0,
            "poly_handle_size": 8.0,
            
            "win_remember_size": True,
            "win_lock_size": False,
            "win_w": 600,
            "win_h": 800,
            "win_x": -9999,
            "win_y": -9999,
            "animbar_x": -9999,
            "animbar_y": -9999,
            "editor_w": 380,
            "editor_h": 600,
            "editor_x": -9999,
            "editor_y": -9999,
            
            "path_picker": "",
            "path_icons": os.path.join(self.module_dir, "icons").replace("\\", "/"),
            "path_templates": os.path.join(self.module_dir, "templates").replace("\\", "/"),
            "io_auto_save": False,
            "io_show_name": True,
            "io_show_ns": True,
            
            # --- LIBRARY PREFERENCES ---
            "lib_columns": 4,
            "lib_ns_mode": "selection",
            "lib_thumb_detail": True,
            "lib_geometry": None,
            "lib_last_paste": "Replace",
            "lib_last_path": "",
            "lib_paths": {},
            "lib_active": "",
            "lib_last_tag": "All Tags",
            "lib_favorites": [],
            "lib_recent": [],
            
            # --- HOTKEYS ---
            "hk_prefs": "Ctrl+P",
            "hk_reset": "R",
            "hk_focus": "F",
            "hk_pose": "P",
            "hk_edit": "O",
            "hk_editor": "E",
            "hk_hier_add": "",
            "hk_hier_rem": "",
            "hk_animbar": "",
            "hk_library": "",
            "mirror_use_canvas": False,

            # --- NEW: Menu Styling Engine ---
            "menu_bg": "#2b2b2b",
            "menu_text": "#dfdfdf",
            "menu_hl": "#5285a6",
            "menu_border": "#555555",
            "menu_thick": 1,
            "menu_rad": 6,
            "menu_pad": 4,

            # --- Master Mirror Dictionary ---
            "custom_mirror_pairs": []
        }
        self.data = self.defaults.copy()

    def get_mirror_pairs_list(self):
        """Combines the hardcoded defaults with the artist's custom list."""
        # 1. Hardcoded Defaults (Always Active)
        defaults = [(".L", ".R"), ("L_", "R_"), ("_L", "_R"), (".l", ".r"), ("l_", "r_"), ("_l", "_r"), ("Left", "Right"), ("left", "right"), ("lf", "rt")]
        
        # 2. Artist Custom Pairs
        custom = self.get("custom_mirror_pairs") or []
        valid_custom = [(c[0], c[1]) for c in custom if isinstance(c, (list, tuple)) and len(c) == 2]
        
        return defaults + valid_custom
    
    def load(self):
        if os.path.exists(self.prefs_file):
            try:
                with open(self.prefs_file, 'r') as f:
                    self.data.update(json.load(f))
            except Exception as e: print(f"ARTools: Pref load error - {e}")

    def save(self):
        try:
            with open(self.prefs_file, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e: print(f"ARTools: Pref save error - {e}")

    def get(self, key): return self.data.get(key, self.defaults.get(key))
    def set(self, key, val): 
        self.data[key] = val
        self.save()

    def load_user_presets(self):
        if os.path.exists(self.preset_file) and os.path.getsize(self.preset_file) > 0:
            with open(self.preset_file, "rb") as f:
                return pickle.load(f)
        return {"visuals": [], "commands": [], "shapes": []}

    def save_user_presets(self, data):
        with open(self.preset_file, "wb") as f:
            pickle.dump(data, f)

class PrefsWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(PrefsWindow, self).__init__(parent)
        self.setWindowTitle("ARTools Preferences")
        self.resize(550, 450)
        self.prefs = PrefManager()
        
        main_layout = QtWidgets.QHBoxLayout(self)
        
        self.nav_list = QtWidgets.QListWidget()
        self.nav_list.setFixedWidth(120)
        self.nav_list.addItems(["General", "File I/O", "Library", "Mirrors", "Theme", "Shortcuts"])
        self.nav_list.setStyleSheet("""
            QListWidget { background: #2A2A2A; border: 1px solid #111; }
            QListWidget::item { padding: 10px; color: #E0E0E0; border-bottom: 1px solid #333; }
            QListWidget::item:selected { background: #4CAF50; color: white; font-weight: bold; }
        """)
        
        self.stack = QtWidgets.QStackedWidget()
        main_layout.addWidget(self.nav_list)
        main_layout.addWidget(self.stack)
        
        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        
        self._build_general_tab()
        self._build_io_tab()
        self._build_library_tab()
        self._build_mirrors_tab()
        self._build_theme_tab()
        self._build_shortcuts_tab()
        
        self.nav_list.setCurrentRow(0)

    def _build_general_tab(self):
        w = QtWidgets.QWidget(); lay = QtWidgets.QVBoxLayout(w)
        
        g_start = QtWidgets.QGroupBox("Startup"); l_start = QtWidgets.QFormLayout(g_start)
        self.c_mode = QtWidgets.QComboBox(); self.c_mode.addItems(["Pose", "Edit"])
        self.c_mode.setCurrentText(self.prefs.get("startup_mode"))
        self.chk_bg = QtWidgets.QCheckBox(); self.chk_bg.setChecked(self.prefs.get("startup_bg_lock"))
        self.chk_hier = QtWidgets.QCheckBox(); self.chk_hier.setChecked(self.prefs.get("startup_hier"))
        l_start.addRow("Default Mode:", self.c_mode)
        l_start.addRow("Lock Backgrounds:", self.chk_bg)
        l_start.addRow("Hierarchy Visibility:", self.chk_hier)
        
        g_grid = QtWidgets.QGroupBox("Canvas Display Settings"); l_grid = QtWidgets.QFormLayout(g_grid)
        self.chk_grid = QtWidgets.QCheckBox(); self.chk_grid.setChecked(self.prefs.get("grid_visible"))
        self.sp_grid = QtWidgets.QDoubleSpinBox(); self.sp_grid.setRange(10, 500)
        self.sp_grid.setValue(self.prefs.get("grid_scale"))
        self.sp_handle = QtWidgets.QDoubleSpinBox(); self.sp_handle.setRange(2.0, 30.0)
        self.sp_handle.setValue(self.prefs.get("poly_handle_size"))
        self.chk_mir = QtWidgets.QCheckBox(); self.chk_mir.setChecked(self.prefs.get("mirror_use_canvas"))
        
        l_grid.addRow("Grid On:", self.chk_grid)
        l_grid.addRow("Grid Scale:", self.sp_grid)
        l_grid.addRow("Polygon Handle Size:", self.sp_handle)
        l_grid.addRow("Mirror Uses Canvas Center:", self.chk_mir)
        
        g_win = QtWidgets.QGroupBox("Window"); l_win = QtWidgets.QFormLayout(g_win)
        self.chk_win_rem = QtWidgets.QCheckBox("Restore on restart"); self.chk_win_rem.setChecked(self.prefs.get("win_remember_size"))
        self.chk_win_lck = QtWidgets.QCheckBox("Lock Default Size"); self.chk_win_lck.setChecked(self.prefs.get("win_lock_size"))
        
        size_lay = QtWidgets.QHBoxLayout()
        self.sp_win_w = QtWidgets.QSpinBox(); self.sp_win_w.setRange(300, 4000); self.sp_win_w.setValue(self.prefs.get("win_w"))
        self.sp_win_h = QtWidgets.QSpinBox(); self.sp_win_h.setRange(300, 4000); self.sp_win_h.setValue(self.prefs.get("win_h"))
        size_lay.addWidget(QtWidgets.QLabel("W:")); size_lay.addWidget(self.sp_win_w)
        size_lay.addWidget(QtWidgets.QLabel("H:")); size_lay.addWidget(self.sp_win_h)
        size_lay.addWidget(self.chk_win_lck)
        
        l_win.addRow("Remember Size:", self.chk_win_rem)
        l_win.addRow("Default Size:", size_lay)
        
        g_path = QtWidgets.QGroupBox("Paths"); l_path = QtWidgets.QFormLayout(g_path)
        self.txt_p_pick = QtWidgets.QLineEdit(self.prefs.get("path_picker"))
        self.btn_p_pick = QtWidgets.QPushButton("Browse"); self.btn_p_pick.clicked.connect(lambda: self._browse(self.txt_p_pick))
        p1 = QtWidgets.QHBoxLayout(); p1.addWidget(self.txt_p_pick); p1.addWidget(self.btn_p_pick)
        
        self.txt_p_icon = QtWidgets.QLineEdit(self.prefs.get("path_icons"))
        self.btn_p_icon = QtWidgets.QPushButton("Browse"); self.btn_p_icon.clicked.connect(lambda: self._browse(self.txt_p_icon))
        p2 = QtWidgets.QHBoxLayout(); p2.addWidget(self.txt_p_icon); p2.addWidget(self.btn_p_icon)
        
        self.txt_p_temp = QtWidgets.QLineEdit(self.prefs.get("path_templates"))
        self.btn_p_temp = QtWidgets.QPushButton("Browse"); self.btn_p_temp.clicked.connect(lambda: self._browse(self.txt_p_temp))
        p3 = QtWidgets.QHBoxLayout(); p3.addWidget(self.txt_p_temp); p3.addWidget(self.btn_p_temp)
        
        l_path.addRow("Default Picker Folder:", p1)
        l_path.addRow("Icon Folder:", p2)
        l_path.addRow("Templates Folder:", p3)
        
        lay.addWidget(g_start); lay.addWidget(g_grid); lay.addWidget(g_win); lay.addWidget(g_path); lay.addStretch()
        self.stack.addWidget(w)
        
        self.c_mode.currentTextChanged.connect(partial(self.prefs.set, "startup_mode"))
        self.chk_bg.toggled.connect(partial(self.prefs.set, "startup_bg_lock"))
        self.chk_hier.toggled.connect(partial(self.prefs.set, "startup_hier"))
        self.chk_grid.toggled.connect(partial(self.prefs.set, "grid_visible"))
        self.sp_grid.valueChanged.connect(partial(self.prefs.set, "grid_scale"))
        self.chk_win_rem.toggled.connect(partial(self.prefs.set, "win_remember_size"))
        self.chk_win_lck.toggled.connect(partial(self.prefs.set, "win_lock_size"))
        self.sp_win_w.valueChanged.connect(partial(self.prefs.set, "win_w"))
        self.sp_win_h.valueChanged.connect(partial(self.prefs.set, "win_h"))
        self.txt_p_pick.textChanged.connect(partial(self.prefs.set, "path_picker"))
        self.txt_p_icon.textChanged.connect(partial(self.prefs.set, "path_icons"))
        self.txt_p_temp.textChanged.connect(partial(self.prefs.set, "path_templates"))
        self.sp_handle.valueChanged.connect(self._live_update_handle)
        self.chk_mir.toggled.connect(partial(self.prefs.set, "mirror_use_canvas"))

    def _live_update_handle(self, val):
        self.prefs.set("poly_handle_size", val)
        if self.parent():
            for view in self.parent().findChildren(QtWidgets.QGraphicsView):
                view.viewport().update()

    def _browse(self, line_edit):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder", line_edit.text())
        if folder: line_edit.setText(folder)

    def _build_io_tab(self):
        w = QtWidgets.QWidget(); lay = QtWidgets.QVBoxLayout(w)
        g_io = QtWidgets.QGroupBox("Saving & UI"); l_io = QtWidgets.QVBoxLayout(g_io)
        
        self.chk_io_save = QtWidgets.QCheckBox("Auto-Save picker into Maya Scene on close")
        self.chk_io_save.setChecked(self.prefs.get("io_auto_save"))
        self.chk_io_name = QtWidgets.QCheckBox("Show current character (Tab) name on Titlebar")
        self.chk_io_name.setChecked(self.prefs.get("io_show_name"))
        self.chk_io_ns = QtWidgets.QCheckBox("Show current Namespace on Titlebar")
        self.chk_io_ns.setChecked(self.prefs.get("io_show_ns"))
        
        l_io.addWidget(self.chk_io_save); l_io.addWidget(self.chk_io_name); l_io.addWidget(self.chk_io_ns)
        lay.addWidget(g_io); lay.addStretch()
        self.stack.addWidget(w)
        
        self.chk_io_save.toggled.connect(partial(self.prefs.set, "io_auto_save"))
        self.chk_io_name.toggled.connect(partial(self.prefs.set, "io_show_name"))
        self.chk_io_ns.toggled.connect(partial(self.prefs.set, "io_show_ns"))

    def _build_library_tab(self):
        w = QtWidgets.QWidget(); lay = QtWidgets.QVBoxLayout(w)
        
        g_disp = QtWidgets.QGroupBox("Library Display & Defaults")
        l_disp = QtWidgets.QFormLayout(g_disp)
        
        self.sp_cols = QtWidgets.QSpinBox()
        self.sp_cols.setRange(1, 10)
        self.sp_cols.setValue(self.prefs.get("lib_columns"))
        self.sp_cols.valueChanged.connect(partial(self.prefs.set, "lib_columns"))
        
        self.c_ns = QtWidgets.QComboBox()
        self.c_ns.addItems(["picker", "selection", "file"])
        self.c_ns.setCurrentText(self.prefs.get("lib_ns_mode"))
        self.c_ns.currentTextChanged.connect(partial(self.prefs.set, "lib_ns_mode"))
        
        self.c_paste = QtWidgets.QComboBox()
        self.c_paste.addItems(["Replace", "Replace All", "Insert", "Merge"])
        self.c_paste.setCurrentText(self.prefs.get("lib_last_paste"))
        self.c_paste.currentTextChanged.connect(partial(self.prefs.set, "lib_last_paste"))
        
        self.chk_thumb = QtWidgets.QCheckBox("Show Thumbnail Details Overlay")
        self.chk_thumb.setChecked(self.prefs.get("lib_thumb_detail"))
        self.chk_thumb.toggled.connect(partial(self.prefs.set, "lib_thumb_detail"))

        l_disp.addRow("Default Grid Columns:", self.sp_cols)
        l_disp.addRow("Default Namespace Source:", self.c_ns)
        l_disp.addRow("Default Paste Method:", self.c_paste)
        l_disp.addRow("", self.chk_thumb)
        
        lay.addWidget(g_disp)
        lay.addStretch()
        self.stack.addWidget(w)

    def _build_mirrors_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        
        # --- 1. Default Pairs: Clean, minimal, read-only display ---
        g_def = QtWidgets.QGroupBox("Default Internal Pairs (System Reserved)")
        l_def = QtWidgets.QVBoxLayout(g_def)
        
        # Using a single-line label instead of a giant TableWidget for defaults
        lbl_def = QtWidgets.QLabel("L_ ↔ R_,  _L ↔ _R,  .L ↔ .R, .l ↔ .r, l_ ↔ r_,  _l ↔ _r,  Left ↔ Right,  left ↔ right,  lf ↔ rt")
        lbl_def.setStyleSheet("color: #888; font-style: italic; padding: 5px;")
        lbl_def.setWordWrap(True)
        l_def.addWidget(lbl_def)
        
        # --- 2. Custom Pairs: Editable Table ---
        g_cust = QtWidgets.QGroupBox("Custom Naming Pairs")
        l_cust = QtWidgets.QVBoxLayout(g_cust)
        
        self.tbl_cust = QtWidgets.QTableWidget(0, 2)
        self.tbl_cust.setMinimumHeight(350)
        self.tbl_cust.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.tbl_cust.setHorizontalHeaderLabels(["Left Side", "Right Side"])
        self.tbl_cust.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.tbl_cust.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        
        btn_lay = QtWidgets.QHBoxLayout()
        self.btn_add_mir = QtWidgets.QPushButton("➕ Add Custom Pair")
        self.btn_rem_mir = QtWidgets.QPushButton("➖ Remove Selected")
        self.btn_add_mir.setStyleSheet("background-color: #2e5c3a;")
        self.btn_rem_mir.setStyleSheet("background-color: #6b2e2e;")
        btn_lay.addWidget(self.btn_add_mir)
        btn_lay.addWidget(self.btn_rem_mir)
        
        l_cust.addWidget(self.tbl_cust)
        l_cust.addLayout(btn_lay)
        
        self.btn_add_mir.clicked.connect(self._add_custom_mirror)
        self.btn_rem_mir.clicked.connect(self._rem_custom_mirror)
        self.tbl_cust.itemChanged.connect(self._save_custom_mirrors)
        
        # Populate Custom Pairs
        custom_mirrors = self.prefs.get("custom_mirror_pairs") or []
        self.tbl_cust.blockSignals(True)
        self.tbl_cust.setRowCount(len(custom_mirrors))
        for r, pair in enumerate(custom_mirrors):
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                self.tbl_cust.setItem(r, 0, QtWidgets.QTableWidgetItem(str(pair[0])))
                self.tbl_cust.setItem(r, 1, QtWidgets.QTableWidgetItem(str(pair[1])))
        self.tbl_cust.blockSignals(False)
        
        lay.addWidget(g_def)
        lay.addWidget(g_cust)
        lay.addStretch() # Ensure table fills space correctly
        
        self.stack.addWidget(w)
    
    def _add_custom_mirror(self):
        self.tbl_cust.blockSignals(True)
        r = self.tbl_cust.rowCount()
        self.tbl_cust.insertRow(r)
        self.tbl_cust.setItem(r, 0, QtWidgets.QTableWidgetItem("New_L_Name"))
        self.tbl_cust.setItem(r, 1, QtWidgets.QTableWidgetItem("New_R_Name"))
        self.tbl_cust.blockSignals(False)
        self._save_custom_mirrors()
        
    def _rem_custom_mirror(self):
        rows = set(item.row() for item in self.tbl_cust.selectedItems())
        self.tbl_cust.blockSignals(True)
        for r in sorted(rows, reverse=True):
            self.tbl_cust.removeRow(r)
        self.tbl_cust.blockSignals(False)
        self._save_custom_mirrors()
        
    def _save_custom_mirrors(self, *args):
        pairs = []
        for r in range(self.tbl_cust.rowCount()):
            it_l = self.tbl_cust.item(r, 0)
            it_r = self.tbl_cust.item(r, 1)
            l_str = it_l.text().strip() if it_l else ""
            r_str = it_r.text().strip() if it_r else ""
            if l_str and r_str:
                pairs.append([l_str, r_str])
        self.prefs.set("custom_mirror_pairs", pairs)
    
    def _build_theme_tab(self):
        w = QtWidgets.QWidget(); lay = QtWidgets.QVBoxLayout(w)
        g_menu = QtWidgets.QGroupBox("Context Menu Styling"); l_menu = QtWidgets.QFormLayout(g_menu)
        
        # Helper to make color pickers fast and clean
        def _color_row(label, key):
            btn = QtWidgets.QPushButton()
            btn.setFixedSize(60, 22)
            btn.setStyleSheet(f"background-color: {self.prefs.get(key)}; border: 1px solid #777; border-radius: 4px;")
            def _pick():
                col = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.prefs.get(key)), self)
                if col.isValid():
                    self.prefs.set(key, col.name())
                    btn.setStyleSheet(f"background-color: {col.name()}; border: 1px solid #777; border-radius: 4px;")
            btn.clicked.connect(_pick)
            l_menu.addRow(label, btn)

        _color_row("Background Color:", "menu_bg")
        _color_row("Text Color:", "menu_text")
        _color_row("Hover Highlight Color:", "menu_hl")
        _color_row("Edge / Border Color:", "menu_border")
        
        self.sp_m_thk = QtWidgets.QSpinBox(); self.sp_m_thk.setRange(0, 5); self.sp_m_thk.setValue(self.prefs.get("menu_thick"))
        self.sp_m_rad = QtWidgets.QSpinBox(); self.sp_m_rad.setRange(0, 20); self.sp_m_rad.setValue(self.prefs.get("menu_rad"))
        self.sp_m_pad = QtWidgets.QSpinBox(); self.sp_m_pad.setRange(2, 16); self.sp_m_pad.setValue(self.prefs.get("menu_pad"))
        
        self.sp_m_thk.valueChanged.connect(partial(self.prefs.set, "menu_thick"))
        self.sp_m_rad.valueChanged.connect(partial(self.prefs.set, "menu_rad"))
        self.sp_m_pad.valueChanged.connect(partial(self.prefs.set, "menu_pad"))
        
        l_menu.addRow("Edge Thickness (px):", self.sp_m_thk)
        l_menu.addRow("Corner Radius (px):", self.sp_m_rad)
        l_menu.addRow("Item Vertical Padding:", self.sp_m_pad)
        
        lay.addWidget(g_menu); lay.addStretch()
        self.stack.addWidget(w)
    
    def _build_shortcuts_tab(self):
        w = QtWidgets.QWidget(); lay = QtWidgets.QVBoxLayout(w)
        g_hk = QtWidgets.QGroupBox("Hotkeys (Click box and press keys)"); l_hk = QtWidgets.QFormLayout(g_hk)
        
        def _add_hk(label, key):
            edit = QtWidgets.QKeySequenceEdit(QtGui.QKeySequence(self.prefs.get(key)))
            edit.keySequenceChanged.connect(lambda seq, k=key: self.prefs.set(k, seq.toString()))
            l_hk.addRow(label, edit)

        _add_hk("Preferences Window:", "hk_prefs")
        _add_hk("Toggle Anim Bar:", "hk_animbar")
        _add_hk("Toggle Library Browser:", "hk_library")
        _add_hk("Reset View:", "hk_reset")
        _add_hk("Focus View:", "hk_focus")
        _add_hk("Toggle Pose Mode:", "hk_pose")
        _add_hk("Toggle Edit Mode:", "hk_edit")
        _add_hk("Open Editor Panel:", "hk_editor")
        _add_hk("Hierarchy Connect:", "hk_hier_add")
        _add_hk("Hierarchy Remove:", "hk_hier_rem")
        
        lay.addWidget(g_hk); lay.addStretch()
        self.stack.addWidget(w)

# =========================================================================
# THE BRIDGE: Exposes PrefManager data to static calls from library tools
# =========================================================================
class Prefs:
    @staticmethod
    def library_columns(): return PrefManager().get("lib_columns")
    @staticmethod
    def set_library_columns(v): PrefManager().set("lib_columns", v)

    @staticmethod
    def library_namespace_mode(): return PrefManager().get("lib_ns_mode")
    @staticmethod
    def set_library_namespace_mode(v): PrefManager().set("lib_ns_mode", v)

    @staticmethod
    def library_thumbnail_detail(): return PrefManager().get("lib_thumb_detail")
    @staticmethod
    def set_library_thumbnail_detail(v): PrefManager().set("lib_thumb_detail", v)

    @staticmethod
    def library_geometry(): return PrefManager().get("lib_geometry")
    @staticmethod
    def set_library_geometry(v): PrefManager().set("lib_geometry", v)

    @staticmethod
    def remember_window_size(): return PrefManager().get("win_remember_size")

    @staticmethod
    def library_last_paste_method(): return PrefManager().get("lib_last_paste")
    @staticmethod
    def set_library_last_paste_method(v): PrefManager().set("lib_last_paste", v)

    @staticmethod
    def library_last_path(): return PrefManager().get("lib_last_path")
    @staticmethod
    def set_library_last_path(v): PrefManager().set("lib_last_path", v)

    @staticmethod
    def library_paths(): return PrefManager().get("lib_paths") or {}
    @staticmethod
    def set_library_paths(v): PrefManager().set("lib_paths", v)
    
    @staticmethod
    def add_library_path(name, path):
        paths = dict(PrefManager().get("lib_paths") or {})
        paths[name] = path
        PrefManager().set("lib_paths", paths)
        
    @staticmethod
    def remove_library_path(name):
        paths = dict(PrefManager().get("lib_paths") or {})
        if name in paths:
            del paths[name]
            PrefManager().set("lib_paths", paths)
            
    @staticmethod
    def rename_library(old, new):
        paths = dict(PrefManager().get("lib_paths") or {})
        if old in paths and new not in paths:
            paths[new] = paths.pop(old)
            PrefManager().set("lib_paths", paths)
            if PrefManager().get("lib_active") == old:
                PrefManager().set("lib_active", new)
            return True
        return False

    @staticmethod
    def active_library(): return PrefManager().get("lib_active")
    @staticmethod
    def set_active_library(v): PrefManager().set("lib_active", v)

    @staticmethod
    def library_last_tag(): return PrefManager().get("lib_last_tag")
    @staticmethod
    def set_library_last_tag(v): PrefManager().set("lib_last_tag", v)

    @staticmethod
    def library_favorites(): return PrefManager().get("lib_favorites") or []
    @staticmethod
    def set_library_favorites(v): PrefManager().set("lib_favorites", v)

    @staticmethod
    def animbar_last_tweener(): return PrefManager().get("animbar_last_tweener") or "Tweener"
    @staticmethod
    def set_animbar_last_tweener(v): PrefManager().set("animbar_last_tweener", v)

    @staticmethod
    def library_recent_items(): return PrefManager().get("lib_recent") or []
    @staticmethod
    def set_library_recent_items(v): PrefManager().set("lib_recent", v)

    @staticmethod
    def get_menu_style_sheet():
        p = PrefManager()
        bg = p.get("menu_bg"); txt = p.get("menu_text"); hl = p.get("menu_hl")
        bord = p.get("menu_border"); thk = p.get("menu_thick"); rad = p.get("menu_rad")
        pad = p.get("menu_pad")
        
        return f"""
            QMenu {{ background: {bg}; color: {txt}; border: {thk}px solid {bord}; border-radius: {rad}px; padding: 4px; }}
            QMenu::item {{ padding: {pad}px 24px {pad}px 28px; border-radius: {max(0, rad-2)}px; margin: 1px 4px; }}
            QMenu::item:selected {{ background: {hl}; color: white; }}
            QMenu::separator {{ height: 1px; background: {bord}; margin: 4px 12px; }}
            QMenu::indicator {{ width: 14px; height: 14px; left: 8px; }}
            QMenu::indicator:non-exclusive:checked {{ image: none; background: {hl}; border: 1px solid white; border-radius: 3px; }}
            QMenu::indicator:non-exclusive:unchecked {{ image: none; background: transparent; border: 1px solid {bord}; border-radius: 3px; }}
        """

    @staticmethod
    def create_styled_menu(parent=None):
        """Universal Factory to generate perfectly styled, borderless rounded menus!"""
        from PySide6 import QtWidgets, QtCore
        menu = QtWidgets.QMenu(parent)
        menu.setWindowFlags(menu.windowFlags() | QtCore.Qt.FramelessWindowHint | QtCore.Qt.NoDropShadowWindowHint | QtCore.Qt.Popup)
        menu.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        menu.setStyleSheet(Prefs.get_menu_style_sheet())
        return menu