# ASEPicker/ui.py
from maya import cmds
from functools import partial  # <--- CRITICAL IMPORT FOR CYTHON

try:
    from PySide2 import QtWidgets, QtGui, QtCore
    IS_PYSIDE2 = True
except ImportError:
    from PySide6 import QtWidgets, QtGui, QtCore
    IS_PYSIDE2 = False

from .picker_shapes import (
    PickerRectangleItem, PickerRoundRectangleItem, PickerCircleItem, 
    PickerPolygonItem, PickerTextItem, PickerSliderItem, 
    PickerPoseItem, PickerCheckboxItem, PickerImageItem,
    PickerHierarchyLayer
)

class SubTab(QtWidgets.QWidget):
    def __init__(self, name='Main', parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.name = name
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = PickerCanvas(self)
        self.main_layout.addWidget(self.canvas)

class CharacterTab(QtWidgets.QWidget):
    def __init__(self, name='Character', namespace='', parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.name = name
        self.namespace = namespace
        self.ikfk_chains = []
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        
        self.sub_tabs = QtWidgets.QTabWidget(self)
        self.main_layout.addWidget(self.sub_tabs)
        self.sub_tabs.tabBar().setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        
        if hasattr(self, "show_tab_menu"):
            self.sub_tabs.tabBar().customContextMenuRequested.connect(self.show_tab_menu)
            self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self.customContextMenuRequested.connect(self.show_tab_menu)
            
        self.sub_tabs.currentChanged.connect(self._on_subtab_changed)
    
    def add_sub_tab(self, name):
        sub = SubTab(name, self)
        self.sub_tabs.addTab(sub, name)
        window = self.window()
        if hasattr(window, "selection_requested"): sub.canvas.item_selected.connect(window.selection_requested.emit)
        if hasattr(window, "alignment_requested"): sub.canvas.alignment_requested.connect(window.alignment_requested.emit)
        if hasattr(window, "item_interacted"): sub.canvas.item_interacted.connect(window.item_interacted.emit)
        if hasattr(window, "slider_moved"): sub.canvas.slider_moved.connect(window.slider_moved.emit)

        if window:
            sub.canvas.is_edit_mode = getattr(window, "is_edit_mode", False)
            
        return sub

    def _on_subtab_changed(self, idx):
        win = self.window()
        # FIX: Removed lambda, calling the safe helper method directly
        if win and win.isVisible() and hasattr(win, "_trigger_smart_sync"):
            QtCore.QTimer.singleShot(0, win._trigger_smart_sync)

################################################

def get_maya_main_window():
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == 'MayaWindow': return widget
    return None

class PickerWindow(QtWidgets.QMainWindow):
    selection_requested = QtCore.Signal(list, str)
    alignment_requested = QtCore.Signal(str, list)
    item_interacted = QtCore.Signal(object, str, object)
    slider_moved = QtCore.Signal(object, float)
    controls_modified_requested = QtCore.Signal(list, str)
    attribute_modified_requested = QtCore.Signal(list, str)
    checkbox_action_requested = QtCore.Signal(list, str, str)
    checkbox_toggled = QtCore.Signal(object)
    image_action_requested = QtCore.Signal(list, str)
    mirror_requested = QtCore.Signal(list, str, bool)
    
    pose_drag_started = QtCore.Signal(object)
    pose_dragged = QtCore.Signal(object, float)
    pose_drag_ended = QtCore.Signal(object)
    pose_action_requested = QtCore.Signal(list, str)
    
    edit_mode_toggled = QtCore.Signal(bool)
    bg_lock_toggled = QtCore.Signal(bool)
    hier_toggled = QtCore.Signal(bool)
    prefs_requested = QtCore.Signal()
    namespace_refresh_requested = QtCore.Signal()
    namespace_changed = QtCore.Signal(str)
    menu_action_requested = QtCore.Signal(str)

    copy_requested = QtCore.Signal(list)
    paste_requested = QtCore.Signal(object)
    window_closed = QtCore.Signal()

    def closeEvent(self, event):
        self.window_closed.emit()
        self.menu_action_requested.emit("close")
        event.ignore() 
        self.hide()

    def __init__(self, parent=None):
        if parent is None: parent = get_maya_main_window()
        QtWidgets.QMainWindow.__init__(self, parent)

        self.setWindowTitle("ASEPicker 1.0.2")
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "icon", "ASEPicker.svg")
        if os.path.exists(icon_path):
            self.app_icon = QtGui.QIcon(icon_path)
            self.setWindowIcon(self.app_icon)
        else:
            self.app_icon = QtGui.QIcon()
        
        self.resize(600, 800)
        self.setWindowFlags(QtCore.Qt.Window)

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 5, 0, 0)
        
        self.is_edit_mode = False
        self.bg_locked = False
        self.current_namespace = ""
        self.available_namespaces = []

        self._init_canvas_area()

        self.prefs_requested.connect(self.show_preferences)
        self.main_tabs.currentChanged.connect(self._on_main_tab_changed)

    # --- SAFE CYTHON SIGNAL HELPERS ---
    # These replace all anonymous lambdas and safely absorb PySide hidden arguments.
    def _emit_menu_action(self, action_name, *args):
        self.menu_action_requested.emit(action_name)
    def _trigger_sync_title(self, *args):
        self.menu_action_requested.emit("sync_title")
    def _trigger_smart_sync(self, *args):
        self.menu_action_requested.emit("smart_sync")
    def _emit_prefs(self, *args):
        self.prefs_requested.emit()
    def _close_window(self, *args):
        self.close()
        
    def _on_editor_controls_modified(self, act):
        self.controls_modified_requested.emit(self.editor_panel_ui.target_items, act)
    def _on_editor_attr_modified(self, act):
        self.attribute_modified_requested.emit(self.editor_panel_ui.target_items, act)
    def _on_editor_pose_action(self, act):
        self.pose_action_requested.emit(self.editor_panel_ui.target_items, act)
    def _on_editor_checkbox_action(self, state, act):
        self.checkbox_action_requested.emit(self.editor_panel_ui.target_items, state, act)
    def _on_editor_alignment(self, act):
        self.alignment_requested.emit(act, self.editor_panel_ui.target_items)
    def _on_editor_image(self, act):
        self.image_action_requested.emit(self.editor_panel_ui.target_items, act)
    # ----------------------------------
    
    def show_preferences(self, *args):
        from .preferences import PrefsWindow
        if not hasattr(self, "prefs_ui") or self.prefs_ui is None:
            self.prefs_ui = PrefsWindow(self)
        self.prefs_ui.show()
        self.prefs_ui.raise_()
    
    def show_api_help(self, *args):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("ASEPicker API & Scripting Guide")
        dialog.resize(850, 750)
        dialog.setWindowFlags(dialog.windowFlags() | QtCore.Qt.WindowMaximizeButtonHint)
        lay = QtWidgets.QVBoxLayout(dialog)
        
        text = QtWidgets.QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("QTextEdit { background-color: #1e1e1e; color: #dfdfdf; font-family: Consolas, monospace; font-size: 13px; border: 1px solid #444; padding: 10px; }")
        
        html = """
        <h1 style='color: #5285a6; margin-bottom: 0px;'>ASEPicker API Guide</h1>
        <p style='color: #888; margin-top: 0px;'>Use these commands in your <b>Command Presets</b> or <b>Script Editor</b> to create dynamic, interactive UI elements.</p>
        <hr style='border: 1px solid #444;'>
        
        <h3 style='color: #4CAF50;'>1. Getting Started (Always Include This!)</h3>
        <p>At the top of every script, you must import the API:</p>
        <pre style='background: #111; padding: 8px; border-radius: 4px; color: #f1fa8c;'>import ASEPicker.api as api</pre>
        
        <h3 style='color: #4CAF50;'>2. How to find a Button's ID (Safe Method)</h3>
        <p>Using Names/Labels is risky because they can change. It is safer to use the button's permanent ID. To find an ID:</p>
        <ul>
            <li>Select the button in Edit Mode.</li>
            <li>Open the Script Editor and click <b>Run / Test Script</b> with this code: <br>
            <pre style='background: #111; padding: 8px; display: inline-block; color: #f1fa8c;'>import ASEPicker.api as api<br>print(api.get_selected_ids())</pre>
            </li>
            <li>Copy the ID from the Maya Script Editor output to use in your scripts!</li>
        </ul>

        <h3 style='color: #4CAF50;'>3. Core Commands (Using IDs)</h3>
        <p>Replace <i>"YOUR_ID"</i> with the unique ID you copied.</p>
        <table width="100%" cellspacing="0" cellpadding="8" style="background: #222; border: 1px solid #333;">
            <tr><td style="color:#ff79c6; border-bottom: 1px solid #333;"><b>Visibility</b></td><td style="border-bottom: 1px solid #333;"><code>api.set_visibility("YOUR_ID", False)</code></td></tr>
            <tr><td style="color:#ff79c6; border-bottom: 1px solid #333;"><b>Change Text</b></td><td style="border-bottom: 1px solid #333;"><code>api.set_text("YOUR_ID", "New Text!")</code></td></tr>
            <tr><td style="color:#ff79c6; border-bottom: 1px solid #333;"><b>BG Color</b></td><td style="border-bottom: 1px solid #333;"><code>api.set_color("YOUR_ID", "#ff0000")</code></td></tr>
            <tr><td style="color:#ff79c6; border-bottom: 1px solid #333;"><b>Text Color</b></td><td style="border-bottom: 1px solid #333;"><code>api.set_text_color("YOUR_ID", "#00ff00")</code></td></tr>
            <tr><td style="color:#ff79c6; border-bottom: 1px solid #333;"><b>Edge Color</b></td><td style="border-bottom: 1px solid #333;"><code>api.set_edge_color("YOUR_ID", "#0000ff")</code></td></tr>
            <tr><td style="color:#ff79c6; border-bottom: 1px solid #333;"><b>Set Checkbox</b></td><td style="border-bottom: 1px solid #333;"><code>api.set_checkbox("YOUR_ID", True)</code></td></tr>
        </table>
        
        <h3 style='color: #4CAF50;'>4. Layer Control</h3>
        <p>Easily toggle entire layers by their exact name in the Layers Tab.</p>
        <pre style='background: #111; padding: 8px; border-radius: 4px; color: #f1fa8c;'>api.set_layer_visibility("FK Controls", True)<br>api.set_layer_visibility("IK Controls", False)</pre>

        <h3 style='color: #4CAF50;'>5. Rigging Helpers</h3>
        <p>Get information about the current rig to run custom Maya commands.</p>
        <pre style='background: #111; padding: 8px; border-radius: 4px; color: #f1fa8c;'>from maya import cmds<br># Get namespace (e.g. 'Character1')<br>ns = api.get_namespace()<br><br># Get assigned controls for a specific shape<br>ctrls = api.get_controls("YOUR_ID")<br><br># Get ALL assigned controls across the entire character tab<br>all_ctrls = api.get_all_character_controls()<br>cmds.setKeyframe(all_ctrls)</pre>

        <h3 style='color: #4CAF50;'>6. IK/FK Matching Engine</h3>
        <p>Trigger the built-in AAA Matrix matching engine flawlessly from a script or checkbox toggle. The chain name must perfectly match the name configured in the Rig Settings tab.</p>
        <pre style='background: #111; padding: 8px; border-radius: 4px; color: #f1fa8c;'># Switch a configured limb to IK (Snaps IK to current FK pose)<br>api.match_ikfk("Right Hand", "to_ik")<br><br># Switch a configured limb to FK (Snaps FK to current IK pose)<br>api.match_ikfk("Right Hand", "to_fk")</pre>

        <h3 style='color: #4CAF50;'>7. AnimBar Integration</h3>
        <p>Trigger the AnimBar's snapshot engine directly from a custom shape to reset controls.</p>
        <pre style='background: #111; padding: 8px; border-radius: 4px; color: #f1fa8c;'># Resets only the controls assigned to the selected shapes on the canvas<br>api.reset_selected_shapes()</pre>
        """
        text.setHtml(html)
        lay.addWidget(text)
        
        btn = QtWidgets.QPushButton("Close Guide")
        btn.setStyleSheet("padding: 8px; font-weight: bold; background: #333;")
        # FIX: Reverted to native dialog.accept() which naturally catches hidden C++ args
        btn.clicked.connect(dialog.accept)
        lay.addWidget(btn)
        
        getattr(dialog, "exec", dialog.exec_)()
    
    def show_release_notes(self, *args):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Release Notes")
        dialog.resize(550, 450)
        lay = QtWidgets.QVBoxLayout(dialog)
        
        text = QtWidgets.QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("QTextEdit { background-color: #1e1e1e; color: #dfdfdf; font-family: Consolas, monospace; font-size: 13px; border: 1px solid #444; padding: 10px; }")
        
        html = """
        <h2 style='color: #5285a6; margin-bottom: 0px;'>ASEPicker v1.0.2 (Current Update)</h2>
        <ul style='color: #888; margin-top: 5px;'>
            <li><b>Hierarchy Z-Layer Engine:</b> Hierarchy connection lines now render independently on a dedicated Z-Layer, ensuring they display beautifully above Background Images but safely below interactive buttons.</li>
            <li><b>Smart Sync API for Checkboxes:</b> Checkboxes using custom <i>api.match_ikfk</i> commands now dynamically read rig states via Regex, syncing visual canvas updates without standard Maya attributes.</li>
            <li><b>Custom Command UI Refresh:</b> Custom shape scripts (e.g., right-click to zero-out attributes) can now trigger instant UI refreshes by calling the Smart Sync API.</li>
            <li><b>Background Image Selection Fix:</b> Resolved Qt bounding box interference, allowing seamless click-selection of Background Images and transparent PNGs.</li>
            <li><b>In-App Release Notes:</b> Added this dedicated UI to track version history and updates.</li>
        </ul>
        """
        text.setHtml(html)
        lay.addWidget(text)
        
        btn = QtWidgets.QPushButton("Close")
        btn.setStyleSheet("padding: 8px; font-weight: bold; background: #333;")
        btn.clicked.connect(dialog.accept)
        lay.addWidget(btn)
        
        getattr(dialog, "exec", dialog.exec_)()
    
    def show_about(self, *args):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("About ASEPicker")
        dialog.resize(550, 400)
        lay = QtWidgets.QVBoxLayout(dialog)
        
        text = QtWidgets.QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("QTextEdit { background-color: #1e1e1e; color: #dfdfdf; font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; border: 1px solid #444; padding: 15px; }")
        
        html = """
        <h2 style='color: #5285a6; margin-bottom: 5px;'>ASEPicker v1.0.2</h2>
        <p style='color: #888; font-size: 12px; margin-top: 0px;'>Professional Animation Picker & Workflow Suite</p>
        
        <h3 style='color: #5285a6; border-bottom: 1px solid #444; padding-bottom: 5px;'>Creator & Developer</h3>
        <p><b>Ashwin V Rathod</b><br>
        <i>Animation Technical Lead & Supervisor</i><br></p>
        
        <h3 style='color: #5285a6; border-bottom: 1px solid #444; padding-bottom: 5px;'>Tool Workflow & Architecture</h3>
        <p>ASEPicker is a premium, highly customizable animation interface designed specifically for Autodesk Maya. It goes beyond standard selection tools by offering an advanced <b>Smart Sync API</b> that bi-directionally communicates with complex rig attributes.</p>
        """
        text.setHtml(html)
        lay.addWidget(text)
        
        btn = QtWidgets.QPushButton("Close")
        btn.setStyleSheet("padding: 8px; font-weight: bold; background: #333;")
        btn.clicked.connect(dialog.accept)
        lay.addWidget(btn)
        
        getattr(dialog, "exec", dialog.exec_)()

    def show_eula(self, *args):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("End User License Agreement (EULA)")
        dialog.resize(600, 500)
        lay = QtWidgets.QVBoxLayout(dialog)
        
        text = QtWidgets.QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("QTextEdit { background-color: #1e1e1e; color: #b0b0b0; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #444; padding: 15px; }")
        
        html = """
        <h2 style='color: #dfdfdf; text-align: center;'>END USER LICENSE AGREEMENT</h2>
        <p><b>IMPORTANT - READ CAREFULLY:</b> This End User License Agreement ("EULA") is a legal agreement between you (either an individual or a single entity) and Ashwin V Rathod for the ASEPicker software product.</p>
        """
        text.setHtml(html)
        lay.addWidget(text)
        
        btn = QtWidgets.QPushButton("I Agree - Close")
        btn.setStyleSheet("padding: 8px; font-weight: bold; background: #333;")
        btn.clicked.connect(dialog.accept)
        lay.addWidget(btn)
        
        getattr(dialog, "exec", dialog.exec_)()

    def show_license_status(self, *args):
        import datetime, json, base64
        from . import security
        
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("License Status")
        dialog.resize(400, 200)
        lay = QtWidgets.QVBoxLayout(dialog)
        
        status_layout = QtWidgets.QHBoxLayout()
        dot_label = QtWidgets.QLabel()
        text_label = QtWidgets.QLabel()
        text_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #dfdfdf;")
        
        if security._check_time_tamper():
            dot_label.setFixedSize(30, 30)
            dot_label.setStyleSheet("background-color: #D32F2F; border-radius: 15px;")
            text_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #FF5252;")
            text_label.setText("CRITICAL: License has been tampered\nwith and cannot be activated.")
        else:
            key = security.get_saved_license()
            exp_date = None
            
            if key and key.startswith("OFF-"):
                try:
                    json_str = base64.b64decode(key[4:]).decode('utf-8')
                    data = json.loads(json_str)
                    exp_date = datetime.datetime.strptime(data.get("exp", "2099-12-31"), "%Y-%m-%d").date()
                except: pass
            elif key and key.startswith("ONL-"):
                parts = key.split("|")
                if len(parts) == 2:
                    try: exp_date = datetime.datetime.strptime(parts[1], "%Y-%m-%d").date()
                    except: pass
                    
            if not exp_date:
                dot_label.setFixedSize(20, 20)
                dot_label.setStyleSheet("background-color: #757575; border-radius: 10px;")
                text_label.setText("No License Found.")
            else:
                today = datetime.date.today()
                delta = (exp_date - today).days
                
                if delta < 0:
                    dot_label.setFixedSize(20, 20)
                    dot_label.setStyleSheet("background-color: #F44336; border-radius: 10px;")
                    text_label.setText("License is Expired.")
                else:
                    dot_label.setFixedSize(20, 20)
                    dot_label.setStyleSheet("background-color: #4CAF50; border-radius: 10px;")
                    if delta > 3650:
                        text_label.setText("Status: Active (Permanent License)")
                    else:
                        text_label.setText(f"Status: Active\nTime Remaining: {delta} Days")

        status_layout.addWidget(dot_label)
        status_layout.addWidget(text_label)
        status_layout.addStretch()
        
        lay.addLayout(status_layout)
        
        sys_info = QtWidgets.QLabel(f"System ID: {security.get_system_id()}")
        sys_info.setStyleSheet("color: #777; font-size: 11px; margin-top: 20px;")
        lay.addWidget(sys_info)
        
        btn = QtWidgets.QPushButton("Close")
        btn.setStyleSheet("padding: 8px; font-weight: bold; background: #333; margin-top: 10px;")
        btn.clicked.connect(dialog.accept)
        lay.addWidget(btn)

        getattr(dialog, "exec", dialog.exec_)()

    def _init_canvas_area(self):
        self.main_tabs = QtWidgets.QTabWidget()
        self.main_layout.addWidget(self.main_tabs)
        self.main_tabs.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        
        if hasattr(self, "show_main_tab_menu"):
            self.main_tabs.customContextMenuRequested.connect(self.show_main_tab_menu)
        
        self.corner_widget = QtWidgets.QWidget()
        self.corner_widget.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        self.corner_layout = QtWidgets.QHBoxLayout(self.corner_widget)
        self.corner_layout.setContentsMargins(0, 0, 4, 0)
        self.corner_layout.setSpacing(0)
        
        self.corner_widget.setStyleSheet("""
            QToolButton { border: none; padding: 2px 4px; margin: 0px; border-radius: 3px; font-weight: bold; }
            QToolButton:hover { background-color: rgba(255, 255, 255, 30); }
            QToolButton::menu-indicator { image: none; }
        """)
        
        self.btn_edit = QtWidgets.QToolButton()
        self.btn_edit.setText("Pose") 
        self.btn_edit.setToolTip("Toggle Edit / Pose Mode")
        self.btn_edit.setCheckable(True)
        self.btn_edit.clicked.connect(self._on_edit_toggled)
        
        self.btn_bg_lock = QtWidgets.QToolButton()
        self.btn_bg_lock.setText("🖼️")
        self.btn_bg_lock.setToolTip("Lock BG Images")
        self.btn_bg_lock.setCheckable(True)
        self.btn_bg_lock.clicked.connect(self._on_bg_lock_toggled)
        
        self.btn_hier = QtWidgets.QToolButton()
        self.btn_hier.setText("🔗")
        self.btn_hier.setToolTip("Toggle Hierarchy Visibility")
        self.btn_hier.setCheckable(True)
        self.btn_hier.clicked.connect(self._on_hier_toggled)
        
        self.btn_ns = QtWidgets.QToolButton()
        self.btn_ns.setText("N:")
        self.btn_ns.setToolTip("Namespace: (None)")
        self.btn_ns.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.ns_menu = QtWidgets.QMenu(self.btn_ns)
        self.btn_ns.setMenu(self.ns_menu)
        self.ns_menu.aboutToShow.connect(self._populate_ns_menu)
        
        self.btn_menu = QtWidgets.QToolButton()
        self.btn_menu.setText("☰")
        self.btn_menu.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.main_menu = QtWidgets.QMenu(self.btn_menu)
        
        # FIX: Replaced ALL lambdas with functools.partial to guarantee Cython compilation stability
        act_open = self.main_menu.addAction("📂 Open...")
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(partial(self._emit_menu_action, "open"))
        
        act_save = self.main_menu.addAction("💾 Save")
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(partial(self._emit_menu_action, "save"))
        
        act_save_as = self.main_menu.addAction("💾 Save As...")
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(partial(self._emit_menu_action, "save_as"))
        
        self.main_menu.addAction("📦 Save to Scene").triggered.connect(partial(self._emit_menu_action, "save_scene"))
        self.main_menu.addSeparator()
        
        self.main_menu.addAction("🔄 Smart Sync UI").triggered.connect(partial(self._emit_menu_action, "smart_sync"))
        self.main_menu.addSeparator()
        
        anim_menu = self.main_menu.addMenu("🎬 Anim Tools")
        anim_menu.addAction("Floating Anim Bar").triggered.connect(partial(self._emit_menu_action, "open_anim_bar"))
        self.main_menu.addSeparator()

        self.main_menu.addAction("⚙️ Preferences").triggered.connect(self._emit_prefs)
        self.main_menu.addSeparator()
        
        self.main_menu.addAction("📖 Help / API Guide").triggered.connect(self.show_api_help)
        self.main_menu.addAction("📝 Release Notes").triggered.connect(self.show_release_notes)
        self.main_menu.addSeparator()

        self.main_menu.addAction("📜 EULA").triggered.connect(self.show_eula)
        self.main_menu.addAction("🔑 License Status").triggered.connect(self.show_license_status)
        self.main_menu.addSeparator()
        
        self.main_menu.addAction(getattr(self.window(), "app_icon", QtGui.QIcon()), "About ASEPicker").triggered.connect(self.show_about)
        self.main_menu.addSeparator()
        
        self.main_menu.addAction("❌ Close").triggered.connect(self._close_window)
        self.main_menu.addAction("💀 Kill ASEPicker").triggered.connect(partial(self._emit_menu_action, "kill"))
        
        self.btn_menu.setMenu(self.main_menu)
        
        self.corner_layout.addWidget(self.btn_edit)
        self.corner_layout.addWidget(self.btn_bg_lock)
        self.corner_layout.addWidget(self.btn_hier)
        self.corner_layout.addWidget(self.btn_ns)
        self.corner_layout.addWidget(self.btn_menu)
        
        self.main_tabs.setCornerWidget(self.corner_widget, QtCore.Qt.TopRightCorner)

    def _on_edit_toggled(self, checked):
        self.btn_edit.setText("Edit" if checked else "Pose")
        self.is_edit_mode = checked
        self.edit_mode_toggled.emit(checked)
        
    def _on_bg_lock_toggled(self, checked):
        self.btn_bg_lock.setStyleSheet("color: #4CAF50;" if checked else "")
        self.bg_locked = checked
        self.bg_lock_toggled.emit(checked)

    def _on_hier_toggled(self, checked):
        self.btn_hier.setStyleSheet("color: #4CAF50;" if checked else "")
        self.hier_toggled.emit(checked)
        for i in range(self.main_tabs.count()):
            char_tab = self.main_tabs.widget(i)
            for j in range(char_tab.sub_tabs.count()):
                char_tab.sub_tabs.widget(j).canvas.viewport().update()

    def _on_main_tab_changed(self, idx):
        # FIX: Removed lambda, calling safe helper
        QtCore.QTimer.singleShot(0, self._trigger_sync_title)
        char_tab = self.main_tabs.widget(idx)
        if char_tab:
            ns = getattr(char_tab, "namespace", "")
            self.current_namespace = ns
            self.btn_ns.setToolTip(f"Namespace: {ns if ns else '(None)'}")
            self.namespace_changed.emit(ns)

    def _populate_ns_menu(self, *args):
        self.ns_menu.clear()
        self.ns_menu.addAction("✨ Set Selected Namespace").triggered.connect(self._set_ns_from_selection)
        self.ns_menu.addSeparator()
        self.ns_menu.addAction("➕ Add Namespace...").triggered.connect(self._add_manual_ns)
        # FIX: Replaced lambda with functools.partial
        self.ns_menu.addAction("🧹 Clear Namespace").triggered.connect(partial(self._set_namespace, ""))
        self.ns_menu.addSeparator()
        self.namespace_refresh_requested.emit()

        for ns in self.available_namespaces:
            # FIX: Replaced lambda with functools.partial
            self.ns_menu.addAction(ns).triggered.connect(partial(self._set_namespace, ns))

    # FIX: Added *args to safely absorb extra Qt background arguments
    def _set_namespace(self, ns, *args):
        self.current_namespace = ns
        self.btn_ns.setToolTip(f"Namespace: {ns if ns else '(None)'}")
        char_tab = self.main_tabs.currentWidget()
        if char_tab: char_tab.namespace = ns
        self.namespace_changed.emit(ns)

    def _set_ns_from_selection(self, *args):
        sel = cmds.ls(selection=True)
        if not sel: return
        if ":" in sel[0]:
            ns = sel[0].rsplit(":", 1)[0]
            self._set_namespace(ns)

    def _add_manual_ns(self, *args):
        text, ok = QtWidgets.QInputDialog.getText(self, "Manual Namespace", "Enter Namespace:")
        if ok: self._set_namespace(text.strip())

    def add_character_tab(self, name, namespace):
        char_tab = CharacterTab(name, namespace, self)
        self.main_tabs.addTab(char_tab, name)
        return char_tab

    def show_editor_panel(self, items):
        from .editor_panel import EditorPanel
        if not hasattr(self, "editor_panel_ui") or self.editor_panel_ui is None:
            self.editor_panel_ui = EditorPanel(self)
            self.editor_panel_ui.setWindowFlags(QtCore.Qt.Tool)
            
            # FIX: Removed lambdas completely. Connected to secure class helpers instead.
            self.editor_panel_ui.controls_modified.connect(self._on_editor_controls_modified)
            self.editor_panel_ui.attribute_modified.connect(self._on_editor_attr_modified)
            self.editor_panel_ui.pose_action_requested.connect(self._on_editor_pose_action)
            self.editor_panel_ui.checkbox_action_requested.connect(self._on_editor_checkbox_action)
            self.editor_panel_ui.alignment_requested.connect(self._on_editor_alignment)
            self.editor_panel_ui.image_action_requested.connect(self._on_editor_image)
        
        if not isinstance(items, list): items = [items]
        self.editor_panel_ui.show()
        self.editor_panel_ui.raise_()
        self.editor_panel_ui.set_target_items(items)

