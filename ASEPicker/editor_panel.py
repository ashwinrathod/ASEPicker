# ASEPicker/editor_panel.py
try:
    from PySide2 import QtWidgets, QtGui, QtCore
except ImportError:
    from PySide6 import QtWidgets, QtGui, QtCore

from .alignment_panel import AlignmentPanel
from .script_editor import ScriptEditorWidget

class ColorPickerWidget(QtWidgets.QWidget):
    colorChanged = QtCore.Signal(str)
    
    def __init__(self, color="#ffffffff", parent=None):
        super(ColorPickerWidget, self).__init__(parent)
        self.color_hex = color
        self._is_updating = False
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn = QtWidgets.QPushButton()
        self.btn.setFixedSize(30, 22)
        self.btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn.clicked.connect(self.pick_color)
        
        self.hex_edit = QtWidgets.QLineEdit()
        self.hex_edit.setMaxLength(9) 
        self.hex_edit.setFixedWidth(70)
        self.hex_edit.textEdited.connect(self.manual_hex_edit)
        
        self.alpha_spin = QtWidgets.QSpinBox()
        self.alpha_spin.setRange(0, 10)
        self.alpha_spin.setToolTip("Alpha (0 = Transparent, 10 = Solid)")
        self.alpha_spin.valueChanged.connect(self.alpha_changed)
        
        layout.addWidget(self.btn)
        layout.addWidget(self.hex_edit)
        layout.addWidget(QtWidgets.QLabel("A:"))
        layout.addWidget(self.alpha_spin)
        layout.addStretch()
        
        self.update_ui()
        
    def alpha_changed(self, val):
        if self._is_updating: return
        c = QtGui.QColor(self.color_hex)
        alpha_int = int((val / 10.0) * 255)
        c.setAlpha(alpha_int)
        self.set_color(c.name(QtGui.QColor.HexArgb))
        self.colorChanged.emit(self.color_hex)

    def pick_color(self):
        opts = QtWidgets.QColorDialog.ShowAlphaChannel | QtWidgets.QColorDialog.DontUseNativeDialog
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.color_hex), self, "Select Color", opts)
        if color.isValid():
            self.set_color(color.name(QtGui.QColor.HexArgb))
            self.colorChanged.emit(self.color_hex)
            
    def manual_hex_edit(self, text):
        if self._is_updating: return
        if QtGui.QColor(text).isValid():
            self.set_color(text, update_hex=False)
            self.colorChanged.emit(self.color_hex)
            
    def update_ui(self):
        self._is_updating = True
        c = QtGui.QColor(self.color_hex)
        rgba_css = f"rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()})"
        self.btn.setStyleSheet(f"background-color: {rgba_css}; border: 1px solid #777; border-radius: 3px;")
        
        self.hex_edit.setText(self.color_hex)
        alpha_val = int(round((c.alpha() / 255.0) * 10))
        self.alpha_spin.setValue(alpha_val)
        self._is_updating = False
        
    def text(self): return self.color_hex
    def setText(self, hx): self.set_color(hx)
        
    def set_color(self, hx, update_hex=True):
        if isinstance(hx, QtGui.QColor):
            hx = hx.name(QtGui.QColor.HexArgb)
        if not isinstance(hx, str):
            hx = str(hx)
            
        if not hx.startswith("#"): hx = "#" + hx
        self.color_hex = hx
        
        self._is_updating = True
        c = QtGui.QColor(self.color_hex)
        rgba_css = f"rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()})"
        self.btn.setStyleSheet(f"background-color: {rgba_css}; border: 1px solid #777; border-radius: 3px;")
        
        if update_hex: self.hex_edit.setText(self.color_hex)
        
        alpha_val = int(round((c.alpha() / 255.0) * 10))
        self.alpha_spin.setValue(alpha_val)
        self._is_updating = False

