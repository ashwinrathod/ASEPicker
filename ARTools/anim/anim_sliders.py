# ARTools/anim/anim_sliders.py
from PySide6 import QtWidgets, QtCore, QtGui
import maya.cmds as cmds

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
        try:
            if self.active_cache: AnimMath.action_euler_filter(self.active_targets)
        finally:
            cmds.undoInfo(closeChunk=True)
        
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