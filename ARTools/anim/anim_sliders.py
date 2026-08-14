# ARTools/anim/anim_sliders.py
from PySide6 import QtWidgets, QtCore, QtGui
import maya.cmds as cmds
from functools import partial

from .anim_context import AnimContext
from .anim_math import AnimMath

class CompactDynamicsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_val = 0
        self.active_targets = {}
        self.active_cache = {}
        self.build_ui()
        
        self.mod_timer = QtCore.QTimer(self)
        self.mod_timer.timeout.connect(self.live_shortcut_check)
        self.mod_timer.start(50)
        
    def build_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        
        self.combo = QtWidgets.QComboBox()
        self.combo.setStyleSheet("QComboBox { background: #2A2A2A; color: #ddd; border: 1px solid #444; border-radius: 3px; padding: 2px 6px; } QComboBox::drop-down { border: none; }")
        layout.addWidget(self.combo)
        
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setFixedWidth(200)
        self.slider.setFixedHeight(26) # Taller widget area to accommodate the thicker handle
        self.slider.sliderPressed.connect(self.on_press)
        self.slider.valueChanged.connect(self.on_drag)
        self.slider.sliderReleased.connect(self.on_release)
        layout.addWidget(self.slider)
        
        self.lbl_val = QtWidgets.QLabel("0%")
        self.lbl_val.setMinimumWidth(100) # Made slightly wider to comfortably fit the larger font
        self.lbl_val.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        
        # --- CRITICAL FIX: Increased Font Size & Brightness ---
        self.lbl_val.setStyleSheet("color: #dddddd; font-size: 13px; font-weight: bold;")
        # ------------------------------------------------------
        layout.addWidget(self.lbl_val)
        
        self.lbl_help = QtWidgets.QLabel(" ⓘ ")
        self.lbl_help.setStyleSheet("color: #666666; font-size: 12px; font-weight: bold;")
        self.lbl_help.setToolTip(
            "<b style='color:#5285a6; font-size:12px;'>Modifier Shortcuts:</b><br><br>"
            "<b>Shift:</b> Tweener<br>"
            "<b>Alt:</b> Neighbor<br>"
            "<b>Ctrl:</b> Push / Pull<br>"
            "<b>Shift + Alt:</b> Smooth<br>"
            "<b>Ctrl + Alt:</b> Ease In/Out<br>"
            "<b>Ctrl + Shift:</b> Mirror Blend<br>"
            "<b>Ctrl + Shift + Alt:</b> Blend to Default<br><br>"
            "<i style='color:#888888; font-size:10px;'>Note: Scale Avg & Linearize are available via Dropdown.</i>"
        )
        layout.addWidget(self.lbl_help)
        
        # --- NEW: DYNAMIC COLOR PALETTE ENGINE ---
        self.tool_configs = {
            "Tweener": {"min": -100, "max": 100, "color": "#5285a6"},     # Blue
            "Neighbor": {"min": -100, "max": 100, "color": "#27ae60"},    # Green
            "Push / Pull": {"min": -100, "max": 100, "color": "#8e44ad"}, # Purple
            "Scale Avg": {"min": -100, "max": 100, "color": "#d35400"},   # Orange
            "Ease In/Out": {"min": -100, "max": 100, "color": "#e84393"}, # Pink
            "Linearize": {"min": 0, "max": 100, "color": "#16a085"},      # Teal
            "Smooth": {"min": 0, "max": 100, "color": "#f1c40f"},         # Gold
            "Blend to Default": {"min": 0, "max": 100, "color": "#00cec9"}, # Cyan
            "Mirror Blend": {"min": 0, "max": 100, "color": "#fd79a8"},     # Magenta
        }
        self.combo.clear()
        self.combo.addItems(list(self.tool_configs.keys()))
        
        # Load state AFTER the combobox is populated!
        from ARTools.preferences import Prefs
        saved_tool = Prefs.animbar_last_tweener()
        idx = self.combo.findText(saved_tool)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
            
        self.on_combo_changed()
        self.combo.currentIndexChanged.connect(self.on_combo_changed)

    def update_slider_style(self, color_hex):
        """Generates a stunning, thick rounded-rectangle slider dynamically based on the tool color."""
        style = f"""
            QSlider::groove:horizontal {{ 
                border: 1px solid #1a1a1a; 
                height: 10px; 
                background: #111111; 
                border-radius: 5px; 
            }}
            QSlider::handle:horizontal {{ 
                background: {color_hex}; 
                border: 1px solid #000000; 
                width: 24px; 
                margin: -7px 0; /* Overhangs the groove top and bottom perfectly */
                border-radius: 6px; /* Smooth rounded rectangle */
            }}
            QSlider::handle:horizontal:hover {{ 
                background: {color_hex};
                border: 1px solid #ffffff; /* White outline pop on hover */
            }}
        """
        self.slider.setStyleSheet(style)

    def get_active_tool(self, mods):
        has_shift = bool(mods & QtCore.Qt.ShiftModifier)
        has_ctrl = bool(mods & QtCore.Qt.ControlModifier)
        has_alt = bool(mods & QtCore.Qt.AltModifier)
        
        # --- Swapped out Linearize and Scale Avg for the new tools ---
        if has_shift and has_ctrl and has_alt: return "Blend to Default"
        if has_shift and has_ctrl: return "Mirror Blend"
        if has_shift and has_alt: return "Smooth"
        if has_ctrl and has_alt: return "Ease In/Out"
        if has_shift: return "Tweener"
        if has_ctrl: return "Push / Pull"
        if has_alt: return "Neighbor"
        return self.combo.currentText()

    def live_shortcut_check(self):
        if self.slider.isSliderDown(): return 
        
        mods = QtWidgets.QApplication.keyboardModifiers()
        active_tool = self.get_active_tool(mods)
        
        current_visual_tool = getattr(self, "_visual_tool", self.combo.currentText())
        
        if active_tool != current_visual_tool:
            self._visual_tool = active_tool
            config = self.tool_configs.get(active_tool)
            if config:
                self.slider.blockSignals(True)
                self.slider.setRange(config["min"], config["max"])
                self.slider.setValue(0)
                self.slider.blockSignals(False)
                
                self.lbl_val.setText(f"<span style='color:{config['color']};'>{active_tool}</span>")
                self.update_slider_style(config['color'])
        elif active_tool == self.combo.currentText():
            config = self.tool_configs.get(self.combo.currentText())
            self.lbl_val.setText("0%")
            if config: self.update_slider_style(config['color'])

    def on_combo_changed(self, *args):
        tool_name = self.combo.currentText()
        self._visual_tool = tool_name
        config = self.tool_configs.get(tool_name)
        if not config: return
        self.slider.blockSignals(True)
        self.slider.setRange(config["min"], config["max"])
        self.slider.setValue(0)
        self.lbl_val.setText("0%")
        self.update_slider_style(config["color"])
        self.slider.blockSignals(False)

        from ARTools.preferences import Prefs
        Prefs.set_animbar_last_tweener(tool_name)

    def on_press(self):
        self.last_val = 0
        cmds.scriptEditorInfo(e=True, suppressWarnings=True, suppressInfo=True, suppressErrors=True, suppressResults=True)
        self._global_autokey = cmds.autoKeyframe(q=True, state=True)
        if self._global_autokey:
            cmds.autoKeyframe(state=False)

        self.active_targets = AnimContext.get_anim_targets()
        tool_name = self.get_active_tool(QtWidgets.QApplication.keyboardModifiers())
        self.active_cache = AnimMath.build_cache(self.active_targets, tool_name)
        
        cmds.undoInfo(openChunk=True, chunkName=f"AnimBar_{tool_name}")

    def on_drag(self, value):
        active_tool = self.get_active_tool(QtWidgets.QApplication.keyboardModifiers())
        config = self.tool_configs.get(active_tool)
        self.last_val = value
        
        # Text is now colored to match the tool!
        self.lbl_val.setText(f"<span style='color:{config['color']};'>{active_tool}:</span> {value}%")
            
        if self.active_cache:
            AnimMath.apply_tool(active_tool, self.active_cache, value)
            cmds.refresh(cv=True, force=True)

    def on_release(self):
        if self.active_cache: 
            AnimMath.action_euler_filter(self.active_targets)
        cmds.undoInfo(closeChunk=True)

        if getattr(self, "_global_autokey", False):
            cmds.autoKeyframe(state=True)
        cmds.scriptEditorInfo(e=True, suppressWarnings=False, suppressInfo=False, suppressErrors=False, suppressResults=False)
        
        self.slider.blockSignals(True)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.active_targets = {}
        self.active_cache = {}
        self.lbl_val.setText("0%")
        
        # Reset color explicitly
        config = self.tool_configs.get(self.combo.currentText())
        if config: self.update_slider_style(config["color"])
        
        self.slider.clearFocus()
        self.combo.clearFocus()
        self.clearFocus()
        
        try:
            panel = cmds.getPanel(withFocus=True)
            if not panel or "modelPanel" not in panel:
                panels = cmds.getPanel(visiblePanels=True)
                for p in panels:
                    if "modelPanel" in p:
                        cmds.setFocus(p)
                        break
                else:
                    cmds.setFocus("MayaWindow")
        except:
            cmds.setFocus("MayaWindow")

