# ARTools/library/browser.py
from PySide6 import QtWidgets, QtGui, QtCore
IS_PYSIDE2 = False

from maya import cmds
import os
import glob
import json
from . import core
from ARTools.anim import logic_anim, clipboard

library_core = None 
_browser_instance = None
_property_instance = None
_last_paste_method = "Replace"

# -------------------------------------------------------------------------
# SATELLITE PROPERTY WINDOW
# -------------------------------------------------------------------------
class PropertySatellite(QtWidgets.QDialog):
    apply_triggered = QtCore.Signal(dict)

    def __init__(self, parent=None):
        super(PropertySatellite, self).__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        self.scale = self.get_dpi_scale()
        s = self.scale

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.frame = QtWidgets.QFrame()
        self.frame.setObjectName("PopupFrame")
        
        self.frame.setStyleSheet(f"""
            #PopupFrame {{ 
                background-color: #12171D; 
                border: 1px solid #29323B; 
                border-radius: {int(10*s)}px;
            }}
            QLabel {{ font-family: Segoe UI; }}
            #ThumbName {{ font-size: 12pt; font-weight: bold; color: #F1F5F7; margin-bottom: {int(6*s)}px; }}
            #StatLabel {{ font-size: 9pt; color: #8F9CA6; }}
            #StatValue {{ font-size: 9pt; font-weight: bold; color: #E7EDF1; }}
            
            QLineEdit#ScrollableText, QComboBox#ScrollableText {{
                background: #1A232B;
                color: #D9E2E8;
                border: 1px solid #2F3B45;
                border-radius: {int(4*s)}px;
                padding: {int(3*s)}px {int(6*s)}px;
                font-size: 9pt;
                selection-background-color: #4FB8A7;
                selection-color: #FFF;
            }}
            QLineEdit#ScrollableText:hover, QComboBox#ScrollableText:hover {{
                border: 1px solid #51616D;
            }}
            QLineEdit#ScrollableText:focus, QComboBox#ScrollableText:focus {{ border: 1px solid #4FB8A7; }}
            QComboBox#ScrollableText::drop-down {{ border: none; width: {int(18*s)}px; }}
            QComboBox#ScrollableText QAbstractItemView {{
                background: #1A232B;
                color: #D9E2E8;
                border: 1px solid #2F3B45;
                selection-background-color: #4FB8A7;
                selection-color: #FFF;
            }}

            QRadioButton {{ font-size: 9pt; color: #D6DDE2; spacing: {int(6*s)}px; }}
            QRadioButton::indicator {{ width: {int(12*s)}px; height: {int(12*s)}px; border-radius: {int(6*s)}px; border: 1px solid #55636E; background: #162028; }}
            
            QGroupBox#NSGroup {{ 
                border: 1px solid #2C6F84; 
                margin-top: {int(8*s)}px; 
                padding-top: {int(12*s)}px; 
                border-radius: {int(6*s)}px; 
                background-color: rgba(79, 184, 167, 0.06); 
            }}
            QGroupBox#NSGroup::title {{ subcontrol-origin: margin; left: {int(10*s)}px; padding: 0 {int(4*s)}px; color: #6CC7B7; font-weight: bold; font-size: 9pt; }}
            
            QRadioButton#NSRadio {{ color: #D4ECE7; }}
            QRadioButton#NSRadio::indicator:checked {{ background-color: #4FB8A7; border: 1px solid #4FB8A7; border-radius: {int(7*s)}px; }}
            
            #RangeLabel {{ font-size: 9pt; font-weight: bold; color: #E7A55A; }}
            
            QSpinBox#RangeInput {{ 
                background: #211A15; 
                color: #F1BC7C; 
                border: 1px solid #B87C3D; 
                padding: {int(4*s)}px; 
                border-radius: {int(4*s)}px; 
                font-weight: bold; 
                min-height: {int(18*s)}px;
            }}
            
            #MethodLabel {{ font-size: 9pt; font-weight: bold; color: #69B7D0; }}
            
            QComboBox#MethodInput {{ 
                background: #182129; 
                color: #D7E8EF; 
                border: 1px solid #345366; 
                padding: {int(4*s)}px; 
                border-radius: {int(4*s)}px; 
                font-weight: bold; 
                min-height: {int(18*s)}px;
            }}
            QComboBox#MethodInput::drop-down {{ border: none; width: {int(18*s)}px; }}
            
            QRadioButton#BlueRadio {{ color: #B4DAE6; }}
            QRadioButton#BlueRadio::indicator:checked {{ background-color: #69B7D0; border: 1px solid #69B7D0; border-radius: {int(7*s)}px; }}
            
            QGroupBox#MirrorGroup {{ 
                border: 1px solid #82525F; 
                margin-top: {int(8*s)}px; 
                padding-top: {int(12*s)}px; 
                border-radius: {int(6*s)}px; 
                background-color: rgba(224, 114, 103, 0.05); 
            }}
            QGroupBox#MirrorGroup::title {{ subcontrol-origin: margin; left: {int(10*s)}px; padding: 0 {int(4*s)}px; color: #E08A7D; font-weight: bold; font-size: 9pt; }}
            QGroupBox#MirrorGroup::indicator {{
                width: {int(14*s)}px;
                height: {int(14*s)}px;
                border-radius: {int(4*s)}px;
                border: 1px solid #8E5B66;
                background-color: #161D24;
                margin-left: {int(2*s)}px;
            }}
            QGroupBox#MirrorGroup::indicator:unchecked {{
                background-color: #161D24;
                border: 1px solid #8E5B66;
            }}
            QGroupBox#MirrorGroup::indicator:checked {{
                background-color: #E07267;
                border: 1px solid #E07267;
            }}
            
            QRadioButton::indicator:checked {{ background-color: #E07267; border: 1px solid #E07267; border-radius: {int(7*s)}px; }}
            
            QPushButton {{ 
                background-color: #2E8C74; 
                color: white; 
                font-weight: bold; 
                font-size: 10pt; 
                border-radius: {int(6*s)}px; 
                border: none; 
            }}
            QPushButton:hover {{ background-color: #39A188; }}
            QPushButton#MiniBtn {{
                background-color: #1A232B;
                color: #D5E0E6;
                border: 1px solid #36505C;
                border-radius: {int(4*s)}px;
                font-size: 8pt;
                font-weight: bold;
                padding: 0 {int(8*s)}px;
                min-height: {int(24*s)}px;
            }}
            QPushButton#MiniBtn:hover {{ background-color: #22303A; }}
            
            QPlainTextEdit {{ background: #151D24; border: 1px solid #2F3B45; color: #B8C4CC; border-radius: {int(5*s)}px; font-size: 9pt; selection-background-color: #4FB8A7; }}
        """)
        
        self.inner_layout = QtWidgets.QVBoxLayout(self.frame)
        self.inner_layout.setContentsMargins(int(16*s), int(16*s), int(16*s), int(16*s))
        self.inner_layout.setSpacing(int(10*s))
        
        # 1. Thumbnail Name
        self.lbl_name = QtWidgets.QLabel("Name")
        self.lbl_name.setObjectName("ThumbName")
        self.inner_layout.addWidget(self.lbl_name)
        
        # 2. Stats Section
        stats_grid = QtWidgets.QGridLayout()
        stats_grid.setVerticalSpacing(int(2*s))
        stats_grid.setHorizontalSpacing(int(5*s))
        
        # Row 0: User
        self.lbl_user = QtWidgets.QLabel("User: -"); self.lbl_user.setObjectName("StatLabel")
        stats_grid.addWidget(self.lbl_user, 0, 0, 1, 2)
        
        # Row 1: Date
        self.lbl_date = QtWidgets.QLabel("Date: -"); self.lbl_date.setObjectName("StatLabel")
        stats_grid.addWidget(self.lbl_date, 1, 0, 1, 2)
        
        # Row 2: Source NS
        stats_grid.addWidget(QtWidgets.QLabel("Source NS:", objectName="StatLabel"), 2, 0)
        self.val_ns = QtWidgets.QLineEdit("-")
        self.val_ns.setObjectName("ScrollableText")
        self.val_ns.setReadOnly(True)
        stats_grid.addWidget(self.val_ns, 2, 1, 1, 3)

        # Row 3: FPS / Controls
        stats_grid.addWidget(QtWidgets.QLabel("FPS:", objectName="StatLabel"), 3, 0)
        self.val_fps = QtWidgets.QLabel("-", objectName="StatValue")
        stats_grid.addWidget(self.val_fps, 3, 1)
        
        stats_grid.addWidget(QtWidgets.QLabel("Controls:", objectName="StatLabel"), 3, 2)
        self.val_ctls = QtWidgets.QLabel("-", objectName="StatValue")
        stats_grid.addWidget(self.val_ctls, 3, 3)

        # Row 4: Method / Frames
        stats_grid.addWidget(QtWidgets.QLabel("Method:", objectName="StatLabel"), 4, 0)
        self.val_method = QtWidgets.QLabel("-", objectName="StatValue")
        stats_grid.addWidget(self.val_method, 4, 1)
        
        stats_grid.addWidget(QtWidgets.QLabel("Frames:", objectName="StatLabel"), 4, 2)
        self.val_frames = QtWidgets.QLabel("-", objectName="StatValue")
        stats_grid.addWidget(self.val_frames, 4, 3)

        # Row 5: Tag
        stats_grid.addWidget(QtWidgets.QLabel("Tag:", objectName="StatLabel"), 5, 0)
        tag_wrap = QtWidgets.QWidget()
        tag_lay = QtWidgets.QHBoxLayout(tag_wrap)
        tag_lay.setContentsMargins(0, 0, 0, 0)
        tag_lay.setSpacing(int(4*s))
        self.val_tag = QtWidgets.QComboBox()
        self.val_tag.setObjectName("ScrollableText")
        self.val_tag.setEditable(True)
        self.val_tag.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.val_tag.lineEdit().setPlaceholderText("Comma separated tags")
        self.val_tag.textActivated.connect(self.append_tag_choice)
        self.btn_save_tag = QtWidgets.QPushButton("Save")
        self.btn_save_tag.setObjectName("MiniBtn")
        self.btn_save_tag.clicked.connect(self.save_tags)
        tag_lay.addWidget(self.val_tag, 1)
        tag_lay.addWidget(self.btn_save_tag)
        stats_grid.addWidget(tag_wrap, 5, 1, 1, 3)

        # Row 6: Path
        stats_grid.addWidget(QtWidgets.QLabel("Path:", objectName="StatLabel"), 6, 0)
        self.val_path = QtWidgets.QLineEdit("-")
        self.val_path.setObjectName("ScrollableText")
        self.val_path.setReadOnly(True)
        stats_grid.addWidget(self.val_path, 6, 1, 1, 3)
        
        self.inner_layout.addLayout(stats_grid)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet(f"background-color: #444; height: 1px; margin: {int(5*s)}px 0;")
        self.inner_layout.addWidget(line)
        
        # 3. Namespace Options
        self.grp_ns = QtWidgets.QGroupBox("Target Namespace")
        self.grp_ns.setObjectName("NSGroup")
        ns_lay = QtWidgets.QVBoxLayout(self.grp_ns)
        ns_lay.setSpacing(int(4*s))
        ns_lay.setContentsMargins(int(10*s), int(5*s), int(10*s), int(10*s))
        
        self.bg_ns = QtWidgets.QButtonGroup(self)
        self.rb_ns_picker = QtWidgets.QRadioButton("Picker Namespace (Active Tab)")
        self.rb_ns_picker.setObjectName("NSRadio")
        self.rb_ns_picker.setToolTip("Use the namespace from the currently active picker tab.")
        self.rb_ns_sel = QtWidgets.QRadioButton("Selection Namespace")
        self.rb_ns_sel.setObjectName("NSRadio")
        self.rb_ns_sel.setChecked(True)
        self.rb_ns_sel.setToolTip("Use the namespace from your current Maya selection.")
        self.rb_ns_file = QtWidgets.QRadioButton("File Namespace (Stored)")
        self.rb_ns_file.setObjectName("NSRadio")
        self.rb_ns_file.setToolTip("Use the namespace stored with this library item.")
        
        self.bg_ns.addButton(self.rb_ns_picker)
        self.bg_ns.addButton(self.rb_ns_sel)
        self.bg_ns.addButton(self.rb_ns_file)

        self.rb_ns_picker.toggled.connect(self._sync_mirror_snapshot_state)
        self.rb_ns_sel.toggled.connect(self._sync_mirror_snapshot_state)
        self.rb_ns_file.toggled.connect(self._sync_mirror_snapshot_state)
        
        ns_lay.addWidget(self.rb_ns_picker)
        ns_lay.addWidget(self.rb_ns_sel)
        ns_lay.addWidget(self.rb_ns_file)
        self.inner_layout.addWidget(self.grp_ns)
        
        # 4. Range
        self.inner_layout.addWidget(QtWidgets.QLabel("Range (Start - End):", objectName="RangeLabel"))
        range_lay = QtWidgets.QHBoxLayout()
        self.spin_start = QtWidgets.QSpinBox(); self.spin_start.setRange(-9999, 9999); self.spin_start.setObjectName("RangeInput")
        self.spin_end = QtWidgets.QSpinBox(); self.spin_end.setRange(-9999, 9999); self.spin_end.setObjectName("RangeInput")
        range_lay.addWidget(self.spin_start)
        range_lay.addWidget(QtWidgets.QLabel("-", styleSheet="color: #FF9800; font-weight: bold;"))
        range_lay.addWidget(self.spin_end)
        self.inner_layout.addLayout(range_lay)
        
        # 5. Paste Time
        self.inner_layout.addWidget(QtWidgets.QLabel("Paste Time:", objectName="MethodLabel"))
        time_lay = QtWidgets.QHBoxLayout()
        self.bg_time = QtWidgets.QButtonGroup(self)
        
        self.rb_time_orig = QtWidgets.QRadioButton("Original Time")
        self.rb_time_orig.setObjectName("BlueRadio")
        self.rb_time_orig.setToolTip("Paste keys back to their saved frame positions.")
        self.rb_time_curr = QtWidgets.QRadioButton("Current Frame")
        self.rb_time_curr.setObjectName("BlueRadio")
        self.rb_time_curr.setToolTip("Offset the pasted animation so it starts at the current frame.")
        self.rb_time_orig.setChecked(True)
        
        self.bg_time.addButton(self.rb_time_orig)
        self.bg_time.addButton(self.rb_time_curr)
        
        time_lay.addWidget(self.rb_time_orig)
        time_lay.addWidget(self.rb_time_curr)
        self.inner_layout.addLayout(time_lay)

        # 6. Paste Method
        self.inner_layout.addWidget(QtWidgets.QLabel("Paste Method:", objectName="MethodLabel"))
        self.combo_method = QtWidgets.QComboBox()
        self.combo_method.setObjectName("MethodInput")
        self.combo_method.addItems(["Replace", "Replace All", "Insert", "Merge"])
        self.combo_method.currentTextChanged.connect(self._remember_paste_method)
        self.combo_method.setToolTip("Choose how the pasted animation should affect existing keys.")
        self.inner_layout.addWidget(self.combo_method)
        
        # 7. Mirror Box
        self.grp_mirror = QtWidgets.QGroupBox("Mirror Paste")
        self.grp_mirror.setObjectName("MirrorGroup")
        self.grp_mirror.setCheckable(True)
        self.grp_mirror.setChecked(False)

        m_lay = QtWidgets.QVBoxLayout(self.grp_mirror)
        m_lay.setContentsMargins(int(10*s), int(5*s), int(10*s), int(10*s))
        
        self.bg_mirror = QtWidgets.QButtonGroup(self)
        self.rb_swap = QtWidgets.QRadioButton("Swap"); self.rb_swap.setChecked(True)
        self.rb_swap.setToolTip("Swap left and right animation between both sides.")
        self.rb_l2r = QtWidgets.QRadioButton("Left > Right")
        self.rb_l2r.setToolTip("Copy left-side animation onto the right side.")
        self.rb_r2l = QtWidgets.QRadioButton("Right > Left")
        self.rb_r2l.setToolTip("Copy right-side animation onto the left side.")
        
        self.bg_mirror.addButton(self.rb_swap)
        self.bg_mirror.addButton(self.rb_l2r)
        self.bg_mirror.addButton(self.rb_r2l)
        
        m_lay.addWidget(self.rb_swap); m_lay.addWidget(self.rb_l2r); m_lay.addWidget(self.rb_r2l)
        self.inner_layout.addWidget(self.grp_mirror)

        # 8. Note
        self.lbl_note = QtWidgets.QLabel("Note:")
        self.lbl_note.setStyleSheet("color: #90A0AA; font-size: 9pt; font-weight: bold;")
        self.inner_layout.addWidget(self.lbl_note)
        self.txt_note = QtWidgets.QPlainTextEdit()
        self.txt_note.setReadOnly(True)
        self.txt_note.setFixedHeight(int(52*s))
        self.inner_layout.addWidget(self.txt_note)
        
        # 9. APPLY Button
        self.btn_apply = QtWidgets.QPushButton("APPLY")
        self.btn_apply.setFixedHeight(int(42*s))
        self.btn_apply.setAutoDefault(True)
        self.btn_apply.setDefault(True)
        self.btn_apply.clicked.connect(self.emit_apply)
        self.inner_layout.addWidget(self.btn_apply)
        
        self.main_layout.addWidget(self.frame)

    def get_dpi_scale(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if not screen: return 1.0
        dpi = screen.logicalDotsPerInch()
        # Base DPI is 96. If 4K, often 144 or 192 (150% or 200%)
        return max(1.0, dpi / 96.0)
    
    def _current_target_snapshot_state(self):
        from ARTools.anim import snapshot
        ns_mode = "selection"
        if self.rb_ns_picker.isChecked(): ns_mode = "picker"
        elif self.rb_ns_file.isChecked(): ns_mode = "file"
        
        parent = self.parent()
        meta_data = getattr(self, "meta", {})
        ns = parent.resolve_namespace(ns_mode, {"metadata": meta_data}) if hasattr(parent, "resolve_namespace") else ""
        
        has_snap = os.path.exists(snapshot.get_snapshot_path(ns))
        return has_snap, ns

    def _sync_mirror_snapshot_state(self, *args):
        has_snapshot, ns = self._current_target_snapshot_state()
        ns_text = ns if ns else "Root"
        self.grp_mirror.blockSignals(True)
        if not has_snapshot:
            self.grp_mirror.setChecked(False)
        self.grp_mirror.setEnabled(has_snapshot)
        self.rb_swap.setEnabled(has_snapshot)
        self.rb_l2r.setEnabled(has_snapshot)
        self.rb_r2l.setEnabled(has_snapshot)
        if has_snapshot:
            self.grp_mirror.setToolTip(f"Mirror paste is available for namespace: {ns_text}")
        else:
            self.grp_mirror.setToolTip(f"Mirror paste requires a snapshot for namespace: {ns_text}")
        self.grp_mirror.blockSignals(False)
    
    def populate(self, widget):
        import datetime
        from ARTools import preferences
        
        self.widget = widget
        name = widget.name
        meta = widget.meta
        path = widget.item_root
        
        # --- Kill Picker Radio Button if Picker is closed ---
        picker_open, _ = self.parent()._get_picker_info() if hasattr(self.parent(), "_get_picker_info") else (False, "")
        self.rb_ns_picker.setEnabled(picker_open)
        if not picker_open:
            self.rb_ns_picker.setStyleSheet("color: #55636E;") # Dead gray color
            self.rb_ns_picker.setToolTip("ARTools is not open. Option Disabled.")
            if self.rb_ns_picker.isChecked():
                self.rb_ns_sel.setChecked(True)
        else:
            self.rb_ns_picker.setStyleSheet("color: #D4ECE7;")
            self.rb_ns_picker.setToolTip("Use the namespace from the currently active picker tab.")
        
        self.lbl_name.setText(name)
        self.current_name = name
        self.current_path = path
        self._sync_mirror_snapshot_state()
        
        item_type = meta.get("type", "anim")
        is_pose = (item_type == "pose")
        
        user = meta.get('user', 'Unknown')
        raw_date = meta.get('created_date', meta.get('date', 'Unknown'))
        try:
            dt = datetime.datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S")
            date_str = dt.strftime("%d-%m-%Y %I:%M %p")
        except: date_str = raw_date
        
        method = meta.get('method', 'local').title()
        src_ns = meta.get('source_ns', '-')
        
        self.lbl_user.setText(f"User: {user}")
        self.lbl_date.setText(f"Date: {date_str}")
        
        self.val_ns.setText(src_ns)
        self.val_ns.setCursorPosition(0)
        
        self.val_fps.setText(str(meta.get('fps', '24')))
        self.val_ctls.setText(str(meta.get('controls', 0)))
        
        # --- Accurately generate the ID without the V1 folder! ---
        tags = meta.get("tags", [])
        if not tags and library_core and getattr(self, "widget", None):
            item_id = os.path.join(self.widget.relative_path, self.widget.name).replace("\\", "/").strip("/")
            tags = library_core.get_global_tags().get(item_id, [])
            
        if isinstance(tags, str):
            tags = [tags] if tags else []
        self.populate_tag_options(tags)
        
        self.val_path.setText(path)
        self.val_path.setCursorPosition(0)
        
        self.val_method.setText(f"{method} ({item_type.upper()})")
        
        if is_pose:
            self.val_frames.setText("Pose")
            self.spin_start.setEnabled(False)
            self.spin_end.setEnabled(False)
            self.combo_method.setEnabled(False)
            self.rb_time_orig.setEnabled(False)
            self.rb_time_curr.setChecked(True)
            self.btn_apply.setFocus()
        else:
            start = int(meta.get('start', 0))
            end = int(meta.get('end', 0))
            self.val_frames.setText(str(end - start + 1))
            self.spin_start.setEnabled(True)
            self.spin_end.setEnabled(True)
            self.spin_start.setValue(start)
            self.spin_end.setValue(end)
            self.combo_method.setEnabled(True)
            method_idx = self.combo_method.findText(preferences.Prefs.library_last_paste_method())
            if method_idx >= 0:
                self.combo_method.setCurrentIndex(method_idx)
            self.rb_time_orig.setEnabled(True)
            self.combo_method.setFocus()

        note = meta.get('note', '')
        if note:
            self.txt_note.setPlainText(note)
            self.txt_note.setVisible(True)
            self.lbl_note.setVisible(True)
        else:
            self.txt_note.setVisible(False)
            self.lbl_note.setVisible(False)

    def populate_tag_options(self, selected_tags=None):
        selected_tags = selected_tags or []
        all_tags = set(selected_tags)
        if library_core:
            global_tags = library_core.get_global_tags()
            for item_id, tag_list in global_tags.items():
                if os.path.exists(os.path.join(library_core.data_root, item_id)):
                    all_tags.update(tag_list)
        text = ", ".join(selected_tags) if selected_tags else ""
        self.val_tag.blockSignals(True)
        self.val_tag.clear()
        for tag in sorted(all_tags):
            self.val_tag.addItem(tag)
        self.val_tag.setEditText(text)
        if self.val_tag.lineEdit():
            self.val_tag.lineEdit().setCursorPosition(0)
        self.val_tag.blockSignals(False)

    def append_tag_choice(self, tag):
        current = [t.strip() for t in self.val_tag.currentText().replace(";", ",").split(",") if t.strip()]
        if tag and tag not in current:
            current.append(tag)
        self.val_tag.setEditText(", ".join(current))
        if self.val_tag.lineEdit():
            self.val_tag.lineEdit().setCursorPosition(0)

    def save_tags(self):
        if not library_core or not getattr(self, "widget", None):
            return

        raw = self.val_tag.currentText().replace(";", ",")
        tags = [t.strip() for t in raw.split(",") if t.strip()]
        
        # --- Accurately generate the ID without the V1 folder! ---
        item_id = os.path.join(self.widget.relative_path, self.widget.name).replace("\\", "/").strip("/")
        meta_path = os.path.join(self.widget.item_root, "meta.json")
        
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, "r") as fh:
                meta = json.load(fh)
        meta["tags"] = tags
        with open(meta_path, "w") as fh:
            json.dump(meta, fh, indent=4)
            
        library_core.update_global_tags(item_id, tags)
        self.populate_tag_options(tags)
        
        parent = self.parent()
        if parent and hasattr(parent, "current_item") and parent.current_item == self.widget:
            parent.current_item.meta["tags"] = tags
        if parent and hasattr(parent, "populate_tag_filter"):
            parent.populate_tag_filter()

    def emit_apply(self):
        self._remember_paste_method(self.combo_method.currentText())
        ns_mode = "selection"
        if self.rb_ns_picker.isChecked(): ns_mode = "picker"
        elif self.rb_ns_file.isChecked(): ns_mode = "file"
        
        data = {
            "namespace_mode": ns_mode,
            "mirror": self.grp_mirror.isEnabled() and self.grp_mirror.isChecked(),
            "mirror_mode": "swap",
            "paste_method": self.combo_method.currentText(),
            "paste_time": "original" if self.rb_time_orig.isChecked() else "current",
            "start_frame": self.spin_start.value(),
            "end_frame": self.spin_end.value()
        }
        if self.rb_l2r.isChecked(): data["mirror_mode"] = "l2r"
        elif self.rb_r2l.isChecked(): data["mirror_mode"] = "r2l"
        
        self.apply_triggered.emit(data)
        self.close()

    def _remember_paste_method(self, method):
        global _last_paste_method
        from ARTools import preferences
        if method:
            _last_paste_method = method
            preferences.Prefs.set_library_last_paste_method(method)

    def set_namespace_mode_ui(self, mode):
        self.bg_ns.blockSignals(True)
        if mode == "picker":
            self.rb_ns_picker.setChecked(True)
        elif mode == "file":
            self.rb_ns_file.setChecked(True)
        else:
            self.rb_ns_sel.setChecked(True)
        self.bg_ns.blockSignals(False)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_pos = QtGui.QCursor.pos()

    def mouseMoveEvent(self, event):
        if getattr(self, 'old_pos', None) is not None:
            delta = QtGui.QCursor.pos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = QtGui.QCursor.pos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.emit_apply()
            event.accept()
            return
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
            event.accept()
            return
        super(PropertySatellite, self).keyPressEvent(event)