class PresetButton(QtWidgets.QPushButton):
    def __init__(self, data, preset_type, editor):
        super(PresetButton, self).__init__()
        self.data = data
        self.p_type = preset_type
        self.editor = editor
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context)
        
        if preset_type == "visual":
            self.setText("")
            self.setToolTip("Visual Preset (Hover to preview states)")
            self._apply_style("normal")
            self._timer = QtCore.QTimer(self)
            self._timer.timeout.connect(self._cycle_visual)
            self._state_idx = 0
            
        elif preset_type == "command":
            self.setText(data.get("label", "Cmd"))
            self.setStyleSheet("QPushButton { background-color: #333; border: 1px solid #555; color: #eee; border-radius: 4px; padding: 4px; font-weight: bold; } QPushButton:hover { background-color: #444; }")
            
        elif preset_type == "shape":
            self.setText("") 
            shape_name = data.get("shape", "Rectangle")
            self.setToolTip(f"Shape: {shape_name}")
            self.setFlat(True)
            self.setStyleSheet("QPushButton { background-color: #262626; border: 1px solid #3a3a3a; border-radius: 4px; } QPushButton:hover { background-color: #333; border-color: #555; }")

        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Preferred if preset_type in ["visual", "shape"] else QtWidgets.QSizePolicy.Fixed)
        if preset_type in ["visual", "shape"]: self.setMinimumWidth(36)
        else: self.setMinimumHeight(28)

    def resizeEvent(self, event):
        QtWidgets.QPushButton.resizeEvent(self, event)
        if self.p_type in ["visual", "shape"]:
            w = self.width()
            if self.minimumHeight() != w or self.maximumHeight() != w:
                self.setFixedHeight(w)

    def paintEvent(self, event):
        QtWidgets.QPushButton.paintEvent(self, event)
        if self.p_type == "shape":
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            rect = QtCore.QRectF(self.rect()).adjusted(6, 6, -6, -6)
            shape_name = str(self.data.get("shape", "")).lower()
            
            w, h = float(self.data.get("w", 100)), float(self.data.get("h", 100))
            if w <= 0: w = 1.0
            if h <= 0: h = 1.0
            
            # --- MODERN 0.1.0 POLYGON BEZIER RENDER ---
            if "poly" in shape_name and "path_data" in self.data:
                pts = self.data["path_data"]
                if pts:
                    path = QtGui.QPainterPath()
                    path.moveTo(pts[0]["p"][0], pts[0]["p"][1])
                    n = len(pts)
                    for i in range(n):
                        nxt = pts[(i + 1) % n]
                        cp1 = QtCore.QPointF(pts[i]["p"][0] + pts[i]["out"][0], pts[i]["p"][1] + pts[i]["out"][1])
                        cp2 = QtCore.QPointF(nxt["p"][0] + nxt["in"][0], nxt["p"][1] + nxt["in"][1])
                        ep = QtCore.QPointF(nxt["p"][0], nxt["p"][1])
                        path.cubicTo(cp1, cp2, ep)
                    path.closeSubpath()
                    
                    br = path.boundingRect()
                    scale = min(rect.width() / br.width(), rect.height() / br.height()) if br.width() > 0 else 1.0
                    painter.translate(self.rect().center())
                    painter.scale(scale * 0.8, scale * 0.8)
                    painter.translate(-br.center())
                    
                    painter.setPen(QtGui.QPen(QtGui.QColor("#ddd"), 2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
                    painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 30)))
                    painter.drawPath(path)
                    return
            
            # --- STANDARD SHAPES ---
            painter.setPen(QtGui.QPen(QtGui.QColor("#ddd"), 2))
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 30)))
            
            if "circle" in shape_name: painter.drawEllipse(rect)
            elif "round" in shape_name:
                sx = rect.width() / w; sy = rect.height() / h; s = min(sx, sy)
                tl, tr, bl, br = [float(self.data.get(k, 0))*s for k in ["rad_tl", "rad_tr", "rad_bl", "rad_br"]]
                path = QtGui.QPainterPath()
                path.moveTo(rect.left() + tl, rect.top()); path.lineTo(rect.right() - tr, rect.top()); path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + tr); path.lineTo(rect.right(), rect.bottom() - br); path.quadTo(rect.right(), rect.bottom(), rect.right() - br, rect.bottom()); path.lineTo(rect.left() + bl, rect.bottom()); path.quadTo(rect.left(), rect.bottom(), rect.left(), rect.bottom() - bl); path.lineTo(rect.left(), rect.top() + tl); path.quadTo(rect.left(), rect.top(), rect.left() + tl, rect.top()); path.closeSubpath()
                painter.drawPath(path)
            elif "slider" in shape_name:
                painter.drawLine(rect.left(), rect.center().y(), rect.right(), rect.center().y())
                painter.setBrush(QtGui.QColor("#ddd"))
                painter.drawRoundedRect(QtCore.QRectF(rect.center().x()-5, rect.top()+2, 10, rect.height()-4), 2, 2)
            elif "pose" in shape_name:
                painter.drawRect(rect); painter.setBrush(QtCore.Qt.NoBrush); painter.drawRect(rect.adjusted(3,3,-3,-3))
            else:
                painter.drawRect(rect)
                if "text" in shape_name:
                    painter.setPen(QtGui.QPen(QtGui.QColor("#ddd"), 1)); painter.drawText(rect, QtCore.Qt.AlignCenter, "T")

    def enterEvent(self, event):
        if self.p_type == "visual": self._timer.start(600)
        QtWidgets.QPushButton.enterEvent(self, event)

    def leaveEvent(self, event):
        if self.p_type == "visual": self._timer.stop(); self._state_idx = 0; self._apply_style("normal")
        QtWidgets.QPushButton.leaveEvent(self, event)

    def _cycle_visual(self):
        self._state_idx = (self._state_idx + 1) % 3
        self._apply_style(["normal", "hover", "press"][self._state_idx])

    def _apply_style(self, state="normal"):
        if self.p_type != "visual": return
        d = self.data
        def _c(key, df):
            val = d.get(key, {})
            return val.get(state, val.get("normal", df)) if isinstance(val, dict) else (val if val else df)
        
        bg = _c("bg", "#3c6e71")
        border = _c("edge_color", "#111111")
        text = _c("text_color", "#ffffff")
        th_data = d.get("edge_thickness", {})
        th = th_data.get(state, th_data.get("normal", 1)) if isinstance(th_data, dict) else 1
        vis = d.get("edge_visible", True)
        border_css = f"{th}px solid {border}" if vis else "none"
        self.setStyleSheet(f"QPushButton {{ background-color: {bg}; color: {text}; border: {border_css}; border-radius: 4px; padding: 4px; }}")

    def _on_context(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu { background: #2b2b2b; color: #dfdfdf; border: 1px solid #555; } QMenu::item:selected { background: #5285a6; }")
        if self.p_type == "command": menu.addAction("Rename Preset", self._rename)
        menu.addAction("Update from Current Selection", lambda: self.editor.update_preset(self.p_type, self.data))
        menu.addSeparator()
        menu.addAction("Delete Preset", lambda: self.editor.delete_preset(self.p_type, self.data))
        menu.exec_(self.mapToGlobal(pos))

    def _rename(self):
        new, ok = QtWidgets.QInputDialog.getText(self, "Rename", "Name:", text=self.data.get("label", ""))
        if ok and new:
            self.data["label"] = new
            self.setText(new)
            self.editor.save_presets()

class EditorPanel(QtWidgets.QWidget):
    controls_modified = QtCore.Signal(str)
    alignment_requested = QtCore.Signal(str)
    attribute_modified = QtCore.Signal(str)
    pose_action_requested = QtCore.Signal(str)
    checkbox_action_requested = QtCore.Signal(str, str)
    image_action_requested = QtCore.Signal(str)
    
    def _build_cb_state(self, state):
        grp = QtWidgets.QGroupBox(f"{state} State")
        lay = QtWidgets.QVBoxLayout(grp)
        
        form = QtWidgets.QFormLayout()
        txt = QtWidgets.QLineEdit(); col = ColorPickerWidget()
        form.addRow("Text Override:", txt); form.addRow("Normal Color:", col)
        lay.addLayout(form)
        
        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # 1. Attributes (Controls removed entirely)
        aw = QtWidgets.QWidget(); al = QtWidgets.QVBoxLayout(aw); al.setContentsMargins(0,0,0,0)
        al.addWidget(QtWidgets.QLabel("Attributes:"))
        a_lst = QtWidgets.QListWidget()
        a_btn = QtWidgets.QHBoxLayout()
        a_add = QtWidgets.QPushButton("Add"); a_add.setStyleSheet("background-color: #2e5c3a;")
        a_rem = QtWidgets.QPushButton("Rem"); a_rem.setStyleSheet("background-color: #6b2e2e;")
        a_clr = QtWidgets.QPushButton("Clr"); a_clr.setStyleSheet("background-color: #6b2e2e;")
        a_btn.addWidget(a_add); a_btn.addWidget(a_rem); a_btn.addWidget(a_clr)
        al.addWidget(a_lst); al.addLayout(a_btn); split.addWidget(aw)

        # 2. Shapes
        sw = QtWidgets.QWidget(); sl = QtWidgets.QVBoxLayout(sw); sl.setContentsMargins(0,0,0,0)
        sl.addWidget(QtWidgets.QLabel("Shapes:"))
        s_lst = QtWidgets.QListWidget()
        s_btn = QtWidgets.QHBoxLayout()
        s_add = QtWidgets.QPushButton("Add"); s_add.setStyleSheet("background-color: #2e5c3a;")
        s_rem = QtWidgets.QPushButton("Rem"); s_rem.setStyleSheet("background-color: #6b2e2e;")
        s_clr = QtWidgets.QPushButton("Clr"); s_clr.setStyleSheet("background-color: #6b2e2e;")
        s_btn.addWidget(s_add); s_btn.addWidget(s_rem); s_btn.addWidget(s_clr)
        sl.addWidget(s_lst); sl.addLayout(s_btn); split.addWidget(sw)
        
        lay.addWidget(split)
        
        # --- NEW: Command Section ---
        cmd_grp = QtWidgets.QGroupBox(f"{state} Command Execution")
        cmd_lay = QtWidgets.QVBoxLayout(cmd_grp)
        
        c_type_lay = QtWidgets.QHBoxLayout()
        c_type_lay.addWidget(QtWidgets.QLabel("Type:"))
        cmd_type = QtWidgets.QComboBox()
        cmd_type.addItems(["python", "mel"])
        c_type_lay.addWidget(cmd_type)
        c_type_lay.addStretch()
        
        btn_expand = QtWidgets.QPushButton("⛶ Expand")
        btn_expand.setToolTip("Open script in a larger standalone window")
        c_type_lay.addWidget(btn_expand)
        
        cmd_txt = QtWidgets.QTextEdit()
        cmd_txt.setMaximumHeight(60)
        
        cmd_lay.addLayout(c_type_lay)
        cmd_lay.addWidget(cmd_txt)
        lay.addWidget(cmd_grp)
        
        return grp, txt, col, a_lst, a_add, a_rem, a_clr, s_lst, s_add, s_rem, s_clr, cmd_type, cmd_txt, btn_expand

    def __init__(self, parent=None):
        super(EditorPanel, self).__init__(parent)
        self.setWindowTitle("ASEPicker Live Editor")
        self.setMinimumWidth(380)
        
        self.target_items = []
        self._is_populating = False
        self._undo_timer = QtCore.QTimer()
        self._undo_timer.setSingleShot(True)
        self._undo_timer.setInterval(600)
        self._undo_timer.timeout.connect(self._push_undo_from_editor)
        
        self._setup_ui()
        self._bind_live_events()
        
        # THE FIX: Restore Size & Position AFTER the UI is fully built!
        from .preferences import PrefManager
        prefs = PrefManager()
        self.resize(prefs.get("editor_w"), prefs.get("editor_h"))
        ex, ey = prefs.get("editor_x"), prefs.get("editor_y")
        
        if ex != -9999 and ey != -9999:
            self.move(ex, ey)

    def get_scale(self):
        return 1.0
    
    def _setup_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)

        # 1. ALIGNMENT PANEL (SVG Toolbar)
        try:
            self.alignment_panel = AlignmentPanel(parent=self)
            self.alignment_panel.action_requested.connect(self.alignment_requested.emit)
            self.main_layout.addWidget(self.alignment_panel)
        except Exception as e:
            print(f"ASEPicker: Could not load AlignmentPanel - {e}")

        # 2. SHAPE ID FIELD
        id_lay = QtWidgets.QHBoxLayout()
        id_lay.addWidget(QtWidgets.QLabel("Shape ID:"))
        self.shape_id_edit = QtWidgets.QLineEdit()
        self.shape_id_edit.setReadOnly(True)
        self.shape_id_edit.setStyleSheet("background-color: #1a1a1a; color: #777; border: 1px solid #333; border-radius: 3px;")
        id_lay.addWidget(self.shape_id_edit)
        self.main_layout.addLayout(id_lay)

        # BLENDER-STYLE SIDEBAR
        self.tab_container = QtWidgets.QWidget()
        tab_layout = QtWidgets.QHBoxLayout(self.tab_container)
        tab_layout.setContentsMargins(0, 5, 0, 0)
        
        self.nav_list = QtWidgets.QListWidget()
        self.nav_list.setFixedWidth(80)
        self.nav_list.setStyleSheet("""
            QListWidget { background: #2A2A2A; border: 1px solid #111; border-radius: 4px; }
            QListWidget::item { padding: 8px 5px; color: #E0E0E0; border-bottom: 1px solid #333; }
            QListWidget::item:selected { background: #5285a6; color: white; font-weight: bold; }
        """)
        
        self.stack = QtWidgets.QStackedWidget()
        tab_layout.addWidget(self.nav_list)
        tab_layout.addWidget(self.stack)
        self.main_layout.addWidget(self.tab_container)
        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)

        # ===============================================
        # PRESETS TAB
        # ===============================================
        t_preset = QtWidgets.QWidget(); l_preset = QtWidgets.QVBoxLayout(t_preset)
        l_preset.setContentsMargins(4, 4, 4, 4)
        
        self.preset_tabs = QtWidgets.QTabWidget()
        
        # 1. Visual Page
        self.p_vis_sc = QtWidgets.QScrollArea(); self.p_vis_sc.setWidgetResizable(True); self.p_vis_sc.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.p_vis_w = QtWidgets.QWidget(); self.p_vis_l = QtWidgets.QGridLayout(self.p_vis_w); self.p_vis_l.setAlignment(QtCore.Qt.AlignTop)
        self.p_vis_sc.setWidget(self.p_vis_w); self.preset_tabs.addTab(self.p_vis_sc, "Visuals")
        
        # 2. Command/Script Page
        self.p_cmd_sc = QtWidgets.QScrollArea(); self.p_cmd_sc.setWidgetResizable(True); self.p_cmd_sc.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.p_cmd_w = QtWidgets.QWidget(); self.p_cmd_l = QtWidgets.QGridLayout(self.p_cmd_w); self.p_cmd_l.setAlignment(QtCore.Qt.AlignTop)
        self.p_cmd_sc.setWidget(self.p_cmd_w); self.preset_tabs.addTab(self.p_cmd_sc, "Scripts")
        
        # 3. Shape Page
        self.p_shp_sc = QtWidgets.QScrollArea(); self.p_shp_sc.setWidgetResizable(True); self.p_shp_sc.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.p_shp_w = QtWidgets.QWidget(); self.p_shp_l = QtWidgets.QGridLayout(self.p_shp_w); self.p_shp_l.setAlignment(QtCore.Qt.AlignTop)
        self.p_shp_sc.setWidget(self.p_shp_w); self.preset_tabs.addTab(self.p_shp_sc, "Shapes")
        
        l_preset.addWidget(self.preset_tabs)
        
        h_pbtn = QtWidgets.QHBoxLayout()
        btn_add_vis = QtWidgets.QPushButton("+ Visual"); btn_add_cmd = QtWidgets.QPushButton("+ Script"); btn_add_shp = QtWidgets.QPushButton("+ Shape")
        
        btn_add_vis.clicked.connect(lambda: self.add_preset("visual"))
        btn_add_cmd.clicked.connect(lambda: self.add_preset("command"))
        btn_add_shp.clicked.connect(lambda: self.add_preset("shape"))
        
        h_pbtn.addWidget(btn_add_vis); h_pbtn.addWidget(btn_add_cmd); h_pbtn.addWidget(btn_add_shp)
        l_preset.addLayout(h_pbtn)
        
        self._add_page("PRESETS", t_preset)
        if hasattr(self, "refresh_presets"): self.refresh_presets()

        # ===============================================
        # 1. THE MEGA-TAB (Geo, Colors, Edges, Text)
        # ===============================================
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        t_mega = QtWidgets.QWidget(); l_mega = QtWidgets.QVBoxLayout(t_mega)

        # GEO SECTION
        g_geo = QtWidgets.QGroupBox("Geometry"); l_geo = QtWidgets.QFormLayout(g_geo)
        self.pos_x = QtWidgets.QDoubleSpinBox(); self.pos_x.setRange(-9999, 9999)
        self.pos_y = QtWidgets.QDoubleSpinBox(); self.pos_y.setRange(-9999, 9999)
        self.geo_w = QtWidgets.QDoubleSpinBox(); self.geo_w.setRange(1, 9999)
        self.geo_h = QtWidgets.QDoubleSpinBox(); self.geo_h.setRange(1, 9999)
        self.geo_r = QtWidgets.QDoubleSpinBox(); self.geo_r.setRange(-360, 360)
        l_geo.addRow("Pos X / Y:", self._row(self.pos_x, self.pos_y))
        l_geo.addRow("Size W / H:", self._row(self.geo_w, self.geo_h))
        l_geo.addRow("Rotation:", self.geo_r)
        l_mega.addWidget(g_geo)

        # COLORS SECTION
        g_col = QtWidgets.QGroupBox("Colors"); l_col = QtWidgets.QFormLayout(g_col)
        self.bg_n = ColorPickerWidget(); self.bg_h = ColorPickerWidget(); self.bg_p = ColorPickerWidget()
        l_col.addRow("Normal:", self.bg_n); l_col.addRow("Hover:", self.bg_h); l_col.addRow("Press:", self.bg_p)
        l_mega.addWidget(g_col)

        # TEXT SECTION
        g_txt = QtWidgets.QGroupBox("Typography"); l_txt = QtWidgets.QFormLayout(g_txt)
        self.label_edit = QtWidgets.QLineEdit()
        self.font_size = QtWidgets.QSpinBox(); self.font_size.setRange(4, 150)
        self.chk_bold = QtWidgets.QCheckBox("B"); self.chk_italic = QtWidgets.QCheckBox("I")
        self.align_h = QtWidgets.QComboBox(); self.align_h.addItems(["center", "left", "right"])
        self.align_v = QtWidgets.QComboBox(); self.align_v.addItems(["center", "up", "down"])
        self.txt_n = ColorPickerWidget(); self.txt_h = ColorPickerWidget(); self.txt_p = ColorPickerWidget()
        
        l_txt.addRow("Label:", self.label_edit)
        l_txt.addRow("Size/Style:", self._row(self.font_size, self._row(self.chk_bold, self.chk_italic)))
        l_txt.addRow("Align H/V:", self._row(self.align_h, self.align_v))
        l_txt.addRow("Normal:", self.txt_n)
        l_txt.addRow("Hover:", self.txt_h)
        l_txt.addRow("Press:", self.txt_p)
        l_mega.addWidget(g_txt)

        # EDGES SECTION
        g_edg = QtWidgets.QGroupBox("Edges"); l_edg = QtWidgets.QFormLayout(g_edg)
        self.chk_edge = QtWidgets.QCheckBox("Visible")
        self.edg_n = ColorPickerWidget(); self.edg_h = ColorPickerWidget(); self.edg_p = ColorPickerWidget()
        self.eth_n = QtWidgets.QDoubleSpinBox(); self.eth_h = QtWidgets.QDoubleSpinBox(); self.eth_p = QtWidgets.QDoubleSpinBox()
        
        l_edg.addRow("Edge:", self.chk_edge)
        l_edg.addRow("Color Normal:", self.edg_n)
        l_edg.addRow("Color Hover:", self.edg_h)
        l_edg.addRow("Color Press:", self.edg_p)
        
        l_edg.addRow("Thick Normal:", self.eth_n)
        l_edg.addRow("Thick Hover:", self.eth_h)
        l_edg.addRow("Thick Press:", self.eth_p)
        l_mega.addWidget(g_edg)

        l_mega.addStretch()
        scroll.setWidget(t_mega)
        self._add_page("GEO", scroll)

        # ===============================================
        # 2. FLAGS TAB
        # ===============================================
        t_st = QtWidgets.QWidget(); l_st = QtWidgets.QVBoxLayout(t_st)
        
        # Placement Mode
        mode_lay = QtWidgets.QHBoxLayout()
        mode_lay.addWidget(QtWidgets.QLabel("Item Mode:"))
        self.cmb_mode = QtWidgets.QComboBox()
        self.cmb_mode.addItems(["world", "screen"])
        mode_lay.addWidget(self.cmb_mode)
        mode_lay.addStretch()
        l_st.addLayout(mode_lay)
        
        # --- NEW: 3x3 Anchor Grid ---
        self.grp_anchor = QtWidgets.QGroupBox("Screen Anchors (HUD)")
        grid_lay = QtWidgets.QGridLayout(self.grp_anchor)
        grid_lay.setSpacing(4)
        
        self.anchor_btns = QtWidgets.QButtonGroup(self)
        anchors = [
            ("top-left", 0, 0), ("top-center", 0, 1), ("top-right", 0, 2),
            ("center-left", 1, 0), ("center", 1, 1), ("center-right", 1, 2),
            ("bottom-left", 2, 0), ("bottom-center", 2, 1), ("bottom-right", 2, 2)
        ]
        
        for name, r, c in anchors:
            btn = QtWidgets.QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(30, 30)
            btn.setProperty("anchor_name", name)
            btn.setStyleSheet("QPushButton:checked { background-color: #5285a6; border: 1px solid #72a5c6; }")
            btn.toggled.connect(self._on_live_change) 
            self.anchor_btns.addButton(btn)
            grid_lay.addWidget(btn, r, c, QtCore.Qt.AlignCenter)
        
        l_st.addWidget(self.grp_anchor)
        
        # Interaction checkboxes
        self.chk_movable = QtWidgets.QCheckBox("Movable (Edit)")
        self.chk_sel_pose = QtWidgets.QCheckBox("Selectable in Pose Mode")
        
        l_st.addWidget(self.chk_movable)
        l_st.addWidget(self.chk_sel_pose)

        # --- NEW: HIERARCHY UI ---
        self.grp_hier = QtWidgets.QGroupBox("Hierarchy Connections")
        l_hier = QtWidgets.QVBoxLayout(self.grp_hier)
        self.hier_list = QtWidgets.QListWidget()
        self.hier_list.setMinimumHeight(50)
        self.hier_list.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        btn_hier_lay = QtWidgets.QHBoxLayout()
        self.btn_hier_sel_chain = QtWidgets.QPushButton("Select Chain")
        self.btn_hier_rem_link = QtWidgets.QPushButton("Remove Link")
        self.btn_hier_clear_all = QtWidgets.QPushButton("Clear All")
        
        btn_hier_lay.addWidget(self.btn_hier_sel_chain)
        btn_hier_lay.addWidget(self.btn_hier_rem_link)
        btn_hier_lay.addWidget(self.btn_hier_clear_all)
        
        # --- NEW: Enable Multi-Selection & Bind Buttons ---
        self.hier_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.btn_hier_sel_chain.clicked.connect(self._on_hier_action_select)
        self.btn_hier_rem_link.clicked.connect(self._on_hier_action_remove)
        self.btn_hier_clear_all.clicked.connect(self._on_hier_action_clear)
        
        l_hier.addWidget(self.hier_list)
        l_hier.addLayout(btn_hier_lay)
        l_st.addWidget(self.grp_hier)
        # -------------------------

        l_st.addStretch()
        self._add_page("FLAGS", t_st)

        # ===============================================
        # 3. SCRIPTS TAB
        # ===============================================
        t_scripts = QtWidgets.QWidget()
        l_scripts = QtWidgets.QHBoxLayout(t_scripts)
        l_scripts.setContentsMargins(4, 4, 4, 4)

        self.scripts_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # Left Side (List & Controls)
        w_slst = QtWidgets.QWidget()
        l_slst = QtWidgets.QVBoxLayout(w_slst)
        l_slst.setContentsMargins(0,0,0,0)
        
        self.list_scripts = QtWidgets.QListWidget()
        h_sbtn = QtWidgets.QHBoxLayout()
        self.btn_scr_add = QtWidgets.QPushButton("+ Add")
        self.btn_scr_rem = QtWidgets.QPushButton("- Rem")
        h_sbtn.addWidget(self.btn_scr_add)
        h_sbtn.addWidget(self.btn_scr_rem)

        l_slst.addWidget(QtWidgets.QLabel("Assigned Scripts:"))
        l_slst.addWidget(self.list_scripts)
        l_slst.addLayout(h_sbtn)
        self.scripts_split.addWidget(w_slst)

        # Right Side (Properties)
        self.w_sprop = QtWidgets.QWidget()
        l_sprop = QtWidgets.QVBoxLayout(self.w_sprop)
        l_sprop.setContentsMargins(4,0,0,0)

        f_sprop = QtWidgets.QFormLayout()
        self.le_scr_name = QtWidgets.QLineEdit()
        self.cb_scr_lang = QtWidgets.QComboBox()
        self.cb_scr_lang.addItems(["python", "mel"])
        self.cb_scr_trig = QtWidgets.QComboBox()
        self.cb_scr_trig.addItems(["Left Click (Menu)", "Left Click (Action)", "Right Click (Menu)", "Right Click (Action)"])

        f_sprop.addRow("Label:", self.le_scr_name)
        f_sprop.addRow("Type:", self.cb_scr_lang)
        f_sprop.addRow("Trigger:", self.cb_scr_trig)

        self.te_scr_code = ScriptEditorWidget()
        self.btn_scr_test = QtWidgets.QPushButton("Test Script (Run)")
        self.btn_scr_test.setStyleSheet("background-color: #3a5f43; font-weight: bold;")

        l_sprop.addLayout(f_sprop)
        
        # --- Expand Editor Button ---
        lbl_lay = QtWidgets.QHBoxLayout()
        lbl_lay.addWidget(QtWidgets.QLabel("Code Output:"))
        lbl_lay.addStretch()
        self.btn_scr_expand = QtWidgets.QPushButton("⛶ Expand")
        self.btn_scr_expand.setToolTip("Open script in a larger standalone window")
        lbl_lay.addWidget(self.btn_scr_expand)
        l_sprop.addLayout(lbl_lay)
        
        l_sprop.addWidget(self.te_scr_code)
        l_sprop.addWidget(self.btn_scr_test)

        self.w_sprop.setEnabled(False) # Disabled until script selected
        self.scripts_split.addWidget(self.w_sprop)
        self.scripts_split.setSizes([120, 250])

        l_scripts.addWidget(self.scripts_split)
        
        # Wire Signals
        self.btn_scr_add.clicked.connect(self._on_scr_add)
        self.btn_scr_rem.clicked.connect(self._on_scr_rem)
        self.list_scripts.itemSelectionChanged.connect(self._on_scr_select)
        self.btn_scr_test.clicked.connect(self._on_scr_test)
        self.btn_scr_expand.clicked.connect(self._on_scr_expand)
        
        self.le_scr_name.textEdited.connect(self._on_scr_live)
        self.cb_scr_lang.currentTextChanged.connect(self._on_scr_live)
        self.cb_scr_trig.currentTextChanged.connect(self._on_scr_live)
        self.te_scr_code.textChanged.connect(self._on_scr_live)

        self._add_page("SCRIPTS", t_scripts)

        # ===============================================
        # 4. LIST TAB (Controls Management)
        # ===============================================
        t_list = QtWidgets.QWidget(); l_list = QtWidgets.QVBoxLayout(t_list)
        l_list.setContentsMargins(5, 5, 5, 5)
        
        self.controls_listbox = QtWidgets.QListWidget()
        self.controls_listbox.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.controls_listbox.setStyleSheet("background: #111111; border: 1px solid #444; border-radius: 4px; padding: 4px;")
        
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_ctrl_add = QtWidgets.QPushButton("Add")
        self.btn_ctrl_remove = QtWidgets.QPushButton("Remove")
        self.btn_ctrl_replace = QtWidgets.QPushButton("Replace")
        self.btn_ctrl_clear = QtWidgets.QPushButton("Clear")
        
        self.btn_ctrl_add.setStyleSheet("background-color: #2e5c3a;") # Green highlight
        self.btn_ctrl_remove.setStyleSheet("background-color: #6b2e2e;") # Red highlight
        
        btn_layout.addWidget(self.btn_ctrl_add)
        btn_layout.addWidget(self.btn_ctrl_remove)
        btn_layout.addWidget(self.btn_ctrl_replace)
        btn_layout.addWidget(self.btn_ctrl_clear)
        
        l_list.addWidget(QtWidgets.QLabel("<b>Assigned Controls:</b>"))
        l_list.addWidget(self.controls_listbox)
        l_list.addLayout(btn_layout)
        
        # Connect buttons to emit the secure signal
        self.btn_ctrl_add.clicked.connect(lambda: self.controls_modified.emit("add"))
        self.btn_ctrl_remove.clicked.connect(lambda: self.controls_modified.emit("remove"))
        self.btn_ctrl_replace.clicked.connect(lambda: self.controls_modified.emit("replace"))
        self.btn_ctrl_clear.clicked.connect(lambda: self.controls_modified.emit("clear"))
        self._add_page("LIST", t_list)

        # ===============================================
        # Layer Properties
        # ===============================================
        # --- NEW: LAYERS TAB ---
        t_layers = QtWidgets.QWidget()
        l_layers = QtWidgets.QVBoxLayout(t_layers)
        l_layers.setContentsMargins(4, 4, 4, 4)
        
        # --- NEW: Assigned Layers Info ---
        self.lbl_assigned_layers = QtWidgets.QLabel("None")
        self.lbl_assigned_layers.setStyleSheet("color: #66c2ff; font-weight: bold; font-style: italic;")
        l_layers.addWidget(self.lbl_assigned_layers)

        # Top: Create Layer
        h_create = QtWidgets.QHBoxLayout()
        self.le_layer_name = QtWidgets.QLineEdit()
        self.le_layer_name.setPlaceholderText("New Layer Name...")
        self.btn_layer_create = QtWidgets.QPushButton("+ Add")
        h_create.addWidget(self.le_layer_name)
        h_create.addWidget(self.btn_layer_create)
        l_layers.addLayout(h_create)
        
        # Middle: Layer Tree Box (Table)
        self.tree_layers = QtWidgets.QTreeWidget()
        self.tree_layers.setHeaderLabels(["Layer Name", "Edit", "Pose"])
        self.tree_layers.setColumnWidth(0, 140)
        self.tree_layers.setColumnWidth(1, 50)
        self.tree_layers.setColumnWidth(2, 50)
        self.tree_layers.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree_layers.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree_layers.customContextMenuRequested.connect(self._show_layer_context_menu)
        l_layers.addWidget(self.tree_layers)
        
        # Bottom: Action Buttons
        h_actions = QtWidgets.QHBoxLayout()
        self.btn_layer_add_sel = QtWidgets.QPushButton("Add Selected")
        self.btn_layer_rem_sel = QtWidgets.QPushButton("Remove Selected")
        self.btn_layer_del = QtWidgets.QPushButton("Delete")
        h_actions.addWidget(self.btn_layer_add_sel)
        h_actions.addWidget(self.btn_layer_rem_sel)
        h_actions.addWidget(self.btn_layer_del)
        l_layers.addLayout(h_actions)
        
        # --- NEW: WIRE LAYER BUTTONS ---
        self.btn_layer_create.clicked.connect(self._on_layer_create)
        self.btn_layer_add_sel.clicked.connect(self._on_layer_add_sel)
        self.btn_layer_rem_sel.clicked.connect(self._on_layer_rem_sel)
        self.btn_layer_del.clicked.connect(self._on_layer_del)
        self.tree_layers.itemChanged.connect(self._on_layer_tree_changed)
        # -------------------------------
        
        self._add_page("LAYERS", t_layers)

        # ===============================================
        # Round Rectangle Properties
        # ===============================================
        t_spl = QtWidgets.QWidget()
        spl_main_lay = QtWidgets.QVBoxLayout(t_spl)
        spl_main_lay.setContentsMargins(0, 0, 0, 0)
        
        self.spl_scroll = QtWidgets.QScrollArea()
        self.spl_scroll.setWidgetResizable(True)
        self.spl_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        self.spl_content = QtWidgets.QWidget()
        l_spl = QtWidgets.QVBoxLayout(self.spl_content) 
        
        self.spl_scroll.setWidget(self.spl_content)
        spl_main_lay.addWidget(self.spl_scroll)
        
        # Round Rectangle Custom Radii
        self.grp_spl_roundrect = QtWidgets.QGroupBox("Round Rectangle Radii")
        l_rr = QtWidgets.QFormLayout(self.grp_spl_roundrect)
        self.rad_tl = QtWidgets.QDoubleSpinBox(); self.rad_tl.setRange(0, 999)
        self.rad_tr = QtWidgets.QDoubleSpinBox(); self.rad_tr.setRange(0, 999)
        self.rad_bl = QtWidgets.QDoubleSpinBox(); self.rad_bl.setRange(0, 999)
        self.rad_br = QtWidgets.QDoubleSpinBox(); self.rad_br.setRange(0, 999)
        l_rr.addRow("Top Left / Right:", self._row(self.rad_tl, self.rad_tr))
        l_rr.addRow("Bottom Left / Right:", self._row(self.rad_bl, self.rad_br))
        l_spl.addWidget(self.grp_spl_roundrect)
        
        # ===============================================
        # Slider Properties
        # ===============================================
        self.grp_spl_slider = QtWidgets.QGroupBox("Slider Properties")
        l_sl = QtWidgets.QFormLayout(self.grp_spl_slider)
        
        # 1. CRITICAL FIX: Initialize ALL variables first!
        self.sl_attr = QtWidgets.QLineEdit()
        self.sl_inside_text = QtWidgets.QCheckBox("Inside Text (Ignore GEO alignment)")
        self.sl_min = QtWidgets.QDoubleSpinBox(); self.sl_min.setRange(-99999, 99999)
        self.sl_max = QtWidgets.QDoubleSpinBox(); self.sl_max.setRange(-99999, 99999)
        self.sl_val = QtWidgets.QDoubleSpinBox(); self.sl_val.setRange(-99999, 99999)
        self.sl_handle_scale = QtWidgets.QDoubleSpinBox(); self.sl_handle_scale.setRange(0.1, 10.0); self.sl_handle_scale.setSingleStep(0.1)
        self.sl_handle_color = ColorPickerWidget()
        
        # 2. Build the Attribute + Buttons row
        attr_btn_lay = QtWidgets.QHBoxLayout()
        self.btn_attr_add = QtWidgets.QPushButton("Add")
        self.btn_attr_rep = QtWidgets.QPushButton("Replace")
        self.btn_attr_clr = QtWidgets.QPushButton("Clear")
        
        self.btn_attr_add.setStyleSheet("background-color: #2e5c3a;")
        self.btn_attr_rep.setStyleSheet("background-color: #2b455c;")
        self.btn_attr_clr.setStyleSheet("background-color: #6b2e2e;")
        
        attr_btn_lay.addWidget(self.btn_attr_add)
        attr_btn_lay.addWidget(self.btn_attr_rep)
        attr_btn_lay.addWidget(self.btn_attr_clr)
        
        self.btn_attr_add.clicked.connect(lambda: self.attribute_modified.emit("add"))
        self.btn_attr_rep.clicked.connect(lambda: self.attribute_modified.emit("replace"))
        self.btn_attr_clr.clicked.connect(lambda: self.attribute_modified.emit("clear"))
        
        attr_field_w = QtWidgets.QWidget()
        attr_field_l = QtWidgets.QVBoxLayout(attr_field_w)
        attr_field_l.setContentsMargins(0,0,0,0)
        attr_field_l.addWidget(self.sl_attr)
        attr_field_l.addLayout(attr_btn_lay)
        
        # 3. Add rows to the Form Layout (Now safe because variables exist)
        l_sl.addRow("Attribute Name:", attr_field_w)
        l_sl.addRow("Text Placement:", self.sl_inside_text)
        l_sl.addRow("Min / Max:", self._row(self.sl_min, self.sl_max))
        l_sl.addRow("Default Value:", self.sl_val)
        l_sl.addRow("Handle Scale:", self.sl_handle_scale)
        l_sl.addRow("Handle Color:", self.sl_handle_color)

        l_spl.addWidget(self.grp_spl_slider)
        
        # ===============================================
        # Pose Properties - Vertically Stacked
        # ===============================================
        self.grp_spl_pose = QtWidgets.QGroupBox("Pose Properties")
        l_po = QtWidgets.QVBoxLayout(self.grp_spl_pose)
        
        # Image Preview (Bigger: 180x120)
        self.po_img_preview = QtWidgets.QLabel("No Image")
        self.po_img_preview.setFixedSize(180, 120)
        self.po_img_preview.setAlignment(QtCore.Qt.AlignCenter)
        self.po_img_preview.setStyleSheet("border: 2px solid #555; background: #111; border-radius: 4px;")
        l_po.addWidget(self.po_img_preview, 0, QtCore.Qt.AlignCenter)

        # Path display & Load/Capture Buttons
        self.po_img_path = QtWidgets.QLineEdit()
        self.po_img_path.setReadOnly(True)
        self.po_img_path.setStyleSheet("color: #aaa; background-color: #1a1a1a;")
        
        path_lay = QtWidgets.QHBoxLayout()
        path_lay.addWidget(QtWidgets.QLabel("Path:"))
        path_lay.addWidget(self.po_img_path)
        
        btn_lay = QtWidgets.QHBoxLayout()
        self.po_btn_cap = QtWidgets.QPushButton("Capture")
        self.po_btn_load = QtWidgets.QPushButton("Load")
        btn_lay.addWidget(self.po_btn_cap)
        btn_lay.addWidget(self.po_btn_load)
        
        l_po.addLayout(path_lay)
        l_po.addLayout(btn_lay)

        # Mask & Options
        form = QtWidgets.QFormLayout()
        self.po_shape = QtWidgets.QComboBox()
        self.po_shape.addItems(["Rectangle", "Round Rectangle", "Circle"])
        self.po_scale = QtWidgets.QComboBox()
        self.po_scale.addItems(["Fit", "Fill", "Stretch"])
        self.po_pad = QtWidgets.QDoubleSpinBox()
        self.po_pad.setRange(0, 500)
        self.po_inside_text = QtWidgets.QCheckBox("Inside Text")
        form.addRow("Mask Shape:", self.po_shape)
        form.addRow("Image Scale:", self.po_scale)
        form.addRow("Padding:", self.po_pad)
        form.addRow("", self.po_inside_text)
        l_po.addLayout(form)

        # Round Rectangle Radius (Visible only when 'Round Rectangle' mask is selected)
        self.po_rr_group = QtWidgets.QWidget()
        l_po_rr = QtWidgets.QFormLayout(self.po_rr_group)
        self.po_rad = QtWidgets.QDoubleSpinBox()
        self.po_rad.setRange(0, 500)
        self.po_rad.setValue(8.0)
        l_po_rr.addRow("Corner Radius:", self.po_rad)
        l_po.addWidget(self.po_rr_group)

        # V-Stacked Lists (SCALABLE via QSplitter)
        self.po_v_split = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        
        cw = QtWidgets.QWidget(); cl = QtWidgets.QVBoxLayout(cw); cl.setContentsMargins(0,0,0,0)
        cl.addWidget(QtWidgets.QLabel("Stored Controls:"))
        self.po_ctrl_list = QtWidgets.QListWidget()
        self.po_btn_c_rem = QtWidgets.QPushButton("Remove Selected Control")
        self.po_btn_c_rem.setStyleSheet("background-color: #6b2e2e;")
        cl.addWidget(self.po_ctrl_list); cl.addWidget(self.po_btn_c_rem)
        
        aw = QtWidgets.QWidget(); al = QtWidgets.QVBoxLayout(aw); al.setContentsMargins(0,0,0,0)
        al.addWidget(QtWidgets.QLabel("Control Attributes:"))
        self.po_attr_list = QtWidgets.QListWidget()
        self.po_btn_a_rem = QtWidgets.QPushButton("Remove Selected Attribute")
        self.po_btn_a_rem.setStyleSheet("background-color: #6b2e2e;")
        al.addWidget(self.po_attr_list); al.addWidget(self.po_btn_a_rem)
        
        self.po_v_split.addWidget(cw); self.po_v_split.addWidget(aw)
        l_po.addWidget(self.po_v_split)
        
        # Connections
        self.po_btn_cap.clicked.connect(lambda: self.pose_action_requested.emit("capture_image"))
        self.po_btn_load.clicked.connect(lambda: self.pose_action_requested.emit("load_image"))
        self.po_btn_c_rem.clicked.connect(lambda: self.pose_action_requested.emit("rem_ctrl_ui"))
        self.po_btn_a_rem.clicked.connect(lambda: self.pose_action_requested.emit("rem_attr_ui"))
        self.po_ctrl_list.itemSelectionChanged.connect(self._on_pose_ctrl_selected)

        l_spl.addWidget(self.grp_spl_pose)

        # ===============================================
        # Checkbox Properties
        # ===============================================
        self.grp_spl_check = QtWidgets.QGroupBox("Checkbox Properties")
        l_cb = QtWidgets.QVBoxLayout(self.grp_spl_check)
        
        # Top Options (Masks & Marks)
        mark_lay = QtWidgets.QHBoxLayout()
        self.cb_show_mark = QtWidgets.QCheckBox("Right Sign")
        self.cb_mark_col = ColorPickerWidget()
        mark_lay.addWidget(self.cb_show_mark); mark_lay.addWidget(QtWidgets.QLabel("Color:")); mark_lay.addWidget(self.cb_mark_col)
        mark_lay.addStretch()
        l_cb.addLayout(mark_lay)
        
        form_cb = QtWidgets.QFormLayout()
        self.cb_shape = QtWidgets.QComboBox()
        self.cb_shape.addItems(["Rectangle", "Round Rectangle", "Circle"])
        self.cb_inside_text = QtWidgets.QCheckBox("Inside Text")
        form_cb.addRow("Mask Shape:", self.cb_shape)
        form_cb.addRow("", self.cb_inside_text)
        l_cb.addLayout(form_cb)
        
        self.cb_rr_group = QtWidgets.QWidget()
        l_cb_rr = QtWidgets.QFormLayout(self.cb_rr_group)
        self.cb_rad = QtWidgets.QDoubleSpinBox()
        self.cb_rad.setRange(0, 500); self.cb_rad.setValue(8.0)
        l_cb_rr.addRow("Corner Radius:", self.cb_rad)
        l_cb.addWidget(self.cb_rr_group)
        
        self.cb_v_split = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        
        self.cb_on_grp, self.cb_on_txt, self.cb_on_col, self.cb_on_attr, self.cb_on_a_add, self.cb_on_a_rem, self.cb_on_a_clr, self.cb_on_shape, self.cb_on_s_add, self.cb_on_s_rem, self.cb_on_s_clr, self.cb_on_cmd_type, self.cb_on_cmd_txt, self.cb_on_btn_expand = self._build_cb_state("ON")
        self.cb_v_split.addWidget(self.cb_on_grp)
        
        self.cb_off_grp, self.cb_off_txt, self.cb_off_col, self.cb_off_attr, self.cb_off_a_add, self.cb_off_a_rem, self.cb_off_a_clr, self.cb_off_shape, self.cb_off_s_add, self.cb_off_s_rem, self.cb_off_s_clr, self.cb_off_cmd_type, self.cb_off_cmd_txt, self.cb_off_btn_expand = self._build_cb_state("OFF")
        self.cb_v_split.addWidget(self.cb_off_grp)
        
        l_cb.addWidget(self.cb_v_split)
        l_spl.addWidget(self.grp_spl_check)
        
        # Connections
        self.cb_on_a_add.clicked.connect(lambda: self.checkbox_action_requested.emit("ON", "add_attr"))
        self.cb_on_a_rem.clicked.connect(lambda: self.checkbox_action_requested.emit("ON", "rem_attr"))
        self.cb_on_a_clr.clicked.connect(lambda: self.checkbox_action_requested.emit("ON", "clr_attr"))
        self.cb_on_s_add.clicked.connect(lambda: self.checkbox_action_requested.emit("ON", "add_shape"))
        self.cb_on_s_rem.clicked.connect(lambda: self.checkbox_action_requested.emit("ON", "rem_shape"))
        self.cb_on_s_clr.clicked.connect(lambda: self.checkbox_action_requested.emit("ON", "clr_shape"))
        
        self.cb_off_a_add.clicked.connect(lambda: self.checkbox_action_requested.emit("OFF", "add_attr"))
        self.cb_off_a_rem.clicked.connect(lambda: self.checkbox_action_requested.emit("OFF", "rem_attr"))
        self.cb_off_a_clr.clicked.connect(lambda: self.checkbox_action_requested.emit("OFF", "clr_attr"))
        self.cb_off_s_add.clicked.connect(lambda: self.checkbox_action_requested.emit("OFF", "add_shape"))
        self.cb_off_s_rem.clicked.connect(lambda: self.checkbox_action_requested.emit("OFF", "rem_shape"))
        self.cb_off_s_clr.clicked.connect(lambda: self.checkbox_action_requested.emit("OFF", "clr_shape"))
        
        self.cb_on_btn_expand.clicked.connect(lambda: self._on_cb_expand("ON"))
        self.cb_off_btn_expand.clicked.connect(lambda: self._on_cb_expand("OFF"))

        l_spl.addWidget(self.grp_spl_check)
        
        # ===============================================
        # Image Properties
        # ===============================================
        self.grp_spl_image = QtWidgets.QGroupBox("Image Properties")
        l_img = QtWidgets.QVBoxLayout(self.grp_spl_image)
        
        self.img_img_preview = QtWidgets.QLabel("No Image")
        self.img_img_preview.setFixedSize(180, 120)
        self.img_img_preview.setAlignment(QtCore.Qt.AlignCenter)
        self.img_img_preview.setStyleSheet("border: 2px solid #555; background: #111; border-radius: 4px;")
        l_img.addWidget(self.img_img_preview, 0, QtCore.Qt.AlignCenter)

        self.img_img_path = QtWidgets.QLineEdit()
        self.img_img_path.setReadOnly(True)
        self.img_img_path.setStyleSheet("color: #aaa; background-color: #1a1a1a;")
        
        path_lay = QtWidgets.QHBoxLayout()
        path_lay.addWidget(QtWidgets.QLabel("Path:"))
        path_lay.addWidget(self.img_img_path)
        
        self.img_btn_load = QtWidgets.QPushButton("Load New Image")
        
        form_img = QtWidgets.QFormLayout()
        self.img_opacity = QtWidgets.QSpinBox()
        self.img_opacity.setRange(0, 100); self.img_opacity.setSuffix("%")
        self.img_scale = QtWidgets.QComboBox()
        self.img_scale.addItems(["Fit", "Fill", "Stretch"])
        form_img.addRow("Opacity:", self.img_opacity)
        form_img.addRow("Scale Mode:", self.img_scale)
        
        l_img.addLayout(path_lay)
        l_img.addWidget(self.img_btn_load)
        l_img.addLayout(form_img)
        
        self.img_btn_load.clicked.connect(lambda: self.image_action_requested.emit("load_image"))
        l_spl.addWidget(self.grp_spl_image)

        l_spl.addStretch()

        # Fallback text if shape has no special properties
        self.lbl_spl_empty = QtWidgets.QLabel("No special properties for this shape.")
        self.lbl_spl_empty.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_spl_empty.setStyleSheet("color: #777;")
        l_spl.addWidget(self.lbl_spl_empty)
        
        l_spl.addStretch()
        self._add_page("*SPL*", t_spl)

        # ===============================================
        # GLOBAL RIG SETTINGS (EXPLICIT CHAIN MANAGER)
        # ===============================================
        t_rig = QtWidgets.QWidget(); l_rig = QtWidgets.QVBoxLayout(t_rig)
        
        l_rig.addWidget(QtWidgets.QLabel("Configured IK/FK Chains:"))
        self.ikfk_list = QtWidgets.QListWidget()
        self.ikfk_list.setFixedHeight(80)
        self.ikfk_list.currentRowChanged.connect(self._ikfk_on_select)
        l_rig.addWidget(self.ikfk_list)
        
        r_btns = QtWidgets.QHBoxLayout()
        btn_add_chain = QtWidgets.QPushButton("+ New Chain"); btn_add_chain.clicked.connect(self._ikfk_add)
        btn_del_chain = QtWidgets.QPushButton("- Delete Selected"); btn_del_chain.clicked.connect(self._ikfk_del)
        r_btns.addWidget(btn_add_chain); r_btns.addWidget(btn_del_chain)
        l_rig.addLayout(r_btns)
        
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        
        self.ikfk_grp = QtWidgets.QGroupBox("Explicit Chain Properties")
        f_ik = QtWidgets.QFormLayout(self.ikfk_grp)
        
        self.ikfk_name = QtWidgets.QLineEdit()
        f_ik.addRow("Chain Name:", self.ikfk_name)
        
        r_vals = QtWidgets.QHBoxLayout()
        self.ikfk_ik_val = QtWidgets.QDoubleSpinBox(); self.ikfk_ik_val.setRange(0, 10); self.ikfk_ik_val.setValue(1.0)
        self.ikfk_fk_val = QtWidgets.QDoubleSpinBox(); self.ikfk_fk_val.setRange(0, 10); self.ikfk_fk_val.setValue(0.0)
        r_vals.addWidget(QtWidgets.QLabel("IK Val:")); r_vals.addWidget(self.ikfk_ik_val)
        r_vals.addWidget(QtWidgets.QLabel("FK Val:")); r_vals.addWidget(self.ikfk_fk_val)
        f_ik.addRow("Switch Vals:", r_vals)

        # --- SMART ADD BUTTONS ---
        def _add_btn(target_field, multi=False):
            b = QtWidgets.QPushButton("ADD") # FIX: Removed '+' to stop text cutoff
            b.setFixedWidth(50)
            def _apply():
                from maya import cmds
                sel = cmds.ls(sl=True)
                if sel:
                    short_names = [s.split("|")[-1].split(":")[-1] for s in sel]
                    
                    # Safe text extraction (Checks if it's a LineEdit or TextEdit)
                    is_text_edit = isinstance(target_field, QtWidgets.QTextEdit)
                    current_text = target_field.toPlainText() if is_text_edit else target_field.text()
                    
                    if multi:
                        existing = [x.strip() for x in current_text.split(",") if x.strip()]
                        for sn in short_names:
                            if sn not in existing: existing.append(sn)
                        new_txt = ", ".join(existing)
                    else:
                        new_txt = short_names[0]
                        
                    if is_text_edit: target_field.setPlainText(new_txt)
                    else: target_field.setText(new_txt)
            b.clicked.connect(_apply)
            return b

        def _add_attr_btn(target_field):
            b = QtWidgets.QPushButton("ADD") # FIX: Removed '+' to stop text cutoff
            b.setFixedWidth(50)
            def _apply():
                from maya import cmds
                cb_attrs = cmds.channelBox('mainChannelBox', q=True, selectedMainAttributes=True) or []
                if cb_attrs: target_field.setText(cb_attrs[0])
                else: cmds.warning("[ASEPicker] Select an attribute in the Maya Channel Box first!")
            b.clicked.connect(_apply)
            return b
        # -------------------------

        r_swn = QtWidgets.QHBoxLayout(); self.ikfk_sw_node = QtWidgets.QLineEdit()
        r_swn.addWidget(self.ikfk_sw_node); r_swn.addWidget(_add_btn(self.ikfk_sw_node))
        f_ik.addRow("Switch Node:", r_swn)
        
        r_swa = QtWidgets.QHBoxLayout(); self.ikfk_sw_attr = QtWidgets.QLineEdit()
        self.ikfk_sw_attr.setPlaceholderText("Select in Channel Box ->")
        r_swa.addWidget(self.ikfk_sw_attr); r_swa.addWidget(_add_attr_btn(self.ikfk_sw_attr))
        f_ik.addRow("Switch Attr:", r_swa)

        r_ik = QtWidgets.QHBoxLayout(); self.ikfk_ik_ctrl = QtWidgets.QLineEdit()
        r_ik.addWidget(self.ikfk_ik_ctrl); r_ik.addWidget(_add_btn(self.ikfk_ik_ctrl))
        f_ik.addRow("IK Control:", r_ik)
        
        r_pv = QtWidgets.QHBoxLayout(); self.ikfk_pv_ctrl = QtWidgets.QLineEdit()
        r_pv.addWidget(self.ikfk_pv_ctrl); r_pv.addWidget(_add_btn(self.ikfk_pv_ctrl))
        f_ik.addRow("Pole Vector:", r_pv)
        
        r_fk = QtWidgets.QHBoxLayout(); self.ikfk_fk_ctrls = QtWidgets.QLineEdit()
        r_fk.addWidget(self.ikfk_fk_ctrls); r_fk.addWidget(_add_btn(self.ikfk_fk_ctrls, multi=True))
        f_ik.addRow("FK Controls:", r_fk)
        
        # BONES (Driven Joints) with Auto-Find AND Manual Add
        r_bn_main = QtWidgets.QVBoxLayout()
        r_bn_top = QtWidgets.QHBoxLayout()
        
        self.ikfk_bones = QtWidgets.QTextEdit() # FIX: Changed to multi-line box!
        self.ikfk_bones.setMaximumHeight(65)
        
        btn_auto = QtWidgets.QPushButton("AUTO FIND")
        btn_auto.setFixedWidth(75)
        btn_auto.clicked.connect(self._ikfk_auto_joints)
        
        # Auto Find goes on the right side of the bone box
        r_bn_top.addWidget(self.ikfk_bones)
        r_bn_top.addWidget(btn_auto)
        
        r_bn_bot = QtWidgets.QHBoxLayout()
        r_bn_bot.addStretch()
        # Add button goes below the box
        r_bn_bot.addWidget(_add_btn(self.ikfk_bones, multi=True))
        
        r_bn_main.addLayout(r_bn_top)
        r_bn_main.addLayout(r_bn_bot)
        
        f_ik.addRow("Driven Joints:", r_bn_main)
        
        btn_save = QtWidgets.QPushButton("💾 Save Changes to Chain")
        btn_save.setStyleSheet("background-color: #5285a6; font-weight: bold; padding: 4px;")
        btn_save.clicked.connect(self._ikfk_save)
        f_ik.addRow("", btn_save)
        
        scroll.setWidget(self.ikfk_grp)
        l_rig.addWidget(scroll)
        self.ikfk_grp.setEnabled(False)
        self._add_page("IK - FK", t_rig)
        
        # Wire auto-refresh when tab is clicked
        self.nav_list.currentRowChanged.connect(self._on_tab_changed)
        self.nav_list.setCurrentRow(0)

    def _on_pose_ctrl_selected(self):
        self.po_attr_list.clear()
        sel = self.po_ctrl_list.currentItem()
        if not sel or not getattr(self, "target_items", None): return
        
        pose_data = getattr(self.target_items[0], "pose_data", {})
        attrs = pose_data.get(sel.text(), {})
        for k, v in attrs.items():
            v_str = str(round(v, 4)) if isinstance(v, float) else str(v)
            self.po_attr_list.addItem(f"{k}: {v_str}")
    
    def _add_page(self, name, widget):
        self.nav_list.addItem(name)
        self.stack.addWidget(widget)

    def _row(self, w1, w2):
        w = QtWidgets.QWidget(); l = QtWidgets.QHBoxLayout(w); l.setContentsMargins(0,0,0,0)
        l.addWidget(w1); l.addWidget(w2)
        return w

    def _bind_live_events(self):
        for widget in self.findChildren(QtWidgets.QLineEdit): widget.textChanged.connect(self._on_live_change)
        for widget in self.findChildren(QtWidgets.QDoubleSpinBox): widget.valueChanged.connect(self._on_live_change)
        for widget in self.findChildren(QtWidgets.QSpinBox): widget.valueChanged.connect(self._on_live_change)
        for widget in self.findChildren(QtWidgets.QCheckBox): widget.toggled.connect(self._on_live_change)
        for widget in self.findChildren(QtWidgets.QComboBox): widget.currentIndexChanged.connect(self._on_live_change)
        for widget in self.findChildren(QtWidgets.QTextEdit): widget.textChanged.connect(self._on_live_change)
        for widget in self.findChildren(ColorPickerWidget): widget.colorChanged.connect(self._on_live_change)

    def _block_all(self, state):
        for w in self.findChildren(QtWidgets.QWidget): w.blockSignals(state)

    def set_target_items(self, items):
        self._is_updating = True
        self.target_items = items
        
        # --- REFRESH LAYERS AND SCRIPTS ---
        self._populate_layers()
        self._populate_scripts()
        self.refresh_ikfk_manager()

        # --- LAYER INFO LABEL REFRESH ---
        self._populate_layers()
        canvas = self._get_canvas()
        if hasattr(self, "lbl_assigned_layers"):
            if canvas and items:
                assigned = set()
                for itm in items:
                    for l in getattr(canvas, "layer_data", []):
                        if itm.item_id in l.get("shapes", []):
                            assigned.add(l["name"])
                if assigned:
                    self.lbl_assigned_layers.setText(", ".join(assigned))
                else:
                    self.lbl_assigned_layers.setText("None")
            else:
                self.lbl_assigned_layers.setText("None")
        # --------------------------------

        if not items: return
        
        # Populate UI based on the primary selected item
        item = items[0]
        self._is_populating = True
        self._block_all(True)

        # Populate Shape ID
        if len(items) == 1:
            self.shape_id_edit.setText(getattr(item, "item_id", ""))
        else:
            self.shape_id_edit.setText("<Multiple Shapes Selected>")

        self.label_edit.setText(getattr(item, "label", ""))
        
        # Populate ListBox
        self.controls_listbox.clear()
        ctrls = getattr(item, "controls", [])
        if ctrls:
            self.controls_listbox.addItems(ctrls)

        # --- POPULATE LAYERS BOX ---
        self._populate_layers()
        
        # --- POPULATE SCRIPTS BOX ---
        self._populate_scripts()
        
        # --- POPULATE HIERARCHY BOX ---
        self.hier_list.clear()
        if items:
            scene_items = {i.item_id: i for i in items[0].scene().items() if hasattr(i, "item_id")}
            for itm in items:
                prefix = f"[{getattr(itm, 'label', 'Shape')}] " if len(items) > 1 else ""
                
                for pid in getattr(itm, "parent_links", []):
                    p_item = scene_items.get(pid)
                    if p_item:
                        li = QtWidgets.QListWidgetItem(f"{prefix}▲ Parent: {getattr(p_item, 'label', 'Unnamed')}")
                        li.setData(QtCore.Qt.UserRole, ("parent", itm, p_item))
                        self.hier_list.addItem(li)
                        
                for cid in getattr(itm, "child_links", []):
                    c_item = scene_items.get(cid)
                    if c_item:
                        li = QtWidgets.QListWidgetItem(f"{prefix}▼ Child: {getattr(c_item, 'label', 'Unnamed')}")
                        li.setData(QtCore.Qt.UserRole, ("child", itm, c_item))
                        self.hier_list.addItem(li)
        # -----------------------------------

        self.pos_x.setValue(float(item.pos().x())); self.pos_y.setValue(float(item.pos().y()))
        self.geo_w.setValue(float(getattr(item, "width", 60.0))); self.geo_h.setValue(float(getattr(item, "height", 30.0)))
        self.geo_r.setValue(float(item.rotation()))

        bg = getattr(item, "bg", {}); ed = getattr(item, "edge_color", {}); tx = getattr(item, "text_color", {})
        self.bg_n.setText(bg.get("normal", "#3c6e71")); self.bg_h.setText(bg.get("hover", "#4d8c90")); self.bg_p.setText(bg.get("press", "#2a4d4f"))
        self.edg_n.setText(ed.get("normal", "#111111")); self.edg_h.setText(ed.get("hover", "#ffffff")); self.edg_p.setText(ed.get("press", "#000000"))
        self.txt_n.setText(tx.get("normal", "#ffffff")); self.txt_h.setText(tx.get("hover", "#ffffff")); self.txt_p.setText(tx.get("press", "#cccccc"))
        
        self.chk_edge.setChecked(bool(getattr(item, "edge_visible", True)))
        eth = getattr(item, "edge_thickness", {})
        if not isinstance(eth, dict): eth = {"normal": eth, "hover": eth, "press": eth}
        self.eth_n.setValue(float(eth.get("normal", 1.5))); self.eth_h.setValue(float(eth.get("hover", 2.0))); self.eth_p.setValue(float(eth.get("press", 1.5)))

        self.font_size.setValue(int(getattr(item, "font_point_size", 10)))
        self.chk_bold.setChecked(bool(getattr(item, "font_bold", False)))
        self.chk_italic.setChecked(bool(getattr(item, "font_italic", False)))
        self.align_h.setCurrentText(getattr(item, "text_align_h", "center"))
        self.align_v.setCurrentText(getattr(item, "text_align_v", "center"))

        self.chk_movable.setChecked(bool(getattr(item, "movable_edit", True)))
        self.chk_sel_pose.setChecked(bool(getattr(item, "selectable_pose", True)))
        
        self.cmb_mode.setCurrentText(getattr(item, "placement_mode", "world"))
        self.grp_anchor.setVisible(self.cmb_mode.currentText() == "screen")
        
        anchor_val = getattr(item, "screen_anchor", "center")
        for btn in self.anchor_btns.buttons():
            btn.blockSignals(True)
            btn.setChecked(btn.property("anchor_name") == anchor_val)
            btn.blockSignals(False)

        # --- Handle *SPL* Tab Visibility & Values ---
        shape_type = ""
        if items:
            first_type = getattr(items[0], "shape_name", "")
            if all(getattr(i, "shape_name", "") == first_type for i in items):
                shape_type = first_type
        
        self.grp_spl_roundrect.setVisible(shape_type == "Round Rectangle")
        self.grp_spl_slider.setVisible(shape_type == "Slider")
        self.grp_spl_pose.setVisible(shape_type == "Pose")
        self.grp_spl_check.setVisible(shape_type == "Checkbox")
        self.grp_spl_image.setVisible(shape_type == "Image")
        self.lbl_spl_empty.setVisible(shape_type not in ["Round Rectangle", "Slider", "Pose", "Checkbox", "Image"])
        
        if shape_type == "Round Rectangle":
            self.rad_tl.setValue(float(getattr(item, "rad_tl", 4.0)))
            self.rad_tr.setValue(float(getattr(item, "rad_tr", 4.0)))
            self.rad_bl.setValue(float(getattr(item, "rad_bl", 4.0)))
            self.rad_br.setValue(float(getattr(item, "rad_br", 4.0)))
            
        elif shape_type == "Slider":
            self.sl_attr.setText(getattr(item, "attribute", ""))
            self.sl_inside_text.setChecked(bool(getattr(item, "inside_text", False)))
            self.sl_min.setValue(float(getattr(item, "min_value", 0.0)))
            self.sl_max.setValue(float(getattr(item, "max_value", 1.0)))
            self.sl_val.setValue(float(getattr(item, "value", 0.0)))
            self.sl_handle_scale.setValue(float(getattr(item, "handle_scale", 1.0)))
            hc = getattr(item, "handle_color", "#bfbfbf")
            if isinstance(hc, QtGui.QColor): hc = hc.name(QtGui.QColor.HexArgb)
            self.sl_handle_color.setText(hc)
        
        elif shape_type == "Pose":
            import os
            self.po_inside_text.setChecked(bool(getattr(item, "inside_text", False)))
            self.po_shape.setCurrentText(getattr(item, "pose_shape", "Rectangle"))
            self.po_scale.setCurrentText(getattr(item, "pose_scale_mode", "Fit"))
            self.po_pad.setValue(float(getattr(item, "pose_padding", 0.0)))
            self.po_rad.setValue(float(getattr(item, "pose_roundness", 8.0)))
            
            # Show/Hide Round Rect properties dynamically
            self.po_rr_group.setVisible(self.po_shape.currentText() == "Round Rectangle")
            
            if len(items) > 1: 
                self.po_img_preview.setText("Multiple Shapes")
                self.po_img_path.setText("<Multiple Shapes Selected>")
            else:
                img_path = getattr(item, "image_path", "")
                if img_path:
                    import os
                    # FIX: Safely retrieve the path from the parent PickerWindow!
                    main_win = self.parentWidget()
                    base = getattr(main_win, "image_base_dir", "")
                    full_path = img_path if os.path.isabs(img_path) else os.path.join(base, img_path)
                    
                    self.po_img_path.setText(full_path)
                    
                    if os.path.exists(full_path):
                        pixmap = QtGui.QPixmap(full_path)
                        if not pixmap.isNull():
                            self.po_img_preview.setPixmap(pixmap.scaled(180, 120, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                        else: 
                            self.po_img_preview.setText("Invalid Image")
                    else:
                        self.po_img_preview.setText("Image Not Found")
                else: 
                    self.po_img_preview.setText("No Image")
                    self.po_img_path.setText("")
            
            self.po_ctrl_list.clear()
            self.po_attr_list.clear()
            self.po_ctrl_list.addItems(list(getattr(item, "pose_data", {}).keys()))
        
        elif shape_type == "Checkbox":
            self.cb_show_mark.blockSignals(True)
            self.cb_show_mark.setChecked(bool(getattr(item, "show_mark", True)))
            self.cb_show_mark.blockSignals(False)
            
            self.cb_inside_text.setChecked(bool(getattr(item, "inside_text", False)))
            self.cb_shape.setCurrentText(getattr(item, "cb_shape", "Rectangle"))
            self.cb_rad.setValue(float(getattr(item, "cb_roundness", 8.0)))
            self.cb_rr_group.setVisible(self.cb_shape.currentText() == "Round Rectangle")
            
            mc = getattr(item, "mark_color", "#ffffff")
            if isinstance(mc, QtGui.QColor): mc = mc.name()
            self.cb_mark_col.set_color(mc)
            
            data = getattr(item, "cb_data", {})
            d_on = data.get("ON", {})
            d_off = data.get("OFF", {})
            
            self.cb_on_txt.blockSignals(True); self.cb_on_txt.setText(d_on.get("text", "ON")); self.cb_on_txt.blockSignals(False)
            self.cb_off_txt.blockSignals(True); self.cb_off_txt.setText(d_off.get("text", "OFF")); self.cb_off_txt.blockSignals(False)
            self.cb_on_col.set_color(d_on.get("color", "#4d8c90"))
            self.cb_off_col.set_color(d_off.get("color", "#3c6e71"))
            
            # Populate Command Scripts
            self.cb_on_cmd_type.blockSignals(True); self.cb_on_cmd_type.setCurrentText(d_on.get("cmd_type", "python")); self.cb_on_cmd_type.blockSignals(False)
            self.cb_on_cmd_txt.blockSignals(True); self.cb_on_cmd_txt.setText(d_on.get("command", "")); self.cb_on_cmd_txt.blockSignals(False)
            self.cb_off_cmd_type.blockSignals(True); self.cb_off_cmd_type.setCurrentText(d_off.get("cmd_type", "python")); self.cb_off_cmd_type.blockSignals(False)
            self.cb_off_cmd_txt.blockSignals(True); self.cb_off_cmd_txt.setText(d_off.get("command", "")); self.cb_off_cmd_txt.blockSignals(False)
            
            self.cb_on_attr.clear()
            for k, v in d_on.get("attributes", {}).items():
                v_str = str(round(v, 4)) if isinstance(v, float) else str(v)
                self.cb_on_attr.addItem(f"{k}: {v_str}")
            self.cb_off_attr.clear()
            for k, v in d_off.get("attributes", {}).items():
                v_str = str(round(v, 4)) if isinstance(v, float) else str(v)
                self.cb_off_attr.addItem(f"{k}: {v_str}")
                
            self.cb_on_shape.clear()
            for s in d_on.get("shapes", []):
                lbl = s.split("::")[-1].strip()
                li = QtWidgets.QListWidgetItem(lbl if lbl else f"Unnamed ({s.split('::')[0][:6]})")
                li.setData(QtCore.Qt.UserRole, s)
                self.cb_on_shape.addItem(li)
            self.cb_off_shape.clear()
            for s in d_off.get("shapes", []):
                lbl = s.split("::")[-1].strip()
                li = QtWidgets.QListWidgetItem(lbl if lbl else f"Unnamed ({s.split('::')[0][:6]})")
                li.setData(QtCore.Qt.UserRole, s)
                self.cb_off_shape.addItem(li)
        
        elif shape_type == "Image":
            self.img_opacity.setValue(int(getattr(item, "image_opacity", 1.0) * 100))
            self.img_scale.setCurrentText(getattr(item, "image_scale_mode", "Fit"))
            
            if len(items) > 1: 
                self.img_img_preview.setText("Multiple Shapes")
                self.img_img_path.setText("<Multiple Shapes Selected>")
            else:
                img_path = getattr(item, "image_path", "")
                if img_path:
                    import os
                    main_win = self.parentWidget()
                    base = getattr(main_win, "image_base_dir", "")
                    full_path = img_path if os.path.isabs(img_path) else os.path.join(base, img_path)
                    
                    self.img_img_path.setText(full_path)
                    if os.path.exists(full_path):
                        pixmap = QtGui.QPixmap(full_path)
                        if not pixmap.isNull():
                            self.img_img_preview.setPixmap(pixmap.scaled(180, 120, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                        else: self.img_img_preview.setText("Invalid Image")
                    else: self.img_img_preview.setText("Image Not Found")
                else: 
                    self.img_img_preview.setText("No Image")
                    self.img_img_path.setText("")
        
        self._block_all(False)
        self._is_populating = False

    def _push_undo_from_editor(self):
        win = self.parentWidget()
        if not win: 
            win = self.window()
        if win and hasattr(win, "menu_action_requested"):
            win.menu_action_requested.emit("push_undo")

    def _on_live_change(self, *args):
        if self._is_populating: return
        sender = self.sender()
        if not sender: return

        # --- PROCEED WITH NORMAL SHAPE DATA ---
        if not getattr(self, "target_items", None): return

        # If an anchor button is turning OFF, ignore its signal entirely!
        if getattr(self, "anchor_btns", None) and sender in self.anchor_btns.buttons():
            if not sender.isChecked(): return

        for item in self.target_items:
            if hasattr(item, "prepareGeometryChange"): item.prepareGeometryChange()
            
            # --- Ensure dictionaries exist safely before applying ---
            if not hasattr(item, "bg"): item.bg = {}
            if not hasattr(item, "edge_color"): item.edge_color = {}
            if not hasattr(item, "text_color"): item.text_color = {}
            if not hasattr(item, "edge_thickness") or not isinstance(item.edge_thickness, dict): 
                item.edge_thickness = {"normal": 1.5, "hover": 2.0, "press": 1.5}

            # --- Target only the modified property ---
            if sender == self.label_edit: item.label = self.label_edit.text()
            
            elif sender == self.pos_x: item.setPos(self.pos_x.value(), item.pos().y())
            elif sender == self.pos_y: item.setPos(item.pos().x(), self.pos_y.value())
            elif sender == self.geo_r: item.setRotation(self.geo_r.value())
            elif sender == self.geo_w: 
                item.width = self.geo_w.value()
                if hasattr(item, "setRect"): item.setRect(-item.width/2.0, -item.height/2.0, item.width, item.height)
            elif sender == self.geo_h: 
                item.height = self.geo_h.value()
                if hasattr(item, "setRect"): item.setRect(-item.width/2.0, -item.height/2.0, item.width, item.height)

            elif sender == self.bg_n: item.bg["normal"] = self.bg_n.text()
            elif sender == self.bg_h: item.bg["hover"] = self.bg_h.text()
            elif sender == self.bg_p: item.bg["press"] = self.bg_p.text()

            elif sender == self.chk_edge: item.edge_visible = self.chk_edge.isChecked()
            elif sender == self.edg_n: item.edge_color["normal"] = self.edg_n.text()
            elif sender == self.edg_h: item.edge_color["hover"] = self.edg_h.text()
            elif sender == self.edg_p: item.edge_color["press"] = self.edg_p.text()

            elif sender == self.eth_n: item.edge_thickness["normal"] = self.eth_n.value()
            elif sender == self.eth_h: item.edge_thickness["hover"] = self.eth_h.value()
            elif sender == self.eth_p: item.edge_thickness["press"] = self.eth_p.value()

            elif sender == self.font_size: item.font_point_size = self.font_size.value()
            elif sender == self.chk_bold: item.font_bold = self.chk_bold.isChecked()
            elif sender == self.chk_italic: item.font_italic = self.chk_italic.isChecked()
            elif sender == self.align_h: item.text_align_h = self.align_h.currentText()
            elif sender == self.align_v: item.text_align_v = self.align_v.currentText()

            elif sender == self.txt_n: item.text_color["normal"] = self.txt_n.text()
            elif sender == self.txt_h: item.text_color["hover"] = self.txt_h.text()
            elif sender == self.txt_p: item.text_color["press"] = self.txt_p.text()

            elif sender == self.chk_movable: 
                item.movable_edit = self.chk_movable.isChecked()
                item.locked_edit = not item.movable_edit
                item.locked = not item.movable_edit
                # Instantly apply flags dynamically through the Canvas
                if hasattr(item, "scene") and item.scene() and item.scene().views():
                    if hasattr(item.scene().views()[0], "update_item_flags"):
                        item.scene().views()[0].update_item_flags(item)
            
            elif sender == self.cmb_mode:
                item.placement_mode = self.cmb_mode.currentText()
                self.grp_anchor.setVisible(item.placement_mode == "screen")
                if hasattr(item, "scene") and item.scene():
                    canvas = item.scene().views()[0]
                    if item.placement_mode == "screen":
                        # When switching to screen, capture its current location as the starting offset!
                        vp_pt = canvas.mapFromScene(item.pos())
                        vp_size = canvas.viewport().size()
                        w, h = vp_size.width(), vp_size.height()
                        
                        ax, ay = w / 2.0, h / 2.0
                        if "left" in getattr(item, "screen_anchor", "center"): ax = 0
                        elif "right" in getattr(item, "screen_anchor", "center"): ax = w
                        if "top" in getattr(item, "screen_anchor", "center"): ay = 0
                        elif "bottom" in getattr(item, "screen_anchor", "center"): ay = h
                        
                        item.screen_offset_px = [vp_pt.x() - ax, vp_pt.y() - ay]
                    
                    if hasattr(canvas, "update_screen_items"):
                        canvas.update_screen_items()
            
            elif sender in self.anchor_btns.buttons():
                item.screen_anchor = sender.property("anchor_name")
                if hasattr(item, "scene") and item.scene():
                    canvas = item.scene().views()[0]
                    # Recalculate offset so it doesn't jump across the screen!
                    vp_pt = canvas.mapFromScene(item.pos())
                    px, py = vp_pt.x(), vp_pt.y()
                    
                    vp_size = canvas.viewport().size()
                    w, h = vp_size.width(), vp_size.height()
                    ax, ay = w / 2.0, h / 2.0
                    if "left" in item.screen_anchor: ax = 0
                    elif "right" in item.screen_anchor: ax = w
                    if "top" in item.screen_anchor: ay = 0
                    elif "bottom" in item.screen_anchor: ay = h
                    
                    item.screen_offset_px = [px - ax, py - ay]
                    if hasattr(canvas, "update_screen_items"):
                        canvas.update_screen_items()
            
            elif sender == self.chk_sel_pose: item.selectable_pose = self.chk_sel_pose.isChecked()

            elif sender in [self.rad_tl, self.rad_tr, self.rad_bl, self.rad_br] and item.shape_name == "Round Rectangle":
                item.rad_tl = self.rad_tl.value()
                item.rad_tr = self.rad_tr.value()
                item.rad_bl = self.rad_bl.value()
                item.rad_br = self.rad_br.value()
            
            elif item.shape_name == "Slider":
                if sender == self.sl_attr: item.attribute = self.sl_attr.text()
                elif sender == self.sl_inside_text: item.inside_text = self.sl_inside_text.isChecked()
                elif sender == self.sl_min: item.min_value = self.sl_min.value()
                elif sender == self.sl_max: item.max_value = self.sl_max.value()
                elif sender == self.sl_val: item.value = self.sl_val.value()
                elif sender == self.sl_handle_scale: item.handle_scale = self.sl_handle_scale.value()
                elif sender == self.sl_handle_color: item.handle_color = QtGui.QColor(self.sl_handle_color.text())
            
            elif item.shape_name == "Pose":
                if sender == self.po_inside_text: item.inside_text = self.po_inside_text.isChecked()
                elif sender == self.po_shape: 
                    item.pose_shape = self.po_shape.currentText()
                    self.po_rr_group.setVisible(item.pose_shape == "Round Rectangle")
                elif sender == self.po_scale: item.pose_scale_mode = self.po_scale.currentText()
                elif sender == self.po_pad: item.pose_padding = self.po_pad.value()
                elif sender == self.po_rad: item.pose_roundness = self.po_rad.value()
            
            elif item.shape_name == "Checkbox":
                if sender == self.cb_show_mark: item.show_mark = self.cb_show_mark.isChecked()
                elif sender == self.cb_inside_text: item.inside_text = self.cb_inside_text.isChecked()
                elif sender == self.cb_mark_col: item.mark_color = self.cb_mark_col.color_hex
                elif sender == self.cb_shape:
                    item.cb_shape = self.cb_shape.currentText()
                    self.cb_rr_group.setVisible(item.cb_shape == "Round Rectangle")
                elif sender == self.cb_rad: item.cb_roundness = self.cb_rad.value()
                elif not hasattr(item, "cb_data"): return
                elif sender == self.cb_on_txt: item.cb_data["ON"]["text"] = self.cb_on_txt.text()
                elif sender == self.cb_off_txt: item.cb_data["OFF"]["text"] = self.cb_off_txt.text()
                elif sender == self.cb_on_col: item.cb_data["ON"]["color"] = self.cb_on_col.color_hex
                elif sender == self.cb_off_col: item.cb_data["OFF"]["color"] = self.cb_off_col.color_hex
                elif sender == self.cb_on_cmd_type: item.cb_data["ON"]["cmd_type"] = self.cb_on_cmd_type.currentText()
                elif sender == self.cb_on_cmd_txt: item.cb_data["ON"]["command"] = self.cb_on_cmd_txt.toPlainText()
                elif sender == self.cb_off_cmd_type: item.cb_data["OFF"]["cmd_type"] = self.cb_off_cmd_type.currentText()
                elif sender == self.cb_off_cmd_txt: item.cb_data["OFF"]["command"] = self.cb_off_cmd_txt.toPlainText()
            
            elif item.shape_name == "Image":
                if sender == self.img_opacity: item.image_opacity = self.img_opacity.value() / 100.0
                elif sender == self.img_scale: item.image_scale_mode = self.img_scale.currentText()
            
            item.update()

        self._undo_timer.start()

    def _on_hier_action_select(self):
        if not getattr(self, "target_items", None) or not self.target_items[0].scene(): return
        scene = self.target_items[0].scene()
        all_shapes = {i.item_id: i for i in scene.items() if hasattr(i, "item_id")}
        to_select = set(self.target_items)
        
        def get_children(shape):
            for cid in getattr(shape, "child_links", []):
                child = all_shapes.get(cid)
                if child and child not in to_select:
                    to_select.add(child)
                    get_children(child)
        
        for item in self.target_items: get_children(item)
        scene.clearSelection()
        for item in to_select: item.setSelected(True)

    def _on_hier_action_remove(self):
        for sel in self.hier_list.selectedItems():
            data = sel.data(QtCore.Qt.UserRole)
            if not data: continue
            rel_type, source_item, target_item = data
            
            if target_item.item_id in source_item.parent_links: source_item.parent_links.remove(target_item.item_id)
            if target_item.item_id in source_item.child_links: source_item.child_links.remove(target_item.item_id)
            if source_item.item_id in target_item.parent_links: target_item.parent_links.remove(source_item.item_id)
            if source_item.item_id in target_item.child_links: target_item.child_links.remove(source_item.item_id)
            
            source_item.update(); target_item.update()
        
        if self.target_items and self.target_items[0].scene():
            self.target_items[0].scene().views()[0].viewport().update()
            self.set_target_items(self.target_items)
        self._push_undo_from_editor()

    def _on_hier_action_clear(self):
        if not getattr(self, "target_items", None) or not self.target_items[0].scene(): return
        scene = self.target_items[0].scene()
        all_shapes = [i for i in scene.items() if hasattr(i, "item_id")]
        
        for item in self.target_items:
            for other in all_shapes:
                if item.item_id in getattr(other, "parent_links", []): other.parent_links.remove(item.item_id)
                if item.item_id in getattr(other, "child_links", []): other.child_links.remove(item.item_id)
            item.parent_links = []; item.child_links = []
            item.update()
            
        scene.views()[0].viewport().update()
        self.set_target_items(self.target_items)
        self._push_undo_from_editor()

    #-------------------------------------------------------------------------------#
    # Layer managment
    #-------------------------------------------------------------------------------#

    def _get_canvas(self):
        if getattr(self, "target_items", None) and self.target_items[0].scene():
            return self.target_items[0].scene().views()[0]
            
        # Fallback if nothing is selected:
        main_win = self.parentWidget()
        if not main_win or not hasattr(main_win, "main_tabs"):
            main_win = self.window()
            
        if main_win and hasattr(main_win, "main_tabs"):
            char_tab = main_win.main_tabs.currentWidget()
            if char_tab and hasattr(char_tab, "sub_tabs"):
                sub_tab = char_tab.sub_tabs.currentWidget()
                if sub_tab and hasattr(sub_tab, "canvas"):
                    return sub_tab.canvas
        return None

    def _populate_layers(self):
        self.tree_layers.blockSignals(True)
        self.tree_layers.clear()
        canvas = self._get_canvas()
        if canvas and hasattr(canvas, "layer_data"):
            for layer in canvas.layer_data:
                item = QtWidgets.QTreeWidgetItem([layer["name"]])
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                item.setData(0, QtCore.Qt.UserRole, layer["id"])
                item.setCheckState(1, QtCore.Qt.Checked if layer.get("vis_edit", True) else QtCore.Qt.Unchecked)
                item.setCheckState(2, QtCore.Qt.Checked if layer.get("vis_pose", True) else QtCore.Qt.Unchecked)
                self.tree_layers.addTopLevelItem(item)
        self.tree_layers.blockSignals(False)

    def _on_layer_tree_changed(self, item, column):
        canvas = self._get_canvas()
        if not canvas: return
        layer_id = item.data(0, QtCore.Qt.UserRole)
        for layer in canvas.layer_data:
            if layer["id"] == layer_id:
                if column == 0: layer["name"] = item.text(0)
                elif column == 1: layer["vis_edit"] = (item.checkState(1) == QtCore.Qt.Checked)
                elif column == 2: layer["vis_pose"] = (item.checkState(2) == QtCore.Qt.Checked)
                break
                
        if hasattr(canvas, "apply_layer_visibility"): 
            canvas.apply_layer_visibility()
        self._push_undo_from_editor()

    def _on_layer_create(self):
        canvas = self._get_canvas()
        if not canvas: return
        name = self.le_layer_name.text().strip() or "New Layer"
        import uuid
        new_layer = {
            "id": str(uuid.uuid4()), "name": name,
            "shapes": [s.item_id for s in getattr(self, "target_items", [])],
            "vis_edit": True, "vis_pose": True
        }
        canvas.layer_data.append(new_layer)
        self.le_layer_name.clear()
        self._populate_layers()
        self.set_target_items(getattr(self, "target_items", []))
        self._push_undo_from_editor()

    def _on_layer_add_sel(self):
        canvas = self._get_canvas(); sel_layer = self.tree_layers.currentItem()
        if not canvas or not sel_layer or not getattr(self, "target_items", None): return
        l_id = sel_layer.data(0, QtCore.Qt.UserRole)
        for layer in canvas.layer_data:
            if layer["id"] == l_id:
                for s in self.target_items:
                    if s.item_id not in layer["shapes"]: layer["shapes"].append(s.item_id)
                break
        self._populate_layers()
        self._push_undo_from_editor()

    def _on_layer_rem_sel(self):
        canvas = self._get_canvas(); sel_layer = self.tree_layers.currentItem()
        if not canvas or not sel_layer or not getattr(self, "target_items", None): return
        l_id = sel_layer.data(0, QtCore.Qt.UserRole)
        for layer in canvas.layer_data:
            if layer["id"] == l_id:
                layer["shapes"] = [sid for sid in layer["shapes"] if sid not in [s.item_id for s in self.target_items]]
                break
        self._populate_layers()
        self._push_undo_from_editor()

    def _on_layer_del(self):
        canvas = self._get_canvas(); sel_layer = self.tree_layers.currentItem()
        if not canvas or not sel_layer: return
        l_id = sel_layer.data(0, QtCore.Qt.UserRole)
        
        # --- FIX: Reset visibility of shapes before deleting the layer ---
        layer_to_delete = next((l for l in canvas.layer_data if l["id"] == l_id), None)
        if layer_to_delete:
            for item in canvas.scene.items():
                if hasattr(item, "item_id") and item.item_id in layer_to_delete.get("shapes", []):
                    item.setVisible(True)
        # -----------------------------------------------------------------
        
        canvas.layer_data = [l for l in canvas.layer_data if l["id"] != l_id]
        self._populate_layers()
        self._push_undo_from_editor()

    def _show_layer_context_menu(self, pos):
        item = self.tree_layers.itemAt(pos)
        if not item: return
        
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu { background: #2b2b2b; color: #dfdfdf; border: 1px solid #555; } QMenu::item:selected { background: #5285a6; }")
        
        act_ren = menu.addAction("Rename Layer")
        menu.addSeparator()
        act_sel = menu.addAction("Select Layer Contents")
        act_iso = menu.addAction("Isolate Layer (Solo)")
        menu.addSeparator()
        act_clr = menu.addAction("Clear Contents")
        
        action = getattr(menu, "exec", menu.exec_)(self.tree_layers.viewport().mapToGlobal(pos))
        
        canvas = self._get_canvas()
        if not canvas or not action: return
        layer_id = item.data(0, QtCore.Qt.UserRole)
        
        if action == act_ren:
            self.tree_layers.editItem(item, 0)
        elif action == act_sel:
            layer = next((l for l in canvas.layer_data if l["id"] == layer_id), None)
            if layer:
                canvas.scene.clearSelection()
                sel_items = []
                for i in canvas.scene.items():
                    if hasattr(i, "item_id") and i.item_id in layer["shapes"]: 
                        i.setSelected(True)
                        sel_items.append(i)
                self.set_target_items(sel_items)
        elif action == act_iso:
            is_edit = getattr(canvas, "is_edit_mode", False)
            for l in canvas.layer_data:
                state = (l["id"] == layer_id)
                if is_edit: l["vis_edit"] = state
                else: l["vis_pose"] = state
            self._populate_layers()
        elif action == act_clr:
            layer = next((l for l in canvas.layer_data if l["id"] == layer_id), None)
            if layer:
                layer["shapes"] = []
                self._populate_layers()
                self.set_target_items(getattr(self, "target_items", []))
    
    #-------------------------------------------------------------------------------#
    # ADVANCED SCRIPTS SYSTEM
    #-------------------------------------------------------------------------------#
    def _get_active_script_list(self):
        if getattr(self, "target_items", None):
            return getattr(self.target_items[0], "scripts", [])
        canvas = self._get_canvas()
        if canvas:
            return getattr(canvas, "canvas_scripts", [])
        return None

    def _populate_scripts(self):
        self.list_scripts.blockSignals(True)
        self.list_scripts.clear()
        
        # Get list from Shape or Canvas
        s_list = None
        if getattr(self, "target_items", None):
            s_list = getattr(self.target_items[0], "scripts", [])
        else:
            canvas = self._get_canvas()
            if canvas:
                s_list = getattr(canvas, "canvas_scripts", [])
        
        if s_list is not None:
            for i, scr in enumerate(s_list):
                item = QtWidgets.QListWidgetItem(f"{scr.get('label', 'Script')} [{scr.get('trigger', 'Context Menu')}]")
                item.setData(QtCore.Qt.UserRole, i)
                self.list_scripts.addItem(item)
        self.list_scripts.blockSignals(False)
        self._on_scr_select()

    def _on_scr_add(self):
        s_list = self._get_active_script_list()
        if s_list is not None:
            s_list.append({"label": "New Script", "command": "", "type": "python", "trigger": "Left Click (Menu)"})
            self._populate_scripts()
            self.list_scripts.setCurrentRow(len(s_list)-1)

    def _on_scr_rem(self):
        s_list = self._get_active_script_list()
        row = self.list_scripts.currentRow()
        if s_list is not None and 0 <= row < len(s_list):
            s_list.pop(row)
            self._populate_scripts()

    def _on_scr_select(self):
        row = self.list_scripts.currentRow()
        s_list = self._get_active_script_list()
        if s_list is not None and 0 <= row < len(s_list):
            scr = s_list[row]
            self.w_sprop.setEnabled(True)
            self.le_scr_name.blockSignals(True)
            self.cb_scr_lang.blockSignals(True)
            self.cb_scr_trig.blockSignals(True)
            self.te_scr_code.blockSignals(True)
            
            self.le_scr_name.setText(scr.get("label", ""))
            self.cb_scr_lang.setCurrentText(scr.get("type", "python"))
            self.cb_scr_trig.setCurrentText(scr.get("trigger", "Context Menu"))
            self.te_scr_code.setPlainText(scr.get("command", ""))
            
            if hasattr(self.te_scr_code, "set_language"):
                self.te_scr_code.set_language(scr.get("type", "python"))
            
            self.le_scr_name.blockSignals(False)
            self.cb_scr_lang.blockSignals(False)
            self.cb_scr_trig.blockSignals(False)
            self.te_scr_code.blockSignals(False)
        else:
            self.w_sprop.setEnabled(False)
            self.le_scr_name.clear()
            self.te_scr_code.clear()

    def _on_cb_expand(self, state):
        from .script_editor import ExpandedScriptEditor
        lang = self.cb_on_cmd_type.currentText() if state == "ON" else self.cb_off_cmd_type.currentText()
        text_widget = self.cb_on_cmd_txt if state == "ON" else self.cb_off_cmd_txt
        
        dialog = ExpandedScriptEditor(self, initial_text=text_widget.toPlainText(), lang=lang)
        if dialog.exec_():
            text_widget.setPlainText(dialog.editor.toPlainText())

    def _on_scr_expand(self):
        from .script_editor import ExpandedScriptEditor
        lang = self.cb_scr_lang.currentText()
        text = self.te_scr_code.toPlainText()
        
        dialog = ExpandedScriptEditor(self, initial_text=text, lang=lang)
        if getattr(dialog, "exec", dialog.exec_)(): # If user clicks 'Apply & Close'
            self.te_scr_code.setPlainText(dialog.editor.toPlainText())

    def _on_scr_live(self, *args):
        if not self.w_sprop.isEnabled(): return # Prevent ghost signals during selection changes
        row = self.list_scripts.currentRow()
        s_list = self._get_active_script_list()
        if s_list is not None and 0 <= row < len(s_list):
            scr = s_list[row]
            scr["label"] = self.le_scr_name.text()
            scr["type"] = self.cb_scr_lang.currentText()
            scr["trigger"] = self.cb_scr_trig.currentText()
            scr["command"] = self.te_scr_code.toPlainText()
            
            if hasattr(self.te_scr_code, "set_language"):
                self.te_scr_code.set_language(scr["type"])
            
            item = self.list_scripts.item(row)
            if item: item.setText(f"{scr['label']} [{scr['trigger']}]")

    def _on_scr_test(self):
        row = self.list_scripts.currentRow()
        s_list = self._get_active_script_list()
        if s_list is not None and 0 <= row < len(s_list):
            scr = s_list[row]
            cmd, cmd_type = scr.get("command", ""), scr.get("type", "python")
            if not cmd.strip(): return
            try:
                if cmd_type == "mel":
                    import maya.mel as mel
                    mel.eval(cmd)
                else:
                    exec(cmd, globals())
            except Exception as e:
                print(f"ASEPicker Script Test Error: {e}")

    #-------------------------------------------------------------------------------#
    # BINARY PRESETS ENGINE
    #-------------------------------------------------------------------------------#
    def refresh_presets(self):
        from .preferences import PrefManager
        pm = PrefManager()
        if hasattr(pm, "load_user_presets"): self.preset_data = pm.load_user_presets()
        else: self.preset_data = {"visuals": [], "commands": [], "shapes": []}
        
        def _pop(grid, items, p_type):
            while grid.count():
                it = grid.takeAt(0)
                if it.widget(): it.widget().deleteLater()
            col_count = 5 if p_type in ["visual", "shape"] else 3
            for i, d in enumerate(items):
                btn = PresetButton(d, p_type, self)
                btn.clicked.connect(lambda checked=False, d2=d, t2=p_type: self.apply_preset(t2, d2))
                grid.addWidget(btn, i // col_count, i % col_count)
                
        _pop(self.p_vis_l, self.preset_data.get("visuals", []), "visual")
        _pop(self.p_cmd_l, self.preset_data.get("commands", []), "command")
        _pop(self.p_shp_l, self.preset_data.get("shapes", []), "shape")

    def save_presets(self):
        from .preferences import PrefManager
        pm = PrefManager()
        if hasattr(pm, "save_user_presets"): pm.save_user_presets(self.preset_data)
        self.refresh_presets()

    def _scrape_preset(self, item, p_type):
        d = {}
        if p_type == "visual":
            for attr in ["bg", "text_color", "edge_color", "edge_thickness"]:
                if hasattr(item, attr):
                    val = getattr(item, attr)
                    if isinstance(val, dict): d[attr] = {k: v.name(QtGui.QColor.HexArgb) if hasattr(v, "name") else str(v) for k, v in val.items()}
                    else: d[attr] = val
            for attr in ["edge_visible", "font_point_size", "font_bold", "font_italic", "text_align_h", "text_align_v"]:
                if hasattr(item, attr): d[attr] = getattr(item, attr)
        elif p_type == "command":
            d["label"] = getattr(item, "label", "Script Preset")
            if hasattr(item, "scripts"):
                import copy
                d["scripts"] = copy.deepcopy(item.scripts)
        elif p_type == "shape":
            d["shape"] = getattr(item, "shape_name", "Rectangle")
            d["w"] = getattr(item, "width", 80); d["h"] = getattr(item, "height", 40)
            for c in ["rad_tl", "rad_tr", "rad_bl", "rad_br"]:
                if hasattr(item, c): d[c] = getattr(item, c)
            if hasattr(item, "path_points"):
                pd = []
                for pt in item.path_points:
                    pd.append({"p": [pt["p"].x(), pt["p"].y()], "in": [pt["in"].x(), pt["in"].y()], "out": [pt["out"].x(), pt["out"].y()], "s": pt.get("s", False)})
                d["path_data"] = pd
        return d

    def add_preset(self, p_type):
        items = getattr(self, "target_items", [])
        if len(items) != 1: return QtWidgets.QMessageBox.warning(self, "Add Preset", "Please select exactly ONE item.")
        
        new_data = self._scrape_preset(items[0], p_type)
        if p_type == "command":
            name, ok = QtWidgets.QInputDialog.getText(self, "Preset Name", "Name:")
            if not ok or not name: return
            new_data["label"] = name
            
        key = f"{p_type}s"
        if key not in self.preset_data: self.preset_data[key] = []
        self.preset_data[key].append(new_data)
        self.save_presets()

    def update_preset(self, p_type, old_data):
        items = getattr(self, "target_items", [])
        if len(items) != 1: return QtWidgets.QMessageBox.warning(self, "Update", "Please select exactly ONE item.")
            
        new_data = self._scrape_preset(items[0], p_type)
        if p_type == "command": new_data["label"] = old_data.get("label", "Cmd")
            
        old_data.clear(); old_data.update(new_data)
        self.save_presets()

    def delete_preset(self, p_type, item_data):
        key = f"{p_type}s"
        if item_data in self.preset_data.get(key, []):
            self.preset_data[key].remove(item_data)
            self.save_presets()

    def apply_preset(self, p_type, data):
        items = getattr(self, "target_items", [])
        if not items: return
        
        from maya import cmds
        try: cmds.undoInfo(openChunk=True, chunkName=f"Apply Preset {p_type}")
        except: pass
        
        for i, item in enumerate(items):
            if p_type == "visual":
                for attr in ["bg", "text_color", "edge_color"]:
                    if attr in data:
                        t_dict = getattr(item, attr, {})
                        for k, v in data[attr].items(): t_dict[k] = str(v)
                if "edge_thickness" in data: item.edge_thickness = data["edge_thickness"].copy() if isinstance(data["edge_thickness"], dict) else data["edge_thickness"]
                for attr in ["edge_visible", "font_point_size", "font_bold", "font_italic", "text_align_h", "text_align_v"]:
                    if attr in data and hasattr(item, attr): setattr(item, attr, data[attr])
            
            elif p_type == "command":
                if "scripts" in data and hasattr(item, "scripts"):
                    import copy
                    item.scripts = copy.deepcopy(data["scripts"])
            
            elif p_type == "shape":
                target_shape_name = data.get("shape", getattr(item, "shape_name", "Rectangle"))
                
                # --- MORPH ENGINE: Safely swap the underlying Qt class! ---
                if getattr(item, "shape_name", "") != target_shape_name:
                    from . import ui
                    class_name = f"Picker{target_shape_name.replace(' ', '')}Item"
                    shape_class = getattr(ui, class_name, None)
                    
                    if shape_class:
                        new_item = shape_class()
                        
                        # Transfer pure python dictionary state (Colors, IDs, Scripts, Hierarchies, Controls)
                        for key, val in item.__dict__.items():
                            if not key.startswith("_"):
                                try:
                                    import copy
                                    setattr(new_item, key, copy.deepcopy(val))
                                except:
                                    setattr(new_item, key, val)
                                    
                        new_item.shape_name = target_shape_name
                        
                        # Transfer Qt scene transform state
                        new_item.setPos(item.pos())
                        new_item.setRotation(item.rotation())
                        new_item.setZValue(item.zValue())
                        
                        # Swap out the physical item in the Graphics Scene
                        scene = item.scene()
                        if scene:
                            scene.removeItem(item)
                            scene.addItem(new_item)
                            new_item.setSelected(True)
                            
                        items[i] = new_item
                        item = new_item # Update local loop reference
                
                # --- Apply standard shape dimensions and points to the item ---
                if hasattr(item, "width") and "w" in data: item.width = float(data["w"])
                if hasattr(item, "height") and "h" in data: item.height = float(data["h"])
                if hasattr(item, "setRect"): item.setRect(-item.width/2.0, -item.height/2.0, item.width, item.height)
                
                for c in ["rad_tl", "rad_tr", "rad_bl", "rad_br"]:
                    if c in data and hasattr(item, c): setattr(item, c, data[c])
                
                if "path_data" in data and hasattr(item, "path_points"):
                    pd = []
                    for d in data["path_data"]:
                        pd.append({"p": QtCore.QPointF(d["p"][0], d["p"][1]), "in": QtCore.QPointF(d["in"][0], d["in"][1]), "out": QtCore.QPointF(d["out"][0], d["out"][1]), "s": d.get("s", False)})
                    item.path_points = pd
                    if hasattr(item, "_calculate_rect"): item._calculate_rect()
            
            if hasattr(item, "update"): item.update()
            
        try: cmds.undoInfo(closeChunk=True)
        except: pass
        
        self.set_target_items(items) # Force Editor to refresh targeting the newly spawned instances
        if items and items[0].scene() and items[0].scene().views():
            items[0].scene().views()[0].viewport().update()

    # ====================================================================
    # IK-FK CHAIN MANAGER LOGIC
    # ====================================================================
    def _get_active_char_tab(self):
        main_win = self.parentWidget() if hasattr(self.parentWidget(), "main_tabs") else self.window()
        if hasattr(main_win, "main_tabs") and main_win.main_tabs.currentWidget():
            return main_win.main_tabs.currentWidget()
        return None

    def _on_tab_changed(self, idx):
        if self.nav_list.item(idx).text() in ["IK - FK", "RIG SETTINGS"]:
            self.refresh_ikfk_manager()

    def refresh_ikfk_manager(self):
        char_tab = self._get_active_char_tab()
        if not char_tab: return
        chains = getattr(char_tab, "ikfk_chains", [])
        self.ikfk_list.blockSignals(True)
        self.ikfk_list.clear()
        for c in chains:
            self.ikfk_list.addItem(c.get("name", "Unnamed Chain"))
        self.ikfk_list.blockSignals(False)
        self.ikfk_grp.setEnabled(False)

    def _ikfk_on_select(self, row):
        if row < 0:
            self.ikfk_grp.setEnabled(False)
            return
        char_tab = self._get_active_char_tab()
        chains = getattr(char_tab, "ikfk_chains", [])
        if row >= len(chains): return
        
        chain = chains[row]
        self.ikfk_name.setText(chain.get("name", ""))
        self.ikfk_ik_val.setValue(chain.get("ik_val", 1.0))
        self.ikfk_fk_val.setValue(chain.get("fk_val", 0.0))
        self.ikfk_sw_node.setText(chain.get("sw_node", ""))
        self.ikfk_sw_attr.setText(chain.get("sw_attr", ""))
        self.ikfk_ik_ctrl.setText(chain.get("ik_ctrl", ""))
        self.ikfk_pv_ctrl.setText(chain.get("pv_ctrl", ""))
        self.ikfk_fk_ctrls.setText(", ".join(chain.get("fk_ctrls", [])))
        self.ikfk_bones.setPlainText(", ".join(chain.get("bones", [])))
        
        self.ikfk_grp.setEnabled(True)

    def _ikfk_add(self):
        char_tab = self._get_active_char_tab()
        if not char_tab: return
        if not hasattr(char_tab, "ikfk_chains"): char_tab.ikfk_chains = []
        new_chain = {
            "name": f"New Chain {len(char_tab.ikfk_chains) + 1}",
            "ik_ctrl": "", "pv_ctrl": "", "sw_node": "", "sw_attr": "", 
            "fk_ctrls": [], "bones": [], "ik_val": 1.0, "fk_val": 0.0
        }
        char_tab.ikfk_chains.append(new_chain)
        self.refresh_ikfk_manager()
        self.ikfk_list.setCurrentRow(len(char_tab.ikfk_chains) - 1)
        self._push_undo_from_editor()

    def _ikfk_del(self):
        row = self.ikfk_list.currentRow()
        if row < 0: return
        char_tab = self._get_active_char_tab()
        if char_tab and hasattr(char_tab, "ikfk_chains"):
            char_tab.ikfk_chains.pop(row)
            self.refresh_ikfk_manager()
            self._push_undo_from_editor()

    def _ikfk_save(self):
        row = self.ikfk_list.currentRow()
        if row < 0: return
        char_tab = self._get_active_char_tab()
        if not char_tab or not hasattr(char_tab, "ikfk_chains"): return
        
        char_tab.ikfk_chains[row] = {
            "name": self.ikfk_name.text(),
            "ik_val": self.ikfk_ik_val.value(),
            "fk_val": self.ikfk_fk_val.value(),
            "ik_ctrl": self.ikfk_ik_ctrl.text(),
            "pv_ctrl": self.ikfk_pv_ctrl.text(),
            "sw_node": self.ikfk_sw_node.text(),
            "sw_attr": self.ikfk_sw_attr.text(),
            "fk_ctrls": [x.strip() for x in self.ikfk_fk_ctrls.text().split(",") if x.strip()],
            "bones": [x.strip() for x in self.ikfk_bones.toPlainText().split(",") if x.strip()]
        }
        self.ikfk_list.item(row).setText(self.ikfk_name.text())
        self._push_undo_from_editor()
        from maya import cmds
        cmds.inViewMessage(amg="Chain Saved Successfully", pos="midCenter", fade=True)

    def _ikfk_auto_joints(self):
        fk_str = self.ikfk_fk_ctrls.text()
        if not fk_str:
            from maya import cmds
            cmds.warning("[ASEPicker] Please add FK Controls first so the script knows where to look.")
            return
            
        fk_list = [x.strip() for x in fk_str.split(",") if x.strip()]
        
        try:
            from .anim import logic_ikfk
            bones = logic_ikfk.auto_find_chain(fk_list)
            
            if bones and len(bones) > 0:
                self.ikfk_bones.setPlainText(", ".join([b.split("|")[-1].split(":")[-1] for b in bones]))
            else:
                from maya import cmds
                cmds.warning("[ASEPicker] Auto-find failed for this rig format. Please select the joints manually and click '+ ADD'.")
        except Exception as e:
            from maya import cmds
            cmds.warning(f"[ASEPicker] Auto-find Error: {e}")
    
    #-------------------------------------------------------------------------------#

    def closeEvent(self, event):
        """Saves Editor position and size exactly when the user clicks the 'X'."""
        from .preferences import PrefManager
        prefs = PrefManager()
        prefs.set("editor_w", self.width())
        prefs.set("editor_h", self.height())
        prefs.set("editor_x", self.x())
        prefs.set("editor_y", self.y())
        super(EditorPanel, self).closeEvent(event)