class FloatingSliderPalette(QtWidgets.QWidget):
    def __init__(self, parent_bar=None):
        super().__init__(parent_bar)
        self.parent_bar = parent_bar
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.3)

        self.active_targets = {}
        self.active_cache = {}

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.bg_frame = QtWidgets.QFrame()
        self.bg_frame.setStyleSheet("background-color: rgba(30, 32, 36, 245); border: 1px solid #454A50; border-radius: 10px;")
        layout.addWidget(self.bg_frame)
        
        inner_layout = QtWidgets.QVBoxLayout(self.bg_frame)
        inner_layout.setContentsMargins(10, 10, 10, 10)
        inner_layout.setSpacing(8)

        self.anim = QtCore.QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(200)

        configs = {
            "Tweener": {"min": -100, "max": 100, "color": "#5285a6"},
            "Neighbor": {"min": -100, "max": 100, "color": "#27ae60"},
            "Push / Pull": {"min": -100, "max": 100, "color": "#8e44ad"},
            "Scale Avg": {"min": -100, "max": 100, "color": "#d35400"},
            "Ease In/Out": {"min": -100, "max": 100, "color": "#e84393"},
            "Linearize": {"min": 0, "max": 100, "color": "#16a085"},
            "Smooth": {"min": 0, "max": 100, "color": "#f1c40f"},
            "Blend to Default": {"min": 0, "max": 100, "color": "#00cec9"},
            "Mirror Blend": {"min": 0, "max": 100, "color": "#fd79a8"}
        }

        self.sliders = {}
        for name, cfg in configs.items():
            row = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(name)
            lbl.setFixedWidth(100)
            lbl.setStyleSheet(f"color: {cfg['color']}; font-weight: bold; font-size: 11px;")
            
            sl = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            sl.setRange(cfg["min"], cfg["max"])
            sl.setFixedHeight(20)
            sl.setStyleSheet(f"""
                QSlider::groove:horizontal {{ border: 1px solid #1a1a1a; height: 6px; background: #111; border-radius: 3px; }}
                QSlider::handle:horizontal {{ background: {cfg['color']}; border: 1px solid #000; width: 16px; margin: -5px 0; border-radius: 4px; }}
                QSlider::handle:horizontal:hover {{ border: 1px solid #fff; }}
            """)
            
            val_lbl = QtWidgets.QLabel("0%")
            val_lbl.setFixedWidth(40)
            val_lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            val_lbl.setStyleSheet("color: #aaa; font-size: 10px;")

            sl.sliderPressed.connect(partial(self._on_press, name))
            sl.valueChanged.connect(partial(self._on_drag, name, val_lbl))
            sl.sliderReleased.connect(partial(self._on_release, sl, val_lbl))

            row.addWidget(lbl)
            row.addWidget(sl)
            row.addWidget(val_lbl)
            inner_layout.addLayout(row)
            self.sliders[name] = sl

    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setEndValue(1.0)
        self.anim.start()
        QtWidgets.QWidget.enterEvent(self, event)

    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setEndValue(0.3)
        self.anim.start()
        QtWidgets.QWidget.leaveEvent(self, event)

    def _on_press(self, tool_name):
        cmds.scriptEditorInfo(e=True, suppressWarnings=True, suppressInfo=True, suppressErrors=True, suppressResults=True)
        self._global_autokey = cmds.autoKeyframe(q=True, state=True)
        if self._global_autokey:
            cmds.autoKeyframe(state=False)
        self.active_targets = AnimContext.get_anim_targets()
        self.active_cache = AnimMath.build_cache(self.active_targets, tool_name)
        cmds.undoInfo(openChunk=True, chunkName=f"AnimBar_Palette_{tool_name}")

    def _on_drag(self, tool_name, lbl, value):
        lbl.setText(f"{value}%")
        if self.active_cache:
            AnimMath.apply_tool(tool_name, self.active_cache, value)
            cmds.refresh(cv=True, force=True)

    def _on_release(self, slider, lbl):
        if self.active_cache:
            AnimMath.action_euler_filter(self.active_targets)
        cmds.undoInfo(closeChunk=True)
        if getattr(self, "_global_autokey", False):
            cmds.autoKeyframe(state=True)
        cmds.scriptEditorInfo(e=True, suppressWarnings=False, suppressInfo=False, suppressErrors=False, suppressResults=False)
        
        slider.blockSignals(True)
        slider.setValue(0)
        slider.blockSignals(False)
        lbl.setText("0%")
        self.active_targets = {}
        self.active_cache = {}
        
        panel = cmds.getPanel(withFocus=True)
        if not panel or "modelPanel" not in panel:
            cmds.setFocus("MayaWindow")

    # --- FREE FLOATING & MEMORY ENGINE ---
    def showEvent(self, event):
        super().showEvent(event)
        try:
            from ARTools.preferences import PrefManager
            prefs = PrefManager()
            x = prefs.get("palette_x")
            y = prefs.get("palette_y")
            
            if x is not None and y is not None and x != -9999 and y != -9999:
                self.move(x, y)
            elif self.parent_bar:
                # Fallback: Spawn directly under AnimBar on the very first launch
                geo = self.parent_bar.geometry()
                self.move(geo.x(), geo.y() + geo.height() + 5)
        except Exception: 
            pass

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
            try:
                # Instantly save the exact coordinates when you drop the palette
                from ARTools.preferences import PrefManager
                prefs = PrefManager()
                prefs.set("palette_x", self.x())
                prefs.set("palette_y", self.y())
            except Exception: 
                pass