# -------------------------------------------------------------------------
# ICONS FOR LIBRARY FOLDERS
# -------------------------------------------------------------------------
class CodeIcon:
    """Generates standalone icons purely from code (No external files needed)."""
    _cache = {}

    @staticmethod
    def get(name):
        if name in CodeIcon._cache: 
            return CodeIcon._cache[name]
            
        # You can add or change any of these symbols via code!
        icon_map = {
            "Folder": "📁", "Full Human": "🧍", "Full Animal": "🐕", 
            "Human Head": "👤", "Animal Head": "🐶", "Bird": "🦅", 
            "Bird Head": "🦜", "Lock": "🔒", "Delete": "❌", 
            "Dustbin": "🗑️", "Bicycle": "🚲", "Car": "🚗", 
            "Tree": "🌳", "Layer": "📑", "Book": "📖", 
            "Fire": "🔥", "Bulb": "💡", "No Entry": "⛔",
            "Star": "⭐", "Warning": "⚠️", "Prop": "📦"
        }
        
        symbol = icon_map.get(name, "📁")
        
        # Draw the symbol natively into a QPixmap
        pixmap = QtGui.QPixmap(64, 64)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        
        font = painter.font()
        font.setPixelSize(46)  # Large, crisp resolution
        painter.setFont(font)
        
        painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, symbol)
        painter.end()
        
        icon = QtGui.QIcon(pixmap)
        CodeIcon._cache[name] = icon
        return icon

