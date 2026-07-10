# ARTools/editor_panel.py
from PySide6 import QtWidgets, QtGui, QtCore

from .alignment_panel import AlignmentPanel
from .script_editor import ScriptEditorWidget, ExpandedScriptEditor

class ColorPickerWidget(QtWidgets.QWidget):
    colorChanged = QtCore.Signal(str)
    
    def __init__(self, *args, **kwargs):
        parent = kwargs.get("parent", args[1] if len(args) > 1 else None)
        QtWidgets.QWidget.__init__(self, parent)
        self.color_hex = args[0] if args else kwargs.get("color", "#ffffffff")
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

    def pick_color(self, *args, **kwargs):
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
    preset_clicked = QtCore.Signal(str, dict)

    def __init__(self, *args, **kwargs):
        QtWidgets.QPushButton.__init__(self)
        
        data = args[0] if len(args) > 0 else kwargs.get("data")
        preset_type = args[1] if len(args) > 1 else kwargs.get("preset_type")
        editor = args[2] if len(args) > 2 else kwargs.get("editor")
        
        self.data = data
        self.p_type = preset_type
        self.editor = editor
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context)
        self.clicked.connect(self._on_click)
        
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

        if preset_type in ["visual", "shape"]:
            self.setFixedSize(50, 50)
            self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        else:
            self.setMinimumHeight(28)
            self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Fixed)

    def _on_click(self, *args, **kwargs):
        self.preset_clicked.emit(self.p_type, self.data)

    def paintEvent(self, event):
        QtWidgets.QPushButton.paintEvent(self, event)
        if self.p_type == "shape":
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            
            box_size = min(self.width(), self.height()) - 12
            cx, cy = self.width() / 2.0, self.height() / 2.0
            
            shape_name = str(self.data.get("shape", "")).lower()
            
            w, h = float(self.data.get("w", 100)), float(self.data.get("h", 100))
            if w <= 0: w = 1.0
            if h <= 0: h = 1.0
            
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
                    scale = min(box_size / br.width(), box_size / br.height()) if br.width() > 0 and br.height() > 0 else 1.0
                    painter.translate(cx, cy)
                    painter.scale(scale * 0.9, scale * 0.9)
                    painter.translate(-br.center())
                    
                    safe_pen_width = max(1.0, 2.0 / scale) if scale > 0 else 2.0
                    painter.setPen(QtGui.QPen(QtGui.QColor("#ddd"), safe_pen_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
                    painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 30)))
                    painter.drawPath(path)
                    return
            
            aspect = w / h
            if aspect > 1.0:
                draw_w = box_size
                draw_h = box_size / aspect
            else:
                draw_h = box_size
                draw_w = box_size * aspect
                
            draw_rect = QtCore.QRectF(cx - draw_w/2.0, cy - draw_h/2.0, draw_w, draw_h)

            painter.setPen(QtGui.QPen(QtGui.QColor("#ddd"), 2))
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 30)))
            
            if "circle" in shape_name: 
                painter.drawEllipse(draw_rect)
            elif "round" in shape_name:
                sx = draw_rect.width() / w; sy = draw_rect.height() / h; s = min(sx, sy)
                tl, tr, bl, br = [float(self.data.get(k, 0))*s for k in ["rad_tl", "rad_tr", "rad_bl", "rad_br"]]
                path = QtGui.QPainterPath()
                path.moveTo(draw_rect.left() + tl, draw_rect.top())
                path.lineTo(draw_rect.right() - tr, draw_rect.top())
                path.quadTo(draw_rect.right(), draw_rect.top(), draw_rect.right(), draw_rect.top() + tr)
                path.lineTo(draw_rect.right(), draw_rect.bottom() - br)
                path.quadTo(draw_rect.right(), draw_rect.bottom(), draw_rect.right() - br, draw_rect.bottom())
                path.lineTo(draw_rect.left() + bl, draw_rect.bottom())
                path.quadTo(draw_rect.left(), draw_rect.bottom(), draw_rect.left(), draw_rect.bottom() - bl)
                path.lineTo(draw_rect.left(), draw_rect.top() + tl)
                path.quadTo(draw_rect.left(), draw_rect.top(), draw_rect.left() + tl, draw_rect.top())
                path.closeSubpath()
                painter.drawPath(path)
            elif "slider" in shape_name:
                painter.drawLine(draw_rect.left(), draw_rect.center().y(), draw_rect.right(), draw_rect.center().y())
                painter.setBrush(QtGui.QColor("#ddd"))
                painter.drawRoundedRect(QtCore.QRectF(draw_rect.center().x()-5, draw_rect.top(), 10, draw_rect.height()), 2, 2)
            elif "pose" in shape_name:
                painter.drawRect(draw_rect)
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.drawRect(draw_rect.adjusted(3,3,-3,-3))
            else:
                painter.drawRect(draw_rect)
                if "text" in shape_name:
                    painter.setPen(QtGui.QPen(QtGui.QColor("#ddd"), 1))
                    painter.drawText(draw_rect, QtCore.Qt.AlignCenter, "T")

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
        
        act_ren = None
        if self.p_type == "command": act_ren = menu.addAction("Rename Preset")
        act_upd = menu.addAction("Update from Current Selection")
        menu.addSeparator()
        act_del = menu.addAction("Delete Preset")
        
        action = menu.exec_(self.mapToGlobal(pos))
        if not action: return
        
        if action == act_ren: self._rename()
        elif action == act_upd: self.editor.update_preset(self.p_type, self.data)
        elif action == act_del: self.editor.delete_preset(self.p_type, self.data)
        
    def _rename(self, *args, **kwargs):
        new, ok = QtWidgets.QInputDialog.getText(self, "Rename", "Name:", text=self.data.get("label", ""))
        if ok and new:
            self.data["label"] = new
            self.setText(new)
            self.editor.save_presets()