#######################################################

class PickerCanvas(QtWidgets.QGraphicsView):
    item_selected = QtCore.Signal(list, str)  
    item_interacted = QtCore.Signal(object, str, object)
    alignment_requested = QtCore.Signal(str, list)
    slider_moved = QtCore.Signal(object, float)

    def __init__(self, parent=None):
        QtWidgets.QGraphicsView.__init__(self, parent)
        core_scene = QtWidgets.QGraphicsScene(self)
        self.setScene(core_scene)
        self.scene().setSceneRect(-32000, -32000, 64000, 64000)

        self.hier_layer = PickerHierarchyLayer()
        self.scene().addItem(self.hier_layer)

        from .preferences import PrefManager
        prefs = PrefManager()
        self.grid_visible = prefs.get("grid_visible")
        self.grid_scale = prefs.get("grid_scale")
        self.grid_color = QtGui.QColor(255, 255, 255, 30)

        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        
        self._rb_active = False
        self._rb_origin_scene = QtCore.QPointF()
        self._rb_visual_rect = QtCore.QRectF()
        
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.background_color = QtGui.QColor("#474747")

        self._is_panning = False
        self._pan_start_pos = QtCore.QPoint()
        self.is_edit_mode = False
        
        self._hier_mode = None
        self._hier_drag_source = None
        self._hier_drag_pos = None

        self._mirror_use_canvas = prefs.get("mirror_use_canvas")
        
        self.layer_data = []
        self.canvas_scripts = []

    def apply_layer_visibility(self):
        is_edit = getattr(self, "is_edit_mode", False)
        all_shapes = [i for i in self.scene().items() if hasattr(i, "item_id")]
        
        shape_to_layer = {}
        for layer in getattr(self, "layer_data", []):
            for sid in layer.get("shapes", []):
                shape_to_layer[sid] = layer
                
        for item in all_shapes:
            layer = shape_to_layer.get(item.item_id)
            if layer:
                vis = layer.get("vis_edit", True) if is_edit else layer.get("vis_pose", True)
                item.setVisible(vis)
            self.update_item_flags(item)

    def update_item_flags(self, item):
        if not hasattr(item, "shape_name"): return
        
        win = self.window()
        is_edit = getattr(win, "is_edit_mode", False) if win else False
        is_bg_locked = getattr(win, "bg_locked", False) if win else False
        
        layer = next((l for l in getattr(self, "layer_data", []) if item.item_id in l.get("shapes", [])), None)

        item.setAcceptedMouseButtons(QtCore.Qt.LeftButton | QtCore.Qt.RightButton | QtCore.Qt.MiddleButton)
        if is_edit:
            item.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
            item.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, not getattr(item, "locked_edit", False))
        else:
            item.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, getattr(item, "selectable_pose", True))
            item.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)

        if item.shape_name == "Image" and is_bg_locked:
            item.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)
            item.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)
            item.setAcceptedMouseButtons(QtCore.Qt.NoButton)

    def update_all_flags(self):
        for item in self.scene().items():
            self.update_item_flags(item)
    
    def execute_custom_script(self, cmd, cmd_type):
        if not cmd or not cmd.strip(): return
        try:
            if cmd_type == "mel":
                import maya.mel as mel
                mel.eval(cmd)
            else:
                exec(cmd, globals())
        except Exception as e:
            print(f"ASEPicker Script Execution Error: {e}")
    
    def drawBackground(self, painter, rect):
        painter.fillRect(rect, self.background_color)
        if getattr(self, "grid_visible", False):
            scale = max(10, getattr(self, "grid_scale", 50))
            color = getattr(self, "grid_color", QtGui.QColor(255, 255, 255, 30))
            
            left = int(rect.left()) - (int(rect.left()) % scale)
            top = int(rect.top()) - (int(rect.top()) % scale)
            
            lines = []
            painter.setPen(QtGui.QPen(color, 1))
            
            x = left
            while x < rect.right():
                if x != 0: lines.append(QtCore.QLineF(x, rect.top(), x, rect.bottom()))
                x += scale
            y = top
            while y < rect.bottom():
                if y != 0: lines.append(QtCore.QLineF(rect.left(), y, rect.right(), y))
                y += scale
                
            painter.drawLines(lines)
            
            painter.setPen(QtGui.QPen(color, 2))
            painter.drawLine(QtCore.QLineF(0, rect.top(), 0, rect.bottom()))
            painter.drawLine(QtCore.QLineF(rect.left(), 0, rect.right(), 0))

    def _update_editor_ui(self):
        window = self.window()
        if hasattr(window, "editor_panel_ui") and window.editor_panel_ui:
            sel_shapes = [i for i in self.scene().selectedItems() if hasattr(i, "shape_name")]
            window.editor_panel_ui.set_target_items(sel_shapes)

    def drawForeground(self, painter, rect):
        if getattr(self, "_rb_active", False) and getattr(self, "_rb_visual_rect", None):
            pen = QtGui.QPen(QtGui.QColor(100, 150, 255, 200), 1, QtCore.Qt.SolidLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor(100, 150, 255, 100)))
            painter.drawRect(self._rb_visual_rect)
            
        if getattr(self, "_hier_drag_source", None) and getattr(self, "_hier_drag_pos", None):
            mode = getattr(self, "_hier_mode", "add")
            color = QtGui.QColor(100, 255, 100, 200) if mode == "add" else QtGui.QColor(255, 100, 100, 200)
            pen = QtGui.QPen(color, 2, QtCore.Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(self._hier_drag_source.sceneBoundingRect().center(), self._hier_drag_pos)

    def change_z_depth(self, items, direction):
        if not items: return
        self.alignment_requested.emit("z_front" if direction == "front" else "z_back", items)

    def add_new_shape(self, shape_type, scene_pos):
        max_z = 0.0
        for item in self.scene().items():
            if hasattr(item, "shape_name"):
                max_z = max(max_z, float(item.zValue()))
                
        data = {"type": shape_type, "label": "New", "pos": [scene_pos.x(), scene_pos.y()], "width": 60, "height": 30, "z_index": max_z + 1.0}
        if shape_type == "Circle": data["width"] = 50; data["height"] = 50
        elif shape_type == "Image": data["width"] = 200; data["height"] = 200; data["z_index"] = -1000.0 
        
        before = set(self.scene().items()); self.build_items_from_data([data]); after = set(self.scene().items())
        diff = list(after - before)
        return diff[0] if diff else None

    def edit_shape_properties(self, items):
        window = self.window()
        if hasattr(window, "show_editor_panel"): window.show_editor_panel(items)
    
    def build_items_from_data(self, items_list):
        shape_map = {
            "Rectangle": PickerRectangleItem, "Round Rectangle": PickerRoundRectangleItem, 
            "Circle": PickerCircleItem, "Polygon": PickerPolygonItem, 
            "Text": PickerTextItem, "Slider": PickerSliderItem, 
            "Pose": PickerPoseItem, "Checkbox": PickerCheckboxItem, "Image": PickerImageItem
        }
        new_items = []

        for data in items_list:
            item_type = data.get("type", "Rectangle")
            shape_class = shape_map.get(item_type, PickerRectangleItem)
            shape_item = shape_class(label=data.get("label", "Ctrl"), controls=data.get("controls", []))
            
            if "id" in data and data["id"]: shape_item.item_id = str(data["id"])
            
            def _f(key, default): 
                val = data.get(key, default)
                try: return float(val) if val is not None else default
                except: return default
            
            if item_type == "Polygon":
                if "path_data" in data:
                    pd = []
                    for d in data["path_data"]:
                        pd.append({
                            "p": QtCore.QPointF(float(d["p"][0]), float(d["p"][1])),
                            "in": QtCore.QPointF(float(d["in"][0]), float(d["in"][1])),
                            "out": QtCore.QPointF(float(d["out"][0]), float(d["out"][1])),
                            "s": bool(d.get("s", False))
                        })
                    shape_item.path_points = pd
                elif "points" in data: 
                    points_data = data.get("points", [])
                    if points_data:
                        pd = []
                        for p in points_data:
                            pd.append({
                                "p": QtCore.QPointF(float(p[0] if p[0] is not None else 0), float(p[1] if p[1] is not None else 0)),
                                "in": QtCore.QPointF(0,0), "out": QtCore.QPointF(0,0), "s": False
                            })
                        shape_item.path_points = pd
                if hasattr(shape_item, "_calculate_rect"): shape_item._calculate_rect()
            
            elif item_type == "Round Rectangle":
                shape_item.rad_tl = _f("rad_tl", 4.0); shape_item.rad_tr = _f("rad_tr", 4.0)
                shape_item.rad_bl = _f("rad_bl", 4.0); shape_item.rad_br = _f("rad_br", 4.0)
            
            elif item_type == "Pose":
                shape_item.pose_data = data.get("pose_data", {})
                shape_item.image_path = str(data.get("image_path", ""))
                shape_item.inside_text = bool(data.get("inside_text", False))
                shape_item.pose_shape = str(data.get("pose_shape", "Rectangle"))
                shape_item.pose_scale_mode = str(data.get("pose_scale_mode", "Fit"))
                shape_item.pose_padding = _f("pose_padding", 0.0)
                shape_item.pose_roundness = _f("pose_roundness", 8.0)
            
            elif item_type == "Checkbox": 
                shape_item.is_checked = bool(data.get("is_checked", False))
                shape_item.show_mark = bool(data.get("show_mark", True))
                shape_item.inside_text = bool(data.get("inside_text", False))
                shape_item.cb_shape = str(data.get("cb_shape", "Rectangle"))
                shape_item.cb_roundness = _f("cb_roundness", 8.0)
                
                mc = data.get("mark_color", "#ffffff")
                shape_item.mark_color = QtGui.QColor(mc) if mc else QtGui.QColor("#ffffff")
                
                cb_data = data.get("cb_data", {})
                for state in ["ON", "OFF"]:
                    if state not in cb_data: cb_data[state] = {}
                    cb_data[state]["text"] = cb_data[state].get("text", state)
                    cb_data[state]["color"] = cb_data[state].get("color", "#4d8c90" if state == "ON" else "#3c6e71")
                    cb_data[state]["attributes"] = cb_data[state].get("attributes", {})
                    cb_data[state]["shapes"] = cb_data[state].get("shapes", [])
                    cb_data[state]["command"] = cb_data[state].get("command", "")
                    cb_data[state]["cmd_type"] = cb_data[state].get("cmd_type", "python")
                shape_item.cb_data = cb_data
            
            elif item_type == "Image":
                shape_item.image_path = str(data.get("image_path", ""))
                shape_item.image_opacity = _f("image_opacity", 1.0)
                shape_item.image_scale_mode = str(data.get("image_scale_mode", "Fit"))
            
            elif item_type == "Slider":
                shape_item.attribute = str(data.get("attribute", "") or "")
                shape_item.inside_text = bool(data.get("inside_text", False))
                shape_item.min_value = _f("min_value", 0.0)
                shape_item.max_value = _f("max_value", 1.0)
                shape_item.value = _f("value", 0.0)
                shape_item.handle_scale = _f("handle_scale", 1.0)
                
                hc = data.get("handle_color", "#bfbfbf")
                shape_item.handle_color = QtGui.QColor(hc) if hc else QtGui.QColor("#bfbfbf")
            
            shape_item.width = _f("width", 60.0); shape_item.height = _f("height", 30.0)
            if hasattr(shape_item, "setRect"): shape_item.setRect(-shape_item.width/2.0, -shape_item.height/2.0, shape_item.width, shape_item.height)
            shape_item.setRotation(_f("rotation", 0.0))
            
            pos = data.get("pos", [0.0, 0.0])
            x_pos = float(pos[0]) if len(pos) > 0 and pos[0] is not None else 0.0
            y_pos = float(pos[1]) if len(pos) > 1 and pos[1] is not None else 0.0
            shape_item.setPos(x_pos, y_pos)
            shape_item.setZValue(_f("z_index", 1.0))
            
            shape_item.parent_links = data.get("parent_links", [])
            shape_item.child_links = data.get("child_links", [])
            shape_item.scripts = data.get("scripts", [])
            
            shape_item.placement_mode = str(data.get("placement_mode", "world"))
            shape_item.screen_anchor = str(data.get("screen_anchor", "center"))
            shape_item.thumb_path = str(data.get("thumb_path", ""))
            shape_item.thumb_padding = _f("thumb_padding", 6.0)
            shape_item.thumb_scale_mode = str(data.get("thumb_scale_mode", "fit"))
            
            shape_item.bg = {"normal": str(data.get("bg_normal", "#3c6e71")), "hover": str(data.get("bg_hover", "#4d8c90")), "press": str(data.get("bg_press", "#2a4d4f"))}
            shape_item.edge_color = {"normal": str(data.get("edge_normal", "#111111")), "hover": str(data.get("edge_hover", "#ffffff")), "press": str(data.get("edge_press", "#000000"))}
            shape_item.text_color = {"normal": str(data.get("text_normal", "#ffffff")), "hover": str(data.get("text_hover", "#ffffff")), "press": str(data.get("text_press", "#cccccc"))}
            
            shape_item.edge_visible = bool(data.get("edge_visible", True))
            shape_item.edge_thickness = {"normal": _f("edge_thick_n", 1.5), "hover": _f("edge_thick_h", 2.0), "press": _f("edge_thick_p", 1.5)}
            shape_item.font_point_size = int(_f("font_size", 10))
            shape_item.font_bold = bool(data.get("font_bold", False)); shape_item.font_italic = bool(data.get("font_italic", False))
            shape_item.text_align_h = str(data.get("text_align_h", "center")); shape_item.text_align_v = str(data.get("text_align_v", "center"))
            
            is_movable = data.get("movable_edit", not data.get("locked", False))
            shape_item.movable_edit = bool(is_movable)
            shape_item.locked = not bool(is_movable)
            shape_item.locked_edit = not bool(is_movable)
            shape_item.selectable_pose = bool(data.get("selectable_pose", True))
            
            shape_item.placement_mode = str(data.get("placement_mode", "world"))
            shape_item.screen_anchor = str(data.get("screen_anchor", "center"))
            shape_item.screen_offset_px = data.get("screen_offset_px", [0, 0])

            shape_item.command_type = str(data.get("command_type", "python")); shape_item.command_left = str(data.get("command_left", "")); shape_item.command_right = str(data.get("command_right", ""))

            if item_type == "Image" and "image_path" in data: shape_item.image_path = str(data["image_path"])
            
            self.scene().addItem(shape_item)
            self.update_item_flags(shape_item)
            new_items.append(shape_item)
        
        if not any(getattr(i, "is_hierarchy_layer", False) for i in self.scene().items()):
            self.hier_layer = PickerHierarchyLayer()
            self.scene().addItem(self.hier_layer)
        
        return new_items
    
    # FIX: Added *args to properly absorb the C++ arguments
    def update_screen_items(self, *args):
        vp_size = self.viewport().size()
        w, h = vp_size.width(), vp_size.height()

        if not hasattr(self, "scene") or not self.scene: return
        
        for item in self.scene().items():
            if getattr(item, "placement_mode", "world") == "screen":
                item.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)
                
                anchor = getattr(item, "screen_anchor", "center")
                ax, ay = w / 2.0, h / 2.0
                if "left" in anchor: ax = 0
                elif "right" in anchor: ax = w
                
                if "top" in anchor: ay = 0
                elif "bottom" in anchor: ay = h
                
                offset = getattr(item, "screen_offset_px", [0, 0])
                px = ax + offset[0]
                py = ay + offset[1]
                
                scene_pt = self.mapToScene(int(px), int(py))
                item.setPos(scene_pt)
            else:
                item.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, False)

    def scrollContentsBy(self, dx, dy):
        QtWidgets.QGraphicsView.scrollContentsBy(self, dx, dy)
        self.update_screen_items()

    def resizeEvent(self, event):
        QtWidgets.QGraphicsView.resizeEvent(self, event)
        # FIX: Removed lambda, calling the method directly
        QtCore.QTimer.singleShot(0, self.update_screen_items)