# -------------------------------------------------------------------------
# BREADCRUMB NAVIGATOR & VISUAL FOLDERS
# -------------------------------------------------------------------------
class BreadcrumbWidget(QtWidgets.QWidget):
    path_clicked = QtCore.Signal(str)

    def __init__(self, parent=None):
        super(BreadcrumbWidget, self).__init__(parent)
        
        screen = QtWidgets.QApplication.primaryScreen()
        self.scale = max(1.0, screen.logicalDotsPerInch() / 96.0) if screen else 1.0
        
        exact_height = int(26 * self.scale)
        self.setFixedHeight(exact_height)
        
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. The Single Box Button (Icon Only!)
        self.btn_current = QtWidgets.QPushButton(" ▼")
        self.btn_current.setCursor(QtCore.Qt.PointingHandCursor)
        
        # --- CRITICAL FIX: Fixed policy keeps the button tight and compact! ---
        self.btn_current.setFixedHeight(exact_height)
        self.btn_current.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        
        # Default CSS Style
        self.base_style = f"""
            QPushButton {{ 
                background: #1A232B;
                border: 1px solid #2F3B45;
                padding: 0px {int(6 * self.scale)}px;
                border-radius: {int(4 * self.scale)}px;
                font-size: 9pt;
                font-weight: bold;
                text-align: center;
            }}
            QPushButton:hover {{ 
                border: 1px solid #51616D;
                background: #202B34;
            }}
            QPushButton:pressed {{
                background: #12171D;
            }}
        """
        self.btn_current.setStyleSheet(self.base_style + "color: #5285a6;")
        self.btn_current.clicked.connect(self.show_full_tree)
        
        self.main_layout.addWidget(self.btn_current)
        self.main_layout.addStretch()

    def build(self, current_path):
        self.current_path = current_path
        
        if not current_path:
            self.btn_current.setText(" ▼")
            self.btn_current.setStyleSheet(self.base_style + "color: #5285a6;")
            self.btn_current.setIcon(CodeIcon.get("Folder"))
            self.btn_current.setToolTip("Library Root")
            return

        folder_name = current_path.replace("\\", "/").split("/")[-1]
        
        # --- CRITICAL FIX: Text removed. Full name securely stored in Tooltip! ---
        self.btn_current.setText(" ▼")
        self.btn_current.setToolTip(folder_name) 
        
        meta = library_core.get_folder_meta(current_path) if library_core else {}
        
        # --- CRITICAL FIX: Dynamically color the ENTIRE box if a color is assigned ---
        if meta.get("color"):
            col = meta["color"]
            colored_box_style = f"""
                QPushButton {{ 
                    background: {col};
                    border: 1px solid {col};
                    padding: 0px {int(6 * self.scale)}px;
                    border-radius: {int(4 * self.scale)}px;
                    font-size: 9pt;
                    font-weight: bold;
                    color: #FFFFFF;
                }}
                QPushButton:hover {{ 
                    background: {col};
                    border: 1px solid #FFFFFF;
                }}
                QPushButton:pressed {{
                    background: #12171D;
                }}
            """
            self.btn_current.setStyleSheet(colored_box_style)
        else:
            # Fallback to default dark box
            self.btn_current.setStyleSheet(self.base_style + "color: #5285a6;")
        
        if meta.get("icon"): self.btn_current.setIcon(CodeIcon.get(meta["icon"]))
        else: self.btn_current.setIcon(CodeIcon.get("Folder"))

    def show_full_tree(self):
        """Spawns the full library tree inside a popup menu."""
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu { background: #1A2129; border: 1px solid #555; border-radius: 4px; }")
        
        tree = QtWidgets.QTreeWidget(menu)
        tree.setHeaderHidden(True)
        tree.setStyleSheet("QTreeWidget { background: transparent; border: none; color: #DDD; font-weight: bold; } QTreeWidget::item { padding: 4px; } QTreeWidget::item:hover { background: #265468; } QTreeWidget::item:selected { background: #5285a6; }")
        tree.setMinimumWidth(320)
        tree.setMinimumHeight(450)
        
        root_item = QtWidgets.QTreeWidgetItem(["Library Root"])
        root_item.setData(0, QtCore.Qt.UserRole, "")
        root_item.setIcon(0, CodeIcon.get("Folder"))
        tree.addTopLevelItem(root_item)
        
        struct = library_core.get_structure() if library_core else {}
        
        # Recursively build the FULL library tree
        def _build_tree(parent_item, current_struct, current_path):
            for key in sorted(current_struct.keys()):
                this_path = os.path.join(current_path, key).replace("\\", "/")
                item = QtWidgets.QTreeWidgetItem([key])
                item.setData(0, QtCore.Qt.UserRole, this_path)
                
                meta = library_core.get_folder_meta(this_path)
                if meta.get("color"): item.setForeground(0, QtGui.QColor(meta["color"]))
                
                if meta.get("icon"): item.setIcon(0, CodeIcon.get(meta["icon"]))
                else: item.setIcon(0, CodeIcon.get("Folder"))
                
                parent_item.addChild(item)
                _build_tree(item, current_struct[key], this_path)
        
        _build_tree(root_item, struct, "")
        
        # --- Smart Path Expansion & Highlighting ---
        target_item = root_item
        iterator = QtWidgets.QTreeWidgetItemIterator(tree)
        while iterator.value():
            item = iterator.value()
            if item.data(0, QtCore.Qt.UserRole) == (self.current_path or ""):
                target_item = item
                break
            iterator += 1
            
        # Expand ONLY the parents upward to reveal the target
        p = target_item
        while p:
            p.setExpanded(True)
            p = p.parent()
            
        tree.setCurrentItem(target_item)
        tree.scrollToItem(target_item, QtWidgets.QAbstractItemView.PositionAtCenter)
        
        # Connect clicking to navigate instantly
        def on_item_clicked(item, col):
            path = item.data(0, QtCore.Qt.UserRole)
            self.path_clicked.emit(path)
            menu.close()
            
        tree.itemClicked.connect(on_item_clicked)
        
        # Inject tree into menu and display
        action = QtWidgets.QWidgetAction(menu)
        action.setDefaultWidget(tree)
        menu.addAction(action)
        menu.exec_(self.btn_current.mapToGlobal(QtCore.QPoint(0, self.btn_current.height())))

class FolderCustomizerDialog(QtWidgets.QDialog):
    def __init__(self, current_meta, parent=None):
        super(FolderCustomizerDialog, self).__init__(parent)
        self.setWindowTitle("Customize Folder")
        self.setFixedSize(380, 480)
        self.setStyleSheet("background-color: #12171D; color: white;")
        
        self.result_meta = {"color": current_meta.get("color", ""), "icon": current_meta.get("icon", "")}
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("<b>Folder Color Tag:</b>"))
        
        color_grid = QtWidgets.QGridLayout()
        # Expanded 24 Color Palette!
        colors = [
            "", "#5285a6", "#2980b9", "#8e44ad", "#9b59b6", "#27ae60", 
            "#2ecc71", "#16a085", "#1abc9c", "#f39c12", "#f1c40f", "#d35400", 
            "#e67e22", "#e74c3c", "#c0392b", "#e84393", "#fd79a8", "#34495e", 
            "#7f8c8d", "#bdc3c7", "#FFB6C1", "#87CEFA", "#98FB98", "#DDA0DD"
        ]
        
        self.color_btns = []
        for i, hex_col in enumerate(colors):
            btn = QtWidgets.QPushButton("X" if not hex_col else "")
            btn.setFixedSize(30, 30)
            btn.setStyleSheet(f"background-color: {hex_col or '#333'}; border: 2px solid #111; border-radius: 4px; color: #888; font-weight: bold;")
            
            # --- CRITICAL FIX: lambda *_ safely absorbs the PyQt 'checked' signal argument! ---
            btn.clicked.connect(lambda *_, c=hex_col, b=btn: self.select_color(c, b))
            # ---------------------------------------------------------------------------------
            
            color_grid.addWidget(btn, i // 6, i % 6)
            self.color_btns.append((hex_col, btn))
            
        layout.addLayout(color_grid)
        layout.addSpacing(15)
        
        layout.addWidget(QtWidgets.QLabel("<b>Folder Icon:</b>"))
        icon_grid = QtWidgets.QGridLayout()
        
        # Fully Custom Code-Based Icons
        icons = [
            "", "Folder", "Full Human", "Full Animal", "Human Head", 
            "Animal Head", "Bird", "Bird Head", "Prop", "Tree", 
            "Car", "Bicycle", "Fire", "Bulb", "Book", "Layer",
            "Star", "Lock", "Warning", "No Entry", "Delete", "Dustbin"
        ]
        
        self.icon_btns = []
        for i, name in enumerate(icons):
            btn = QtWidgets.QPushButton("X" if not name else "")
            btn.setFixedSize(36, 36)
            if name:
                btn.setIcon(CodeIcon.get(name))
                btn.setIconSize(QtCore.QSize(24, 24))
            btn.setStyleSheet("background-color: #333; border: 2px solid #111; border-radius: 4px; color: #888; font-weight: bold;")
            
            btn.clicked.connect(lambda *_, n=name, b=btn: self.select_icon(n, b))
            icon_grid.addWidget(btn, i // 6, i % 6)
            self.icon_btns.append((name, btn))
        
        layout.addLayout(icon_grid)
        layout.addStretch()
        
        btn_apply = QtWidgets.QPushButton("Apply Visuals")
        btn_apply.setFixedHeight(30)
        btn_apply.setStyleSheet("background-color: #5285a6; color: white; font-weight: bold; border-radius: 4px;")
        btn_apply.clicked.connect(self.accept)
        layout.addWidget(btn_apply)
        
        self.select_color(self.result_meta["color"], next((b for c, b in self.color_btns if c == self.result_meta["color"]), self.color_btns[0][1]))
        self.select_icon(self.result_meta["icon"], next((b for i, b in self.icon_btns if i == self.result_meta["icon"]), self.icon_btns[0][1]))

    def select_color(self, hex_col, btn):
        self.result_meta["color"] = hex_col
        for c, b in self.color_btns: b.setStyleSheet(b.styleSheet().replace("border: 2px solid white;", "border: 2px solid #111;"))
        btn.setStyleSheet(btn.styleSheet().replace("border: 2px solid #111;", "border: 2px solid white;"))

    def select_icon(self, icon_name, btn):
        self.result_meta["icon"] = icon_name
        for n, b in self.icon_btns: b.setStyleSheet(b.styleSheet().replace("border: 2px solid white;", "border: 2px solid #111;"))
        btn.setStyleSheet(btn.styleSheet().replace("border: 2px solid #111;", "border: 2px solid white;"))

class SidePanelSatellite(QtWidgets.QDialog):
    def __init__(self, browser_parent):
        super(SidePanelSatellite, self).__init__(browser_parent)
        self.browser = browser_parent
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        s = self.browser.scale
        self.setFixedWidth(int(220 * s))
        
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.frame = QtWidgets.QFrame()
        self.frame.setStyleSheet(f"QFrame {{ background-color: #12171D; border: 1px solid #29323B; border-radius: {int(6*s)}px; }}")
        lay = QtWidgets.QVBoxLayout(self.frame)
        lay.setContentsMargins(int(8*s), int(8*s), int(8*s), int(8*s))
        lay.setSpacing(int(6*s))
        
        toggle_lay = QtWidgets.QHBoxLayout()
        toggle_lay.setSpacing(0)
        self.btn_tab_folders = QtWidgets.QPushButton("📁 Folders")
        self.btn_tab_sets = QtWidgets.QPushButton("🎯 Sets")
        self.btn_tab_folders.setCheckable(True); self.btn_tab_folders.setChecked(True)
        self.btn_tab_sets.setCheckable(True)
        
        style = "QPushButton { background: #1A2129; color: #888; border: 1px solid #333; padding: 6px; font-weight: bold; } QPushButton:checked { background: #265468; color: white; border-color: #265468; }"
        self.btn_tab_folders.setStyleSheet(style + f"border-top-left-radius: {int(4*s)}px; border-bottom-left-radius: {int(4*s)}px;")
        self.btn_tab_sets.setStyleSheet(style + f"border-top-right-radius: {int(4*s)}px; border-bottom-right-radius: {int(4*s)}px;")
        
        toggle_lay.addWidget(self.btn_tab_folders)
        toggle_lay.addWidget(self.btn_tab_sets)
        lay.addLayout(toggle_lay)
        
        self.stack = QtWidgets.QStackedWidget()
        lay.addWidget(self.stack)
        
        # --- FOLDERS PAGE ---
        self.page_folders = QtWidgets.QWidget()
        f_lay = QtWidgets.QVBoxLayout(self.page_folders)
        f_lay.setContentsMargins(0, 4, 0, 0)
        self.tree_folders = QtWidgets.QTreeWidget()
        self.tree_folders.setHeaderHidden(True)
        self.tree_folders.setStyleSheet(f"background: #1A2129; border: 1px solid #333; color: #DDD; border-radius: {int(4*s)}px; outline: none;")
        self.tree_folders.itemClicked.connect(self.on_folder_clicked)
        self.tree_folders.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree_folders.customContextMenuRequested.connect(self.show_folder_context)
        f_lay.addWidget(self.tree_folders)
        self.stack.addWidget(self.page_folders)
        
        # --- SETS PAGE ---
        self.page_sets = QtWidgets.QWidget()
        s_lay = QtWidgets.QVBoxLayout(self.page_sets)
        s_lay.setContentsMargins(0, 4, 0, 0)
        self.chk_inherit = QtWidgets.QCheckBox("Use Top Selection List")
        self.chk_inherit.setStyleSheet(f"color: #A0B0BA; font-size: {int(9*s)}px; border: none;")
        self.chk_inherit.toggled.connect(self.on_inherit_toggled)
        s_lay.addWidget(self.chk_inherit)
        
        self.list_sets = QtWidgets.QListWidget()
        self.list_sets.setStyleSheet(f"background: #1A2129; border: 1px solid #333; color: #DDD; border-radius: {int(4*s)}px; outline: none;")
        self.list_sets.itemClicked.connect(self.on_set_clicked)
        self.list_sets.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list_sets.customContextMenuRequested.connect(self.show_set_context)
        s_lay.addWidget(self.list_sets)
        
        self.btn_add = QtWidgets.QPushButton("Add Selected")
        self.btn_add.setFixedHeight(int(26*s))
        self.btn_add.setStyleSheet(f"background-color: #265468; border-radius: {int(4*s)}px; font-weight: bold; color: white;")
        self.btn_add.clicked.connect(self.browser.add_selection_set)
        s_lay.addWidget(self.btn_add)
        self.stack.addWidget(self.page_sets)
        
        self.main_layout.addWidget(self.frame)
        
        self.btn_tab_folders.clicked.connect(lambda: self.switch_tab(0))
        self.btn_tab_sets.clicked.connect(lambda: self.switch_tab(1))

    def switch_tab(self, idx):
        self.btn_tab_folders.setChecked(idx == 0)
        self.btn_tab_sets.setChecked(idx == 1)
        self.stack.setCurrentIndex(idx)

    # -- FOLDERS LOGIC --
    def refresh_folders(self):
        self.tree_folders.clear()
        if not library_core: return
        struct = library_core.get_structure()
        pinned = library_core.get_global_pinned_folders()
        
        # --- CRITICAL UPDATE 1: Root Folder uses CodeIcon ---
        root_item = QtWidgets.QTreeWidgetItem(["Library Root"])
        root_item.setData(0, QtCore.Qt.UserRole, "")
        root_item.setIcon(0, CodeIcon.get("Folder")) 
        self.tree_folders.addTopLevelItem(root_item)
        
        if pinned:
            pin_root = QtWidgets.QTreeWidgetItem(["Pinned Folders"])
            pin_root.setForeground(0, QtGui.QColor("#F5B041"))
            pin_root.setData(0, QtCore.Qt.UserRole, "__pinned_header__")
            self.tree_folders.addTopLevelItem(pin_root)
            for p_path in pinned:
                name = p_path.split("/")[-1]
                p_item = QtWidgets.QTreeWidgetItem([name])
                p_item.setData(0, QtCore.Qt.UserRole, p_path)
                
                # --- CRITICAL UPDATE 2: Pinned items use CodeIcon Star ---
                p_item.setIcon(0, CodeIcon.get("Star"))
                
                meta = library_core.get_folder_meta(p_path)
                if meta.get("color"): p_item.setForeground(0, QtGui.QColor(meta["color"]))
                pin_root.addChild(p_item)

        def _build_tree(parent_item, current_struct, current_path):
            for key in sorted(current_struct.keys()):
                this_path = os.path.join(current_path, key).replace("\\", "/")
                item = QtWidgets.QTreeWidgetItem([key])
                item.setData(0, QtCore.Qt.UserRole, this_path)
                
                meta = library_core.get_folder_meta(this_path)
                if meta.get("color"): item.setForeground(0, QtGui.QColor(meta["color"]))
                
                # --- Process Maya's internal icons properly! ---
                if meta.get("icon"): item.setIcon(0, CodeIcon.get(meta["icon"]))
                else: item.setIcon(0, CodeIcon.get("Folder"))
                
                parent_item.addChild(item)
                _build_tree(item, current_struct[key], this_path)

        _build_tree(root_item, struct, "")
        root_item.setExpanded(True)
        if pinned: pin_root.setExpanded(True)

    def sync_folder_selection(self, rel_path):
        target_item = None
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree_folders)
        
        while iterator.value():
            item = iterator.value()
            # 1. Force collapse everything (except top headers) to keep UI clean
            if item.parent(): item.setExpanded(False)
            
            # 2. Find the active folder
            if item.data(0, QtCore.Qt.UserRole) == (rel_path or ""):
                target_item = item
            iterator += 1

        if target_item:
            # 3. Expand only the direct path to the active folder
            p = target_item
            while p:
                p.setExpanded(True)
                p = p.parent()
            
            # 4. Highlight it beautifully and scroll to it!
            self.tree_folders.setCurrentItem(target_item)
            self.tree_folders.scrollToItem(target_item, QtWidgets.QAbstractItemView.PositionAtCenter)

    def on_folder_clicked(self, item, col):
        path = item.data(0, QtCore.Qt.UserRole)
        if path == "__pinned_header__": return
        self.browser.set_current_path(path)

    def show_folder_context(self, pos):
        item = self.tree_folders.itemAt(pos)
        if not item: return
        rel_path = item.data(0, QtCore.Qt.UserRole)
        if rel_path == "__pinned_header__": return

        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu { background: #2A2A2A; color: #EEE; border: 1px solid #555; } QMenu::item:selected { background: #4CAF50; }")
        
        if rel_path != "":
            menu.addAction("Customize Visuals...", lambda: self.customize_folder(rel_path))
            meta = library_core.get_folder_meta(rel_path)
            is_pinned = meta.get("pin_global", False)
            menu.addAction("Unpin from Top" if is_pinned else "Pin to Top (Global)", lambda: self.toggle_pin(rel_path, not is_pinned))
            menu.addSeparator()

        menu.addAction("New Folder", lambda: self.browser.create_new_folder(rel_path))
        
        if rel_path != "":
            menu.addAction("Rename", lambda: self.rename_folder(rel_path))
            menu.addAction("Delete", lambda: self.delete_folder(rel_path))
        
        menu.addSeparator()
        menu.addAction("Open in OS", lambda: self.browser.open_current_location())
        menu.exec_(self.tree_folders.mapToGlobal(pos))

    def customize_folder(self, rel_path):
        meta = library_core.get_folder_meta(rel_path)
        dlg = FolderCustomizerDialog(meta, self)
        if dlg.exec_():
            library_core.set_folder_meta(rel_path, dlg.result_meta)
            self.refresh_folders()
            self.browser.refresh_grid()

    def toggle_pin(self, rel_path, state):
        library_core.set_folder_meta(rel_path, {"pin_global": state})
        self.refresh_folders()

    def rename_folder(self, rel_path):
        old_name = rel_path.split("/")[-1]
        new_name, ok = QtWidgets.QInputDialog.getText(self, "Rename", "New Name:", text=old_name)
        if ok and new_name and new_name != old_name:
            if library_core.rename_folder(rel_path, new_name):
                self.browser.reload_lib()
            else: cmds.warning("Rename failed.")

    def delete_folder(self, rel_path):
        if QtWidgets.QMessageBox.question(self, "Delete", f"Delete folder?\n{rel_path}", QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
            library_core.delete_folder(rel_path)
            self.browser.reload_lib()

    # -- SETS LOGIC --
    def refresh_sets(self, path):
        self.list_sets.clear()
        if path is None: return
        local_sets, ancestor_list, use_inherited, has_ancestor = library_core.get_resolved_sets(path)
        
        self.chk_inherit.blockSignals(True)
        self.chk_inherit.setVisible(path != "")
        self.chk_inherit.setEnabled(has_ancestor)
        self.chk_inherit.setChecked(use_inherited)
        self.chk_inherit.blockSignals(False)
        
        overridden = set(local_sets.keys())
        for anc_name, anc_sets in ancestor_list:
            header = QtWidgets.QListWidgetItem(f"--- {anc_name} ---")
            header.setTextAlignment(QtCore.Qt.AlignCenter)
            header.setForeground(QtGui.QColor("#7A8B99"))
            header.setFlags(QtCore.Qt.NoItemFlags)
            self.list_sets.addItem(header)
            for name in sorted(anc_sets.keys()):
                if name not in overridden:
                    item = QtWidgets.QListWidgetItem(name)
                    item.setForeground(QtGui.QColor("#F5B041"))
                    item.setData(QtCore.Qt.UserRole, "inherited")
                    item.setData(QtCore.Qt.UserRole + 1, name)
                    self.list_sets.addItem(item)

        if ancestor_list and local_sets:
            header = QtWidgets.QListWidgetItem("--- Local ---")
            header.setTextAlignment(QtCore.Qt.AlignCenter)
            header.setForeground(QtGui.QColor("#7A8B99"))
            header.setFlags(QtCore.Qt.NoItemFlags)
            self.list_sets.addItem(header)

        for name in sorted(local_sets.keys()):
            item = QtWidgets.QListWidgetItem(name)
            item.setForeground(QtGui.QColor("#FFFFFF"))
            item.setData(QtCore.Qt.UserRole, "local")
            item.setData(QtCore.Qt.UserRole + 1, name)
            self.list_sets.addItem(item)

    def on_inherit_toggled(self, state):
        library_core.set_inheritance_flag(self.browser.current_path, state)
        self.refresh_sets(self.browser.current_path)

    def on_set_clicked(self, item):
        raw_name = item.data(QtCore.Qt.UserRole + 1) or item.text()
        self.browser.select_set_controls(raw_name, self.browser.current_path)
        
    def show_set_context(self, pos):
        item = self.list_sets.itemAt(pos)
        if not item: return
        is_inherited = item.data(QtCore.Qt.UserRole) == "inherited"
        raw_name = item.data(QtCore.Qt.UserRole + 1) or item.text()
        
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu { background: #2A2A2A; color: #EEE; border: 1px solid #555; } QMenu::item:selected { background: #4CAF50; }")
        menu.addAction("Select Controls", lambda: self.browser.select_set_controls(raw_name, self.browser.current_path))
        menu.addSeparator()
        
        act_upd = menu.addAction("Update with Selected", lambda: self.browser.update_selection_set(raw_name))
        act_ren = menu.addAction("Rename Set", lambda: self.browser.rename_selection_set(raw_name))
        act_del = menu.addAction("Delete Set", lambda: self.browser.delete_selection_set(raw_name))
        
        if is_inherited: act_upd.setEnabled(False); act_ren.setEnabled(False); act_del.setEnabled(False)
        menu.exec_(self.list_sets.mapToGlobal(pos))

# -------------------------------------------------------------------------
# THUMBNAIL WIDGET
# -------------------------------------------------------------------------
class ThumbnailWidget(QtWidgets.QFrame):
    clicked = QtCore.Signal(object)
    action_triggered = QtCore.Signal(str, object)

    def __init__(self, name, relative_path, thumb_path, item_root, meta, versions=None, current_version=None, show_detail=True, parent=None):
        super(ThumbnailWidget, self).__init__(parent)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.name = name
        self.relative_path = relative_path
        self.meta = meta
        self.thumb_path = thumb_path
        self.item_root = item_root
        self.versions = list(versions or ["V1"])
        self.current_version = current_version or (self.versions[-1] if self.versions else "V1")
        self.show_detail = bool(show_detail)
        self.sequence_loaded = False
        self.sequence_loading = False
        self.pose_icon_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "icons", "lib_pose.svg"))
        self.anim_icon_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "icons", "film_strip.svg"))
        
        self.pixmaps = []
        self.idx = 0
        self.is_selected = False
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.advance)
        
        self.hover_timer = QtCore.QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self._trigger_load_sequence)
        
        self.type_col = QtGui.QColor("#4CAF50") if meta.get("method") == "local" else QtGui.QColor("#2196F3")

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.slider.setRange(0, 100); self.slider.setValue(0)
        self.slider.setCursor(QtCore.Qt.SizeHorCursor)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { border: none; height: 4px; background: #252525; margin: 0px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #FF9800; border: 1px solid #222; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
            QSlider::sub-page:horizontal { background: #FF9800; border-radius: 2px; }
        """)
        self.blender = None
        self.slider.sliderPressed.connect(self._on_slider_press)
        self.slider.sliderMoved.connect(self._on_slider_move)
        self.slider.sliderReleased.connect(self._on_slider_release)

        self.version_combo = QtWidgets.QComboBox(self)
        self.version_combo.setObjectName("VersionCombo")
        self.version_combo.setCursor(QtCore.Qt.PointingHandCursor)
        self.version_combo.setStyleSheet("""
            QComboBox#VersionCombo {
                background-color: rgba(17, 24, 30, 215);
                color: #DCE5EA;
                border: 1px solid #465661;
                border-radius: 6px;
                padding: 0px 4px 0px 5px;
                font-size: 8pt;
                font-weight: bold;
            }
            QComboBox#VersionCombo:hover { border: 1px solid #6B7E8A; }
            QComboBox#VersionCombo::drop-down { border: none; width: 10px; }
            QComboBox#VersionCombo::down-arrow { width: 6px; height: 6px; }
            QComboBox#VersionCombo QAbstractItemView {
                background: #182129;
                color: #E8EEF2;
                border: 1px solid #32414B;
                selection-background-color: #4FB8A7;
                selection-color: #FFF;
            }
        """)
        self.version_combo.currentTextChanged.connect(self._on_version_selected)
        self.set_versions(self.versions, self.current_version)
        
        if self.meta.get("type") == "pose":
            self.slider.show(); self.slider.raise_()
        else: self.slider.hide()

    def set_versions(self, versions, current_version=None):
        self.versions = list(versions or ["V1"])
        self.current_version = current_version or (self.versions[-1] if self.versions else "V1")
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItems(self.versions)
        idx = self.version_combo.findText(self.current_version)
        if idx >= 0:
            self.version_combo.setCurrentIndex(idx)
        self.version_combo.blockSignals(False)
        metrics = self.version_combo.fontMetrics()
        text_w = max([metrics.horizontalAdvance(v) for v in self.versions] + [metrics.horizontalAdvance("V1")])
        self._version_combo_width = max(34, text_w + 20)
        self.update()

    def set_version_payload(self, version, thumb_path, item_root, meta):
        self.current_version = version or self.current_version
        self.thumb_path = thumb_path
        self.item_root = item_root
        self.meta = meta or {}
        self.type_col = QtGui.QColor("#4CAF50") if self.meta.get("method") == "local" else QtGui.QColor("#2196F3")
        self.sequence_loaded = False
        self.sequence_loading = False
        self.pixmaps = []
        self.idx = 0
        self.scaled_cache = {}
        self.timer.stop()
        self.hover_timer.stop()
        if self.meta.get("type") == "pose":
            self.slider.show()
            self.slider.raise_()
        else:
            self.slider.hide()
        self.update()

    def _on_version_selected(self, version):
        if not version or version == self.current_version:
            return
        self.action_triggered.emit("change_version", (self, version))

    def _draw_type_icon(self, painter, rect, is_pose):
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        icon_path = self.pose_icon_path if is_pose else self.anim_icon_path
        icon = QtGui.QIcon(icon_path)
        pixmap = icon.pixmap(rect.size())
        if not pixmap.isNull():
            shadow = QtGui.QPixmap(pixmap.size())
            shadow.fill(QtCore.Qt.transparent)
            shadow_painter = QtGui.QPainter(shadow)
            shadow_painter.drawPixmap(0, 0, pixmap)
            shadow_painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
            shadow_painter.fillRect(shadow.rect(), QtGui.QColor(0, 0, 0, 210))
            shadow_painter.end()
            shadow_rect = QtCore.QRect(rect)
            shadow_rect.translate(1, 1)
            painter.setOpacity(0.5)
            painter.drawPixmap(shadow_rect, shadow)
            painter.setOpacity(1.0)
            painter.drawPixmap(rect, pixmap)

        painter.restore()

    def set_loaded_image(self, images):
        if images:
            self.sequence_loading = False
            if len(images) > 1:
                self.sequence_loaded = True
            
            self.pixmaps = images
            self.scaled_cache = {}
            self.update()

            if self.underMouse() and len(self.pixmaps) > 1:
                fps = float(self.meta.get("fps", 24.0))
                if fps <= 0: fps = 24.0
                if not self.timer.isActive():
                    self.timer.start(int(1000/fps))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        
        radius = 10.0
        outer_rect = QtCore.QRectF(1, 1, w - 2, h - 2)
        path = QtGui.QPainterPath()
        path.addRoundedRect(outer_rect, radius, radius)
        painter.setClipPath(path)
        
        item_type = self.meta.get("type", "anim")
        is_pose = (item_type == "pose")
        text_offset = 16 if is_pose else 0
        
        bg_col = QtGui.QColor("#10161C")
        if self.is_selected: bg_col = QtGui.QColor("#162028")
        painter.fillRect(self.rect(), bg_col)
        
        if self.pixmaps:
            if not hasattr(self, 'scaled_cache'):
                self.scaled_cache = {}
            
            if self.idx not in self.scaled_cache:
                raw_pix = QtGui.QPixmap.fromImage(self.pixmaps[self.idx])
                if not raw_pix.isNull():
                    self.scaled_cache[self.idx] = raw_pix.scaled(w, h, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.FastTransformation)
                else:
                    self.scaled_cache[self.idx] = raw_pix

            scaled_pix = self.scaled_cache[self.idx]
            if not scaled_pix.isNull():
                image_rect = QtCore.QRect(1, 1, w - 2, h - 2 - text_offset)
                x = image_rect.x() + int((image_rect.width() - scaled_pix.width()) / 2.0)
                y = image_rect.y() + int((image_rect.height() - scaled_pix.height()) / 2.0)
                painter.drawPixmap(x, y, scaled_pix)
        else:
            painter.setPen(QtGui.QColor("#61717D"))
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "No Image")

        top_glow = QtGui.QLinearGradient(0, 0, 0, 36)
        top_glow.setColorAt(0, QtGui.QColor(255, 255, 255, 28))
        top_glow.setColorAt(1, QtGui.QColor(255, 255, 255, 0))
        painter.fillRect(0, 0, w, 36, top_glow)

        grad_height = 54
        grad_y = h - grad_height - text_offset
        
        grad = QtGui.QLinearGradient(0, grad_y, 0, h - text_offset)
        grad.setColorAt(0, QtGui.QColor(0, 0, 0, 0))
        grad.setColorAt(1, QtGui.QColor(7, 10, 14, 235))
        painter.fillRect(0, grad_y, w, grad_height, grad)

        type_rect = QtCore.QRect(8, 6, 24, 22)
        self._draw_type_icon(painter, type_rect, is_pose)

        if self.show_detail:
            method_text = (self.meta.get("method", "local") or "local").upper()
            method_width = max(46, 12 + (len(method_text) * 7))
            method_rect = QtCore.QRect(w - method_width - 8, 8, method_width, 18)
            painter.setBrush(QtGui.QColor(13, 19, 24, 170))
            painter.setPen(QtGui.QPen(QtGui.QColor("#50616E")))
            painter.drawRoundedRect(method_rect, 9, 9)
            painter.setPen(QtGui.QColor("#D7E1E8"))
            painter.drawText(method_rect, QtCore.Qt.AlignCenter, method_text)

        painter.setPen(QtGui.QColor("#F5F7F9"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        
        text_rect = QtCore.QRect(10, grad_y + (10 if self.show_detail else 28), w - 20, 18)
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self.name)

        detail_bits = []
        if is_pose:
            detail_bits.append("Blend Preview")
        else:
            start = self.meta.get("start")
            end = self.meta.get("end")
            start_ok = str(start).lstrip("-").isdigit() if start is not None else False
            end_ok = str(end).lstrip("-").isdigit() if end is not None else False
            if start_ok and end_ok:
                detail_bits.append(f"{int(end) - int(start) + 1} fr")
        controls = self.meta.get("controls")
        if controls:
            detail_bits.append(f"{controls} ctrls")
        fps = self.meta.get("fps")
        if fps and not is_pose:
            detail_bits.append(f"{fps} fps")

        painter.setPen(QtGui.QColor("#9FB0BC") if self.show_detail else QtGui.QColor(0, 0, 0, 0))
        detail_font = painter.font()
        detail_font.setBold(False)
        detail_font.setPointSize(7)
        painter.setFont(detail_font)
        detail_rect = QtCore.QRect(10, grad_y + 28, w - 20, 14)
        painter.drawText(detail_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, "  |  ".join(detail_bits))

        if self.is_selected:
            pen = QtGui.QPen(self.type_col)
            pen.setWidth(2)
            pen.setJoinStyle(QtCore.Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRoundedRect(outer_rect, radius, radius)
        else:
            pen = QtGui.QPen(QtGui.QColor("#28343D"))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRoundedRect(outer_rect, radius, radius)

    def advance(self):
        if not self.pixmaps: return
        self.idx = (self.idx + 1) % len(self.pixmaps)
        self.update()

    def enterEvent(self, event):
        if not self.sequence_loaded:
            self._trigger_load_sequence()
        elif len(self.pixmaps) > 1:
            fps = float(self.meta.get("fps", 24.0))
            if fps <= 0: fps = 24.0
            self.timer.start(int(1000/fps))

    def leaveEvent(self, event):
        self.hover_timer.stop()
        self.timer.stop()
        self.idx = 0
        self.update()

    def _trigger_load_sequence(self):
        if self.sequence_loading:
            return
        self.sequence_loading = True
        if self.window() and hasattr(self.window(), "load_sequence_for_item"):
            self.window().load_sequence_for_item(self)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton and self.meta.get("type") == "pose":
            self._on_slider_press()
            val = max(0, min(100, int((event.position().x() / float(self.width())) * 100)))
            self.slider.setValue(val)
            self._on_slider_move(val)
        elif event.button() == QtCore.Qt.RightButton:
            self.show_context(QtGui.QCursor.pos())
        else:
            self.clicked.emit(self)

    def mouseMoveEvent(self, event):
        if event.buttons() & QtCore.Qt.MiddleButton and self.meta.get("type") == "pose":
            val = max(0, min(100, int((event.position().x() / float(self.width())) * 100)))
            self.slider.setValue(val)
            self._on_slider_move(val)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton and self.meta.get("type") == "pose":
            self._on_slider_release()

    def resizeEvent(self, event):
        super(ThumbnailWidget, self).resizeEvent(event)
        self.scaled_cache = {}
        if not self.slider.isHidden():
            h_slider = 16
            pad = 2
            self.slider.setGeometry(pad, self.height() - h_slider - pad, self.width() - (pad*2), h_slider)
            self.slider.raise_()
        combo_w = getattr(self, "_version_combo_width", 40)
        combo_h = 20
        combo_pad = 6
        bottom_gap = 18 if not self.slider.isHidden() else 0
        self.version_combo.setGeometry(self.width() - combo_w - combo_pad, self.height() - combo_h - combo_pad - bottom_gap, combo_w, combo_h)
        self.version_combo.raise_()

    def _on_slider_press(self):
        cmds.undoInfo(openChunk=True)
        data_tuple = library_core.load_item_data(self.relative_path, self.name, version=self.current_version)
        target_data = data_tuple[0] if isinstance(data_tuple, tuple) else data_tuple
        if not target_data: return
        
        mods = QtWidgets.QApplication.keyboardModifiers()
        if mods == QtCore.Qt.AltModifier:
            win = self.window()
            ns = ""
            if hasattr(win, "resolve_namespace") and hasattr(win, "ns_mode"):
                ns = win.resolve_namespace(win.ns_mode, {"metadata": self.meta})
            from ARTools.anim import logic_pose
            target_data = logic_pose.calculate_mirror_data(target_data, ns)

        is_global = (self.meta.get("method") == "world")
        from ARTools.anim import logic_pose
        self.blender = logic_pose.PoseBlender(target_data, global_space=is_global)

    def _on_slider_move(self, val):
        if self.blender: self.blender.update(float(val) / 100.0)

    def _on_slider_release(self):
        cmds.undoInfo(closeChunk=True)
        self.blender = None
        self.slider.blockSignals(True); self.slider.setValue(0); self.slider.blockSignals(False)

    def show_context(self, pos):
        from ARTools import preferences
        menu = QtWidgets.QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | QtCore.Qt.FramelessWindowHint | QtCore.Qt.NoDropShadowWindowHint)
        menu.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        menu.setStyleSheet("""
            QMenu { background: #2A2A2A; color: #EEE; border: 1px solid #555; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 4px 20px; border-radius: 4px; }
            QMenu::item:selected { background: #4CAF50; color: white; }
            QMenu::separator { height: 1px; background: #444; margin: 4px 4px; }
        """)

        def add_colored_action(text, color, action_name):
            label = QtWidgets.QLabel(text)
            label.setStyleSheet(f"QLabel {{ color: {color}; font-weight: bold; padding: 5px 22px; }} QLabel:hover {{ background: #3A3A3A; }}")
            label.setCursor(QtCore.Qt.PointingHandCursor)
            widget_action = QtWidgets.QWidgetAction(menu)
            widget_action.setDefaultWidget(label)
            label.mouseReleaseEvent = lambda event, a=action_name: (menu.close(), self.action_triggered.emit(a, self))
            menu.addAction(widget_action)
        
        add_colored_action("Apply", "#4CAF50", "apply")
        add_colored_action("Select Controls", "#57C7FF", "select")
        menu.addSeparator()

        menu.addAction("Replace", lambda: self.action_triggered.emit("replace", self))
        menu.addAction("Preview", lambda: self.action_triggered.emit("preview", self))
        menu.addAction("Duplicate", lambda: self.action_triggered.emit("duplicate", self))

        menu.addSeparator()
        item_id = os.path.join(self.relative_path, self.name).replace("\\", "/").strip("/")
        favorites = set(preferences.Prefs.library_favorites())
        pin_label = "Unpin from Favorites" if item_id in favorites else "Pin to Favorites"
        menu.addAction(pin_label, lambda: self.action_triggered.emit("toggle_favorite", self))
        
        move_menu = menu.addMenu("Move To")
        structure = library_core.get_structure()
        
        def _build_move_menu(parent_menu, struct, current_rel_path=""):
            for key in sorted(struct.keys()):
                this_path = os.path.join(current_rel_path, key).replace("\\", "/")
                sub_menu = parent_menu.addMenu(key)
                sub_menu.setWindowFlags(sub_menu.windowFlags() | QtCore.Qt.FramelessWindowHint | QtCore.Qt.NoDropShadowWindowHint)
                sub_menu.setAttribute(QtCore.Qt.WA_TranslucentBackground)
                if this_path != self.relative_path.replace("\\", "/"):
                    sub_menu.addAction(f"Move Here ({key})", 
                        lambda _, p=this_path: self.action_triggered.emit("move", (self, p)))
                sub_menu.addSeparator()
                _build_move_menu(sub_menu, struct[key], this_path)

        _build_move_menu(move_menu, structure)

        menu.addSeparator()
        sets_menu = menu.addMenu("Selection Sets")
        local_sets, ancestor_list, _, _ = library_core.get_resolved_sets(self.relative_path)
        
        has_any = local_sets or ancestor_list
        overridden = set(local_sets.keys())
        
        def add_colored_set_action(target_menu, text, color, set_name):
            label = QtWidgets.QLabel(text)
            label.setStyleSheet(f"QLabel {{ color: {color}; padding: 4px 20px; background: transparent; }} QLabel:hover {{ background: #4CAF50; color: white; }}")
            widget_action = QtWidgets.QWidgetAction(target_menu)
            widget_action.setDefaultWidget(label)
            label.mouseReleaseEvent = lambda event, sn=set_name: (menu.close(), self.action_triggered.emit("select_set", (self, sn)))
            target_menu.addAction(widget_action)

        if has_any:
            for anc_name, anc_sets in ancestor_list:
                act_head = sets_menu.addAction(f"--- {anc_name} ---")
                act_head.setEnabled(False)
                for s_name in sorted(anc_sets.keys()):
                    if s_name not in overridden:
                        add_colored_set_action(sets_menu, s_name, "#F5B041", s_name)
                        
            if ancestor_list and local_sets:
                act_head = sets_menu.addAction("--- Local ---")
                act_head.setEnabled(False)
                
            for s_name in sorted(local_sets.keys()):
                add_colored_set_action(sets_menu, s_name, "#FFFFFF", s_name)
        else:
            sets_menu.addAction("(No Sets Available)").setEnabled(False)

        menu.addSeparator()
        menu.addAction("Manage Tags...", lambda: self.action_triggered.emit("manage_tags", self))
        # --- ADDED RENAME OPTION ---
        menu.addAction("Rename", lambda: self.action_triggered.emit("rename", self))
        menu.addAction("Delete", lambda: self.action_triggered.emit("delete", self))
        menu.addAction("Open Location", lambda: self.action_triggered.emit("open_location", self))
        menu.exec_(pos)

# -------------------------------------------------------------------------
# PREVIEW DIALOG
# -------------------------------------------------------------------------
class PreviewDialog(QtWidgets.QDialog):
    def __init__(self, name, images=None, fps=24.0, parent=None):
        super(PreviewDialog, self).__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setMinimumSize(420, 300)
        self.setStyleSheet("""
            QDialog { background-color: #12171D; border: 1px solid #2E3B45; border-radius: 10px; }
            QLabel { color: #E8EEF2; }
            QPushButton#PreviewClose {
                background: #26313A;
                color: #D9E2E7;
                border: 1px solid #3B4A54;
                border-radius: 7px;
                font-weight: bold;
            }
            QPushButton#PreviewClose:hover { background: #B94E4E; color: white; }
            QPushButton#PreviewPlay {
                background: #2E8C74;
                color: white;
                border: none;
                border-radius: 7px;
                font-weight: bold;
            }
            QPushButton#PreviewPlay:hover { background: #39A188; }
            QSlider::groove:horizontal {
                height: 5px;
                background: #26313A;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #D8E2E8;
                border: 1px solid #0E1419;
                width: 13px;
                margin: -5px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal { background: #4FB8A7; border-radius: 2px; }
        """)
        self.pixmaps = []
        for img in images or []:
            if isinstance(img, QtGui.QPixmap):
                self.pixmaps.append(img)
            elif isinstance(img, QtGui.QImage):
                self.pixmaps.append(QtGui.QPixmap.fromImage(img))
        self.idx = 0
        self.drag_pos = None
        self.fps = float(fps) if fps else 24.0
        if self.fps <= 0:
            self.fps = 24.0
        self.playing = len(self.pixmaps) > 1
        self.was_playing_before_seek = False
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.advance)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_row = QtWidgets.QHBoxLayout()
        self.lbl_title = QtWidgets.QLabel(name)
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 10pt;")
        self.lbl_counter = QtWidgets.QLabel("")
        self.lbl_counter.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.lbl_counter.setStyleSheet("color: #92A1AB; font-size: 8pt;")
        self.btn_close = QtWidgets.QPushButton("X")
        self.btn_close.setObjectName("PreviewClose")
        self.btn_close.setFixedSize(24, 22)
        self.btn_close.clicked.connect(self.close)
        title_row.addWidget(self.lbl_title, 1)
        title_row.addWidget(self.lbl_counter)
        title_row.addWidget(self.btn_close)
        layout.addLayout(title_row)

        self.lbl_preview = QtWidgets.QLabel()
        self.lbl_preview.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_preview.setMinimumSize(480, 300)
        self.lbl_preview.setStyleSheet("background: #0D1217; border: 1px solid #222D35; border-radius: 8px;")
        layout.addWidget(self.lbl_preview, 1)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(8)
        self.btn_play = QtWidgets.QPushButton("Pause" if self.playing else "Play")
        self.btn_play.setObjectName("PreviewPlay")
        self.btn_play.setFixedSize(58, 24)
        self.btn_play.setEnabled(len(self.pixmaps) > 1)
        self.btn_play.clicked.connect(self.toggle_play)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, max(0, len(self.pixmaps) - 1))
        self.slider.setEnabled(len(self.pixmaps) > 1)
        self.slider.sliderPressed.connect(self.begin_seek)
        self.slider.valueChanged.connect(self.seek_to)
        self.slider.sliderReleased.connect(self.end_seek)
        controls.addWidget(self.btn_play)
        controls.addWidget(self.slider, 1)
        layout.addLayout(controls)

        grip_row = QtWidgets.QHBoxLayout()
        grip_row.addStretch(1)
        grip_row.addWidget(QtWidgets.QSizeGrip(self))
        layout.addLayout(grip_row)

        self.resize(620, 430)
        self.update_preview()

        if self.playing:
            self.timer.start(self.timer_interval())

    def _event_global_pos(self, event):
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        return event.globalPos()

    def mousePressEvent(self, event):
        blocked = (self.btn_close, self.btn_play, self.slider)
        if event.button() == QtCore.Qt.LeftButton and self.childAt(event.pos()) not in blocked:
            self.drag_pos = self._event_global_pos(event) - self.frameGeometry().topLeft()
            event.accept()
            return
        super(PreviewDialog, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.move(self._event_global_pos(event) - self.drag_pos)
            event.accept()
            return
        super(PreviewDialog, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        super(PreviewDialog, self).mouseReleaseEvent(event)

    def timer_interval(self):
        return max(20, int(round(1000.0 / self.fps)))

    def advance(self):
        if not self.pixmaps:
            return
        self.idx = (self.idx + 1) % len(self.pixmaps)
        self.update_preview()

    def toggle_play(self):
        if len(self.pixmaps) <= 1:
            return
        self.playing = not self.playing
        if self.playing:
            self.timer.start(self.timer_interval())
            self.btn_play.setText("Pause")
        else:
            self.timer.stop()
            self.btn_play.setText("Play")

    def begin_seek(self):
        self.was_playing_before_seek = self.playing
        if self.playing:
            self.timer.stop()

    def seek_to(self, frame):
        self.idx = max(0, min(int(frame), len(self.pixmaps) - 1))
        self.update_preview()

    def end_seek(self):
        self.seek_to(self.slider.value())
        if self.was_playing_before_seek:
            self.playing = True
            self.timer.start(self.timer_interval())
            self.btn_play.setText("Pause")

    def resizeEvent(self, event):
        super(PreviewDialog, self).resizeEvent(event)
        self.update_preview()

    def update_preview(self):
        if not self.pixmaps:
            self.lbl_preview.setText("No Preview")
            return
        pix = self.pixmaps[self.idx].scaled(
            self.lbl_preview.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        self.lbl_preview.setPixmap(pix)
        if hasattr(self, "slider"):
            self.slider.blockSignals(True)
            self.slider.setValue(self.idx)
            self.slider.blockSignals(False)
        if hasattr(self, "lbl_counter"):
            self.lbl_counter.setText("{0} / {1}   {2:g} FPS".format(self.idx + 1, len(self.pixmaps), self.fps))

# -------------------------------------------------------------------------
# RESIZABLE WINDOW
# -------------------------------------------------------------------------
class ResizableWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(ResizableWindow, self).__init__(parent)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setMinimumSize(120, 120)
        self.setMouseTracking(True)
        self.grip_size = 10
        self.moving = False; self.resizing = False; self.edge = None; self.old_pos = None

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self.old_pos = QtGui.QCursor.pos()
            self.edge = self.check_edge(e.pos())
            if self.edge: self.resizing = True
            else: self.moving = True
    
    def mouseReleaseEvent(self, e):
        self.moving = False; self.resizing = False; self.edge = None
        self.setCursor(QtCore.Qt.ArrowCursor)

    def mouseMoveEvent(self, e):
        if self.resizing:
            delta = QtGui.QCursor.pos() - self.old_pos
            geo = self.geometry()
            if self.edge == "R": geo.setWidth(max(120, geo.width() + delta.x()))
            elif self.edge == "B": geo.setHeight(max(120, geo.height() + delta.y()))
            elif self.edge == "BR":
                geo.setWidth(max(120, geo.width() + delta.x()))
                geo.setHeight(max(120, geo.height() + delta.y()))
            self.setGeometry(geo)
            self.old_pos = QtGui.QCursor.pos()
        elif self.moving:
            self.move(self.pos() + (QtGui.QCursor.pos() - self.old_pos))
            self.old_pos = QtGui.QCursor.pos()
        else:
            edge = self.check_edge(e.pos())
            if edge == "R": self.setCursor(QtCore.Qt.SizeHorCursor)
            elif edge == "B": self.setCursor(QtCore.Qt.SizeVerCursor)
            elif edge == "BR": self.setCursor(QtCore.Qt.SizeFDiagCursor)
            else: self.setCursor(QtCore.Qt.ArrowCursor)

    def check_edge(self, pos):
        w, h = self.width(), self.height()
        if pos.x() > w - self.grip_size and pos.y() > h - self.grip_size: return "BR"
        if pos.x() > w - self.grip_size: return "R"
        if pos.y() > h - self.grip_size: return "B"
        return None

# -------------------------------------------------------------------------
# TAG MANAGER
# -------------------------------------------------------------------------
class TagManagerDialog(QtWidgets.QDialog):
    def __init__(self, widget, parent=None):
        super(TagManagerDialog, self).__init__(parent)
        self.widget = widget
        self.setWindowTitle(f"Tags: {widget.name}")
        self.setMinimumWidth(280)
        self.setStyleSheet("background: #222; color: #DDD;")
        
        layout = QtWidgets.QVBoxLayout(self)
        
        layout.addWidget(QtWidgets.QLabel("Applied Tags:"))
        self.applied_list = QtWidgets.QListWidget()
        self.applied_list.setStyleSheet("background: #111; border: 1px solid #444; border-radius: 4px;")
        self.applied_list.setFixedHeight(120)
        self.applied_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        layout.addWidget(self.applied_list)
        
        layout.addWidget(QtWidgets.QLabel("Available Tags (Click to Add):"))
        self.available_list = QtWidgets.QListWidget()
        self.available_list.setStyleSheet("background: #111; border: 1px solid #444; border-radius: 4px;")
        self.available_list.setFixedHeight(120)
        self.available_list.itemClicked.connect(self.on_available_clicked)
        layout.addWidget(self.available_list)
        
        add_lay = QtWidgets.QHBoxLayout()
        self.inp_new = QtWidgets.QLineEdit()
        self.inp_new.setPlaceholderText("Enter new tag...")
        self.inp_new.setStyleSheet("background: #111; border: 1px solid #444; padding: 4px;")
        self.inp_new.returnPressed.connect(self.add_new_tag)
        
        btn_add = QtWidgets.QPushButton("Add")
        btn_add.setStyleSheet("background: #2E7D32; color: white; padding: 4px; border-radius: 4px;")
        btn_add.clicked.connect(self.add_new_tag)
        
        add_lay.addWidget(self.inp_new)
        add_lay.addWidget(btn_add)
        layout.addLayout(add_lay)
        self.load_tags()

    def load_tags(self):
        self.applied_list.clear()
        self.available_list.clear()
        
        import json
        meta_path = os.path.join(self.widget.item_root, "meta.json")
        self.tags = []
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as f:
                meta = json.load(f)
                self.tags = meta.get("tags", [])
        
        for t in self.tags:
            self.add_applied_item(t)
            
        global_tags_dict = library_core.get_global_tags()
        unique_global = set()
        for item_id, tg_list in global_tags_dict.items():
            if os.path.exists(os.path.join(library_core.data_root, item_id)):
                unique_global.update(tg_list)
        
        for gt in sorted(list(unique_global)):
            if gt not in self.tags:
                self.available_list.addItem(gt)

    def add_applied_item(self, tag_text):
        item = QtWidgets.QListWidgetItem(self.applied_list)
        row = QtWidgets.QWidget()
        row_lay = QtWidgets.QHBoxLayout(row)
        row_lay.setContentsMargins(4, 2, 4, 2)
        lbl = QtWidgets.QLabel(tag_text)
        btn_x = QtWidgets.QPushButton("X")
        btn_x.setFixedSize(20, 20)
        btn_x.setStyleSheet("background: #D32F2F; color: white; border: none; border-radius: 3px; font-weight: bold;")
        btn_x.clicked.connect(lambda *args, t=tag_text: self.remove_tag(t))
        row_lay.addWidget(lbl)
        row_lay.addWidget(btn_x)
        item.setSizeHint(row.sizeHint())
        self.applied_list.setItemWidget(item, row)

    def save_tags(self):
        import json
        meta_path = os.path.join(self.widget.item_root, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            meta["tags"] = self.tags
            with open(meta_path, 'w') as f:
                json.dump(meta, f, indent=4)
        
        item_id = os.path.join(self.widget.relative_path, self.widget.name).replace("\\", "/")
        library_core.update_global_tags(item_id, self.tags)
        self.load_tags()
        
        if hasattr(self.parent(), "populate_tag_filter"):
            self.parent().populate_tag_filter()

    def on_available_clicked(self, item):
        t = item.text()
        if t not in self.tags:
            self.tags.append(t)
            self.save_tags()

    def add_new_tag(self):
        t = self.inp_new.text().strip().lower()
        if t and t not in self.tags:
            self.tags.append(t)
            self.inp_new.clear()
            self.save_tags()

    def remove_tag(self, t):
        if t in self.tags:
            self.tags.remove(t)
            self.save_tags()

# -------------------------------------------------------------------------
# MAIN BROWSER
# -------------------------------------------------------------------------
class RibbonBrowser(ResizableWindow):
    def __init__(self, parent=None):
        from ARTools import security
        
        io_check = security.enforce_license("library", parent_window=parent)

        if not io_check or getattr(io_check, "_ase_secure_stamp", "") != "JAY_SHREE_KRISHNA_1986":
            cmds.warning("[ARTools] License Invalid. Library aborted.")
            self.deleteLater() # Safely destroys the window before it shows
            return
        
        super(RibbonBrowser, self).__init__(parent)

        self.sort_reverse = False
        self.current_item = None
        self.property_win = None
        self.thumbs = []
        self.scale = self.get_dpi_scale()
        
        # State: "" is Root, None is All (though both behave recursively now)
        self.current_path = "" 

        self.thread_pool = QtCore.QThreadPool()
        self.thread_pool.setMaxThreadCount(4)

        from ARTools import preferences
        self.col_count = preferences.Prefs.library_columns()
        self.ns_mode = preferences.Prefs.library_namespace_mode()
        self.show_thumbnail_detail = preferences.Prefs.library_thumbnail_detail()
        self.show_recent = cmds.optionVar(q="ASE_Library_ShowRecent") if cmds.optionVar(ex="ASE_Library_ShowRecent") else 0
        
        self.build_ui()
        self.reload_lib()
        
        self.resize(int(240 * self.scale), int(800 * self.scale))
        self.center_window()
        
        if preferences.Prefs.remember_window_size():
            try:
                from ARTools.preferences import PrefManager
                prefs = PrefManager()
                
                x = prefs.get("lib_x")
                y = prefs.get("lib_y")
                w = prefs.get("lib_w")
                h = prefs.get("lib_h")
                
                # Apply size
                if w and h:
                    self.resize(w, h)
                
                # Apply position
                if x is not None and y is not None and x != -9999 and y != -9999:
                    self.move(x, y)
            except Exception:
                pass

    def get_dpi_scale(self):
        screen = QtWidgets.QApplication.primaryScreen()
        return max(1.0, screen.logicalDotsPerInch() / 96.0) if screen else 1.0

    def center_window(self):
        geo = QtGui.QGuiApplication.primaryScreen().geometry()
        self.move((geo.width() - self.width())//2, (geo.height() - self.height())//2)

    def build_ui(self):
        self.central = QtWidgets.QFrame()
        self.central.setObjectName("Ribbon")
        self.central.setStyleSheet(f"""
            #Ribbon {{
                background-color: #12171D;
                border: 1px solid #29323B;
                border-radius: 14px;
            }}
            #TitleBar {{
                background-color: #171E26;
                border-top-left-radius: 13px;
                border-top-right-radius: 13px;
                border-bottom: 1px solid #232D36;
            }}
            QLineEdit, QComboBox, QPushButton {{
                background: #1A232B;
                color: #E8EEF2;
                border: 1px solid #2F3B45;
                padding: {5*self.scale}px;
                border-radius: 6px;
                font-size: 9pt;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid #4FB8A7;
                background: #1E2830;
            }}
            QComboBox::drop-down {{ border: none; width: {18*self.scale}px; }}
            #SearchField {{ padding-left: {10*self.scale}px; }}
            #TagFilter {{ min-width: {92*self.scale}px; }}
            #PathBtn {{
                text-align: left;
                padding-left: {10*self.scale}px;
                font-weight: bold;
                background-color: #182129;
                font-size: 9pt;
            }}
            #PathBtn:hover {{
                border: 1px solid #51616D;
                background-color: #202B34;
            }}
            #IconBtn {{
                background: transparent;
                border: none;
                color: #A4B0B9;
            }}
            #IconBtn:hover {{
                color: #FFFFFF;
                background-color: #24303A;
                border-radius: 5px;
            }}
            #DangerBtn {{
                background: transparent;
                border: none;
            }}
            #DangerBtn:hover {{
                background-color: #C5534A;
                border-radius: 5px;
            }}
            #FooterBar {{
                background-color: #151C23;
                border: 1px solid #232D36;
                border-radius: 8px;
            }}
            #FolderHeader {{
                background-color: #151D24;
                border: 1px solid #24303A;
                border-radius: 8px;
            }}
            #FolderTitle {{
                color: #E6EEF2;
                font-weight: bold;
                font-size: 10pt;
            }}
            #FolderMeta {{
                color: #8B98A4;
                font-size: 8pt;
                font-weight: bold;
            }}
            #EmptyState {{
                background-color: #151D24;
                border: 1px dashed #31414D;
                border-radius: 12px;
            }}
            #EmptyTitle {{
                color: #E8EEF2;
                font-size: 12pt;
                font-weight: bold;
            }}
            #EmptyHint {{
                color: #91A0AB;
                font-size: 9pt;
            }}
            QScrollBar:vertical {{ background: #141B22; width: 8px; }}
            QScrollBar::handle:vertical {{ background: #41515D; min-height: 20px; border-radius: 4px; }}
        """)
        self.setCentralWidget(self.central)
        self.central.setMouseTracking(True)
        
        layout = QtWidgets.QVBoxLayout(self.central)
        layout.setContentsMargins(0, 0, 0, 5)
        layout.setSpacing(6)
        
        # --- TITLE BAR ---
        self.title_bar = QtWidgets.QFrame()
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(int(34 * self.scale))
        t_layout = QtWidgets.QHBoxLayout(self.title_bar)
        t_layout.setContentsMargins(int(10*self.scale), 0, int(5*self.scale), 0)
        t_layout.setSpacing(int(6 * self.scale))
        
        self.lbl_title = QtWidgets.QLabel("Library")
        self.lbl_title.setStyleSheet("color: #E7EDF1; font-weight: bold; font-size: 10pt; letter-spacing: 0.4px;")
        t_layout.addWidget(self.lbl_title)
        t_layout.addStretch()
        
        self.btn_settings = QtWidgets.QPushButton("")
        self.btn_settings.setFixedSize(int(24*self.scale), int(24*self.scale))
        self.btn_settings.setStyleSheet("QPushButton { background: transparent; border: none; font-weight: bold; color: #AAA; font-size: 12pt; } QPushButton:hover { color: #FFF; background-color: #444; border-radius: 4px; } QPushButton::menu-indicator { image: none; }")
        self.btn_settings.setText("")
        self.btn_settings.setObjectName("IconBtn")
        self.btn_settings.setStyleSheet("")
        self.btn_settings.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        self.btn_settings.setIconSize(QtCore.QSize(int(14 * self.scale), int(14 * self.scale)))
        self.btn_settings.clicked.connect(self.show_settings_menu)
        t_layout.addWidget(self.btn_settings)

        btn_min = QtWidgets.QPushButton("-")
        btn_min.setObjectName("WinBtn")
        btn_min.setStyleSheet("background: transparent; border: none; font-weight: bold; color: #AAA; font-size: 12pt;")
        btn_min.setText("")
        btn_min.setObjectName("IconBtn")
        btn_min.setStyleSheet("")
        btn_min.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarMinButton))
        btn_min.setIconSize(QtCore.QSize(int(12 * self.scale), int(12 * self.scale)))
        btn_min.setFixedSize(int(24*self.scale), int(24*self.scale))
        btn_min.clicked.connect(self.toggle_minimize)
        t_layout.addWidget(btn_min)
        
        btn_close = QtWidgets.QPushButton("X")
        btn_close.setObjectName("WinBtn")
        btn_close.setStyleSheet("#WinBtn { background: transparent; border: none; font-weight: bold; color: #AAA; font-size: 11pt; } #WinBtn:hover { background-color: #D32F2F; color: white; border-radius: 4px; }")
        btn_close.setText("")
        btn_close.setObjectName("DangerBtn")
        btn_close.setStyleSheet("")
        btn_close.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarCloseButton))
        btn_close.setIconSize(QtCore.QSize(int(12 * self.scale), int(12 * self.scale)))
        btn_close.setFixedSize(int(24*self.scale), int(24*self.scale))
        btn_close.clicked.connect(self.close)
        t_layout.addWidget(btn_close)
        
        layout.addWidget(self.title_bar)

        # --- CONTENT WRAPPER ---
        self.body_widget = QtWidgets.QWidget()
        self.content_lay = QtWidgets.QVBoxLayout(self.body_widget)
        self.content_lay.setContentsMargins(8, 0, 8, 4)
        self.content_lay.setSpacing(8)
        layout.addWidget(self.body_widget)

        # --- HEADER ---
        h_row = QtWidgets.QHBoxLayout()
        h_row.setSpacing(int(6 * self.scale))
        self.search = QtWidgets.QLineEdit()
        self.search.setObjectName("SearchField")
        self.search.setPlaceholderText("Search library items")
        self.search.setStyleSheet(f"background-color: #FFFFFF; color: #000000; border-radius: {int(4*self.scale)}px;")
        self.search.textChanged.connect(self.refresh_grid)
        h_row.addWidget(self.search)
        
        # --- TAG FILTER ---
        self.combo_tags = QtWidgets.QComboBox()
        self.combo_tags.setObjectName("TagFilter")
        self.combo_tags.addItem("All Tags")
        self.combo_tags.setMaximumWidth(int(110 * self.scale))
        self.combo_tags.setMinimumWidth(int(80 * self.scale))
        self.combo_tags.currentIndexChanged.connect(self.refresh_grid)
        h_row.addWidget(self.combo_tags)
        
        # --- PATH BUTTON (BREADCRUMBS) ---
        self.breadcrumb = BreadcrumbWidget()
        self.breadcrumb.path_clicked.connect(self.set_current_path)
        h_row.addWidget(self.breadcrumb, 1)

        self.btn_add_new = QtWidgets.QPushButton("")
        self.btn_add_new.setFixedSize(int(26*self.scale), int(26*self.scale))
        self.btn_add_new.setStyleSheet(f"background-color: #4CAF50; border-radius: {int(4*self.scale)}px;")
        self.btn_add_new.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon))
        self.btn_add_new.setToolTip("Save new item to library")
        self.btn_add_new.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_add_new.clicked.connect(self.open_saver)
        h_row.addWidget(self.btn_add_new)

        self.btn_toggle_sets = QtWidgets.QPushButton("")
        self.btn_toggle_sets.setCheckable(True)
        self.btn_toggle_sets.setFixedSize(int(26*self.scale), int(26*self.scale))
        self.btn_toggle_sets.setStyleSheet(f"QPushButton {{ background-color: #57C7FF; border-radius: {int(4*self.scale)}px; }} QPushButton:checked {{ background-color: #3498DB; }}")
        
        # --- Pure Code Icon Generation ---
        pix = QtGui.QPixmap(24, 24)
        pix.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor("white"), 2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        painter.drawLine(5, 7, 19, 7)
        painter.drawLine(5, 12, 19, 12)
        painter.drawLine(5, 17, 19, 17)
        painter.end()
        self.btn_toggle_sets.setIcon(QtGui.QIcon(pix))
        
        self.btn_toggle_sets.setIconSize(QtCore.QSize(int(16*self.scale), int(16*self.scale)))
        self.btn_toggle_sets.setToolTip("Toggle Selection Sets Panel")
        self.btn_toggle_sets.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_toggle_sets.clicked.connect(self.toggle_sets_panel)
        h_row.addWidget(self.btn_toggle_sets)

        self.content_lay.addLayout(h_row)
        
        line = QtWidgets.QFrame(); line.setFrameShape(QtWidgets.QFrame.HLine); line.setStyleSheet("background: #444; height: 1px;")
        self.content_lay.addWidget(line)
        
        # --- LIST ---
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        self.grid_wid = QtWidgets.QWidget()
        self.grid_lay = QtWidgets.QVBoxLayout(self.grid_wid)
        self.grid_lay.setContentsMargins(0, 0, 0, 0)
        self.grid_lay.setSpacing(4)
        self.grid_lay.setAlignment(QtCore.Qt.AlignTop)
        
        self.scroll.setWidget(self.grid_wid)
        self.content_lay.addWidget(self.scroll)

        # --- FLOATING OVERLAY SCROLLBAR ---
        self.overlay_scroll = QtWidgets.QScrollBar(QtCore.Qt.Vertical, self.scroll)
        self.overlay_scroll.setStyleSheet(f"""
            QScrollBar:vertical {{ 
                background-color: rgba(0, 0, 0, 0); 
                border: none;
                width: {int(14*self.scale)}px; 
                margin: 0px; 
            }}
            QScrollBar::handle:vertical {{ 
                background-color: rgba(135, 206, 235, 70); 
                border-radius: {int(7*self.scale)}px; 
                min-height: 30px; 
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover, QScrollBar::handle:vertical:pressed {{ 
                background-color: #87CEEB; 
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ 
                height: 0px; 
                background-color: rgba(0, 0, 0, 0); 
                border: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ 
                background-color: rgba(0, 0, 0, 0); 
                border: none;
            }}
        """)
        
        native_vsb = self.scroll.verticalScrollBar()
        
        def sync_scroll(*args):
            self.overlay_scroll.setRange(native_vsb.minimum(), native_vsb.maximum())
            self.overlay_scroll.setPageStep(native_vsb.pageStep())
            
        native_vsb.rangeChanged.connect(sync_scroll)
        self.overlay_scroll.valueChanged.connect(native_vsb.setValue)
        native_vsb.valueChanged.connect(self.overlay_scroll.setValue)
        
        sync_scroll()
        self.overlay_scroll.show()
        self.overlay_scroll.raise_()
        
        # --- FOOTER ---
        self.footer_bar = QtWidgets.QFrame()
        self.footer_bar.setObjectName("FooterBar")
        self.footer_bar.setFixedHeight(24)
        f_layout = QtWidgets.QHBoxLayout(self.footer_bar)
        f_layout.setContentsMargins(5, 0, 5, 0)
        
        self.lbl_status = QtWidgets.QLabel("0 Items")
        self.lbl_status.setStyleSheet("color: #888; font-size: 8pt; font-weight: bold;")
        f_layout.addWidget(self.lbl_status)
        
        f_layout.addStretch()
        
        self.slider_zoom = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_zoom.setRange(1, 6)
        self.slider_zoom.setValue(self.col_count)
        self.slider_zoom.setFixedWidth(80)
        self.slider_zoom.setStyleSheet("""
            QSlider::groove:horizontal { border: 1px solid #444; height: 4px; background: #222; border-radius: 2px; }
            QSlider::handle:horizontal { background: #888; border: 1px solid #555; width: 12px; margin: -4px 0; border-radius: 6px; }
        """)
        self.slider_zoom.valueChanged.connect(self._on_zoom_changed)
        f_layout.addWidget(self.slider_zoom)
        
        self.content_lay.addWidget(self.footer_bar)

    def toggle_minimize(self):
        self.is_minimized = not getattr(self, 'is_minimized', False)
        if self.is_minimized:
            self.normal_size = self.size()
            self.body_widget.hide()
            self.central.layout().setContentsMargins(0, 0, 0, 0)
            
            # Absolute lock to bypass OS/Maya limits (+2px accounts for the borders)
            self.setFixedHeight(self.title_bar.height() + 2)
        else:
            self.body_widget.show()
            self.central.layout().setContentsMargins(0, 0, 0, 5)
            
            # Release the absolute lock (16777215 is the Qt default maximum)
            self.setMinimumHeight(120)
            self.setMaximumHeight(16777215)
            
            self.resize(self.normal_size)
    
    def _on_zoom_changed(self, val):
        from ARTools import preferences
        self.col_count = val
        preferences.Prefs.set_library_columns(val)
        
        # FIX: Do not call refresh_grid (which destroys and recreates thousands of widgets).
        # Instead, dynamically resize existing thumbnails in place.
        self.update_thumb_sizes()
        
        # Adjust the grid layout column count mathematically without rebuilding
        if not hasattr(self, 'thumbs') or not self.thumbs:
            return
            
        spacing = self._thumb_spacing()
        avail_w = self.scroll.width() - 10
        item_w = int((avail_w - (spacing * (self.col_count - 1))) / self.col_count)
        if item_w < 50: item_w = 50 
        target_h = int(item_w * 0.75)

        # Loop through categories and rearrange the grid layouts
        for i in range(self.grid_lay.count()):
            cat_layout = self.grid_lay.itemAt(i)
            # Find the QGridLayouts inside the main VBox
            if isinstance(cat_layout, QtWidgets.QGridLayout):
                items = []
                # Extract all items
                while cat_layout.count():
                    item = cat_layout.takeAt(0)
                    if item.widget():
                        items.append(item.widget())
                
                # Re-insert them with new column wrapping
                row, col = 0, 0
                for widget in items:
                    widget.setFixedSize(item_w, target_h)
                    cat_layout.addWidget(widget, row, col)
                    col += 1
                    if col >= self.col_count:
                        col = 0
                        row += 1

    def _thumb_spacing(self):
        viewport = self.scroll.viewport().width() if hasattr(self, "scroll") else self.width()
        per_thumb = float(viewport) / max(1, self.col_count)
        if per_thumb <= 160:
            return 2
        if per_thumb <= 220:
            return 3
        return 4

    def _item_id(self, rel_path, name):
        return os.path.join(rel_path, name).replace("\\", "/").strip("/")

    def _remember_recent_item(self, rel_path, name):
        from ARTools import preferences
        item_id = self._item_id(rel_path, name)
        recent = [x for x in preferences.Prefs.library_recent_items() if x != item_id]
        recent.insert(0, item_id)
        preferences.Prefs.set_library_recent_items(recent)

    def _preview_images_for_widget(self, widget):
        seq_dir = os.path.join(widget.item_root, "preview_sequence")
        if os.path.exists(seq_dir):
            imgs = []
            for path in sorted(glob.glob(os.path.join(seq_dir, "*.jpg"))):
                img = QtGui.QImage(path)
                if not img.isNull():
                    imgs.append(img.copy())
            if imgs:
                return imgs
        if widget.pixmaps:
            return list(widget.pixmaps)
        if os.path.exists(widget.thumb_path):
            return [QtGui.QImage(widget.thumb_path)]
        return []

    def _load_widget_version(self, widget, version):
        versions = library_core.list_item_versions(widget.relative_path, widget.name)
        current_version = version if version in versions else (versions[-1] if versions else "V1")
        item_root = library_core.get_item_path(widget.relative_path, widget.name, current_version)
        thumb = os.path.join(item_root, "thumbnail.jpg")
        _, meta = library_core.load_item_data(widget.relative_path, widget.name, version=current_version)
        widget.set_versions(versions, current_version)
        widget.set_version_payload(current_version, thumb, item_root, meta or {})
        if os.path.exists(thumb):
            loader = ThumbnailLoader(thumb, item_root, widget, load_sequence=False)
            loader.signals.result.connect(self._on_image_loaded)
            self.thread_pool.start(loader, 5)
        if self.current_item == widget and self.property_win and self.property_win.isVisible():
            self.property_win.populate(widget)

    def update_thumb_sizes(self):
        if not self.thumbs: return
        avail_w = self.scroll.width() - 10
        spacing = self._thumb_spacing()
        if self.col_count < 1: self.col_count = 1
        item_w = int((avail_w - (spacing * (self.col_count - 1))) / self.col_count)
        if item_w < 50: item_w = 50 
        target_h = int(item_w * 0.75)
        for t in self.thumbs:
            if t.width() != item_w or t.height() != target_h:
                t.setFixedSize(item_w, target_h)

    def resizeEvent(self, event):
        super(RibbonBrowser, self).resizeEvent(event)
        self.update_thumb_sizes()
        if hasattr(self, 'overlay_scroll') and hasattr(self, 'scroll'):
            sw = self.scroll.width()
            sh = self.scroll.height()
            w = int(14 * self.scale)
            self.overlay_scroll.setGeometry(sw - w, 0, w, sh)
            
            native_vsb = self.scroll.verticalScrollBar()
            self.overlay_scroll.setPageStep(native_vsb.pageStep())
            self.overlay_scroll.setRange(native_vsb.minimum(), native_vsb.maximum())
            
            self.overlay_scroll.raise_()
        self.update_sets_geometry()

    def showEvent(self, event):
        super(RibbonBrowser, self).showEvent(event)
        self.update_thumb_sizes()
        if hasattr(self, 'overlay_scroll') and hasattr(self, 'scroll'):
            sw = self.scroll.width()
            sh = self.scroll.height()
            w = int(14 * self.scale)
            self.overlay_scroll.setGeometry(sw - w, 0, w, sh)
            
            native_vsb = self.scroll.verticalScrollBar()
            self.overlay_scroll.setPageStep(native_vsb.pageStep())
            self.overlay_scroll.setRange(native_vsb.minimum(), native_vsb.maximum())
            
            self.overlay_scroll.raise_()

    def reload_lib(self):
        global library_core
        from ARTools import preferences
        
        stored_path = preferences.Prefs.library_last_path()
        all_libs = preferences.Prefs.library_paths()
        active_name = preferences.Prefs.active_library()

        if active_name in all_libs:
            path = all_libs[active_name]
            if not os.path.exists(path):
                QtWidgets.QMessageBox.warning(self, "Path Missing", 
                    f"The folder for library '{active_name}' is missing:\n{path}\n\nIt has been removed from preferences.")
                preferences.Prefs.remove_library_path(active_name)
                all_libs = preferences.Prefs.library_paths()
                active_name = ""

        # --- CRITICAL FIX: Removed infinite while loop! ---
        if not all_libs:
            res = QtWidgets.QMessageBox.question(self, "No Library Found", 
                "No valid libraries detected.\nWould you like to create one now?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            
            if res == QtWidgets.QMessageBox.Yes:
                path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder for New Library")
                if path:
                    name, ok = QtWidgets.QInputDialog.getText(self, "New Library", "Enter Library Name:", text="MyLibrary")
                    if ok and name:
                        preferences.Prefs.add_library_path(name, path)
                        preferences.Prefs.set_active_library(name)
                        all_libs = preferences.Prefs.library_paths()

        if not all_libs:
            # GHOST STATE: Allows the window to open safely even if empty!
            self.structure = {}
            self.active_library_name = "None"
            self.setWindowTitle("Lib: None")
            if hasattr(self, "lbl_title"): self.lbl_title.setText("No Library")
            self.refresh_grid()
            return
        # --------------------------------------------------

        if not active_name or active_name not in all_libs:
            active_name = sorted(list(all_libs.keys()))[0]
            preferences.Prefs.set_active_library(active_name)
        
        path = all_libs.get(active_name, "")
        library_core = core.LibraryCore(path)
        self.structure = library_core.get_structure()
        
        self.active_library_name = active_name
        self.setWindowTitle(f"Lib: {active_name}")
        if hasattr(self, "lbl_title"):
            self.lbl_title.setText(f"{active_name} Library")
        if hasattr(self, "btn_settings"):
            self.btn_settings.setToolTip(f"Settings (Current: {active_name})")
            
        if hasattr(self, 'populate_tag_filter'):
            self.populate_tag_filter()
            
        if stored_path and os.path.exists(os.path.join(library_core.data_root, stored_path)):
            self.set_current_path(stored_path)
        else:
            self.set_current_path("")

    def show_path_menu(self):
        menu = QtWidgets.QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | QtCore.Qt.FramelessWindowHint | QtCore.Qt.NoDropShadowWindowHint)
        menu.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        menu.setStyleSheet("""
            QMenu { background: #2A2A2A; color: #EEE; border: 1px solid #555; border-radius: 8px; padding: 4px; }
            QMenu::item { padding: 4px 20px; border-radius: 4px; }
            QMenu::item:selected { background: #444; }
            QMenu::separator { height: 1px; background: #444; margin: 4px 4px; }
            /* Header Buttons */
            QPushButton { background: transparent; border: none; border-radius: 3px; }
            QPushButton:hover { background: #555; border: 1px solid #777; }
            QLabel { font-weight: bold; color: #DDD; padding-left: 5px; }
        """)

        act_all = menu.addAction("All Items")
        act_all.triggered.connect(lambda *_: self.set_current_path("")) 
        menu.addSeparator()

        def _delete_folder_action(folder_path):
            if QtWidgets.QMessageBox.question(self, "Delete", f"Delete folder?\n{folder_path}", QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                library_core.delete_folder(folder_path)
                self.reload_lib()

        def _rename_folder_action(folder_path, old_name):
            new_name, ok = QtWidgets.QInputDialog.getText(self, "Rename", "New Name:", text=old_name)
            if ok and new_name and new_name != old_name:
                if library_core.rename_folder(folder_path, new_name):
                    self.reload_lib()
                else:
                    cmds.warning("Rename failed (Name exists or invalid).")

        def _open_folder_action(folder_path):
            full_path = os.path.join(library_core.data_root, folder_path)
            if os.path.exists(full_path):
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(full_path))
            else:
                cmds.warning(f"Path not found: {full_path}")

        def _build_menu(parent_menu, struct, current_rel_path=""):
            for key in sorted(struct.keys()):
                this_path = os.path.join(current_rel_path, key).replace("\\", "/")
                sub = parent_menu.addMenu(key)
                sub.setWindowFlags(sub.windowFlags() | QtCore.Qt.FramelessWindowHint | QtCore.Qt.NoDropShadowWindowHint)
                sub.setAttribute(QtCore.Qt.WA_TranslucentBackground)
                
                # Header Row Frame
                header_frame = QtWidgets.QWidget()
                header_lay = QtWidgets.QHBoxLayout(header_frame)
                header_lay.setContentsMargins(2, 2, 2, 6)
                header_lay.setSpacing(4)
                
                # Label
                lbl = QtWidgets.QLabel(key); header_lay.addWidget(lbl); header_lay.addStretch()
                
                # Rename Icon
                btn_ren = QtWidgets.QPushButton()
                btn_ren.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView)) 
                btn_ren.setToolTip(f"Rename '{key}'")
                btn_ren.setFixedSize(22, 22)
                btn_ren.clicked.connect(lambda *_, p=this_path, n=key: (menu.close(), _rename_folder_action(p, n)))
                header_lay.addWidget(btn_ren)

                # Select Icon
                btn_sel = QtWidgets.QPushButton()
                btn_sel.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogApplyButton)) 
                btn_sel.setToolTip(f"Select '{key}'")
                btn_sel.setFixedSize(22, 22)
                btn_sel.clicked.connect(lambda *_, p=this_path: (self.set_current_path(p), menu.close()))
                header_lay.addWidget(btn_sel)
                
                # Open Icon
                btn_open = QtWidgets.QPushButton()
                btn_open.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirOpenIcon)) 
                btn_open.setToolTip(f"Open '{key}' in OS")
                btn_open.setFixedSize(22, 22)
                btn_open.clicked.connect(lambda *_, p=this_path: (menu.close(), _open_folder_action(p)))
                header_lay.addWidget(btn_open)
                
                # Delete Icon
                btn_del = QtWidgets.QPushButton()
                btn_del.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon)) 
                btn_del.setToolTip(f"Delete '{key}'")
                btn_del.setFixedSize(22, 22)
                btn_del.clicked.connect(lambda *_, p=this_path: (menu.close(), _delete_folder_action(p)))
                header_lay.addWidget(btn_del)
                
                wa = QtWidgets.QWidgetAction(sub)
                wa.setDefaultWidget(header_frame)
                sub.addAction(wa)
                
                sub.addSeparator()
                _build_menu(sub, struct[key], this_path)

        _build_menu(menu, self.structure)
        pt = self.btn_path.mapToGlobal(QtCore.QPoint(0, self.btn_path.height()))
        menu.exec_(pt)

    def set_current_path(self, path):
        self.current_path = path
        from ARTools import preferences
        preferences.Prefs.set_library_last_path(path if path is not None else "")
        
        # Build Breadcrumb
        if hasattr(self, "breadcrumb"): self.breadcrumb.build(path if path is not None else "")
        
        self.refresh_grid()
        
        # Sync the Side Panel
        if getattr(self, 'side_win', None) and self.side_win.isVisible():
            self.side_win.refresh_sets(self.current_path)
            self.side_win.sync_folder_selection(self.current_path)

    def toggle_sets_panel(self):
        if self.btn_toggle_sets.isChecked():
            if not getattr(self, 'side_win', None): self.side_win = SidePanelSatellite(self)
            self.side_win.refresh_sets(self.current_path)
            self.side_win.refresh_folders()
            self.side_win.sync_folder_selection(self.current_path)
            self.side_win.show()
            self.update_sets_geometry()
        else:
            if getattr(self, 'side_win', None): self.side_win.hide()

    def update_sets_geometry(self):
        if getattr(self, 'side_win', None) and self.side_win.isVisible():
            geo = self.geometry()
            self.side_win.setGeometry(geo.x() - self.side_win.width() - 4, geo.y(), self.side_win.width(), geo.height())

    def create_new_folder(self, target_rel_path=None):
        parent = target_rel_path if target_rel_path is not None else (self.current_path if self.current_path else "")
        parent_display = parent if parent else "Root"
        
        name, ok = QtWidgets.QInputDialog.getText(self, "New Folder", f"Create folder inside '{parent_display}':")
        if ok and name:
            safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
            if not safe_name: return
            
            new_rel = os.path.join(parent, safe_name).replace("\\", "/")
            full = os.path.join(library_core.data_root, new_rel)
            
            if not os.path.exists(full):
                try:
                    os.makedirs(full)
                    self.set_current_path(new_rel)
                    self.reload_lib() # Force tree update
                    cmds.inViewMessage(amg=f"Created: {safe_name}", pos="midCenter", fade=True)
                except: cmds.warning("Failed.")
            else:
                cmds.warning("Exists.")
    
    def open_current_location(self):
        import os, platform, subprocess
        target = library_core.data_root if not self.current_path else os.path.join(library_core.data_root, self.current_path)
        if not os.path.exists(target): return
        try:
            if platform.system() == "Windows": os.startfile(target)
            elif platform.system() == "Darwin": subprocess.Popen(["open", target])
            else: subprocess.Popen(["xdg-open", target])
        except Exception as e:
            cmds.warning(f"Could not open OS folder: {e}")
    
    def show_license_status(self, *args):
        from ARTools import security
        security.show_license_status_ui(self)
    
    def open_saver(self):
        from . import saver
        target_ns = self.resolve_namespace(self.ns_mode, {})
        saver.LibrarySaver(method="local", ns=self.ns_mode, mode="anim", prefill={"path": self.current_path}, lock_method=False)
    
    def populate_sets_panel(self):
        self.list_sets.clear()
        if not self.current_path is None and library_core:
            sets = library_core.get_selection_sets(self.current_path)
            for s_name in sorted(sets.keys()):
                self.list_sets.addItem(s_name)

    def on_set_clicked(self, item):
        self.select_set_controls(item.text(), self.current_path)

    def select_set_controls(self, set_name, rel_path):
        local_sets, ancestor_list, _, _ = library_core.get_resolved_sets(rel_path)
        controls = local_sets.get(set_name)
        if not controls:
            for _, anc_sets in reversed(ancestor_list):
                if set_name in anc_sets:
                    controls = anc_sets[set_name]
                    break
                    
        if controls:
            target_ns = self.resolve_namespace(self.ns_mode, {})
            to_select = []
            for short in controls:
                full = f"{target_ns}:{short}" if target_ns else short
                if cmds.objExists(full): to_select.append(full)
            if to_select: 
                cmds.select(to_select)
            else:
                cmds.warning(f"No matching controls found in scene for set '{set_name}'.")

    def add_selection_set(self):
        sel = cmds.ls(sl=True)
        if not sel: return
        shorts = [x.split("|")[-1].split(":")[-1] for x in sel]
        name, ok = QtWidgets.QInputDialog.getText(self, "New Selection Set", "Set Name:")
        if ok and name:
            if library_core.save_selection_set(self.current_path, name, shorts):
                if getattr(self, 'sets_win', None): self.sets_win.refresh(self.current_path)

    def update_selection_set(self, set_name):
        sel = cmds.ls(sl=True)
        if not sel: return
        shorts = [x.split("|")[-1].split(":")[-1] for x in sel]
        library_core.save_selection_set(self.current_path, set_name, shorts)
        if getattr(self, 'sets_win', None): self.sets_win.refresh(self.current_path)

    def rename_selection_set(self, old_name):
        new_name, ok = QtWidgets.QInputDialog.getText(self, "Rename Set", "New Name:", text=old_name)
        if ok and new_name and new_name != old_name:
            library_core.rename_selection_set(self.current_path, old_name, new_name)
            if getattr(self, 'sets_win', None): self.sets_win.refresh(self.current_path)

    def delete_selection_set(self, set_name):
        library_core.delete_selection_set(self.current_path, set_name)
        if getattr(self, 'sets_win', None): self.sets_win.refresh(self.current_path)
    
    def show_sets_context_menu(self, pos):
        item = self.list_sets.itemAt(pos)
        if not item: return
        set_name = item.text()
        
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu { background: #2A2A2A; color: #EEE; border: 1px solid #555; border-radius: 6px; padding: 4px; } QMenu::item:selected { background: #4CAF50; color: white; }")
        
        menu.addAction("Select Controls", lambda: self.select_set_controls(set_name, self.current_path))
        menu.addSeparator()
        
        def update_set():
            sel = cmds.ls(sl=True)
            if not sel:
                cmds.warning("Select controls to update this set.")
                return
            shorts = [x.split("|")[-1].split(":")[-1] for x in sel]
            library_core.save_selection_set(self.current_path, set_name, shorts)
            cmds.inViewMessage(amg=f"Updated Set: {set_name}", pos="midCenter", fade=True)
            
        def rename_set():
            new_name, ok = QtWidgets.QInputDialog.getText(self, "Rename Set", "New Name:", text=set_name)
            if ok and new_name and new_name != set_name:
                library_core.rename_selection_set(self.current_path, set_name, new_name)
                self.populate_sets_panel()
                
        def delete_set():
            if QtWidgets.QMessageBox.question(self, "Delete", f"Delete Set '{set_name}'?", QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                library_core.delete_selection_set(self.current_path, set_name)
                self.populate_sets_panel()
                
        menu.addAction("Update with Selected", update_set)
        menu.addAction("Rename Set", rename_set)
        menu.addAction("Delete Set", delete_set)
        menu.exec_(self.list_sets.mapToGlobal(pos))

    def populate_tag_filter(self):
        from ARTools import preferences
        current_tag = preferences.Prefs.library_last_tag()
        self.combo_tags.blockSignals(True)
        self.combo_tags.clear()
        self.combo_tags.addItem("All Tags")
        
        if library_core:
            global_tags = library_core.get_global_tags()
            unique_tags = set()
            ghost_items = []

            for item_id, tags in global_tags.items():
                item_path = os.path.join(library_core.data_root, item_id)
                if os.path.exists(item_path):
                    if tags: unique_tags.update(tags)
                else:
                    ghost_items.append(item_id)

            # Silently clean up deleted ghost items from the memory database!
            if ghost_items:
                for ghost in ghost_items:
                    library_core.update_global_tags(ghost, [])
            
            for tag in sorted(list(unique_tags)):
                self.combo_tags.addItem(tag)
        
        idx = self.combo_tags.findText(current_tag)
        if idx >= 0:
            self.combo_tags.setCurrentIndex(idx)
        else:
            self.combo_tags.setCurrentIndex(0)
            
        self.combo_tags.blockSignals(False)

    def refresh_grid(self, *args):
        freeze_geo = self.isVisible()
        if freeze_geo:
            current_geo = self.geometry()

        # --- Suspend layout calculations for "Blink Speed" loading! ---
        self.scroll.setUpdatesEnabled(False)
        self.close_prop()

        self.grid_wid.deleteLater()
        self.grid_wid = QtWidgets.QWidget()
        self.grid_lay = QtWidgets.QVBoxLayout(self.grid_wid)
        self.grid_lay.setContentsMargins(0, 0, 0, 0)
        self.grid_lay.setSpacing(4)
        self.grid_lay.setAlignment(QtCore.Qt.AlignTop)
        self.scroll.setWidget(self.grid_wid)
            
        self.thumbs = []
        query = self.search.text().lower()
        
        items_to_show = []
        active_tag = self.combo_tags.currentText() if hasattr(self, 'combo_tags') else "All Tags"
        from ARTools import preferences
        preferences.Prefs.set_library_last_tag(active_tag)
        filter_tag = None if active_tag == "All Tags" else active_tag
        global_tags = library_core.get_global_tags() if filter_tag else {}
        
        if self.current_path is None or self.current_path == "":
            search_root = library_core.data_root
        else:
            search_root = os.path.join(library_core.data_root, self.current_path)

        if os.path.exists(search_root):
            item_map = {}
            for root, dirs, files in os.walk(search_root):
                dirs[:] = [d for d in dirs if d not in ("preview_sequence", "__pycache__")]
                version_dirs = [d for d in dirs if library_core._is_version_name(d) and os.path.exists(os.path.join(root, d, "anim.json"))]
                if "anim.json" in files or version_dirs:
                    full_rel = os.path.relpath(root, library_core.data_root)
                    if full_rel == ".": full_rel = ""
                    folder_name = os.path.basename(root)
                    name = folder_name
                    cat_path = os.path.dirname(full_rel)
                    if cat_path == ".": cat_path = ""
                    if filter_tag:
                        item_id = self._item_id(cat_path, name)
                        if filter_tag not in global_tags.get(item_id, []):
                            dirs[:] = [d for d in dirs if not library_core._is_version_name(d)]
                            continue
                    item_map[(name, cat_path)] = (name, cat_path)
                    dirs[:] = [d for d in dirs if not library_core._is_version_name(d)]
            items_to_show = list(item_map.values())
        
        if query:
            items_to_show = [item for item in items_to_show if query in item[0].lower()]
        items_to_show.sort(key=lambda x: x[0].lower(), reverse=self.sort_reverse)
        
        if hasattr(self, 'lbl_status'):
            active_lib = getattr(self, "active_library_name", "Library")
            self.lbl_status.setText(f"{active_lib}  |  {len(items_to_show)} items")

        favorite_ids = set(preferences.Prefs.library_favorites())
        recent_ids = preferences.Prefs.library_recent_items()
        item_lookup = {self._item_id(rel_path, name): (name, rel_path) for name, rel_path in items_to_show}

        favorite_items = []
        recent_items = []
        grouped_items = {}
        recent_set = set()
        for item_id in recent_ids:
            if item_id in item_lookup and item_id not in favorite_ids:
                recent_items.append(item_lookup[item_id])
                recent_set.add(item_id)
        for name, rel_path in items_to_show:
            item_id = self._item_id(rel_path, name)
            if item_id in favorite_ids:
                favorite_items.append((name, rel_path))
                continue
            if rel_path not in grouped_items:
                grouped_items[rel_path] = []
            grouped_items[rel_path].append((name, rel_path))

        sorted_cats = sorted(grouped_items.keys(), reverse=self.sort_reverse)
        if favorite_items:
            favorite_items.sort(key=lambda x: x[0].lower(), reverse=self.sort_reverse)
            grouped_items["__favorites__"] = favorite_items
            sorted_cats = ["__favorites__"] + sorted_cats
            
        show_recent = getattr(self, 'show_recent', 0)
        if show_recent and recent_items:
            grouped_items["__recent__"] = recent_items
            sorted_cats = (["__favorites__", "__recent__"] if favorite_items else ["__recent__"]) + [x for x in sorted_cats if x not in ("__favorites__", "__recent__")]

        avail_w = self.width() - 25
        spacing = self._thumb_spacing()
        item_w = int((avail_w - (spacing * (self.col_count - 1))) / self.col_count)
        if item_w < 50: item_w = 50
        item_h = int(item_w * 0.75)
        
        if not sorted_cats:
            empty = QtWidgets.QFrame()
            empty.setObjectName("EmptyState")
            empty_lay = QtWidgets.QVBoxLayout(empty)
            empty_lay.setContentsMargins(int(18 * self.scale), int(26 * self.scale), int(18 * self.scale), int(26 * self.scale))
            empty_lay.setSpacing(int(6 * self.scale))
            empty_lay.setAlignment(QtCore.Qt.AlignCenter)

            empty_title = QtWidgets.QLabel("No library items found")
            empty_title.setObjectName("EmptyTitle")
            empty_title.setAlignment(QtCore.Qt.AlignCenter)
            empty_lay.addWidget(empty_title)

            empty_hint = QtWidgets.QLabel("Try another folder, clear the tag filter, or search with a different name.")
            empty_hint.setObjectName("EmptyHint")
            empty_hint.setWordWrap(True)
            empty_hint.setAlignment(QtCore.Qt.AlignCenter)
            empty_lay.addWidget(empty_hint)

            self.grid_lay.addWidget(empty)
            
            # Restore visual updates!
            self.scroll.setUpdatesEnabled(True)
            return

        for cat in sorted_cats:
            if cat == "__favorites__": display_name = "Favorites"
            elif cat == "__recent__": display_name = "Recent"
            else:
                cat_name = cat if cat else "Root"
                display_name = cat_name.replace("/", " > ")

            bg_col = "#151D24"
            if cat not in ["__favorites__", "__recent__"]:
                meta = library_core.get_folder_meta(cat)
                if meta.get("color"): bg_col = meta["color"]
            
            header = QtWidgets.QFrame()
            header.setObjectName("FolderHeader")
            header_lay = QtWidgets.QHBoxLayout(header)
            header_lay.setContentsMargins(int(10 * self.scale), int(4 * self.scale), int(10 * self.scale), int(3 * self.scale))
            header_lay.setSpacing(int(6 * self.scale))

            lbl = QtWidgets.QLabel(display_name)
            lbl.setObjectName("FolderTitle")
            header_lay.addWidget(lbl)
            header_lay.addStretch()

            count_lbl = QtWidgets.QLabel(f"{len(grouped_items[cat])} item(s)")
            count_lbl.setObjectName("FolderMeta")
            header_lay.addWidget(count_lbl)
            self.grid_lay.addWidget(header)
            
            cat_grid = QtWidgets.QGridLayout()
            cat_grid.setContentsMargins(2, 0, 2, 4)
            cat_grid.setSpacing(spacing)
            cat_grid.setAlignment(QtCore.Qt.AlignTop)
            
            row, col = 0, 0
            for name, rel_path in grouped_items[cat]:
                versions = library_core.list_item_versions(rel_path, name)
                current_version = versions[-1] if versions else "V1"
                root_path = library_core.get_item_path(rel_path, name, current_version)
                thumb = os.path.join(root_path, "thumbnail.jpg")
                meta = library_core.load_item_meta(rel_path, name, version=current_version)
                wid = ThumbnailWidget(name, rel_path, thumb, root_path, meta, versions=versions, current_version=current_version, show_detail=self.show_thumbnail_detail)
                wid.setFixedSize(item_w, item_h)
                
                wid.clicked.connect(self.on_thumb_click)
                wid.action_triggered.connect(self.handle_action)
                
                cat_grid.addWidget(wid, row, col)
                self.thumbs.append(wid)
                
                if os.path.exists(thumb):
                    loader = ThumbnailLoader(thumb, root_path, wid, load_sequence=False)
                    loader.signals.result.connect(self._on_image_loaded)
                    self.thread_pool.start(loader, -1)
                
                col += 1
                if col >= self.col_count:
                    col = 0
                    row += 1
                    
            self.grid_lay.addLayout(cat_grid)
            
        if freeze_geo:
            self.setGeometry(current_geo)
            
        # --- Reactivate window updates instantly! ---
        self.scroll.setUpdatesEnabled(True)

    def handle_action(self, act, data):
        if isinstance(data, tuple):
            widget = data[0]
            extra = data[1]
        else:
            widget = data
            extra = None

        if act == "apply":
            self.current_item = widget
            settings = {}
            # Check if property window is open and matches current item
            if self.property_win and self.property_win.isVisible() and self.property_win.lbl_name.text() == widget.name:
                self.property_win.emit_apply() # Use property window logic
            else:
                self.do_apply_logic({"namespace_mode": self.ns_mode})

        elif act == "replace":
            from . import saver
            p_info = {
                "name": widget.name,
                "path": widget.relative_path,
                "type": widget.meta.get("type", "anim"),
                "method": widget.meta.get("method", "local"),
                "version": widget.current_version
            }

            target_ns = self.resolve_namespace(self.ns_mode, {"metadata": widget.meta})
            
            # Open saver with pre-filled data
            saver.LibrarySaver(
                method=p_info["method"], 
                ns="", 
                mode=p_info["type"], 
                prefill=p_info
            )

        elif act == "change_version":
            self._load_widget_version(widget, extra)

        elif act == "preview":
            images = self._preview_images_for_widget(widget)
            self.preview_win = PreviewDialog(widget.name, images, fps=widget.meta.get("fps", 24.0), parent=self)
            geo = self.geometry()
            self.preview_win.move(geo.center() - self.preview_win.rect().center())
            self.preview_win.show()

        elif act == "duplicate":
            anim_data, meta = library_core.load_item_data(widget.relative_path, widget.name, version=widget.current_version)
            if not anim_data or not meta:
                cmds.warning("Failed to duplicate item data.")
                return
            new_name, ok = QtWidgets.QInputDialog.getText(self, "Duplicate Item", "New Name:", text=f"{widget.name} Copy")
            if not ok or not new_name or new_name == widget.name:
                return
            thumb_source = widget.thumb_path if os.path.exists(widget.thumb_path) else None
            preview_source = None
            for candidate in glob.glob(os.path.join(widget.item_root, "preview.*")):
                if os.path.isfile(candidate):
                    preview_source = candidate
                    break
            if library_core.save_item(new_name, widget.relative_path, anim_data, meta, thumb_source=thumb_source, preview_source=preview_source, version_mode="replace", version="V1"):
                QtCore.QTimer.singleShot(0, self.refresh_grid)
            else:
                cmds.warning("Duplicate failed.")

        elif act == "open_location":
            path = widget.item_root
            if path and os.path.exists(path):
                # Using Qt's native desktop services to open folder on any OS
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
            else:
                cmds.warning(f"Path not found: {path}")

        elif act == "select":
            ns_mode = self.ns_mode
            if self.property_win and self.property_win.isVisible() and self.property_win.lbl_name.text() == widget.name:
                if self.property_win.rb_ns_picker.isChecked(): ns_mode = "picker"
                elif self.property_win.rb_ns_file.isChecked(): ns_mode = "file"
                else: ns_mode = "selection"
            item_data, _ = library_core.load_item_data(widget.relative_path, widget.name, version=widget.current_version)
            target_ns = self.resolve_namespace(ns_mode, {"metadata": widget.meta})
            to_select = []
            if item_data:
                data_keys = item_data.get("data", {}).keys() if isinstance(item_data, dict) and "data" in item_data else item_data.keys() if isinstance(item_data, dict) else []
                for ctl in data_keys:
                    node = f"{target_ns}:{ctl}" if target_ns else ctl
                    if cmds.objExists(node): to_select.append(node)
            if to_select: cmds.select(to_select)

        elif act == "move":
            new_path = extra
            if new_path == widget.relative_path: return
            old_root = library_core.get_item_container_path(widget.relative_path, widget.name)
            target_root = library_core.get_item_container_path(new_path, widget.name)
            import shutil
            try:
                if os.path.exists(target_root):
                    cmds.warning("Item already exists in destination.")
                    return
                shutil.move(old_root, target_root)
                QtCore.QTimer.singleShot(0, self.refresh_grid)
            except Exception as e:
                cmds.warning(f"Move failed: {e}")

        elif act == "manage_tags":
            self.tag_win = TagManagerDialog(widget, self)
            self.tag_win.show()

        elif act == "toggle_favorite":
            from ARTools import preferences
            item_id = os.path.join(widget.relative_path, widget.name).replace("\\", "/").strip("/")
            favorites = preferences.Prefs.library_favorites()
            if item_id in favorites:
                favorites = [x for x in favorites if x != item_id]
            else:
                favorites.append(item_id)
            preferences.Prefs.set_library_favorites(favorites)
            QtCore.QTimer.singleShot(0, self.refresh_grid)

        elif act == "rename":
            new_name, ok = QtWidgets.QInputDialog.getText(self, "Rename Item", "New Name:", text=widget.name)
            if ok and new_name and new_name != widget.name:
                if library_core.rename_item(widget.relative_path, widget.name, new_name):
                    QtCore.QTimer.singleShot(0, self.refresh_grid)
                else:
                    cmds.warning("Rename failed (name exists or invalid).")

        elif act == "delete":
            versions = library_core.list_item_versions(widget.relative_path, widget.name)
            if len(versions) > 1:
                msg = QtWidgets.QMessageBox(self)
                msg.setWindowTitle("Delete Version")
                msg.setText(f"Delete '{widget.name}' version?")
                msg.setInformativeText(f"Current version: {widget.current_version}")
                btn_current = msg.addButton("Delete Current", QtWidgets.QMessageBox.AcceptRole)
                btn_all = msg.addButton("Delete All", QtWidgets.QMessageBox.DestructiveRole)
                msg.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)
                msg.exec_()
                clicked = msg.clickedButton()
                if clicked == btn_current:
                    library_core.delete_item_version(widget.relative_path, widget.name, widget.current_version)
                    QtCore.QTimer.singleShot(0, self.refresh_grid)
                elif clicked == btn_all:
                    library_core.delete_item(widget.relative_path, widget.name)
                    QtCore.QTimer.singleShot(0, self.refresh_grid)
            elif QtWidgets.QMessageBox.question(self, "Delete", f"Delete {widget.name}?", QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                library_core.delete_item(widget.relative_path, widget.name)
                QtCore.QTimer.singleShot(0, self.refresh_grid)

    def do_apply_logic(self, settings):
        if not self.current_item: return
        data_tuple = library_core.load_item_data(self.current_item.relative_path, self.current_item.name, version=self.current_item.current_version)
        if isinstance(data_tuple, tuple): anim_data, meta = data_tuple
        else: anim_data = data_tuple; meta = {}
        if not anim_data: cmds.warning("Failed to load item data."); return
        self._remember_recent_item(self.current_item.relative_path, self.current_item.name)

        selection = cmds.ls(sl=True)
        if selection:
            sel_names = set([x.split(":")[-1] for x in selection])
            if isinstance(anim_data, dict):
                filtered_data = {}
                for ctl, info in anim_data.items():
                    if ctl in sel_names: filtered_data[ctl] = info
                if not filtered_data: cmds.warning(f"Selection found, but no matching controls in item."); return
                anim_data = filtered_data

        ns_mode = settings.get("namespace_mode", "selection")
        target_ns = self.resolve_namespace(ns_mode, {"metadata": self.current_item.meta})
        
        item_type = self.current_item.meta.get("type", "anim")
        if item_type == "pose":
            from ARTools.anim import logic_pose
            logic_pose.apply_library_pose(anim_data, namespace=target_ns, mirror=settings.get("mirror", False))
        else:
            logic_anim.apply_library_item(anim_data, settings, target_ns)

    # --- SETTINGS MENU ---
    def show_settings_menu(self):
        from ARTools import preferences
        menu = QtWidgets.QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | QtCore.Qt.FramelessWindowHint | QtCore.Qt.NoDropShadowWindowHint)
        menu.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        menu.setStyleSheet("""
            QMenu { background: #2A2A2A; color: #EEE; border: 1px solid #555; border-radius: 8px; padding: 5px; }
            QMenu::item { padding: 5px 20px; border-radius: 4px; }
            QMenu::item:selected { background: #444; }
            QMenu::separator { height: 1px; background: #444; margin: 4px 4px; }
            QSlider::groove:horizontal { border: 1px solid #555; height: 4px; background: #222; margin: 2px 0; border-radius: 2px; }
            QSlider::handle:horizontal { background: #AAA; border: 1px solid #555; width: 14px; margin: -6px 0; border-radius: 7px; }
            QLabel { color: #BBB; font-weight: bold; padding: 2px 5px; }
        """)

        # Sort
        sort_grp = QtWidgets.QActionGroup(menu) if IS_PYSIDE2 else QtGui.QActionGroup(menu)
        act_asc = menu.addAction("Sort: Ascending")
        act_asc.setCheckable(True); act_asc.setChecked(not self.sort_reverse); act_asc.setActionGroup(sort_grp)
        act_asc.triggered.connect(lambda: self.set_sort_order(False))

        act_desc = menu.addAction("Sort: Descending")
        act_desc.setCheckable(True); act_desc.setChecked(self.sort_reverse); act_desc.setActionGroup(sort_grp)
        act_desc.triggered.connect(lambda: self.set_sort_order(True))
        
        menu.addSeparator()
        
        # Libraries
        libs_menu = menu.addMenu("Libraries")
        libs_menu.setWindowFlags(libs_menu.windowFlags() | QtCore.Qt.FramelessWindowHint | QtCore.Qt.NoDropShadowWindowHint)
        libs_menu.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        current_lib = preferences.Prefs.active_library()
        all_libs = preferences.Prefs.library_paths()

        def on_lib_change(new_lib):
            if new_lib != current_lib:
                preferences.Prefs.set_active_library(new_lib)
                self.reload_lib()

        def _open_lib_path(path):
            if os.path.exists(path):
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
            else:
                cmds.warning(f"Path not found: {path}")

        for name in sorted(all_libs.keys()):
            path = all_libs[name]
            row_widget = QtWidgets.QWidget()
            row_lay = QtWidgets.QHBoxLayout(row_widget)
            row_lay.setContentsMargins(10, 2, 5, 2)
            row_lay.setSpacing(5)
            
            btn_name = QtWidgets.QPushButton(name)
            btn_name.setCheckable(True)
            btn_name.setChecked(name == current_lib)
            btn_name.setStyleSheet("QPushButton { text-align: left; background: transparent; border: none; color: #EEE; } QPushButton:checked { color: #4CAF50; font-weight: bold; } QPushButton:hover { color: #FFF; }")
            btn_name.clicked.connect(lambda *_, n=name: (menu.close(), on_lib_change(n)))
            row_lay.addWidget(btn_name, 1)
            
            btn_open = QtWidgets.QPushButton()
            btn_open.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirOpenIcon))
            btn_open.setToolTip(f"Open Location: {path}")
            btn_open.setFixedSize(22, 22)
            btn_open.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { background: #555; border-radius: 3px; }")
            btn_open.clicked.connect(lambda *_, p=path: (menu.close(), _open_lib_path(p)))
            row_lay.addWidget(btn_open)
            
            wa = QtWidgets.QWidgetAction(libs_menu)
            wa.setDefaultWidget(row_widget)
            libs_menu.addAction(wa)
        
        libs_menu.addSeparator()

        def _rename_lib():
            old_name = preferences.Prefs.active_library()
            new_name, ok = QtWidgets.QInputDialog.getText(self, "Rename Library", "New Name:", text=old_name)
            if ok and new_name and new_name != old_name:
                if preferences.Prefs.rename_library(old_name, new_name):
                    self.reload_lib()
                else:
                    cmds.warning("Rename failed (Name exists or invalid).")
        
        act_ren = libs_menu.addAction(f"Rename '{current_lib}'")
        act_ren.triggered.connect(_rename_lib)

        act_add = libs_menu.addAction("Add New...")
        def do_add_lib():
            path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Root")
            if not path: return
            name, ok = QtWidgets.QInputDialog.getText(self, "Add", "Name:")
            if ok and name:
                preferences.Prefs.add_library_path(name, path)
                preferences.Prefs.set_active_library(name)
                self.reload_lib()
        act_add.triggered.connect(do_add_lib)
        
        if len(all_libs) > 1:
            act_rem = libs_menu.addAction(f"Remove '{current_lib}'")
            def do_remove_lib():
                if QtWidgets.QMessageBox.question(self, "Remove", f"Remove '{current_lib}'?", QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                    preferences.Prefs.remove_library_path(current_lib)
                    self.reload_lib()
            act_rem.triggered.connect(do_remove_lib)

        menu.addSeparator()
        act_refresh = menu.addAction("Refresh")
        act_refresh.triggered.connect(self.reload_lib)
        menu.addSeparator()

        act_snap = menu.addAction("Generate Rig Snapshot (Mirror Setup)")
        act_snap.triggered.connect(self._generate_standalone_snapshot)
        menu.addSeparator()
        
        act_lic = menu.addAction("🔑 License Status")
        act_lic.triggered.connect(self.show_license_status)
        menu.addSeparator()
        
        # Columns Slider
        lbl_col = QtWidgets.QWidgetAction(menu)
        lbl_wid = QtWidgets.QLabel("Columns: " + str(self.col_count))
        lbl_col.setDefaultWidget(lbl_wid)
        menu.addAction(lbl_col)

        sl_action = QtWidgets.QWidgetAction(menu)
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(1, 5); slider.setValue(self.col_count); slider.setFixedWidth(140)
        sl_container = QtWidgets.QWidget(); sl_layout = QtWidgets.QHBoxLayout(sl_container); sl_layout.setContentsMargins(10, 0, 10, 5); sl_layout.addWidget(slider)
        sl_action.setDefaultWidget(sl_container)
        menu.addAction(sl_action)

        def on_slide(val):
            lbl_wid.setText(f"Columns: {val}")
            self.col_count = val
            preferences.Prefs.set_library_columns(val)
            self.refresh_grid()
        slider.valueChanged.connect(on_slide)

        menu.addSeparator()
        
        act_thumb_detail = menu.addAction("Thumbnail Detail")
        act_thumb_detail.setCheckable(True)
        act_thumb_detail.setChecked(self.show_thumbnail_detail)

        def on_thumb_detail_changed(checked):
            self.show_thumbnail_detail = checked
            preferences.Prefs.set_library_thumbnail_detail(checked)
            self.refresh_grid()
        act_thumb_detail.toggled.connect(on_thumb_detail_changed)
        
        act_recent = menu.addAction("Show Recent Items")
        act_recent.setCheckable(True)
        act_recent.setChecked(bool(getattr(self, 'show_recent', 0)))

        def on_recent_changed(checked):
            self.show_recent = 1 if checked else 0
            cmds.optionVar(intValue=("ASE_Library_ShowRecent", self.show_recent))
            self.refresh_grid()
        act_recent.toggled.connect(on_recent_changed)

        menu.addSeparator()
        
        # NS Mode
        lbl_ns = QtWidgets.QWidgetAction(menu)
        l_ns = QtWidgets.QLabel("Default Namespace:")
        lbl_ns.setDefaultWidget(l_ns)
        menu.addAction(lbl_ns)
        ns_group = QtWidgets.QActionGroup(menu) if IS_PYSIDE2 else QtGui.QActionGroup(menu)
        modes = [("Picker", "picker"), ("Selected", "selection"), ("File", "file")]
        
        # --- Disable Picker option if Picker is closed ---
        picker_open, _ = self._get_picker_info()
        
        for label, mode in modes:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setData(mode)
            
            if mode == "picker" and not picker_open:
                act.setEnabled(False)
                if self.ns_mode == "picker": 
                    self.ns_mode = "selection" # Force fallback
                    preferences.Prefs.set_library_namespace_mode("selection")
                    
            act.setChecked(self.ns_mode == mode)
            ns_group.addAction(act)
            
        def on_ns_change(action):
            mode = action.data()
            self.ns_mode = mode
            preferences.Prefs.set_library_namespace_mode(mode)
            if self.property_win and self.property_win.isVisible(): self.property_win.set_namespace_mode_ui(mode)
        ns_group.triggered.connect(on_ns_change)

        menu.exec_(QtGui.QCursor.pos())

    def load_sequence_for_item(self, widget):
        if not widget: return
        # load_sequence=True (Heavy Mode)
        loader = ThumbnailLoader(widget.thumb_path, widget.item_root, widget, load_sequence=True)
        loader.signals.result.connect(self._on_image_loaded)
        self.thread_pool.start(loader, 10)

    def set_sort_order(self, reverse):
        self.sort_reverse = reverse
        self.refresh_grid()

    def _on_image_loaded(self, widget, images):
        if widget and images and widget in self.thumbs:
            widget.set_loaded_image(images)

    def _get_picker_info(self):
        """Finds the main Picker Window (even if docked) and extracts its namespace."""
        for w in QtWidgets.QApplication.allWidgets():
            try:
                c_name = w.__class__.__name__
                if "Browser" in c_name or "Satellite" in c_name: 
                    continue 

                # Method 1: Check if a namespace getter function explicitly exists
                for func_name in ["get_active_namespace", "get_current_namespace", "get_namespace"]:
                    if hasattr(w, func_name):
                        func = getattr(w, func_name)
                        if callable(func):
                            try: return True, func()
                            except: pass

                # Method 2: Aggressive structural X-Ray of the actual PickerWindow UI!
                if "PickerWindow" in c_name:
                    ns = ""
                    # Dig directly into the active tabs to read the custom namespace
                    main_tabs = getattr(w, "main_tabs", None)
                    if main_tabs and hasattr(main_tabs, "currentWidget"):
                        curr_char = main_tabs.currentWidget()
                        if curr_char:
                            ns = getattr(curr_char, "custom_namespace", getattr(curr_char, "namespace", ""))
                            sub_tabs = getattr(curr_char, "sub_tabs", None)
                            if sub_tabs and hasattr(sub_tabs, "currentWidget"):
                                curr_sub = sub_tabs.currentWidget()
                                if curr_sub:
                                    ns = getattr(curr_sub, "custom_namespace", getattr(curr_sub, "namespace", ns))
                    return True, ns
                    
            except Exception:
                continue
                
        return False, ""

    def resolve_namespace(self, mode, item_data):
        if mode == "picker":
            is_open, found_ns = self._get_picker_info()
            if is_open: return found_ns if found_ns is not None else ""
            return ""
        elif mode == "file":
            return item_data.get("metadata", {}).get("source_ns", "")
        else:
            sel = cmds.ls(sl=True)
            if sel and ":" in sel[0]: return sel[0].rsplit(":", 1)[0]
            return ""

    def on_thumb_click(self, widget):
        if self.current_item == widget:
            self.close_prop()
            return
        if self.current_item: 
            self.current_item.is_selected = False
            self.current_item.update()
        self.current_item = widget
        widget.is_selected = True
        widget.update()
        self.open_prop(widget)

    def _generate_standalone_snapshot(self):
        """Generates a rig snapshot for mirroring, completely independent of the AnimBar."""
        from maya import cmds
        from ARTools import api
        from ARTools.anim import snapshot
        
        sel = cmds.ls(sl=True)
        if not sel:
            cmds.warning("[ARTools] Please select at least one character control to generate a snapshot.")
            return
            
        ns = api.get_namespace()
        ns_display = ns if ns else "Global"
        
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Generate Snapshot")
        msg.setText(f"Generate mirror snapshot for namespace: '{ns_display}'?")
        msg.setInformativeText("This allows the Library to mirror animations without needing the AnimBar.")
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel)
        msg.setStyleSheet("background-color: #222; color: #EEE;")
        
        if msg.exec_() == QtWidgets.QMessageBox.Yes:
            try:
                # Trigger the core snapshot math directly
                # (Ensure 'create_snapshot' matches your actual generation def in snapshot.py)
                snapshot.create_character_snapshot(ns)
                cmds.inViewMessage(amg=f"Snapshot created for '{ns_display}'!", pos="midCenter", fade=True)
            except Exception as e:
                cmds.warning(f"[ARTools] Snapshot generation failed: {e}")
    
    def open_prop(self, widget):
        if self.property_win: self.property_win.close()
        self.property_win = PropertySatellite(self)
        self.property_win.setFixedWidth(int(292 * self.scale))
        self.property_win.populate(widget)
        self.property_win.apply_triggered.connect(self.do_apply_logic)
        
        geo = self.geometry()
        t_global = widget.mapToGlobal(QtCore.QPoint(0,0))
        screen = QtGui.QGuiApplication.primaryScreen().geometry()
        
        sat_w = self.property_win.width()
        if geo.right() + 5 + sat_w > screen.right():
            x = geo.left() - sat_w - 5
        else:
            x = geo.right() + 5
            
        y = t_global.y()
        h = self.property_win.sizeHint().height()
        if y + h > screen.bottom(): y = screen.bottom() - h - 10
        self.property_win.move(x, y)
        self.property_win.set_namespace_mode_ui(self.ns_mode)
        self.property_win.show()

    def close_prop(self):
        if self.property_win: 
            self.property_win.close()
            self.property_win = None
        if self.current_item:
            self.current_item.is_selected = False
            self.current_item.update()
            self.current_item = None

    def closeEvent(self, event):
        from ARTools import preferences
        if preferences.Prefs.remember_window_size():
            try:
                from ARTools.preferences import PrefManager
                prefs = PrefManager()
                prefs.set("lib_x", self.x())
                prefs.set("lib_y", self.y())
                prefs.set("lib_w", self.width())
                prefs.set("lib_h", self.height())
            except Exception:
                pass
            
        if self.property_win: self.property_win.close()
        if getattr(self, 'sets_win', None): self.sets_win.close()
        super(RibbonBrowser, self).closeEvent(event)

    def moveEvent(self, event):
        super(RibbonBrowser, self).moveEvent(event)
        if hasattr(self, 'property_win') and self.property_win and self.property_win.isVisible():
            delta = event.pos() - event.oldPos()
            if not delta.isNull():
                self.property_win.move(self.property_win.pos() + delta)
        self.update_sets_geometry()

def _get_maya_window():
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == "MayaWindow": return widget
    return None

def LibraryBrowser(toggle=False):
    global _browser_instance, _property_instance
    is_open = False
    if _browser_instance:
        try:
            if _browser_instance.isVisible(): is_open = True
        except RuntimeError: _browser_instance = None

    if toggle and is_open:
        try: _browser_instance.close(); _browser_instance.deleteLater()
        except: pass
        _browser_instance = None
        if _property_instance:
            try: _property_instance.close(); _property_instance.deleteLater()
            except: pass
            _property_instance = None
        return None

    if _browser_instance:
        try: _browser_instance.close(); _browser_instance.deleteLater()
        except: pass
    if _property_instance:
        try: _property_instance.close(); _property_instance.deleteLater()
        except: pass
        
    _browser_instance = RibbonBrowser(parent=_get_maya_window())
    _browser_instance.show()
    return _browser_instance

class WorkerSignals(QtCore.QObject):
    result = QtCore.Signal(object, object)

class ThumbnailLoader(QtCore.QRunnable):
    def __init__(self, path, root, widget, load_sequence=False):
        super(ThumbnailLoader, self).__init__()
        self.path = path
        self.root = root
        self.widget = widget
        self.load_sequence = load_sequence
        self.signals = WorkerSignals()

    def run(self):
        imgs = []
        
        # 1. Try loading sequence if requested
        if self.load_sequence:
            seq_dir = os.path.join(self.root, "preview_sequence")
            if os.path.exists(seq_dir):
                files = sorted(glob.glob(os.path.join(seq_dir, "*.jpg")))
                for f in files:
                    img = QtGui.QImage(f)
                    if not img.isNull():
                        if img.width() > 300:
                            img = img.scaledToWidth(300, QtCore.Qt.SmoothTransformation)
                        else:
                            img = img.copy() # Detach memory to prevent cross-thread corruption
                        imgs.append(img)
        
        # 2. Fallback: Load single cover (If mode is False, or if sequence was empty)
        if not imgs:
            img = QtGui.QImage(self.path)
            if not img.isNull():
                if img.width() > 300:
                    img = img.scaledToWidth(300, QtCore.Qt.SmoothTransformation)
                else:
                    img = img.copy() # Detach memory to prevent cross-thread corruption
                imgs.append(img)
                
        self.signals.result.emit(self.widget, imgs)