class SmartAddButton(QtWidgets.QPushButton):
    def __init__(self, *args, **kwargs):
        target_field = args[0] if len(args) > 0 else kwargs.get("target_field")
        multi = args[1] if len(args) > 1 else kwargs.get("multi", False)
        attr_mode = args[2] if len(args) > 2 else kwargs.get("attr_mode", False)
        parent = kwargs.get("parent", args[3] if len(args) > 3 else None)
        
        QtWidgets.QPushButton.__init__(self, "ADD", parent)
        self.setFixedWidth(50)
        self.target_field = target_field
        self.multi = multi
        self.attr_mode = attr_mode
        self.clicked.connect(self._on_click)

    def _on_click(self, *args, **kwargs):
        from maya import cmds
        from . import api
        from . import main
        
        # --- Handle Attribute Mode Properly! ---
        if getattr(self, "attr_mode", False):
            objs = cmds.ls(selection=True) or []
            cb_attrs = cmds.channelBox('mainChannelBox', q=True, selectedMainAttributes=True) or []
            if not objs or not cb_attrs:
                cmds.warning("[ARTools] Please select a control and an attribute.")
                return
            
            # Extract the core controller name and strip only the namespace
            core_instance = main._app_instance.core
            active_ns = api.get_namespace()
            clean_node = core_instance.strip_namespace_for_save(objs[0], active_ns)
            
            # Combine back into a reliable node.attribute path string
            full_path = f"{clean_node}.{cb_attrs[0]}"
            
            self.target_field.setText(full_path)
            self.target_field.editingFinished.emit()
            return
        
        sel = cmds.ls(sl=True)
        if not sel: return

        active_ns = api.get_namespace()
        processed_sel = []
        core_instance = main._app_instance.core
        
        for item in sel:
            clean_item = core_instance.strip_namespace_for_save(item, active_ns)
            processed_sel.append(clean_item)
        
        if getattr(self, "multi", False):
            self.target_field.setText(", ".join(processed_sel))
        else:
            self.target_field.setText(processed_sel[0])
            
        self.target_field.editingFinished.emit()

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
        
        aw = QtWidgets.QWidget(); al = QtWidgets.QVBoxLayout(aw); al.setContentsMargins(0,0,0,0)
        al.addWidget(QtWidgets.QLabel("Attributes:"))
        a_lst = QtWidgets.QListWidget()
        a_btn = QtWidgets.QHBoxLayout()
        a_add = QtWidgets.QPushButton("Add"); a_add.setStyleSheet("background-color: #2e5c3a;")
        a_rem = QtWidgets.QPushButton("Rem"); a_rem.setStyleSheet("background-color: #6b2e2e;")
        a_clr = QtWidgets.QPushButton("Clr"); a_clr.setStyleSheet("background-color: #6b2e2e;")
        a_btn.addWidget(a_add); a_btn.addWidget(a_rem); a_btn.addWidget(a_clr)
        al.addWidget(a_lst); al.addLayout(a_btn); split.addWidget(aw)

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

    def __init__(self, *args, **kwargs):
        QtWidgets.QWidget.__init__(self, *args, **kwargs)
        self.setWindowTitle("ARTools Live Editor")
        self.setMinimumWidth(380)
        
        self.target_items = []
        self._is_populating = False
        self._undo_timer = QtCore.QTimer()
        self._undo_timer.setSingleShot(True)
        self._undo_timer.setInterval(600)
        self._undo_timer.timeout.connect(self._push_undo_from_editor)
        
        self._setup_ui()
        self._bind_live_events()
        
        from .preferences import PrefManager
        prefs = PrefManager()
        self.resize(prefs.get("editor_w"), prefs.get("editor_h"))
        ex, ey = prefs.get("editor_x"), prefs.get("editor_y")
        
        if ex != -9999 and ey != -9999:
            safe_ey = max(50, ey)
            def _move_window(): self.move(ex, safe_ey)
            QtCore.QTimer.singleShot(0, _move_window)

    def get_scale(self):
        return 1.0
    
    def _setup_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)

        try:
            self.alignment_panel = AlignmentPanel()      # <--- 0 arguments
            self.alignment_panel.setParent(self)         # <--- Assign parent safely
            self.alignment_panel.action_requested.connect(self._route_alignment)
            self.main_layout.addWidget(self.alignment_panel)
        except Exception as e:
            print(f"ARTools: Could not load AlignmentPanel - {e}")

        id_lay = QtWidgets.QHBoxLayout()
        id_lay.addWidget(QtWidgets.QLabel("Shape ID:"))
        self.shape_id_edit = QtWidgets.QLineEdit()
        self.shape_id_edit.setReadOnly(True)
        self.shape_id_edit.setStyleSheet("background-color: #1a1a1a; color: #777; border: 1px solid #333; border-radius: 3px;")
        id_lay.addWidget(self.shape_id_edit)
        self.main_layout.addLayout(id_lay)

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

        # PRESETS TAB
        t_preset = QtWidgets.QWidget(); l_preset = QtWidgets.QVBoxLayout(t_preset)
        l_preset.setContentsMargins(4, 4, 4, 4)
        
        self.preset_tabs = QtWidgets.QTabWidget()
        
        self.p_vis_sc = QtWidgets.QScrollArea(); self.p_vis_sc.setWidgetResizable(True); self.p_vis_sc.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.p_vis_w = QtWidgets.QWidget(); self.p_vis_l = QtWidgets.QGridLayout(self.p_vis_w); self.p_vis_l.setAlignment(QtCore.Qt.AlignTop)
        self.p_vis_sc.setWidget(self.p_vis_w); self.preset_tabs.addTab(self.p_vis_sc, "Visuals")
        
        self.p_cmd_sc = QtWidgets.QScrollArea(); self.p_cmd_sc.setWidgetResizable(True); self.p_cmd_sc.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.p_cmd_w = QtWidgets.QWidget(); self.p_cmd_l = QtWidgets.QGridLayout(self.p_cmd_w); self.p_cmd_l.setAlignment(QtCore.Qt.AlignTop)
        self.p_cmd_sc.setWidget(self.p_cmd_w); self.preset_tabs.addTab(self.p_cmd_sc, "Scripts")
        
        self.p_shp_sc = QtWidgets.QScrollArea(); self.p_shp_sc.setWidgetResizable(True); self.p_shp_sc.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.p_shp_w = QtWidgets.QWidget(); self.p_shp_l = QtWidgets.QGridLayout(self.p_shp_w); self.p_shp_l.setAlignment(QtCore.Qt.AlignTop)
        self.p_shp_sc.setWidget(self.p_shp_w); self.preset_tabs.addTab(self.p_shp_sc, "Shapes")
        
        l_preset.addWidget(self.preset_tabs)
        
        h_pbtn = QtWidgets.QHBoxLayout()
        btn_add_vis = QtWidgets.QPushButton("+ Visual"); btn_add_cmd = QtWidgets.QPushButton("+ Script"); btn_add_shp = QtWidgets.QPushButton("+ Shape")
        
        btn_add_vis.setProperty("p_type", "visual"); btn_add_vis.clicked.connect(self._on_add_preset_click)
        btn_add_cmd.setProperty("p_type", "command"); btn_add_cmd.clicked.connect(self._on_add_preset_click)
        btn_add_shp.setProperty("p_type", "shape"); btn_add_shp.clicked.connect(self._on_add_preset_click)
        
        h_pbtn.addWidget(btn_add_vis); h_pbtn.addWidget(btn_add_cmd); h_pbtn.addWidget(btn_add_shp)
        l_preset.addLayout(h_pbtn)
        
        self._add_page("PRESETS", t_preset)
        if hasattr(self, "refresh_presets"): self.refresh_presets()

        # THE MEGA-TAB
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        t_mega = QtWidgets.QWidget(); l_mega = QtWidgets.QVBoxLayout(t_mega)

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

        g_col = QtWidgets.QGroupBox("Colors"); l_col = QtWidgets.QFormLayout(g_col)
        self.bg_n = ColorPickerWidget(); self.bg_h = ColorPickerWidget(); self.bg_p = ColorPickerWidget()
        l_col.addRow("Normal:", self.bg_n); l_col.addRow("Hover:", self.bg_h); l_col.addRow("Press:", self.bg_p)
        l_mega.addWidget(g_col)

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

        # FLAGS TAB
        t_st = QtWidgets.QWidget(); l_st = QtWidgets.QVBoxLayout(t_st)
        
        mode_lay = QtWidgets.QHBoxLayout()
        mode_lay.addWidget(QtWidgets.QLabel("Item Mode:"))
        self.cmb_mode = QtWidgets.QComboBox()
        self.cmb_mode.addItems(["world", "screen"])
        mode_lay.addWidget(self.cmb_mode)
        mode_lay.addStretch()
        l_st.addLayout(mode_lay)
        
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
            btn.toggled.connect(self._on_live_bool) 
            
            self.anchor_btns.addButton(btn)
            grid_lay.addWidget(btn, r, c, QtCore.Qt.AlignCenter)
        
        l_st.addWidget(self.grp_anchor)
        
        self.chk_movable = QtWidgets.QCheckBox("Movable (Edit)")
        self.chk_sel_pose = QtWidgets.QCheckBox("Selectable in Pose Mode")
        
        l_st.addWidget(self.chk_movable)
        l_st.addWidget(self.chk_sel_pose)

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
        
        self.hier_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.btn_hier_sel_chain.clicked.connect(self._on_hier_action_select)
        self.btn_hier_rem_link.clicked.connect(self._on_hier_action_remove)
        self.btn_hier_clear_all.clicked.connect(self._on_hier_action_clear)
        
        l_hier.addWidget(self.hier_list)
        l_hier.addLayout(btn_hier_lay)
        l_st.addWidget(self.grp_hier)

        l_st.addStretch()
        self._add_page("FLAGS", t_st)

        # SCRIPTS TAB
        t_scripts = QtWidgets.QWidget()
        l_scripts = QtWidgets.QHBoxLayout(t_scripts)
        l_scripts.setContentsMargins(4, 4, 4, 4)

        self.scripts_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        w_slst = QtWidgets.QWidget()
        l_slst = QtWidgets.QVBoxLayout(w_slst)
        l_slst.setContentsMargins(0,0,0,0)
        
        self.list_scripts = QtWidgets.QListWidget()
        
        # --- Enable Drag & Drop Reordering ---
        self.list_scripts.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.list_scripts.model().rowsMoved.connect(self._on_scr_drag_drop)
        
        h_sbtn = QtWidgets.QHBoxLayout()
        self.btn_scr_add = QtWidgets.QPushButton("+ Add")
        self.btn_scr_rem = QtWidgets.QPushButton("- Rem")
        self.btn_scr_up = QtWidgets.QPushButton("▲")
        self.btn_scr_dn = QtWidgets.QPushButton("▼")
        self.btn_scr_up.setMaximumWidth(30)
        self.btn_scr_dn.setMaximumWidth(30)
        
        h_sbtn.addWidget(self.btn_scr_add)
        h_sbtn.addWidget(self.btn_scr_rem)
        h_sbtn.addWidget(self.btn_scr_up)
        h_sbtn.addWidget(self.btn_scr_dn)
        
        # --- Separator Button ---
        self.btn_scr_sep = QtWidgets.QPushButton("➕ Add Separator")
        self.btn_scr_sep.setStyleSheet("background-color: #2b3a42; color: #88aebb; border: 1px dashed #444;")

        l_slst.addWidget(QtWidgets.QLabel("Assigned Scripts:"))
        l_slst.addWidget(self.list_scripts)
        l_slst.addLayout(h_sbtn)
        l_slst.addWidget(self.btn_scr_sep)
        self.scripts_split.addWidget(w_slst)

        self.w_sprop = QtWidgets.QWidget()
        l_sprop = QtWidgets.QVBoxLayout(self.w_sprop)
        l_sprop.setContentsMargins(4,0,0,0)

        f_sprop = QtWidgets.QFormLayout()
        self.le_scr_name = QtWidgets.QLineEdit()
        self.cb_scr_lang = QtWidgets.QComboBox()
        self.cb_scr_lang.addItems(["python", "mel"])
        self.cb_scr_trig = QtWidgets.QComboBox()
        self.cb_scr_trig.addItems(["Left Click (Menu)", "Left Click (Action)", "Right Click (Menu)", "Right Click (Action)", "On Value Change"])

        self.chk_scr_checkable = QtWidgets.QCheckBox("Checkable")
        self.chk_scr_checkable.setStyleSheet("color: #A0B0BA; font-weight: bold;")
        
        type_lay = QtWidgets.QHBoxLayout()
        type_lay.setContentsMargins(0, 0, 0, 0)
        type_lay.addWidget(self.cb_scr_lang)
        type_lay.addWidget(self.chk_scr_checkable)

        # --- NEW LINKED ATTR FIELD ---
        self.w_scr_attr = QtWidgets.QWidget()
        l_scr_attr = QtWidgets.QHBoxLayout(self.w_scr_attr)
        l_scr_attr.setContentsMargins(0,0,0,0)
        self.le_scr_attr = QtWidgets.QLineEdit()
        self.le_scr_attr.setPlaceholderText("e.g. L_arm.visibility")
        self.btn_scr_attr_add = SmartAddButton(self.le_scr_attr, attr_mode=True)
        l_scr_attr.addWidget(self.le_scr_attr)
        l_scr_attr.addWidget(self.btn_scr_attr_add)

        f_sprop.addRow("Label:", self.le_scr_name)
        f_sprop.addRow("Type:", type_lay)
        f_sprop.addRow("Linked Attr:", self.w_scr_attr)
        self.w_scr_attr.setVisible(False)
        f_sprop.addRow("Trigger:", self.cb_scr_trig)

        self.te_scr_code = ScriptEditorWidget()
        self.btn_scr_test = QtWidgets.QPushButton("Test Script (Run)")
        self.btn_scr_test.setStyleSheet("background-color: #3a5f43; font-weight: bold;")

        l_sprop.addLayout(f_sprop)
        
        lbl_lay = QtWidgets.QHBoxLayout()
        lbl_lay.addWidget(QtWidgets.QLabel("Code Output:"))
        lbl_lay.addStretch()
        self.btn_scr_expand = QtWidgets.QPushButton("⛶ Expand")
        self.btn_scr_expand.setToolTip("Open script in a larger standalone window")
        lbl_lay.addWidget(self.btn_scr_expand)
        l_sprop.addLayout(lbl_lay)
        
        l_sprop.addWidget(self.te_scr_code)
        l_sprop.addWidget(self.btn_scr_test)

        self.w_sprop.setEnabled(False)
        self.scripts_split.addWidget(self.w_sprop)
        self.scripts_split.setSizes([120, 250])

        l_scripts.addWidget(self.scripts_split)
        
        self.btn_scr_add.clicked.connect(self._on_scr_add)
        self.btn_scr_rem.clicked.connect(self._on_scr_rem)
        self.btn_scr_sep.clicked.connect(self._on_scr_add_sep) 
        self.btn_scr_up.clicked.connect(self._on_scr_move_up)
        self.btn_scr_dn.clicked.connect(self._on_scr_move_dn)
        self.list_scripts.itemSelectionChanged.connect(self._on_scr_select)
        self.btn_scr_test.clicked.connect(self._on_scr_test)
        self.btn_scr_expand.clicked.connect(self._on_scr_expand)
        
        self.chk_scr_checkable.toggled.connect(self.w_scr_attr.setVisible)
        self.le_scr_attr.textEdited.connect(self._on_scr_live_str)
        self.le_scr_attr.editingFinished.connect(self._on_scr_live_str)
        self.le_scr_name.textEdited.connect(self._on_scr_live_str)
        self.cb_scr_lang.currentTextChanged.connect(self._on_scr_live_str)
        self.cb_scr_trig.currentTextChanged.connect(self._on_scr_live_str)
        self.te_scr_code.textChanged.connect(self._on_scr_live_none)

        self._add_page("SCRIPTS", t_scripts)

        # LIST TAB
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
        
        self.btn_ctrl_add.setStyleSheet("background-color: #2e5c3a;") 
        self.btn_ctrl_remove.setStyleSheet("background-color: #6b2e2e;") 
        
        btn_layout.addWidget(self.btn_ctrl_add)
        btn_layout.addWidget(self.btn_ctrl_remove)
        btn_layout.addWidget(self.btn_ctrl_replace)
        btn_layout.addWidget(self.btn_ctrl_clear)
        
        l_list.addWidget(QtWidgets.QLabel("<b>Assigned Controls:</b>"))
        l_list.addWidget(self.controls_listbox)
        l_list.addLayout(btn_layout)
        
        self.btn_ctrl_add.setProperty("act", "add"); self.btn_ctrl_add.clicked.connect(self._on_ctrl_btn_click)
        self.btn_ctrl_remove.setProperty("act", "remove"); self.btn_ctrl_remove.clicked.connect(self._on_ctrl_btn_click)
        self.btn_ctrl_replace.setProperty("act", "replace"); self.btn_ctrl_replace.clicked.connect(self._on_ctrl_btn_click)
        self.btn_ctrl_clear.setProperty("act", "clear"); self.btn_ctrl_clear.clicked.connect(self._on_ctrl_btn_click)
        self._add_page("LIST", t_list)

        # LAYERS TAB
        t_layers = QtWidgets.QWidget()
        l_layers = QtWidgets.QVBoxLayout(t_layers)
        l_layers.setContentsMargins(4, 4, 4, 4)
        
        self.lbl_assigned_layers = QtWidgets.QLabel("None")
        self.lbl_assigned_layers.setStyleSheet("color: #66c2ff; font-weight: bold; font-style: italic;")
        l_layers.addWidget(self.lbl_assigned_layers)

        h_create = QtWidgets.QHBoxLayout()
        self.le_layer_name = QtWidgets.QLineEdit()
        self.le_layer_name.setPlaceholderText("New Layer Name...")
        self.btn_layer_create = QtWidgets.QPushButton("+ Add")
        h_create.addWidget(self.le_layer_name)
        h_create.addWidget(self.btn_layer_create)
        l_layers.addLayout(h_create)
        
        self.tree_layers = QtWidgets.QTreeWidget()
        self.tree_layers.setHeaderLabels(["Layer Name", "Edit", "Pose"])
        self.tree_layers.setColumnWidth(0, 140)
        self.tree_layers.setColumnWidth(1, 50)
        self.tree_layers.setColumnWidth(2, 50)
        self.tree_layers.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree_layers.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree_layers.customContextMenuRequested.connect(self._show_layer_context_menu)
        self.tree_layers.setSortingEnabled(True)
        self.tree_layers.sortByColumn(0, QtCore.Qt.AscendingOrder)
        
        l_layers.addWidget(self.tree_layers)
        
        h_actions = QtWidgets.QHBoxLayout()
        self.btn_layer_add_sel = QtWidgets.QPushButton("Add Selected")
        self.btn_layer_rem_sel = QtWidgets.QPushButton("Remove Selected")
        self.btn_layer_del = QtWidgets.QPushButton("Delete")
        h_actions.addWidget(self.btn_layer_add_sel)
        h_actions.addWidget(self.btn_layer_rem_sel)
        h_actions.addWidget(self.btn_layer_del)
        l_layers.addLayout(h_actions)
        
        self.btn_layer_create.clicked.connect(self._on_layer_create)
        self.btn_layer_add_sel.clicked.connect(self._on_layer_add_sel)
        self.btn_layer_rem_sel.clicked.connect(self._on_layer_rem_sel)
        self.btn_layer_del.clicked.connect(self._on_layer_del)
        self.tree_layers.itemChanged.connect(self._on_layer_tree_changed)
        
        self._add_page("LAYERS", t_layers)

        # Round Rectangle Properties
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
        
        self.grp_spl_roundrect = QtWidgets.QGroupBox("Round Rectangle Radii")
        l_rr = QtWidgets.QFormLayout(self.grp_spl_roundrect)
        self.rad_tl = QtWidgets.QDoubleSpinBox(); self.rad_tl.setRange(0, 999)
        self.rad_tr = QtWidgets.QDoubleSpinBox(); self.rad_tr.setRange(0, 999)
        self.rad_bl = QtWidgets.QDoubleSpinBox(); self.rad_bl.setRange(0, 999)
        self.rad_br = QtWidgets.QDoubleSpinBox(); self.rad_br.setRange(0, 999)
        l_rr.addRow("Top Left / Right:", self._row(self.rad_tl, self.rad_tr))
        l_rr.addRow("Bottom Left / Right:", self._row(self.rad_bl, self.rad_br))
        l_spl.addWidget(self.grp_spl_roundrect)
        
        # Slider Properties
        self.grp_spl_slider = QtWidgets.QGroupBox("Slider Properties")
        l_sl = QtWidgets.QFormLayout(self.grp_spl_slider)
        
        self.sl_attr = QtWidgets.QLineEdit()
        self.sl_inside_text = QtWidgets.QCheckBox("Inside Text (Ignore GEO alignment)")
        self.sl_min = QtWidgets.QDoubleSpinBox(); self.sl_min.setRange(-99999, 99999)
        self.sl_max = QtWidgets.QDoubleSpinBox(); self.sl_max.setRange(-99999, 99999)
        self.sl_val = QtWidgets.QDoubleSpinBox(); self.sl_val.setRange(-99999, 99999)
        self.sl_handle_scale = QtWidgets.QDoubleSpinBox(); self.sl_handle_scale.setRange(0.1, 10.0); self.sl_handle_scale.setSingleStep(0.1)
        self.sl_handle_color = ColorPickerWidget()
        
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
        
        self.btn_attr_add.setProperty("act", "add"); self.btn_attr_add.clicked.connect(self._on_attr_btn_click)
        self.btn_attr_rep.setProperty("act", "replace"); self.btn_attr_rep.clicked.connect(self._on_attr_btn_click)
        self.btn_attr_clr.setProperty("act", "clear"); self.btn_attr_clr.clicked.connect(self._on_attr_btn_click)
        
        attr_field_w = QtWidgets.QWidget()
        attr_field_l = QtWidgets.QVBoxLayout(attr_field_w)
        attr_field_l.setContentsMargins(0,0,0,0)
        attr_field_l.addWidget(self.sl_attr)
        attr_field_l.addLayout(attr_btn_lay)
        
        l_sl.addRow("Attribute Name:", attr_field_w)
        l_sl.addRow("Text Placement:", self.sl_inside_text)
        l_sl.addRow("Min / Max:", self._row(self.sl_min, self.sl_max))
        l_sl.addRow("Default Value:", self.sl_val)
        l_sl.addRow("Handle Scale:", self.sl_handle_scale)
        l_sl.addRow("Handle Color:", self.sl_handle_color)

        l_spl.addWidget(self.grp_spl_slider)
        
        # Pose Properties
        self.grp_spl_pose = QtWidgets.QGroupBox("Pose Properties")
        l_po = QtWidgets.QVBoxLayout(self.grp_spl_pose)
        
        self.po_img_preview = QtWidgets.QLabel("No Image")
        self.po_img_preview.setFixedSize(180, 120)
        self.po_img_preview.setAlignment(QtCore.Qt.AlignCenter)
        self.po_img_preview.setStyleSheet("border: 2px solid #555; background: #111; border-radius: 4px;")
        l_po.addWidget(self.po_img_preview, 0, QtCore.Qt.AlignCenter)

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

        self.po_rr_group = QtWidgets.QWidget()
        l_po_rr = QtWidgets.QFormLayout(self.po_rr_group)
        self.po_rad = QtWidgets.QDoubleSpinBox()
        self.po_rad.setRange(0, 500)
        self.po_rad.setValue(8.0)
        l_po_rr.addRow("Corner Radius:", self.po_rad)
        l_po.addWidget(self.po_rr_group)

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
        
        self.po_btn_cap.setProperty("act", "capture_image"); self.po_btn_cap.clicked.connect(self._on_pose_btn_click)
        self.po_btn_load.setProperty("act", "load_image"); self.po_btn_load.clicked.connect(self._on_pose_btn_click)
        self.po_btn_c_rem.setProperty("act", "rem_ctrl_ui"); self.po_btn_c_rem.clicked.connect(self._on_pose_btn_click)
        self.po_btn_a_rem.setProperty("act", "rem_attr_ui"); self.po_btn_a_rem.clicked.connect(self._on_pose_btn_click)
        self.po_ctrl_list.itemSelectionChanged.connect(self._on_pose_ctrl_selected)

        l_spl.addWidget(self.grp_spl_pose)

        # Checkbox Properties
        self.grp_spl_check = QtWidgets.QGroupBox("Checkbox Properties")
        l_cb = QtWidgets.QVBoxLayout(self.grp_spl_check)
        
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
        
        self.cb_on_a_add.setProperty("state", "ON"); self.cb_on_a_add.setProperty("act", "add_attr"); self.cb_on_a_add.clicked.connect(self._on_cb_btn_click)
        self.cb_on_a_rem.setProperty("state", "ON"); self.cb_on_a_rem.setProperty("act", "rem_attr"); self.cb_on_a_rem.clicked.connect(self._on_cb_btn_click)
        self.cb_on_a_clr.setProperty("state", "ON"); self.cb_on_a_clr.setProperty("act", "clr_attr"); self.cb_on_a_clr.clicked.connect(self._on_cb_btn_click)
        self.cb_on_s_add.setProperty("state", "ON"); self.cb_on_s_add.setProperty("act", "add_shape"); self.cb_on_s_add.clicked.connect(self._on_cb_btn_click)
        self.cb_on_s_rem.setProperty("state", "ON"); self.cb_on_s_rem.setProperty("act", "rem_shape"); self.cb_on_s_rem.clicked.connect(self._on_cb_btn_click)
        self.cb_on_s_clr.setProperty("state", "ON"); self.cb_on_s_clr.setProperty("act", "clr_shape"); self.cb_on_s_clr.clicked.connect(self._on_cb_btn_click)
        
        self.cb_off_a_add.setProperty("state", "OFF"); self.cb_off_a_add.setProperty("act", "add_attr"); self.cb_off_a_add.clicked.connect(self._on_cb_btn_click)
        self.cb_off_a_rem.setProperty("state", "OFF"); self.cb_off_a_rem.setProperty("act", "rem_attr"); self.cb_off_a_rem.clicked.connect(self._on_cb_btn_click)
        self.cb_off_a_clr.setProperty("state", "OFF"); self.cb_off_a_clr.setProperty("act", "clr_attr"); self.cb_off_a_clr.clicked.connect(self._on_cb_btn_click)
        self.cb_off_s_add.setProperty("state", "OFF"); self.cb_off_s_add.setProperty("act", "add_shape"); self.cb_off_s_add.clicked.connect(self._on_cb_btn_click)
        self.cb_off_s_rem.setProperty("state", "OFF"); self.cb_off_s_rem.setProperty("act", "rem_shape"); self.cb_off_s_rem.clicked.connect(self._on_cb_btn_click)
        self.cb_off_s_clr.setProperty("state", "OFF"); self.cb_off_s_clr.setProperty("act", "clr_shape"); self.cb_off_s_clr.clicked.connect(self._on_cb_btn_click)
        
        self.cb_on_btn_expand.setProperty("state", "ON"); self.cb_on_btn_expand.clicked.connect(self._on_cb_expand_click)
        self.cb_off_btn_expand.setProperty("state", "OFF"); self.cb_off_btn_expand.clicked.connect(self._on_cb_expand_click)

        l_spl.addWidget(self.grp_spl_check)
        
        # Image Properties
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
        self.img_shape = QtWidgets.QComboBox()
        self.img_shape.addItems(["Rectangle", "Round Rectangle", "Circle"])
        
        self.img_opacity = QtWidgets.QSpinBox()
        self.img_opacity.setRange(0, 100); self.img_opacity.setSuffix("%")
        self.img_scale = QtWidgets.QComboBox()
        self.img_scale.addItems(["Fit", "Fill", "Stretch"])
        
        self.img_pad = QtWidgets.QDoubleSpinBox()
        self.img_pad.setRange(0, 500)
        
        self.img_align = QtWidgets.QComboBox()
        self.img_align.addItems(["Center", "Top", "Bottom", "Left", "Right", "Top Left", "Top Right", "Bottom Left", "Bottom Right"])
        
        form_img.addRow("Mask Shape:", self.img_shape)
        form_img.addRow("Opacity:", self.img_opacity)
        form_img.addRow("Scale Mode:", self.img_scale)
        form_img.addRow("Padding:", self.img_pad)
        form_img.addRow("Alignment:", self.img_align)
        
        l_img.addLayout(path_lay)
        l_img.addWidget(self.img_btn_load)
        l_img.addLayout(form_img)
        
        self.img_rr_group = QtWidgets.QWidget()
        l_img_rr = QtWidgets.QFormLayout(self.img_rr_group)
        self.img_rad = QtWidgets.QDoubleSpinBox()
        self.img_rad.setRange(0, 500)
        self.img_rad.setValue(8.0)
        l_img_rr.addRow("Corner Radius:", self.img_rad)
        l_img.addWidget(self.img_rr_group)
        
        self.img_btn_load.setProperty("act", "load_image"); self.img_btn_load.clicked.connect(self._on_img_btn_click)
        l_spl.addWidget(self.grp_spl_image)

        # Dropdown Properties
        self.grp_spl_dropdown = QtWidgets.QGroupBox("Dropdown Properties")
        l_dd = QtWidgets.QFormLayout(self.grp_spl_dropdown)
        
        self.dd_attr = QtWidgets.QLineEdit()
        self.dd_inside_text = QtWidgets.QCheckBox("Inside Text (Ignore GEO alignment)")
        self.dd_shape = QtWidgets.QComboBox()
        self.dd_shape.addItems(["Rectangle", "Round Rectangle", "Circle"])
        self.dd_rad = QtWidgets.QDoubleSpinBox(); self.dd_rad.setRange(0, 500); self.dd_rad.setValue(6.0)
        
        dd_btn_lay = QtWidgets.QHBoxLayout()
        self.btn_dd_add = QtWidgets.QPushButton("Add")
        self.btn_dd_rep = QtWidgets.QPushButton("Replace")
        self.btn_dd_clr = QtWidgets.QPushButton("Clear")
        
        self.btn_dd_add.setStyleSheet("background-color: #2e5c3a;")
        self.btn_dd_rep.setStyleSheet("background-color: #2b455c;")
        self.btn_dd_clr.setStyleSheet("background-color: #6b2e2e;")
        
        dd_btn_lay.addWidget(self.btn_dd_add)
        dd_btn_lay.addWidget(self.btn_dd_rep)
        dd_btn_lay.addWidget(self.btn_dd_clr)
        
        self.btn_dd_add.setProperty("act", "add"); self.btn_dd_add.clicked.connect(self._on_attr_btn_click)
        self.btn_dd_rep.setProperty("act", "replace"); self.btn_dd_rep.clicked.connect(self._on_attr_btn_click)
        self.btn_dd_clr.setProperty("act", "clear"); self.btn_dd_clr.clicked.connect(self._on_attr_btn_click)
        
        dd_attr_w = QtWidgets.QWidget(); dd_attr_l = QtWidgets.QVBoxLayout(dd_attr_w); dd_attr_l.setContentsMargins(0,0,0,0)
        dd_attr_l.addWidget(self.dd_attr); dd_attr_l.addLayout(dd_btn_lay)
        
        l_dd.addRow("Attribute Name:", dd_attr_w)
        l_dd.addRow("Text Placement:", self.dd_inside_text)
        l_dd.addRow("Mask Shape:", self.dd_shape)
        
        self.dd_rr_group = QtWidgets.QWidget(); l_dd_rr = QtWidgets.QFormLayout(self.dd_rr_group); l_dd_rr.setContentsMargins(0,0,0,0)
        l_dd_rr.addRow("Corner Radius:", self.dd_rad)
        l_dd.addRow("", self.dd_rr_group)
        
        # --- Inner Value Formatting ---
        l_dd.addRow(QtWidgets.QLabel("")) # Spacer
        l_dd.addRow(QtWidgets.QLabel("<b>Inner Value Formatting:</b>"))
        
        self.dd_dyn_color = ColorPickerWidget("#ffffff")
        self.dd_dyn_size = QtWidgets.QDoubleSpinBox(); self.dd_dyn_size.setRange(1, 100); self.dd_dyn_size.setDecimals(0)
        self.dd_dyn_align = QtWidgets.QComboBox(); self.dd_dyn_align.addItems(["Left", "Center", "Right"])
        
        dd_font_lay = QtWidgets.QHBoxLayout()
        self.dd_dyn_bold = QtWidgets.QCheckBox("B"); self.dd_dyn_bold.setStyleSheet("font-weight: bold;")
        self.dd_dyn_italic = QtWidgets.QCheckBox("I"); self.dd_dyn_italic.setStyleSheet("font-style: italic;")
        dd_font_lay.addWidget(self.dd_dyn_bold); dd_font_lay.addWidget(self.dd_dyn_italic); dd_font_lay.addStretch()
        
        l_dd.addRow("Color:", self.dd_dyn_color)
        l_dd.addRow("Size:", self.dd_dyn_size)
        l_dd.addRow("Style:", dd_font_lay)
        l_dd.addRow("Alignment:", self.dd_dyn_align)

        l_spl.addWidget(self.grp_spl_dropdown)
        
        # Text Properties
        self.grp_spl_text = QtWidgets.QGroupBox("Text Properties")
        l_txt_spl = QtWidgets.QFormLayout(self.grp_spl_text)
        
        self.txt_orient = QtWidgets.QComboBox()
        self.txt_orient.addItems(["Horizontal", "Vertical"])
        
        self.txt_v_gap = QtWidgets.QDoubleSpinBox()
        self.txt_v_gap.setRange(-500, 500)
        
        l_txt_spl.addRow("Orientation:", self.txt_orient)
        l_txt_spl.addRow("Vertical Gap:", self.txt_v_gap)
        l_spl.addWidget(self.grp_spl_text)

        # Line Properties
        self.grp_spl_line = QtWidgets.QGroupBox("Line Properties")
        l_line_spl = QtWidgets.QFormLayout(self.grp_spl_line)
        
        self.line_style = QtWidgets.QComboBox()
        self.line_style.addItems(["Solid", "Dots", "Dashes", "Smooth", "Zigzag"])
        self.line_orient = QtWidgets.QComboBox()
        self.line_orient.addItems(["Horizontal", "Vertical", "Diagonal 1", "Diagonal 2"])
        
        self.line_start_cap = QtWidgets.QComboBox()
        self.line_start_cap.addItems(["None", "Arrow", "Bar", "Point"])
        self.line_end_cap = QtWidgets.QComboBox()
        self.line_end_cap.addItems(["None", "Arrow", "Bar", "Point"])
        
        self.line_cap_scale = QtWidgets.QDoubleSpinBox()
        self.line_cap_scale.setRange(0.1, 10.0); self.line_cap_scale.setSingleStep(0.1)
        self.line_wave_count = QtWidgets.QSpinBox()
        self.line_wave_count.setRange(1, 100)
        
        l_line_spl.addRow("Style:", self.line_style)
        l_line_spl.addRow("Orientation:", self.line_orient)
        l_line_spl.addRow("Start Cap:", self.line_start_cap)
        l_line_spl.addRow("End Cap:", self.line_end_cap)
        l_line_spl.addRow("Cap Scale:", self.line_cap_scale)
        l_line_spl.addRow("Wave Count:", self.line_wave_count)
        
        l_spl.addWidget(self.grp_spl_line)

        l_spl.addStretch()

        self.lbl_spl_empty = QtWidgets.QLabel("No special properties for this shape.")
        self.lbl_spl_empty.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_spl_empty.setStyleSheet("color: #777;")
        l_spl.addWidget(self.lbl_spl_empty)
        
        l_spl.addStretch()
        self._add_page("*SPL*", t_spl)

        # GLOBAL RIG SETTINGS
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

        r_swn = QtWidgets.QHBoxLayout(); self.ikfk_sw_node = QtWidgets.QLineEdit()
        r_swn.addWidget(self.ikfk_sw_node); r_swn.addWidget(SmartAddButton(self.ikfk_sw_node))
        f_ik.addRow("Switch Node:", r_swn)
        
        r_swa = QtWidgets.QHBoxLayout(); self.ikfk_sw_attr = QtWidgets.QLineEdit()
        self.ikfk_sw_attr.setPlaceholderText("Select in Channel Box ->")
        r_swa.addWidget(self.ikfk_sw_attr); r_swa.addWidget(SmartAddButton(self.ikfk_sw_attr, attr_mode=True))
        f_ik.addRow("Switch Attr:", r_swa)

        r_ik = QtWidgets.QHBoxLayout(); self.ikfk_ik_ctrl = QtWidgets.QLineEdit()
        r_ik.addWidget(self.ikfk_ik_ctrl); r_ik.addWidget(SmartAddButton(self.ikfk_ik_ctrl))
        f_ik.addRow("IK Control:", r_ik)
        
        r_pv = QtWidgets.QHBoxLayout(); self.ikfk_pv_ctrl = QtWidgets.QLineEdit()
        r_pv.addWidget(self.ikfk_pv_ctrl); r_pv.addWidget(SmartAddButton(self.ikfk_pv_ctrl))
        f_ik.addRow("Pole Vector:", r_pv)
        
        r_fk = QtWidgets.QHBoxLayout(); self.ikfk_fk_ctrls = QtWidgets.QLineEdit()
        r_fk.addWidget(self.ikfk_fk_ctrls); r_fk.addWidget(SmartAddButton(self.ikfk_fk_ctrls, multi=True))
        f_ik.addRow("FK Controls:", r_fk)
        
        r_bn_main = QtWidgets.QVBoxLayout()
        r_bn_top = QtWidgets.QHBoxLayout()
        
        self.ikfk_bones = QtWidgets.QTextEdit()
        self.ikfk_bones.setMaximumHeight(65)
        
        btn_auto = QtWidgets.QPushButton("AUTO FIND")
        btn_auto.setFixedWidth(75)
        btn_auto.clicked.connect(self._ikfk_auto_joints)
        
        r_bn_top.addWidget(self.ikfk_bones)
        r_bn_top.addWidget(btn_auto)
        
        r_bn_bot = QtWidgets.QHBoxLayout()
        r_bn_bot.addStretch()
        r_bn_bot.addWidget(SmartAddButton(self.ikfk_bones, multi=True))
        
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
        
        self.nav_list.currentRowChanged.connect(self._on_tab_changed)
        self.nav_list.setCurrentRow(0)

    # NATIVE CYTHON-SAFE ROUTERS
    def _route_alignment(self, act, *args, **kwargs):
        if getattr(self, "_align_lock", False): return
        self._align_lock = True
        self.alignment_requested.emit(act)
        self._align_lock = False
    
    def _on_add_preset_click(self, *args, **kwargs):
        self.add_preset(self.sender().property("p_type"))
    
    def _on_ctrl_btn_click(self, *args, **kwargs):
        action = self.sender().property("act")
        
        if action == "remove":
            from maya import cmds
            selected_items = self.controls_listbox.selectedItems()
            all_items = [self.controls_listbox.item(i).text() for i in range(self.controls_listbox.count())]
            to_remove = []
            
            # 1. Prioritize UI List Selection
            if selected_items:
                to_remove = [item.text() for item in selected_items]
            # 2. Fallback to Maya Scene Selection
            else:
                maya_sel = cmds.ls(selection=True) or []
                if maya_sel:
                    from . import api
                    from . import main
                    active_ns = api.get_namespace()
                    core_inst = main._app_instance.core if hasattr(main, "_app_instance") and main._app_instance else None
                    if core_inst:
                        maya_sel_short = [core_inst.strip_namespace_for_save(str(x), active_ns) for x in maya_sel]
                        to_remove = [x for x in maya_sel_short if x in all_items]
            
            # 3. Abort with message if nothing is found
            if not to_remove:
                cmds.warning("[ARTools] No controls to Remove.")
                return
                
            # 4. Apply removal to all active shapes
            for item in getattr(self, "target_items", []):
                current_ctrls = getattr(item, "controls", [])
                item.controls = [c for c in current_ctrls if c not in to_remove]
                item.update()
                
            # 5. Instantly refresh the UI and push to the Undo stack
            self.set_target_items(self.target_items)
            self._push_undo_from_editor()
            return
            
        # Route 'add', 'replace', and 'clear' to their standard backend logic
        self.controls_modified.emit(action)

    def _on_attr_btn_click(self, *args, **kwargs):
        self.attribute_modified.emit(self.sender().property("act"))

    def _on_pose_btn_click(self, *args, **kwargs):
        self.pose_action_requested.emit(self.sender().property("act"))

    def _on_cb_btn_click(self, *args, **kwargs):
        s = self.sender()
        self.checkbox_action_requested.emit(s.property("state"), s.property("act"))

    def _on_img_btn_click(self, *args, **kwargs):
        self.image_action_requested.emit(self.sender().property("act"))

    def _on_cb_expand_click(self, *args, **kwargs):
        self._on_cb_expand(self.sender().property("state"))

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

    # --- UNIVERSAL PROXY SHIELDS ---
    # By omitting @QtCore.Slot and using *args, Cython safely absorbs native C++ QString/double emissions!
    def _on_live_str(self, *args): self._on_live_change()
    def _on_live_int(self, *args): self._on_live_change()
    def _on_live_float(self, *args): self._on_live_change()
    def _on_live_bool(self, *args): self._on_live_change()
    def _on_live_none(self, *args): self._on_live_change()
    def _on_scr_live_str(self, *args): self._on_scr_live()
    def _on_scr_live_none(self, *args): self._on_scr_live()

    def _bind_live_events(self):
        for widget in self.findChildren(QtWidgets.QLineEdit): widget.textChanged.connect(self._on_live_str)
        for widget in self.findChildren(QtWidgets.QDoubleSpinBox): widget.valueChanged.connect(self._on_live_float)
        for widget in self.findChildren(QtWidgets.QSpinBox): widget.valueChanged.connect(self._on_live_int)
        for widget in self.findChildren(QtWidgets.QCheckBox): widget.toggled.connect(self._on_live_bool)
        for widget in self.findChildren(QtWidgets.QComboBox): widget.currentIndexChanged.connect(self._on_live_int)
        for widget in self.findChildren(QtWidgets.QTextEdit): widget.textChanged.connect(self._on_live_none)
        for widget in self.findChildren(ColorPickerWidget): widget.colorChanged.connect(self._on_live_str)

    def _block_all(self, state):
        for w in self.findChildren(QtWidgets.QWidget): w.blockSignals(state)

    def set_target_items(self, items):
        self._is_updating = True
        self.target_items = items
        
        self._populate_layers()
        self._populate_scripts()
        self.refresh_ikfk_manager()

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

        if not items: return
        
        item = items[0]
        self._is_populating = True
        self._block_all(True)

        if len(items) == 1:
            self.shape_id_edit.setText(getattr(item, "item_id", ""))
        else:
            self.shape_id_edit.setText("<Multiple Shapes Selected>")

        self.label_edit.setText(getattr(item, "label", ""))
        
        self.controls_listbox.clear()
        all_ctrls = []
        for itm in items:
            for c in getattr(itm, "controls", []):
                if c not in all_ctrls:
                    all_ctrls.append(c)
                    
        if all_ctrls:
            self.controls_listbox.addItems(all_ctrls)

        self._populate_layers()
        self._populate_scripts()
        
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
        self.grp_spl_dropdown.setVisible(shape_type == "Dropdown")
        self.grp_spl_text.setVisible(shape_type == "Text")
        self.grp_spl_line.setVisible(shape_type == "Line")
        self.lbl_spl_empty.setVisible(shape_type not in ["Round Rectangle", "Slider", "Pose", "Checkbox", "Image", "Dropdown", "Text", "Line"])
        
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
            
            self.po_rr_group.setVisible(self.po_shape.currentText() == "Round Rectangle")
            
            if len(items) > 1: 
                self.po_img_preview.setText("Multiple Shapes")
                self.po_img_path.setText("<Multiple Shapes Selected>")
            else:
                img_path = getattr(item, "image_path", "")
                if img_path:
                    import os
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
        
        elif shape_type == "Dropdown":
            self.dd_attr.setText(getattr(item, "attribute", ""))
            self.dd_inside_text.setChecked(bool(getattr(item, "inside_text", True)))
            self.dd_shape.setCurrentText(getattr(item, "dd_shape", "Round Rectangle"))
            self.dd_rad.setValue(float(getattr(item, "dd_roundness", 6.0)))
            self.dd_rr_group.setVisible(self.dd_shape.currentText() == "Round Rectangle")
            self.dd_dyn_color.set_color(getattr(item, "dyn_text_color", "#ffffff"))
            self.dd_dyn_size.setValue(float(getattr(item, "dyn_font_size", 11.0)))
            self.dd_dyn_bold.setChecked(bool(getattr(item, "dyn_font_bold", True)))
            self.dd_dyn_italic.setChecked(bool(getattr(item, "dyn_font_italic", False)))
            self.dd_dyn_align.setCurrentText(getattr(item, "dyn_align_h", "Center"))
        
        elif shape_type == "Text":
            self.txt_orient.setCurrentText(getattr(item, "text_orientation", "Horizontal"))
            self.txt_v_gap.setValue(float(getattr(item, "text_v_gap", 0.0)))
        
        elif shape_type == "Line":
            self.line_style.setCurrentText(getattr(item, "line_style", "Solid"))
            self.line_orient.setCurrentText(getattr(item, "line_orient", "Horizontal"))
            self.line_start_cap.setCurrentText(getattr(item, "line_start_cap", "None"))
            self.line_end_cap.setCurrentText(getattr(item, "line_end_cap", "None"))
            self.line_cap_scale.setValue(float(getattr(item, "line_cap_scale", 1.0)))
            self.line_wave_count.setValue(int(getattr(item, "line_wave_count", 5)))
        
        elif shape_type == "Image":
            self.img_shape.setCurrentText(getattr(item, "image_mask_shape", "Rectangle"))
            self.img_rr_group.setVisible(self.img_shape.currentText() == "Round Rectangle")
            self.img_rad.setValue(float(getattr(item, "image_roundness", 8.0)))
            
            self.img_opacity.setValue(int(getattr(item, "image_opacity", 1.0) * 100))
            self.img_scale.setCurrentText(getattr(item, "image_scale_mode", "Fit"))
            self.img_pad.setValue(float(getattr(item, "image_padding", 0.0)))
            self.img_align.setCurrentText(getattr(item, "image_alignment", "Center"))
            
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

    def _on_live_change(self):
        if self._is_populating: return
        sender = self.sender()
        if not sender: return

        if not getattr(self, "target_items", None): return

        if getattr(self, "anchor_btns", None) and sender in self.anchor_btns.buttons():
            if not sender.isChecked(): return

        for item in self.target_items:
            if hasattr(item, "prepareGeometryChange"): item.prepareGeometryChange()
            
            if not hasattr(item, "bg"): item.bg = {}
            if not hasattr(item, "edge_color"): item.edge_color = {}
            if not hasattr(item, "text_color"): item.text_color = {}
            if not hasattr(item, "edge_thickness") or not isinstance(item.edge_thickness, dict): 
                item.edge_thickness = {"normal": 1.5, "hover": 2.0, "press": 1.5}

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
                if hasattr(item, "scene") and item.scene() and item.scene().views():
                    if hasattr(item.scene().views()[0], "update_item_flags"):
                        item.scene().views()[0].update_item_flags(item)
            
            elif sender == self.cmb_mode:
                item.placement_mode = self.cmb_mode.currentText()
                self.grp_anchor.setVisible(item.placement_mode == "screen")
                if hasattr(item, "scene") and item.scene():
                    canvas = item.scene().views()[0]
                    if item.placement_mode == "screen":
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
            
            elif item.shape_name == "Dropdown":
                if sender == self.dd_attr: item.attribute = self.dd_attr.text()
                elif sender == self.dd_inside_text: item.inside_text = self.dd_inside_text.isChecked()
                elif sender == self.dd_shape: 
                    item.dd_shape = self.dd_shape.currentText()
                    self.dd_rr_group.setVisible(item.dd_shape == "Round Rectangle")
                elif sender == self.dd_rad: item.dd_roundness = self.dd_rad.value()
                elif sender == self.dd_dyn_color: item.dyn_text_color = self.dd_dyn_color.color_hex
                elif sender == self.dd_dyn_size: item.dyn_font_size = self.dd_dyn_size.value()
                elif sender == self.dd_dyn_bold: item.dyn_font_bold = self.dd_dyn_bold.isChecked()
                elif sender == self.dd_dyn_italic: item.dyn_font_italic = self.dd_dyn_italic.isChecked()
                elif sender == self.dd_dyn_align: item.dyn_align_h = self.dd_dyn_align.currentText()
            
            elif item.shape_name == "Text":
                if sender == self.txt_orient: item.text_orientation = self.txt_orient.currentText()
                elif sender == self.txt_v_gap: item.text_v_gap = self.txt_v_gap.value()
            
            elif item.shape_name == "Line":
                if sender == self.line_style: item.line_style = self.line_style.currentText()
                elif sender == self.line_orient: item.line_orient = self.line_orient.currentText()
                elif sender == self.line_start_cap: item.line_start_cap = self.line_start_cap.currentText()
                elif sender == self.line_end_cap: item.line_end_cap = self.line_end_cap.currentText()
                elif sender == self.line_cap_scale: item.line_cap_scale = self.line_cap_scale.value()
                elif sender == self.line_wave_count: item.line_wave_count = self.line_wave_count.value()
            
            elif item.shape_name == "Image":
                if sender == self.img_shape:
                    item.image_mask_shape = self.img_shape.currentText()
                    self.img_rr_group.setVisible(item.image_mask_shape == "Round Rectangle")
                elif sender == self.img_rad: item.image_roundness = self.img_rad.value()
                elif sender == self.img_opacity: item.image_opacity = self.img_opacity.value() / 100.0
                elif sender == self.img_scale: item.image_scale_mode = self.img_scale.currentText()
                elif sender == self.img_pad: item.image_padding = self.img_pad.value()
                elif sender == self.img_align: item.image_alignment = self.img_align.currentText()
            
            item.update()

        self._undo_timer.start()

    def _on_hier_action_select(self, *args, **kwargs):
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

    def _on_hier_action_remove(self, *args, **kwargs):
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

    def _on_hier_action_clear(self, *args, **kwargs):
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

    def _get_canvas(self):
        if getattr(self, "target_items", None) and self.target_items[0].scene():
            return self.target_items[0].scene().views()[0]
            
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

    def _on_layer_create(self, *args, **kwargs):
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

    def _on_layer_add_sel(self, *args, **kwargs):
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

    def _on_layer_rem_sel(self, *args, **kwargs):
        canvas = self._get_canvas(); sel_layer = self.tree_layers.currentItem()
        if not canvas or not sel_layer or not getattr(self, "target_items", None): return
        l_id = sel_layer.data(0, QtCore.Qt.UserRole)
        for layer in canvas.layer_data:
            if layer["id"] == l_id:
                layer["shapes"] = [sid for sid in layer["shapes"] if sid not in [s.item_id for s in self.target_items]]
                break
        self._populate_layers()
        self._push_undo_from_editor()

    def _on_layer_del(self, *args, **kwargs):
        canvas = self._get_canvas(); sel_layer = self.tree_layers.currentItem()
        if not canvas or not sel_layer: return
        l_id = sel_layer.data(0, QtCore.Qt.UserRole)
        
        layer_to_delete = next((l for l in canvas.layer_data if l["id"] == l_id), None)
        if layer_to_delete:
            for item in canvas.scene().items():
                if hasattr(item, "item_id") and item.item_id in layer_to_delete.get("shapes", []):
                    item.setVisible(True)
        
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
        
        exec_func = getattr(menu, "exec", None) or menu.exec_
        action = exec_func(self.tree_layers.viewport().mapToGlobal(pos))
        
        canvas = self._get_canvas()
        if not canvas or not action: return
        layer_id = item.data(0, QtCore.Qt.UserRole)
        
        if action == act_ren:
            self.tree_layers.editItem(item, 0)
        elif action == act_sel:
            layer = next((l for l in canvas.layer_data if l["id"] == layer_id), None)
            if layer:
                canvas.scene().clearSelection()
                sel_items = []
                for i in canvas.scene().items():
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
        
        s_list = None
        if getattr(self, "target_items", None):
            s_list = getattr(self.target_items[0], "scripts", [])
        else:
            canvas = self._get_canvas()
            if canvas:
                s_list = getattr(canvas, "canvas_scripts", [])
        
        if s_list is not None:
            for i, scr in enumerate(s_list):
                if scr.get("is_separator"):
                    item = QtWidgets.QListWidgetItem(f"[ --- Separator --- ] [{scr.get('trigger', 'Left Click (Menu)')}]")
                else:
                    item = QtWidgets.QListWidgetItem(f"{scr.get('label', 'Script')} [{scr.get('trigger', 'Context Menu')}]")
                item.setData(QtCore.Qt.UserRole, i)
                self.list_scripts.addItem(item)
        self.list_scripts.blockSignals(False)
        self._on_scr_select()

    def _on_scr_add(self, *args, **kwargs):
        s_list = self._get_active_script_list()
        if s_list is not None:
            s_list.append({"label": "New Script", "command": "", "type": "python", "trigger": "Left Click (Menu)"})
            self._populate_scripts()
            self.list_scripts.setCurrentRow(len(s_list)-1)

    def _on_scr_add_sep(self, *args, **kwargs):
        s_list = self._get_active_script_list()
        if s_list is not None:
            s_list.append({"label": "[ --- Separator --- ]", "command": "", "type": "python", "trigger": "Left Click (Menu)", "is_separator": True})
            self._populate_scripts()
            self.list_scripts.setCurrentRow(len(s_list)-1)
    
    def _on_scr_move_up(self, *args):
        row = self.list_scripts.currentRow()
        if row <= 0: return
        s_list = self._get_active_script_list()
        if s_list is not None:
            s_list[row], s_list[row-1] = s_list[row-1], s_list[row]
            self._populate_scripts()
            self.list_scripts.setCurrentRow(row - 1)
            self._push_undo_from_editor()

    def _on_scr_move_dn(self, *args):
        row = self.list_scripts.currentRow()
        s_list = self._get_active_script_list()
        if s_list is not None and 0 <= row < len(s_list) - 1:
            s_list[row], s_list[row+1] = s_list[row+1], s_list[row]
            self._populate_scripts()
            self.list_scripts.setCurrentRow(row + 1)
            self._push_undo_from_editor()

    def _on_scr_drag_drop(self, parent, start, end, destination, row):
        """Safely updates the underlying data array when a user drags and drops an item."""
        s_list = self._get_active_script_list()
        if s_list is not None:
            new_list = []
            for i in range(self.list_scripts.count()):
                old_idx = self.list_scripts.item(i).data(QtCore.Qt.UserRole)
                if old_idx is not None and old_idx < len(s_list):
                    new_list.append(s_list[old_idx])
            
            if len(new_list) == len(s_list):
                s_list.clear()
                s_list.extend(new_list)
                self._populate_scripts()
                self._push_undo_from_editor()
    
    def _on_scr_rem(self, *args, **kwargs):
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
            
            if scr.get("is_separator"):
                # --- Lock Name & Code, but LEAVE TRIGGER ENABLED ---
                self.le_scr_name.setEnabled(False)
                self.cb_scr_lang.setEnabled(False)
                self.te_scr_code.setEnabled(False)
                self.cb_scr_trig.setEnabled(True)
                self.chk_scr_checkable.setEnabled(False)
                
                self.le_scr_name.setText("")
                self.te_scr_code.setPlainText("")
                self.cb_scr_trig.setCurrentText(scr.get("trigger", "Left Click (Menu)"))
                self.chk_scr_checkable.setChecked(False)
            else:
                # --- Enable everything for normal scripts ---
                self.le_scr_name.setEnabled(True)
                self.cb_scr_lang.setEnabled(True)
                self.te_scr_code.setEnabled(True)
                self.cb_scr_trig.setEnabled(True)
                self.chk_scr_checkable.setEnabled(True)
                
                self.le_scr_name.setText(scr.get("label", ""))
                self.cb_scr_lang.setCurrentText(scr.get("type", "python"))
                self.cb_scr_trig.setCurrentText(scr.get("trigger", "Context Menu"))
                self.chk_scr_checkable.setChecked(bool(scr.get("is_checkable", False)))
                
                self.le_scr_attr.blockSignals(True)
                self.le_scr_attr.setText(scr.get("linked_attr", ""))
                self.le_scr_attr.blockSignals(False)
                self.w_scr_attr.setVisible(bool(scr.get("is_checkable", False)))
                
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
        lang = self.cb_on_cmd_type.currentText() if state == "ON" else self.cb_off_cmd_type.currentText()
        text_widget = self.cb_on_cmd_txt if state == "ON" else self.cb_off_cmd_txt
        
        dialog = ExpandedScriptEditor(self, initial_text=text_widget.toPlainText(), lang=lang)
        if dialog.exec_():
            text_widget.setPlainText(dialog.editor.toPlainText())

    def _on_scr_expand(self, *args, **kwargs):
        lang = self.cb_scr_lang.currentText()
        text = self.te_scr_code.toPlainText()
        
        dialog = ExpandedScriptEditor(self, initial_text=text, lang=lang)
        exec_func = getattr(dialog, "exec", None) or dialog.exec_
        if exec_func(): 
            self.te_scr_code.setPlainText(dialog.editor.toPlainText())

    def _on_scr_live(self):
        if not self.w_sprop.isEnabled(): return 
        row = self.list_scripts.currentRow()
        s_list = self._get_active_script_list()
        
        if s_list is not None and 0 <= row < len(s_list):
            scr = s_list[row]
            
            # --- ALWAYS save the Trigger (even for Separators!) ---
            scr["trigger"] = self.cb_scr_trig.currentText()
            
            if scr.get("is_separator"):
                # Update List UI and exit before saving Name/Code
                item = self.list_scripts.item(row)
                if item: item.setText(f"[ --- Separator --- ] [{scr['trigger']}]")
                self._push_undo_from_editor()
                return 
            
            # --- Normal Script Saving ---
            scr["label"] = self.le_scr_name.text()
            scr["type"] = self.cb_scr_lang.currentText()
            scr["is_checkable"] = self.chk_scr_checkable.isChecked()
            scr["linked_attr"] = self.le_scr_attr.text()
            scr["command"] = self.te_scr_code.toPlainText()
            
            item = self.list_scripts.item(row)
            if item:
                item.setText(f"{scr['label']} [{scr['trigger']}]")
                
            if hasattr(self.te_scr_code, "set_language"):
                self.te_scr_code.set_language(scr["type"])
                
            self._push_undo_from_editor()

    def _on_scr_test(self, *args, **kwargs):
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
                    exec(cmd, globals().copy())
            except Exception as e:
                print(f"ARTools Script Test Error: {e}")

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
                btn.preset_clicked.connect(self.apply_preset)
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
                
                if getattr(item, "shape_name", "") != target_shape_name:
                    from . import ui
                    class_name = f"Picker{target_shape_name.replace(' ', '')}Item"
                    shape_class = getattr(ui, class_name, None)
                    
                    if shape_class:
                        new_item = shape_class()
                        
                        for key, val in item.__dict__.items():
                            if not key.startswith("_"):
                                try:
                                    import copy
                                    setattr(new_item, key, copy.deepcopy(val))
                                except:
                                    setattr(new_item, key, val)
                                    
                        new_item.shape_name = target_shape_name
                        
                        new_item.setPos(item.pos())
                        new_item.setRotation(item.rotation())
                        new_item.setZValue(item.zValue())
                        
                        scene = item.scene()
                        if scene:
                            scene.removeItem(item)
                            scene.addItem(new_item)
                            new_item.setSelected(True)
                            
                        items[i] = new_item
                        item = new_item 
                
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
        
        self.set_target_items(items) 
        if items and items[0].scene() and items[0].scene().views():
            items[0].scene().views()[0].viewport().update()

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

    def _ikfk_add(self, *args, **kwargs):
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

    def _ikfk_del(self, *args, **kwargs):
        row = self.ikfk_list.currentRow()
        if row < 0: return
        char_tab = self._get_active_char_tab()
        if char_tab and hasattr(char_tab, "ikfk_chains"):
            char_tab.ikfk_chains.pop(row)
            self.refresh_ikfk_manager()
            self._push_undo_from_editor()

    def _ikfk_save(self, *args, **kwargs):
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

    def _ikfk_auto_joints(self, *args, **kwargs):
        fk_str = self.ikfk_fk_ctrls.text()
        if not fk_str:
            from maya import cmds
            cmds.warning("[ARTools] Please add FK Controls first so the script knows where to look.")
            return
            
        fk_list = [x.strip() for x in fk_str.split(",") if x.strip()]
        
        try:
            from .anim import logic_ikfk
            bones = logic_ikfk.auto_find_chain(fk_list)
            
            if bones and len(bones) > 0:
                self.ikfk_bones.setPlainText(", ".join([b.split("|")[-1].split(":")[-1] for b in bones]))
            else:
                from maya import cmds
                cmds.warning("[ARTools] Auto-find failed for this rig format. Please select the joints manually and click '+ ADD'.")
        except Exception as e:
            from maya import cmds
            cmds.warning(f"[ARTools] Auto-find Error: {e}")

    def closeEvent(self, event):
        from .preferences import PrefManager
        prefs = PrefManager()
        prefs.set("editor_w", self.width())
        prefs.set("editor_h", self.height())
        prefs.set("editor_x", self.pos().x())
        prefs.set("editor_y", self.pos().y())
        QtWidgets.QWidget.closeEvent(self, event)