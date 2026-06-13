# ASEPicker/alignment_panel.py
import os

from PySide6 import QtWidgets, QtCore, QtGui

class AlignmentPanel(QtWidgets.QWidget):
    """
    Dumb UI Toolbar for Alignment, Z-Order, and Distribution.
    Emits action names to be processed safely by the Secure Core in main.py.
    """
    action_requested = QtCore.Signal(str)

    def __init__(self, *args, **kwargs):
        parent = kwargs.get("parent", args[0] if len(args) > 0 else None)
        super(AlignmentPanel, self).__init__(parent)
        self.setObjectName("ASEPicker_AlignmentPanel")
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        self.setStyleSheet(
            "QWidget#ASEPicker_AlignmentPanel { background: rgba(30, 30, 30, 200); border: 1px solid #444; border-radius: 4px; }"
            "QToolButton { border: 1px solid transparent; border-radius: 3px; background: transparent; padding: 4px; }"
            "QToolButton:hover { background: #5285a6; border: 1px solid #72a5c6; }"
        )
        self._build_ui()

    def _build_ui(self):
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        
        # Restore the safe Button Group
        self.action_group = QtWidgets.QButtonGroup(self)
        self.action_group.buttonClicked.connect(self._on_group_clicked)

        # 1. Alignment Group
        self._add_btn(lay, "align_left.svg", "left", "Align Left")
        self._add_btn(lay, "align_right.svg", "right", "Align Right")
        self._add_btn(lay, "align_vcenter.svg", "center_y", "Align Vertical Center")
        lay.addWidget(self._sep())
        
        self._add_btn(lay, "align_top.svg", "top", "Align Top")
        self._add_btn(lay, "align_bottom.svg", "bottom", "Align Bottom")
        self._add_btn(lay, "align_hcenter.svg", "center_x", "Align Horizontal Center")
        lay.addWidget(self._sep())

        # 2. Distribute Group
        self._add_btn(lay, "dist_horizontal.svg", "distribute_x", "Distribute Horizontally")
        self._add_btn(lay, "dist_vertical.svg", "distribute_y", "Distribute Vertically")
        lay.addWidget(self._sep())

        # 3. Z-Order Group
        self._add_btn(lay, "z_bring_front.svg", "z_front", "Bring to Front")
        self._add_btn(lay, "z_send_back.svg", "z_back", "Send to Back")
        self._add_btn(lay, "z_bring_forward.svg", "z_forward", "Bring Forward (1 Step)")
        self._add_btn(lay, "z_send_backward.svg", "z_backward", "Send Backward (1 Step)")

        lay.addStretch(1)

    def _add_btn(self, layout, icon_filename, action_name, tooltip):
        btn = QtWidgets.QToolButton()
        btn.setToolTip(tooltip)
        btn.setProperty("action_name", action_name)
        
        icon_path = os.path.join(os.path.dirname(__file__), "icons", icon_filename)
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(__file__), "Icons", icon_filename)
            
        if os.path.exists(icon_path):
            btn.setIcon(QtGui.QIcon(icon_path))
        else:
            btn.setText(action_name.split("_")[-1].upper()) 

        btn.setIconSize(QtCore.QSize(20, 20))
        
        # Add to group instead of individual connection
        self.action_group.addButton(btn)
        layout.addWidget(btn)
        return btn

    def _on_group_clicked(self, *args, **kwargs):
        if not args: return
        btn = args[0]  # Safely catch the button pointer from C++
        if hasattr(btn, "property"):
            self.action_requested.emit(btn.property("action_name"))

    def _sep(self):
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet("color: #555;")
        return sep