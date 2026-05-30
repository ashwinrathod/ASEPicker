# ASEPicker/ui.py
from maya import cmds

try:
    from PySide2 import QtWidgets, QtGui, QtCore
except ImportError:
    from PySide6 import QtWidgets, QtGui, QtCore

# Import all the shapes from the new file!
from .picker_shapes import (
    PickerRectangleItem, PickerRoundRectangleItem, PickerCircleItem, 
    PickerPolygonItem, PickerTextItem, PickerSliderItem, 
    PickerPoseItem, PickerCheckboxItem, PickerImageItem
)

class SubTab(QtWidgets.QWidget):
    def __init__(self, name='Main', parent=None):
        super(SubTab, self).__init__(parent)
        self.name = name
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = PickerCanvas(self)
        self.layout.addWidget(self.canvas)

class CharacterTab(QtWidgets.QWidget):
    def __init__(self, name='Character', namespace='', parent=None):
        super(CharacterTab, self).__init__(parent)
        self.name = name
        self.namespace = namespace
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        
        self.sub_tabs = QtWidgets.QTabWidget(self)
        self.layout.addWidget(self.sub_tabs)
        self.sub_tabs.tabBar().setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.sub_tabs.tabBar().customContextMenuRequested.connect(self.show_tab_menu)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_tab_menu)
    
    def add_sub_tab(self, name):
        sub = SubTab(name, self)
        self.sub_tabs.addTab(sub, name)
        window = self.window()
        if hasattr(window, "selection_requested"): sub.canvas.item_selected.connect(window.selection_requested.emit)
        if hasattr(window, "alignment_requested"): sub.canvas.alignment_requested.connect(window.alignment_requested.emit)
        if hasattr(window, "item_interacted"): sub.canvas.item_interacted.connect(window.item_interacted.emit)
        if hasattr(window, "slider_moved"): sub.canvas.slider_moved.connect(window.slider_moved.emit)

        # --- CRITICAL FIX: Ensure brand new blank tabs inherit current Edit Mode ---
        if window:
            sub.canvas.is_edit_mode = getattr(window, "is_edit_mode", False)
            
        return sub

    def show_tab_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        add_act = menu.addAction("Add New Tab")
        rename_act = menu.addAction("Rename Tab")
        delete_act = menu.addAction("Delete Tab")
        action = getattr(menu, "exec", menu.exec_)(self.sub_tabs.tabBar().mapToGlobal(pos))
        idx = self.sub_tabs.tabBar().tabAt(pos)
        
        if action == add_act:
            text, ok = QtWidgets.QInputDialog.getText(self, "New Tab", "Tab Name:")
            if ok and text.strip(): self.add_sub_tab(text.strip())
        elif action == rename_act and idx >= 0:
            text, ok = QtWidgets.QInputDialog.getText(self, "Rename Tab", "New Name:", text=self.sub_tabs.tabText(idx))
            if ok and text.strip():
                self.sub_tabs.setTabText(idx, text.strip())
                self.sub_tabs.widget(idx).name = text.strip()
        elif action == delete_act and idx >= 0:
            if self.sub_tabs.count() > 0:
                confirm = QtWidgets.QMessageBox.question(self, "Delete Tab", "Delete this tab and all its shapes?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if confirm == QtWidgets.QMessageBox.Yes: self.sub_tabs.removeTab(idx)

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
    
    # NEW V0.0.7 Pose Signals
    pose_drag_started = QtCore.Signal(object)
    pose_dragged = QtCore.Signal(object, float)
    pose_drag_ended = QtCore.Signal(object)
    pose_action_requested = QtCore.Signal(list, str)
    
    # NEW V0.0.6 Signals
    edit_mode_toggled = QtCore.Signal(bool)
    bg_lock_toggled = QtCore.Signal(bool)
    hier_toggled = QtCore.Signal(bool)
    prefs_requested = QtCore.Signal()
    namespace_refresh_requested = QtCore.Signal()
    namespace_changed = QtCore.Signal(str)
    menu_action_requested = QtCore.Signal(str)

    # NEW V0.0.7 Signals
    copy_requested = QtCore.Signal(list)
    paste_requested = QtCore.Signal(object)
    
    # THE MISSING SIGNAL:
    window_closed = QtCore.Signal()

    def closeEvent(self, event):
        self.window_closed.emit()
        self.menu_action_requested.emit("close")
        super(PickerWindow, self).closeEvent(event)

    def __init__(self, parent=None):
        if parent is None: parent = get_maya_main_window()
        super(PickerWindow, self).__init__(parent)
        # ... rest of your __init__ logic ...
        self.setWindowTitle("ASEPicker 1.0.0")
        self.resize(600, 800)
        self.setWindowFlags(QtCore.Qt.Window)

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 5, 0, 0) # Tighter margins
        
        self.is_edit_mode = False
        self.bg_locked = False
        self.current_namespace = ""
        self.available_namespaces = []

        self._init_canvas_area()

        self.prefs_requested.connect(self.show_preferences)
        self.main_tabs.currentChanged.connect(self._on_main_tab_changed)
    
    def show_preferences(self):
        from .preferences import PrefsWindow
        if not hasattr(self, "prefs_ui") or self.prefs_ui is None:
            self.prefs_ui = PrefsWindow(self)
        self.prefs_ui.show()
        self.prefs_ui.raise_()
    
    def show_api_help(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("ASEPicker API & Scripting Guide")
        dialog.resize(850, 650)
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
        </table>
        
        <h3 style='color: #4CAF50;'>4. Layer Control</h3>
        <p>Easily toggle entire layers by their exact name in the Layers Tab.</p>
        <pre style='background: #111; padding: 8px; border-radius: 4px; color: #f1fa8c;'>api.set_layer_visibility("FK Controls", True)<br>api.set_layer_visibility("IK Controls", False)</pre>

        <h3 style='color: #4CAF50;'>5. Rigging Helpers</h3>
        <p>Get information about the current rig to run custom Maya commands.</p>
        <pre style='background: #111; padding: 8px; border-radius: 4px; color: #f1fa8c;'>from maya import cmds<br># Get namespace (e.g. 'Character1')<br>ns = api.get_namespace()<br><br># Automatically gets controls with the correct namespace!<br>ctrls = api.get_controls("YOUR_ID")<br>cmds.setKeyframe(ctrls)</pre>
        """
        text.setHtml(html)
        lay.addWidget(text)
        
        btn = QtWidgets.QPushButton("Close Guide")
        btn.setStyleSheet("padding: 8px; font-weight: bold; background: #333;")
        btn.clicked.connect(dialog.accept)
        lay.addWidget(btn)
        
        getattr(dialog, "exec", dialog.exec_)()
    
    def _init_canvas_area(self):
        self.main_tabs = QtWidgets.QTabWidget()
        self.main_layout.addWidget(self.main_tabs)
        self.main_tabs.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.main_tabs.customContextMenuRequested.connect(self.show_main_tab_menu)
        
        # --- THE CORNER TOOLBAR ---
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
        
        # 0. Edit Toggle (Text Only)
        self.btn_edit = QtWidgets.QToolButton()
        self.btn_edit.setText("Pose") 
        self.btn_edit.setToolTip("Toggle Edit / Pose Mode")
        self.btn_edit.setCheckable(True)
        self.btn_edit.clicked.connect(self._on_edit_toggled)
        
        # 1. Lock BG Images
        self.btn_bg_lock = QtWidgets.QToolButton()
        self.btn_bg_lock.setText("🖼️")
        self.btn_bg_lock.setToolTip("Lock BG Images")
        self.btn_bg_lock.setCheckable(True)
        self.btn_bg_lock.clicked.connect(self._on_bg_lock_toggled)
        
        # 2. Hierarchy
        self.btn_hier = QtWidgets.QToolButton()
        self.btn_hier.setText("🔗")
        self.btn_hier.setToolTip("Toggle Hierarchy Visibility")
        self.btn_hier.setCheckable(True)
        self.btn_hier.clicked.connect(self._on_hier_toggled)
        
        # 3. Namespace Menu
        self.btn_ns = QtWidgets.QToolButton()
        self.btn_ns.setText("N:")
        self.btn_ns.setToolTip("Namespace: (None)")
        self.btn_ns.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.ns_menu = QtWidgets.QMenu(self.btn_ns)
        self.btn_ns.setMenu(self.ns_menu)
        self.ns_menu.aboutToShow.connect(self._populate_ns_menu)
        
        # 4. Main Menu (Preferences Moved Here!)
        self.btn_menu = QtWidgets.QToolButton()
        self.btn_menu.setText("☰")
        self.btn_menu.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.main_menu = QtWidgets.QMenu(self.btn_menu)
        
        # --- THE NEW SHORTCUT ACTIONS ---
        act_open = self.main_menu.addAction("📂 Open...")
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(lambda: self.menu_action_requested.emit("open"))
        
        act_save = self.main_menu.addAction("💾 Save")
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(lambda: self.menu_action_requested.emit("save"))
        
        act_save_as = self.main_menu.addAction("💾 Save As...")
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(lambda: self.menu_action_requested.emit("save_as"))
        
        self.main_menu.addAction("📦 Save to Scene").triggered.connect(lambda: self.menu_action_requested.emit("save_scene"))
        self.main_menu.addSeparator()
        
        self.main_menu.addAction("🔄 Smart Sync UI").triggered.connect(lambda: self.menu_action_requested.emit("smart_sync"))
        self.main_menu.addSeparator()
        
        self.main_menu.addAction("⚙️ Preferences").triggered.connect(lambda: self.prefs_requested.emit())
        self.main_menu.addSeparator()
        
        self.main_menu.addAction("📖 Help / API Guide").triggered.connect(self.show_api_help)
        self.main_menu.addSeparator()
        
        self.main_menu.addAction("❌ Close").triggered.connect(self.close)
        self.main_menu.addAction("💀 Kill ASEPicker").triggered.connect(lambda: self.menu_action_requested.emit("kill"))
        self.main_menu.addSeparator()
        self.main_menu.addAction("ℹ️ About").triggered.connect(lambda: self.menu_action_requested.emit("about"))
        
        self.btn_menu.setMenu(self.main_menu)
        
        self.corner_layout.addWidget(self.btn_edit)
        self.corner_layout.addWidget(self.btn_bg_lock)
        self.corner_layout.addWidget(self.btn_hier)
        self.corner_layout.addWidget(self.btn_ns)
        self.corner_layout.addWidget(self.btn_menu)
        
        self.main_tabs.setCornerWidget(self.corner_widget, QtCore.Qt.TopRightCorner)

    # --- Dual State Toggle Logic ---
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
        
        # Force all canvas viewports to redraw immediately!
        for i in range(self.main_tabs.count()):
            char_tab = self.main_tabs.widget(i)
            for j in range(char_tab.sub_tabs.count()):
                char_tab.sub_tabs.widget(j).canvas.viewport().update()

    def _on_main_tab_changed(self, idx):
        self.menu_action_requested.emit("sync_title")
        char_tab = self.main_tabs.widget(idx)
        if char_tab:
            ns = getattr(char_tab, "namespace", "")
            self.current_namespace = ns
            self.btn_ns.setToolTip(f"Namespace: {ns if ns else '(None)'}")
            self.namespace_changed.emit(ns)

    # --- Dynamic Namespace Menu ---
    def _populate_ns_menu(self):
        self.ns_menu.clear()
        
        # Set Selected Namespace (Grabs whatever is selected in Maya)
        self.ns_menu.addAction("✨ Set Selected Namespace").triggered.connect(self._set_ns_from_selection)
        self.ns_menu.addSeparator()
        
        # Add Namespace (Manual)
        self.ns_menu.addAction("➕ Add Namespace...").triggered.connect(self._add_manual_ns)
        self.ns_menu.addAction("🧹 Clear Namespace").triggered.connect(lambda: self._set_namespace(""))
        self.ns_menu.addSeparator()

        # Emit signal to core to refresh self.available_namespaces safely
        self.namespace_refresh_requested.emit()

        for ns in self.available_namespaces:
            # FIX: Adding checked=False prevents the PySide lambda TypeError!
            self.ns_menu.addAction(ns).triggered.connect(lambda checked=False, n=ns: self._set_namespace(n))

    def _set_ns_from_selection(self):
        """Helper to grab namespace from the first selected object in Maya."""
        sel = cmds.ls(selection=True)
        if not sel: return
        if ":" in sel[0]:
            ns = sel[0].rsplit(":", 1)[0]
            self._set_namespace(ns)

    def _set_namespace(self, ns):
        self.current_namespace = ns
        self.btn_ns.setToolTip(f"Namespace: {ns if ns else '(None)'}")
        char_tab = self.main_tabs.currentWidget()
        if char_tab: char_tab.namespace = ns
        self.namespace_changed.emit(ns)

    def _add_manual_ns(self):
        text, ok = QtWidgets.QInputDialog.getText(self, "Manual Namespace", "Enter Namespace:")
        if ok: self._set_namespace(text.strip())

    # --- Maintain existing Tab and Editor functions below... ---
    def add_character_tab(self, name, namespace):
        char_tab = CharacterTab(name, namespace, self)
        self.main_tabs.addTab(char_tab, name)
        return char_tab

    def show_main_tab_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        
        # 1. Show 'Open' ONLY if there are no tabs loaded
        open_act = None
        if self.main_tabs.count() == 0:
            open_act = menu.addAction("📂 Open...")
            menu.addSeparator()
        
        # 2. Existing Add Tab Option
        add_act = menu.addAction("➕ Add Character Tab")
        
        tab_bar = self.main_tabs.tabBar()
        mapped_pos = tab_bar.mapFrom(self.main_tabs, pos)
        idx = tab_bar.tabAt(mapped_pos)
        
        rename_act = delete_act = None
        if idx >= 0:
            menu.addSeparator()
            rename_act = menu.addAction("Rename Tab")
            delete_act = menu.addAction("Delete Tab")
            
        action = getattr(menu, "exec", menu.exec_)(self.main_tabs.mapToGlobal(pos))
        if not action: return
        
        # 3. Execution Routing
        if action == open_act:
            self.menu_action_requested.emit("open") # Routes securely to main.py
        elif action == add_act:
            text, ok = QtWidgets.QInputDialog.getText(self, "New Character", "Character Name:")
            if ok and text.strip():
                char_tab = self.add_character_tab(text.strip(), "")
                char_tab.add_sub_tab("Main")
        elif action == rename_act:
            text, ok = QtWidgets.QInputDialog.getText(self, "Rename Character", "New Name:", text=self.main_tabs.tabText(idx))
            if ok and text.strip():
                self.main_tabs.setTabText(idx, text.strip())
                self.main_tabs.widget(idx).name = text.strip()
                self.menu_action_requested.emit("sync_title")
        elif action == delete_act:
            confirm = QtWidgets.QMessageBox.question(self, "Delete Character", "Delete this Character Tab and all its Sub-Tabs?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if confirm == QtWidgets.QMessageBox.Yes: self.main_tabs.removeTab(idx)

    def show_editor_panel(self, items):
        from .editor_panel import EditorPanel
        if not hasattr(self, "editor_panel_ui") or self.editor_panel_ui is None:
            self.editor_panel_ui = EditorPanel(self)
            self.editor_panel_ui.setWindowFlags(QtCore.Qt.Tool)
            
            # WIRING ALL THE EDITOR SIGNALS
            self.editor_panel_ui.controls_modified.connect(
                lambda act: self.controls_modified_requested.emit(self.editor_panel_ui.target_items, act)
            )
            self.editor_panel_ui.attribute_modified.connect(
                lambda act: self.attribute_modified_requested.emit(self.editor_panel_ui.target_items, act)
            )
            self.editor_panel_ui.pose_action_requested.connect(
                lambda act: self.pose_action_requested.emit(self.editor_panel_ui.target_items, act)
            )
            self.editor_panel_ui.checkbox_action_requested.connect(
                lambda state, act: self.checkbox_action_requested.emit(self.editor_panel_ui.target_items, state, act)
            )
            self.editor_panel_ui.alignment_requested.connect(
                lambda act: self.alignment_requested.emit(act, self.editor_panel_ui.target_items)
            )
            self.editor_panel_ui.image_action_requested.connect(
                lambda act: self.image_action_requested.emit(self.editor_panel_ui.target_items, act)
            )
        
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
        super().__init__(parent)
        self.scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene)
        self.scene.setSceneRect(-32000, -32000, 64000, 64000)

        # APPLY GRID PREFS
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
        
        # Hierarchy System Trackers
        self._hier_mode = None
        self._hier_drag_source = None
        self._hier_drag_pos = None

        self._mirror_use_canvas = prefs.get("mirror_use_canvas")
        
        # --- NEW: LAYER SYSTEM ---
        self.layer_data = []

        # --- ADVANCED SCRIPTS SYSTEM ---
        self.canvas_scripts = []
        # -------------------------

    def apply_layer_visibility(self):
        is_edit = getattr(self, "is_edit_mode", False)
        all_shapes = [i for i in self.scene.items() if hasattr(i, "item_id")]
        
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
        """Universally updates locks and clickability based on current Window states AND Layers."""
        if not hasattr(item, "shape_name"): return
        
        win = self.window()
        is_edit = getattr(win, "is_edit_mode", False) if win else False
        is_bg_locked = getattr(win, "bg_locked", False) if win else False
        
        # Find layer for this item
        layer = next((l for l in getattr(self, "layer_data", []) if item.item_id in l.get("shapes", [])), None)

        # 1. Base Standard Logic
        item.setAcceptedMouseButtons(QtCore.Qt.LeftButton | QtCore.Qt.RightButton | QtCore.Qt.MiddleButton)
        if is_edit:
            item.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
            item.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, not getattr(item, "locked_edit", False))
        else:
            item.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, getattr(item, "selectable_pose", True))
            item.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)

        # 2. Background Lock override for Images (Highest Priority)
        if item.shape_name == "Image" and is_bg_locked:
            item.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)
            item.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)
            item.setAcceptedMouseButtons(QtCore.Qt.NoButton)

    def update_all_flags(self):
        """Forces all items on canvas to refresh their flags."""
        for item in self.scene.items():
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
            
            # Thick Center Axes
            painter.setPen(QtGui.QPen(color, 2))
            painter.drawLine(QtCore.QLineF(0, rect.top(), 0, rect.bottom()))
            painter.drawLine(QtCore.QLineF(rect.left(), 0, rect.right(), 0))

        # --- NEW: DRAW HIERARCHY CONNECTIONS ---
        win = self.window()
        if win and hasattr(win, "btn_hier") and win.btn_hier.isChecked():
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            pen = QtGui.QPen(QtGui.QColor(100, 255, 100, 150), 2, QtCore.Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(QtGui.QColor(100, 255, 100, 150))
            
            all_shapes = {itm.item_id: itm for itm in self.scene.items() if hasattr(itm, "item_id")}
            import math
            
            for itm in self.scene.items():
                if hasattr(itm, "child_links") and itm.child_links and itm.isVisible():
                    p1 = itm.sceneBoundingRect().center()
                    for cid in itm.child_links:
                        child = all_shapes.get(cid)
                        if child and child.isVisible():
                            p2 = child.sceneBoundingRect().center()
                            painter.drawLine(p1, p2)
                            
                            # Draw Arrow Head at midpoint
                            angle = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
                            arrow_size = 10
                            mid_pt = QtCore.QPointF((p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0)
                            
                            p_a = QtCore.QPointF(mid_pt.x() - arrow_size * math.cos(angle - math.pi / 6),
                                                 mid_pt.y() - arrow_size * math.sin(angle - math.pi / 6))
                            p_b = QtCore.QPointF(mid_pt.x() - arrow_size * math.cos(angle + math.pi / 6),
                                                 mid_pt.y() - arrow_size * math.sin(angle + math.pi / 6))
                            
                            poly = QtGui.QPolygonF([mid_pt, p_a, p_b])
                            painter.drawPolygon(poly)
            painter.restore()

    def wheelEvent(self, event):
        delta = event.angleDelta().y() if hasattr(event, "angleDelta") else event.delta()
        zoom_factor = 1.15 if delta > 0 else (1.0 / 1.15)
        self.scale(zoom_factor, zoom_factor)

    def _update_editor_ui(self):
        """Helper to instantly update the Editor Panel selection list."""
        window = self.window()
        if hasattr(window, "editor_panel_ui") and window.editor_panel_ui:
            sel_shapes = [i for i in self.scene.selectedItems() if hasattr(i, "shape_name")]
            window.editor_panel_ui.set_target_items(sel_shapes)

    def mousePressEvent(self, event):
        # --- NATIVE MAYA ZOOM (Alt + Left/Right Click) ---
        if event.modifiers() == QtCore.Qt.AltModifier and event.button() in [QtCore.Qt.LeftButton, QtCore.Qt.RightButton]:
            self._is_alt_zooming = True
            self._zoom_start_pos = event.pos()
            self._zoom_anchor_pos = event.pos() 
            self.setCursor(QtCore.Qt.SizeBDiagCursor)
            event.accept()
            return
        
        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return

        # 3. POLYGON EXCLUSIVE LOCK: Block all clicks outside the active editing polygon
        exclusive = getattr(self, "_exclusive_poly", None)
        if exclusive:
            # Always allow Right-Click so we can open context menu to exit edit mode
            if event.button() == QtCore.Qt.RightButton:
                QtWidgets.QGraphicsView.mousePressEvent(self, event)
                return
            
            # If Left-Click, only pass the event if they actually clicked the Polygon
            item = self.itemAt(event.pos())
            if item == exclusive:
                QtWidgets.QGraphicsView.mousePressEvent(self, event)
            
            # Eat the event to prevent deselection of the active polygon!
            event.accept()
            return

        is_edit = getattr(self, "is_edit_mode", False)
        
        # --- RECORD POSITIONS BEFORE DRAGGING ---
        if is_edit:
            self._undo_drag_pos = {itm.item_id: itm.pos() for itm in self.scene.items() if hasattr(itm, "item_id")}
        
        item = self.itemAt(event.pos())
        
        # THE BG LOCK FIX: If we click an Image and BG is locked, pretend we clicked empty space!
        if item and getattr(item, "shape_name", "") == "Image":
            win = self.window()
            if win and getattr(win, "bg_locked", False):
                item = None 
                
        is_shape = bool(item and hasattr(item, "shape_name"))
        
        mods = event.modifiers()
        is_shift = bool(mods & QtCore.Qt.ShiftModifier)
        is_ctrl = bool(mods & QtCore.Qt.ControlModifier)
        is_alt = bool(mods & QtCore.Qt.AltModifier)
        click_type = "left" if event.button() == QtCore.Qt.LeftButton else "right"

        # --- NEW: HIERARCHY DRAG START ---
        if getattr(self, "_hier_mode", None) and is_shape and click_type == "left":
            self._hier_drag_source = item
            self._hier_drag_pos = self.mapToScene(event.pos())
            event.accept()
            return

        if is_shape:
            if is_edit:
                if click_type == "left":
                    if is_shift:
                        item.setSelected(True)
                        self._update_editor_ui()
                        event.accept()
                        return
                    elif is_ctrl:
                        item.setSelected(False)
                        self._update_editor_ui()
                        event.accept()
                        return
                    else:
                        if not item.isSelected():
                            self.scene.clearSelection()
                            item.setSelected(True)
                
                QtWidgets.QGraphicsView.mousePressEvent(self, event)
                self._update_editor_ui()
                return
            else:
                self.item_interacted.emit(item, click_type, mods)
                if click_type == "left":
                    self._pressed_item = item  
                    self._shape_press_pos = event.pos()
                    
                    if getattr(item, "shape_name", "") in ["Slider", "Pose", "Checkbox"]:
                        item._visual_state = "press"
                        item.update()
                        
                    if getattr(item, "shape_name", "") in ["Slider", "Pose", "Checkbox"]:
                        if item.shape_name == "Slider":
                            item.update_from_drag(self.mapToScene(event.pos()))
                            self.slider_moved.emit(item, item.value)
                        elif item.shape_name == "Pose":
                            scene_pt = self.mapToScene(event.pos())
                            item._drag_start_x = item.mapFromScene(scene_pt).x()
                            item._drag_pct = 0.0 
                            self.window().pose_drag_started.emit(item)
                        elif item.shape_name == "Checkbox":
                            item.is_checked = not getattr(item, "is_checked", False)
                            item.update()
                            self.window().checkbox_toggled.emit(item)
                            event.accept()

                            state_key = "ON" if item.is_checked else "OFF"
                            cmd = item.cb_data.get(state_key, {}).get("command", "")
                            cmd_type = item.cb_data.get(state_key, {}).get("cmd_type", "python")
                            if cmd:
                                try:
                                    if cmd_type == "mel":
                                        import maya.mel as mel
                                        mel.eval(cmd)
                                    else: exec(cmd, globals())
                                except Exception as e: print(f"ASEPicker Checkbox Script Error [{state_key}]: {e}")
                            
                            self.window().menu_action_requested.emit("smart_sync")
                        
                        event.accept()
                        return
                    else:
                        # STANDARD SHAPE: Do not select immediately. Prep Rubber Band in case of drag.
                        self._rb_active = True
                        self._rb_origin_scene = self.mapToScene(event.pos())
                        self._rb_origin_vp = event.pos()
                        self._rb_visual_rect = QtCore.QRectF(self._rb_origin_scene, self._rb_origin_scene)
                        self._pre_drag_sel = self.scene.selectedItems()
                        event.accept()
                        return
                
                elif click_type == "right":
                    event.accept()
                    return

        else:
            if click_type == "left":
                self._rb_active = True
                self._rb_origin_scene = self.mapToScene(event.pos())
                self._rb_origin_vp = event.pos()
                self._rb_visual_rect = QtCore.QRectF(self._rb_origin_scene, self._rb_origin_scene)
                self._pre_drag_sel = self.scene.selectedItems()
                
                if not (is_shift or is_ctrl):
                    self.scene.clearSelection()
                    if not is_edit:
                        self.item_selected.emit([], "replace") 
                        
                self.viewport().update()
                event.accept()
                return
            elif click_type == "right":
                event.accept()
                return

        QtWidgets.QGraphicsView.mousePressEvent(self, event)

    def keyPressEvent(self, event):
        """Dynamic Keyboard Shortcuts based on Preferences."""
        from .preferences import PrefManager
        prefs = PrefManager()
        
        # PySide6 Compatibility for Enum Integer Extraction
        k = event.key()
        k_int = k.value if hasattr(k, "value") else int(k)
        mods = event.modifiers()
        mods_int = mods.value if hasattr(mods, "value") else int(mods)
        
        key_int = k_int | mods_int
        is_edit = getattr(self, "is_edit_mode", False)
        
        # --- UNDO / REDO HOTKEYS ---
        key_z_int = QtCore.Qt.Key_Z.value if hasattr(QtCore.Qt.Key_Z, "value") else int(QtCore.Qt.Key_Z)
        if is_edit and k_int == key_z_int and (mods_int & QtCore.Qt.ControlModifier):
            if (mods_int & QtCore.Qt.ShiftModifier):
                self.window().menu_action_requested.emit("redo")
            else:
                self.window().menu_action_requested.emit("undo")
            event.accept()
            return
        
        def match(key_name):
            seq = QtGui.QKeySequence(prefs.get(key_name))
            pressed_seq = QtGui.QKeySequence(key_int)
            return seq.matches(pressed_seq) == QtGui.QKeySequence.ExactMatch
        
        if match("hk_hier_add") and not event.isAutoRepeat():
            self._hier_mode = "add"
            self.setCursor(QtCore.Qt.CrossCursor)
            event.accept(); return
        
        if match("hk_hier_rem") and not event.isAutoRepeat():
            self._hier_mode = "rem"
            self.setCursor(QtCore.Qt.ForbiddenCursor)
            event.accept(); return
        
        if match("hk_prefs"):
            self.window().prefs_requested.emit()
            event.accept(); return
        
        if match("hk_pose"):
            self.window().btn_edit.setChecked(False)
            self.window()._on_edit_toggled(False)
            event.accept(); return
        
        if match("hk_edit"):
            self.window().btn_edit.setChecked(True)
            self.window()._on_edit_toggled(True)
            event.accept(); return
        
        if match("hk_editor"):
            # THE FIX: Safely route directly to the Canvas's native editor spawner
            is_edit = getattr(self, "is_edit_mode", False) or getattr(self.window(), "is_edit_mode", False)
            if is_edit:
                sel = [i for i in self.scene.selectedItems() if hasattr(i, "shape_name")]
                if sel: 
                    self.edit_shape_properties(sel)
            event.accept(); return

        if match("hk_focus"):
            # THE FIX: Removed () from self.scene
            target_items = [i for i in self.scene.selectedItems() if hasattr(i, "shape_name")]
            if not target_items: target_items = [i for i in self.scene.items() if hasattr(i, "shape_name")]
            if target_items:
                br = QtCore.QRectF()
                for i in target_items:
                    item_scene_rect = i.mapToScene(i.box_rect()).boundingRect()
                    br = item_scene_rect if br.isEmpty() else br.united(item_scene_rect)
                self.fitInView(br.adjusted(-5, -5, 5, 5), QtCore.Qt.KeepAspectRatio)
            event.accept(); return
        
        if match("hk_reset"):
            self.resetTransform()
            self.centerOn(0, 0)
            event.accept(); return
        
        # 3. Delete = Delete Shapes (Edit Mode Only)
        if is_edit and event.key() == QtCore.Qt.Key_Delete:
            sel_items = [i for i in self.scene.selectedItems() if hasattr(i, "shape_name")]
            for t in sel_items: 
                self.scene.removeItem(t)
            self._update_editor_ui()
            self.window().menu_action_requested.emit("push_undo")
            event.accept()
            return
        
        # 4. Arrow Key Nudging (Edit Mode Only)
        if is_edit and event.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
            dx, dy = 0, 0
            step = 10 if event.modifiers() & QtCore.Qt.ShiftModifier else 1
            
            if event.key() == QtCore.Qt.Key_Left: dx = -step
            elif event.key() == QtCore.Qt.Key_Right: dx = step
            elif event.key() == QtCore.Qt.Key_Up: dy = -step
            elif event.key() == QtCore.Qt.Key_Down: dy = step
            
            sel_items = [i for i in self.scene.selectedItems() if hasattr(i, "shape_name")]
            if sel_items:
                for item in sel_items:
                    item.setPos(item.x() + dx, item.y() + dy)
                    if hasattr(item, "prepareGeometryChange"):
                        item.prepareGeometryChange()
                self._update_editor_ui()
                self._arrow_nudged = True
                event.accept() 
                return
        
        # 5. Copy (Ctrl+C)
        if is_edit and event.key() == QtCore.Qt.Key_C and (event.modifiers() & QtCore.Qt.ControlModifier):
            sel_items = [i for i in self.scene.selectedItems() if hasattr(i, "shape_name")]
            if sel_items:
                self.window().copy_requested.emit(sel_items)
            event.accept()
            return
            
        # 6. Paste (Ctrl+V)
        if is_edit and event.key() == QtCore.Qt.Key_V and (event.modifiers() & QtCore.Qt.ControlModifier):
            self.window().paste_requested.emit(self)
            event.accept()
            return
        
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            if getattr(self, "_hier_mode", None):
                self._hier_mode = None
                self.setCursor(QtCore.Qt.ArrowCursor)
            if getattr(self, "_arrow_nudged", False):
                self.window().menu_action_requested.emit("push_undo")
                self._arrow_nudged = False
        super().keyReleaseEvent(event)
    
    def mouseMoveEvent(self, event):
        # --- NEW: HIERARCHY DRAG UPDATE ---
        if getattr(self, "_hier_drag_source", None):
            self._hier_drag_pos = self.mapToScene(event.pos())
            self.viewport().update()
            event.accept()
            return

        # --- NATIVE MAYA ZOOM ---
        if getattr(self, "_is_alt_zooming", False):
            delta = event.pos() - self._zoom_start_pos
            import math
            factor = math.pow(1.005, delta.x() - delta.y())
            
            # THE FIX: Precision Math to zoom directly towards the original click point!
            old_scene_pos = self.mapToScene(self._zoom_anchor_pos)
            self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
            self.scale(factor, factor)
            new_scene_pos = self.mapToScene(self._zoom_anchor_pos)
            
            delta_scene = new_scene_pos - old_scene_pos
            self.translate(delta_scene.x(), delta_scene.y())
            
            self._zoom_start_pos = event.pos()
            self.update_screen_items()
            event.accept()
            return
        
        if getattr(self, "_is_panning", False):
            delta = event.pos() - self._pan_start_pos
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            self._pan_start_pos = event.pos()
            event.accept()
            return
            
        if getattr(self, "_rb_active", False):
            origin_vp = getattr(self, "_rb_origin_vp", event.pos())
            if (event.pos() - origin_vp).manhattanLength() < 4:
                event.accept()
                return
            cur = self.mapToScene(event.pos())
            self._rb_visual_rect = QtCore.QRectF(self._rb_origin_scene, cur).normalized()
            self.viewport().update()
            event.accept()
            return
        
        is_edit = getattr(self, "is_edit_mode", False)
        if not is_edit and getattr(self, "_pressed_item", None):
            if self._pressed_item.shape_name == "Slider":
                self._pressed_item.update_from_drag(self.mapToScene(event.pos()))
                self.slider_moved.emit(self._pressed_item, self._pressed_item.value)
                
                # --- NEW: Live sync the Editor Panel SpinBox ---
                window = self.window()
                if hasattr(window, "editor_panel_ui") and window.editor_panel_ui:
                    # Only update if this exact slider is currently selected in the Editor
                    if window.editor_panel_ui.target_items == [self._pressed_item]:
                        window.editor_panel_ui.sl_val.blockSignals(True)
                        window.editor_panel_ui.sl_val.setValue(self._pressed_item.value)
                        window.editor_panel_ui.sl_val.blockSignals(False)
                        
                event.accept()
                return
            elif self._pressed_item.shape_name == "Pose":
                pct = self._pressed_item.update_from_drag(self.mapToScene(event.pos()))
                self.window().pose_dragged.emit(self._pressed_item, pct)
                event.accept()
                return
        
        QtWidgets.QGraphicsView.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event):
        is_edit = getattr(self, "is_edit_mode", False) or getattr(self.window(), "is_edit_mode", False)
        
        # --- CHECK IF DRAGGED AND PUSH UNDO ---
        if is_edit and getattr(self, "_undo_drag_pos", None):
            moved = False
            for itm in self.scene.items():
                if hasattr(itm, "item_id") and itm.item_id in self._undo_drag_pos:
                    if itm.pos() != self._undo_drag_pos[itm.item_id]:
                        moved = True
                        break
            if moved:
                self.window().menu_action_requested.emit("push_undo")
            self._undo_drag_pos = None
        
        # --- HIERARCHY LINK EXECUTE ---
        if getattr(self, "_hier_drag_source", None):
            target_item = self.itemAt(event.pos())
            if target_item and getattr(target_item, "shape_name", "") == "Image":
                win = self.window()
                if win and getattr(win, "bg_locked", False): target_item = None 
                
            if target_item and hasattr(target_item, "shape_name") and target_item != self._hier_drag_source:
                source = self._hier_drag_source
                mode = getattr(self, "_hier_mode", "add")
                
                if mode == "add":
                    if target_item.item_id not in source.child_links: source.child_links.append(target_item.item_id)
                    if source.item_id not in target_item.parent_links: target_item.parent_links.append(source.item_id)
                elif mode == "rem":
                    if target_item.item_id in source.child_links: source.child_links.remove(target_item.item_id)
                    if source.item_id in target_item.parent_links: target_item.parent_links.remove(source.item_id)
                
                self._update_editor_ui() 
                self.window().menu_action_requested.emit("push_undo")
                
            self._hier_drag_source = None
            self._hier_drag_pos = None
            self.viewport().update()
            event.accept()
            return

        # --- NATIVE MAYA ZOOM ---
        if getattr(self, "_is_alt_zooming", False):
            self._is_alt_zooming = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            event.accept()
            return
        
        is_edit = getattr(self, "is_edit_mode", False) or getattr(self.window(), "is_edit_mode", False)
        if is_edit and hasattr(self, "scene") and self.scene and self.scene.selectedItems():
            vp_size = self.viewport().size()
            w, h = vp_size.width(), vp_size.height()
            for item in self.scene.selectedItems():
                if getattr(item, "placement_mode", "world") == "screen":
                    vp_pt = self.mapFromScene(item.pos())
                    px, py = vp_pt.x(), vp_pt.y()
                    
                    anchor = getattr(item, "screen_anchor", "center")
                    ax, ay = w / 2.0, h / 2.0
                    if "left" in anchor: ax = 0
                    elif "right" in anchor: ax = w
                    if "top" in anchor: ay = 0
                    elif "bottom" in anchor: ay = h
                    
                    item.screen_offset_px = [px - ax, py - ay]

        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            event.accept()
            return

        is_edit = getattr(self, "is_edit_mode", False)
        mods = event.modifiers()
        is_shift = bool(mods & QtCore.Qt.ShiftModifier)
        is_ctrl = bool(mods & QtCore.Qt.ControlModifier)
        is_alt = bool(mods & QtCore.Qt.AltModifier)

        if not is_edit and getattr(self, "_pressed_item", None):
            item = self._pressed_item
            item._visual_state = "hover" if item.isUnderMouse() else "normal"
            item.update()
            
            dist = (event.pos() - getattr(self, "_shape_press_pos", event.pos())).manhattanLength()
            is_pure_click = dist < 5
            
            if is_pure_click:
                self._rb_active = False # Cancel rubber band for pure click
                
                if item.shape_name not in ["Pose", "Slider", "Checkbox"]:
                    # --- NATIVE SHAPE SELECTION DELAYED TO RELEASE ---
                    if is_shift: mode = "add"
                    elif is_ctrl: mode = "deselect"
                    elif is_alt: mode = "mirror"
                    else: mode = "replace"
                    self.item_selected.emit(item.controls, mode)

                elif item.shape_name == "Pose":
                    self.window().pose_dragged.emit(item, 1.0)
                    item._drag_pct = None
                    self.window().pose_drag_ended.emit(item)
                    
                # --- ADVANCED SCRIPTS: SHAPE LEFT CLICK ENGINE ---
                if hasattr(item, "scripts") and item.scripts:
                    for scr in item.scripts:
                        if scr.get("trigger") == "Left Click (Action)":
                            self.execute_custom_script(scr.get("command", ""), scr.get("type", "python"))
                            
                    left_menus = [s for s in item.scripts if s.get("trigger") == "Left Click (Menu)"]
                    if left_menus:
                        l_menu = QtWidgets.QMenu(self)
                        l_menu.setStyleSheet("QMenu { background: #2b2b2b; color: #dfdfdf; border: 1px solid #555; } QMenu::item:selected { background: #5285a6; }")
                        custom_acts = {}
                        for scr in left_menus:
                            act = l_menu.addAction(scr.get("label", "Script"))
                            custom_acts[act] = scr
                            
                        def _show_left_menu():
                            sel_act = getattr(l_menu, "exec", l_menu.exec_)(QtGui.QCursor.pos())
                            if sel_act in custom_acts:
                                scr = custom_acts[sel_act]
                                self.execute_custom_script(scr.get("command", ""), scr.get("type", "python"))
                                
                        QtCore.QTimer.singleShot(10, _show_left_menu)
                
                self._pressed_item = None
                event.accept()
                return
            else:
                # DRAG DETECTED ON A SHAPE
                if item.shape_name == "Pose":
                    item._drag_pct = None
                    self.window().pose_drag_ended.emit(item)
                    self._pressed_item = None
                    event.accept()
                    return
                elif item.shape_name in ["Slider", "Checkbox"]:
                    self._pressed_item = None
                    event.accept()
                    return
                else:
                    self._pressed_item = None
                    # Fallthrough to Rubber Band logic below!

        if getattr(self, "_rb_active", False):
            self._rb_active = False
            origin_vp = getattr(self, "_rb_origin_vp", event.pos())
            is_click = (event.pos() - origin_vp).manhattanLength() < 5
            
            if is_click and not is_edit:
                canvas_scripts = getattr(self, "canvas_scripts", [])
                if canvas_scripts:
                    for scr in canvas_scripts:
                        if scr.get("trigger") == "Left Click (Action)":
                            self.execute_custom_script(scr.get("command", ""), scr.get("type", "python"))
                            
                    left_menus = [s for s in canvas_scripts if s.get("trigger") == "Left Click (Menu)"]
                    if left_menus:
                        l_menu = QtWidgets.QMenu(self)
                        l_menu.setStyleSheet("QMenu { background: #2b2b2b; color: #dfdfdf; border: 1px solid #555; } QMenu::item:selected { background: #5285a6; }")
                        custom_acts = {}
                        for scr in left_menus:
                            act = l_menu.addAction(scr.get("label", "Script"))
                            custom_acts[act] = scr
                            
                        def _show_left_menu():
                            sel_act = getattr(l_menu, "exec", l_menu.exec_)(QtGui.QCursor.pos())
                            if sel_act in custom_acts:
                                scr = custom_acts[sel_act]
                                self.execute_custom_script(scr.get("command", ""), scr.get("type", "python"))
                                
                        QtCore.QTimer.singleShot(10, _show_left_menu)
                
                # Clicked empty space without dragging, clear selection
                if not (is_shift or is_ctrl):
                    self.scene.clearSelection()
                    self.item_selected.emit([], "replace")
            else:
                items_in_band = self.scene.items(self._rb_visual_rect, QtCore.Qt.IntersectsItemShape)

                if not is_edit:
                    # POSE MODE: Safely ignore UI elements so they don't trigger Maya selections
                    rubber_sel = set(i for i in items_in_band if hasattr(i, "shape_name") and i.shape_name not in ["Image", "Text", "Pose", "Checkbox", "Slider"])
                    band_controls = []
                    for it in rubber_sel:
                        band_controls.extend(getattr(it, "controls", []))
                        
                    if is_shift: mode = "add"
                    elif is_ctrl: mode = "deselect"
                    elif is_alt: mode = "mirror"
                    else: mode = "replace"
                    
                    self.item_selected.emit(band_controls, mode)
                else:
                    # EDIT MODE: Allow selecting ALL shapes! (Images are protected by bg_lock)
                    rubber_sel = set(i for i in items_in_band if hasattr(i, "shape_name"))
                    pre_sel = set(i for i in getattr(self, "_pre_drag_sel", []) if hasattr(i, "shape_name"))

                    if is_shift:
                        final_sel = pre_sel.union(rubber_sel)
                    elif is_ctrl:
                        final_sel = pre_sel - rubber_sel
                    else:
                        final_sel = rubber_sel

                    self.scene.clearSelection()
                    for it in final_sel:
                        it.setSelected(True)

                    window = self.window()
                    if hasattr(window, "editor_panel_ui") and window.editor_panel_ui:
                        sel_shapes = [i for i in self.scene.selectedItems() if hasattr(i, "shape_name")]
                        window.editor_panel_ui.set_target_items(sel_shapes)

                # Ensure the editor panel is updated for non-edit mode selections as well
                if not is_edit:
                    window = self.window()
                    if hasattr(window, "editor_panel_ui") and window.editor_panel_ui:
                        sel_shapes = [i for i in self.scene.selectedItems() if hasattr(i, "shape_name")]
                        window.editor_panel_ui.set_target_items(sel_shapes)

            self._rb_visual_rect = QtCore.QRectF()
            self.viewport().update()
            event.accept()
            return

        QtWidgets.QGraphicsView.mouseReleaseEvent(self, event)

    def mouseDoubleClickEvent(self, event):
        is_edit = getattr(self, "is_edit_mode", False)
        item = self.itemAt(event.pos())
        
        if item and hasattr(item, "shape_name") and not is_edit:
            all_shapes = {i.item_id: i for i in self.scene.items() if hasattr(i, "item_id")}
            to_select = set([item])
            
            def get_children(shape):
                for cid in getattr(shape, "child_links", []):
                    child = all_shapes.get(cid)
                    if child and child not in to_select:
                        to_select.add(child)
                        get_children(child)
                        
            get_children(item)
            
            mods = event.modifiers()
            is_shift = bool(mods & QtCore.Qt.ShiftModifier)
            is_ctrl = bool(mods & QtCore.Qt.ControlModifier)
            is_alt = bool(mods & QtCore.Qt.AltModifier)
            
            hier_controls = []
            for s in to_select:
                hier_controls.extend(getattr(s, "controls", []))
                
            if is_shift: mode = "add"
            elif is_ctrl: mode = "deselect"
            elif is_alt: mode = "mirror"
            else: mode = "replace"
            
            self.item_selected.emit(hier_controls, mode)
            event.accept()
            return
        
        super().mouseDoubleClickEvent(event)

    def drawForeground(self, painter, rect):
        if getattr(self, "_rb_active", False) and getattr(self, "_rb_visual_rect", None):
            pen = QtGui.QPen(QtGui.QColor(100, 150, 255, 200), 1, QtCore.Qt.SolidLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor(100, 150, 255, 100)))
            painter.drawRect(self._rb_visual_rect)
            
        # --- NEW: HIERARCHY DYNAMIC LINE ---
        if getattr(self, "_hier_drag_source", None) and getattr(self, "_hier_drag_pos", None):
            mode = getattr(self, "_hier_mode", "add")
            color = QtGui.QColor(100, 255, 100, 200) if mode == "add" else QtGui.QColor(255, 100, 100, 200)
            pen = QtGui.QPen(color, 2, QtCore.Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(self._hier_drag_source.sceneBoundingRect().center(), self._hier_drag_pos)

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu { background: #2b2b2b; color: #dfdfdf; border: 1px solid #555; } QMenu::item:selected { background: #5285a6; }")
        
        item = self.itemAt(event.pos())
        
        # THE BG LOCK FIX FOR CONTEXT MENUS (Moved up so canvas scripts load properly)
        if item and getattr(item, "shape_name", "") == "Image":
            win = self.window()
            if win and getattr(win, "bg_locked", False):
                item = None 

        # POLYGON LOCK OVERRIDE: Force target to be the polygon even if clicking empty space
        exclusive = getattr(self, "_exclusive_poly", None)
        if exclusive:
            item = exclusive
            
        self._custom_scr_acts = {}

        # 1. Gather Scripts (Item or Canvas)
        script_list = item.scripts if item and hasattr(item, "scripts") else getattr(self, "canvas_scripts", [])

        if script_list:
            # Bypass Menu if Action exists
            right_actions = [s for s in script_list if s.get("trigger") == "Right Click (Action)"]
            if right_actions:
                for scr in right_actions:
                    self.execute_custom_script(scr.get("command", ""), scr.get("type", "python"))
                event.accept()
                return 
                
            # Append to Menu
            right_menus = [s for s in script_list if s.get("trigger") == "Right Click (Menu)"]
            if right_menus:
                for scr in right_menus:
                    act = menu.addAction(scr.get("label", "Script"))
                    self._custom_scr_acts[act] = scr
                menu.addSeparator()
        # --------------------------------------------
        
        is_edit = getattr(self, "is_edit_mode", False)
        
        selected_items = [i for i in self.scene.selectedItems() if hasattr(i, "shape_name")]
        targets = selected_items if item in selected_items else ([item] if item and hasattr(item, "shape_name") else [])
        is_edit = getattr(self, "is_edit_mode", False)

        # 1. UNIVERSAL ACTIONS
        action_add_ctrl = action_rep_ctrl = None
        act_add_attr = act_rep_attr = act_clr_attr = None
        act_pose_sel_ctrl = None 
        act_pose_set = act_pose_upd = act_pose_add_attr = act_pose_rem_attr = act_pose_cap = act_pose_load = None

        if targets:
            # Swap menus based on selected shape types
            if all(t.shape_name == "Slider" for t in targets):
                act_add_attr = menu.addAction("➕ Add Attribute")
                act_rep_attr = menu.addAction("🔄 Replace Attribute")
                act_clr_attr = menu.addAction("❌ Clear")
            elif all(t.shape_name == "Pose" for t in targets):
                act_pose_sel_ctrl = menu.addAction("🎯 Select Controls")
                if len(targets) == 1:
                    menu.addSeparator()
                    act_pose_set = menu.addAction("📸 Set Pose (Merge Selection)")
                    act_pose_upd = menu.addAction("🔄 Update Pose (Replace All)")
                    act_pose_add_attr = menu.addAction("➕ Add Selected Attributes")
                    act_pose_rem_attr = menu.addAction("➖ Remove Selected Attributes")
                    menu.addSeparator()
                    act_pose_cap = menu.addAction("🖥️ Capture Image")
                    act_pose_load = menu.addAction("📂 Load Image")
            elif all(t.shape_name == "Checkbox" for t in targets):
                pass # Checkboxes don't use Maya selections in the same way
            else:
                action_add_ctrl = menu.addAction("➕ Add Selection")
                action_rep_ctrl = menu.addAction("🔄 Replace Selection")
            menu.addSeparator()

        # 2. EDIT MODE ACTIONS
        align_actions = {}
        action_edit = action_front = action_back = action_delete = action_load = None
        add_actions = {}
        act_toggle_grid = act_color_grid = act_bg_color = None
        act_poly_edit = act_poly_add = act_poly_rem = act_poly_smth = None
        act_mir_lr = act_mir_ud = act_mir_cp_lr = act_mir_cp_ud = act_mir_canvas = None

        if is_edit:
            if len(selected_items) > 1:
                align_menu = menu.addMenu("Align Selected")
                align_actions["left"] = align_menu.addAction("Align Left")
                align_actions["center_x"] = align_menu.addAction("Align Center X")
                align_actions["right"] = align_menu.addAction("Align Right")
                align_menu.addSeparator()
                align_actions["top"] = align_menu.addAction("Align Top")
                align_actions["center_y"] = align_menu.addAction("Align Center Y")
                align_actions["bottom"] = align_menu.addAction("Align Bottom")
                align_menu.addSeparator()
                align_actions["distribute_x"] = align_menu.addAction("Distribute Horizontally")
                align_actions["distribute_y"] = align_menu.addAction("Distribute Vertically")
                menu.addSeparator()

            if targets:
                # --- NEW POLYGON MENU ---
                if len(targets) == 1 and targets[0].shape_name == "Polygon":
                    poly = targets[0]
                    act_poly_edit = menu.addAction("✏️ Edit Polygon")
                    act_poly_edit.setCheckable(True)
                    act_poly_edit.setChecked(poly.is_editing_points)
                    if poly.is_editing_points:
                        act_poly_add = menu.addAction("➕ Add Point")
                        act_poly_rem = menu.addAction("➖ Remove Point")
                        act_poly_smth = menu.addAction("〰️ Toggle Smooth")
                    menu.addSeparator()

                # --- NEW MIRROR MENU ---
                import os
                from .preferences import PrefManager
                icon_folder = PrefManager().get("path_icons")
                icon_lr = os.path.join(icon_folder, "mirror_lr.svg")
                icon_ud = os.path.join(icon_folder, "mirror_ud.svg")
                
                mir_menu = menu.addMenu("🪞 Mirror Shapes")
                act_mir_lr = mir_menu.addAction(QtGui.QIcon(icon_lr) if os.path.exists(icon_lr) else QtGui.QIcon(), "Mirror Left / Right")
                act_mir_ud = mir_menu.addAction(QtGui.QIcon(icon_ud) if os.path.exists(icon_ud) else QtGui.QIcon(), "Mirror Up / Down")
                mir_menu.addSeparator()
                act_mir_cp_lr = mir_menu.addAction(QtGui.QIcon(icon_lr) if os.path.exists(icon_lr) else QtGui.QIcon(), "Copy && Mirror Left / Right")
                act_mir_cp_ud = mir_menu.addAction(QtGui.QIcon(icon_ud) if os.path.exists(icon_ud) else QtGui.QIcon(), "Copy && Mirror Up / Down")
                mir_menu.addSeparator()
                
                from .preferences import PrefManager
                act_mir_canvas = mir_menu.addAction("Use Canvas Center")
                act_mir_canvas.setCheckable(True)
                act_mir_canvas.setChecked(PrefManager().get("mirror_use_canvas"))
                menu.addSeparator()
                
                action_edit = menu.addAction("Edit Properties")
                action_front = menu.addAction("Bring to Front")
                action_back = menu.addAction("Send to Back")
                menu.addSeparator()
                action_delete = menu.addAction("Delete Selected")
                if len(targets) == 1 and targets[0].shape_name == "Image":
                    action_load = menu.addAction("Change Image")
            else:
                import os 
                add_menu = menu.addMenu("Add Shape")
                
                shape_defs = [
                    ("Rectangle", "rectangle.svg"), 
                    ("Round Rectangle", "round_rectangle.svg"), 
                    ("Circle", "circle.svg"), 
                    ("Polygon", "polygon.svg"), 
                    ("Text", "text.svg"), 
                    ("Slider", "slider.svg"), 
                    ("Pose", "pose.svg"), 
                    ("Checkbox", "checkbox.svg"), 
                    ("Image", None) 
                ]
                
                from .preferences import PrefManager
                icon_folder = PrefManager().get("path_icons")
                
                add_actions = {}
                for shape_name, icon_file in shape_defs:
                    act = None
                    if icon_file:
                        icon_path = os.path.join(icon_folder, icon_file)
                        if os.path.exists(icon_path):
                            act = add_menu.addAction(QtGui.QIcon(icon_path), shape_name)
                    
                    if act is None:
                        act = add_menu.addAction(shape_name)
                        
                    add_actions[act] = shape_name
                
                # GRID MENU
                grid_menu = menu.addMenu("Grid")
                act_toggle_grid = grid_menu.addAction("Toggle Visibility")
                act_toggle_grid.setCheckable(True)
                act_toggle_grid.setChecked(getattr(self, "grid_visible", False))
                
                scale_widget = QtWidgets.QWidget()
                sl_lay = QtWidgets.QHBoxLayout(scale_widget)
                sl_lay.setContentsMargins(4,2,4,2)
                sl_lay.addWidget(QtWidgets.QLabel("Scale:"))
                slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
                slider.setRange(10, 200)
                slider.setValue(getattr(self, "grid_scale", 50))
                spin = QtWidgets.QSpinBox()
                spin.setRange(10, 200)
                spin.setValue(getattr(self, "grid_scale", 50))
                
                slider.valueChanged.connect(spin.setValue)
                spin.valueChanged.connect(slider.setValue)
                slider.valueChanged.connect(lambda v: setattr(self, "grid_scale", v) or self.viewport().update())
                
                sl_lay.addWidget(slider)
                sl_lay.addWidget(spin)
                
                scale_act = QtWidgets.QWidgetAction(menu)
                scale_act.setDefaultWidget(scale_widget)
                grid_menu.addAction(scale_act)
                act_color_grid = grid_menu.addAction("Color...")

                act_bg_color = menu.addAction("🎨 Set Canvas Color")

        # EXECUTION
        action = getattr(menu, "exec", menu.exec_)(event.globalPos())
        if not action: return

        # Custom Script Routing
        if hasattr(self, "_custom_scr_acts") and action in self._custom_scr_acts:
            scr = self._custom_scr_acts[action]
            self.execute_custom_script(scr.get("command", ""), scr.get("type", "python"))
            return

        # Slider Execution Routing
        if action == act_add_attr: self.window().attribute_modified_requested.emit(targets, "add")
        elif action == act_rep_attr: self.window().attribute_modified_requested.emit(targets, "replace")
        elif action == act_clr_attr: self.window().attribute_modified_requested.emit(targets, "clear")
        
        # Pose Execution Routing
        elif action == act_pose_sel_ctrl: self.window().pose_action_requested.emit(targets, "select_controls")
        elif action == act_pose_set: self.window().pose_action_requested.emit(targets, "set_pose")
        elif action == act_pose_upd: self.window().pose_action_requested.emit(targets, "update_pose")
        elif action == act_pose_add_attr: self.window().pose_action_requested.emit(targets, "add_attrs")
        elif action == act_pose_rem_attr: self.window().pose_action_requested.emit(targets, "rem_attrs")
        elif action == act_pose_cap: self.window().pose_action_requested.emit(targets, "capture_image")
        elif action == act_pose_load: self.window().pose_action_requested.emit(targets, "load_image")

        # Standard Execution Routing
        elif action == action_add_ctrl: self.window().controls_modified_requested.emit(targets, "add")
        elif action == action_rep_ctrl: self.window().controls_modified_requested.emit(targets, "replace")

        elif is_edit:
            if action == act_mir_lr: self.window().mirror_requested.emit(targets, "left_right", False)
            elif action == act_mir_ud: self.window().mirror_requested.emit(targets, "up_down", False)
            elif action == act_mir_cp_lr: self.window().mirror_requested.emit(targets, "left_right", True)
            elif action == act_mir_cp_ud: self.window().mirror_requested.emit(targets, "up_down", True)
            elif action == act_mir_canvas: 
                from .preferences import PrefManager
                prefs = PrefManager()
                new_state = not prefs.get("mirror_use_canvas")
                prefs.set("mirror_use_canvas", new_state)
                self._mirror_use_canvas = new_state

            elif action == act_toggle_grid:
                self.grid_visible = not self.grid_visible
                self.viewport().update()
            elif action == act_color_grid:
                col = QtWidgets.QColorDialog.getColor(self.grid_color, self, "Grid Color", QtWidgets.QColorDialog.ShowAlphaChannel)
                if col.isValid():
                    self.grid_color = col
                    self.viewport().update()
            elif action == act_bg_color:
                col = QtWidgets.QColorDialog.getColor(self.background_color, self, "Canvas Background Color", QtWidgets.QColorDialog.ShowAlphaChannel)
                if col.isValid():
                    self.background_color = col
                    self.viewport().update()
            
            # --- POLYGON EXECUTION ---
            elif action == act_poly_edit: 
                target_id = targets[0].item_id
                valid = [i for i in self.scene.items() if hasattr(i, "item_id") and i.item_id == target_id]
                if valid:
                    valid[0].toggle_edit_mode()
            elif action == act_poly_add: 
                targets[0].context_add_point(self.mapToScene(event.pos()))
                self.window().menu_action_requested.emit("push_undo")
            elif action == act_poly_rem: 
                targets[0].context_remove_point(self.mapToScene(event.pos()))
                self.window().menu_action_requested.emit("push_undo")
            elif action == act_poly_smth: 
                targets[0].context_toggle_smooth(self.mapToScene(event.pos()))
                self.window().menu_action_requested.emit("push_undo")
            
            elif action == action_edit: self.edit_shape_properties(targets)
            elif action == action_front: self.change_z_depth(targets, "front")
            elif action == action_back: self.change_z_depth(targets, "back")
            elif action == action_delete:
                for t in targets: self.scene.removeItem(t)
                self._update_editor_ui()
                self.window().menu_action_requested.emit("push_undo")
            elif action == action_load: 
                self.window().image_action_requested.emit(targets, "load_image")
            elif not targets:
                for act, shape_name in add_actions.items():
                    if action == act:
                        new_item = self.add_new_shape(shape_name, self.mapToScene(event.pos()))
                        if shape_name == "Image" and new_item: 
                            self.window().image_action_requested.emit([new_item], "load_image")
                        self.window().menu_action_requested.emit("push_undo")
                        return
            else:
                for key, act in align_actions.items():
                    if action == act:
                        self.alignment_requested.emit(key, selected_items)
                        return

    def change_z_depth(self, items, direction):
        if not items: return
        self.alignment_requested.emit("z_front" if direction == "front" else "z_back", items)

    def add_new_shape(self, shape_type, scene_pos):
        # Calculate the absolute top Z-Index so new shapes spawn over everything
        max_z = 0.0
        for item in self.scene.items():
            if hasattr(item, "shape_name"):
                max_z = max(max_z, float(item.zValue()))
                
        data = {"type": shape_type, "label": "New", "pos": [scene_pos.x(), scene_pos.y()], "width": 60, "height": 30, "z_index": max_z + 1.0}
        if shape_type == "Circle": data["width"] = 50; data["height"] = 50
        elif shape_type == "Image": data["width"] = 200; data["height"] = 200; data["z_index"] = -1000.0 # Force image to bottom
        
        before = set(self.scene.items()); self.build_items_from_data([data]); after = set(self.scene.items())
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
            
            # --- CRITICAL FIX: Safe Cast Helper to prevent JSON null crashes ---
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
                elif "points" in data: # Legacy Fallback
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
                
                # Protect older saves by dynamically filling missing keys
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
            
            # Load Movable state (safely falls back to legacy 'locked' if older file)
            is_movable = data.get("movable_edit", not data.get("locked", False))
            shape_item.movable_edit = bool(is_movable)
            shape_item.locked = not bool(is_movable)
            shape_item.locked_edit = not bool(is_movable)
            shape_item.selectable_pose = bool(data.get("selectable_pose", True))
            
            # Load Screen Mode defaults
            shape_item.placement_mode = str(data.get("placement_mode", "world"))
            shape_item.screen_anchor = str(data.get("screen_anchor", "center"))
            shape_item.screen_offset_px = data.get("screen_offset_px", [0, 0])

            shape_item.command_type = str(data.get("command_type", "python")); shape_item.command_left = str(data.get("command_left", "")); shape_item.command_right = str(data.get("command_right", ""))

            if item_type == "Image" and "image_path" in data: shape_item.image_path = str(data["image_path"])
            
            self.scene.addItem(shape_item)
            self.update_item_flags(shape_item)
            new_items.append(shape_item)
        
        return new_items
    
    # =========================================================================
    # CANVAS STICKY ENGINE (HUD SYSTEM)
    # =========================================================================
    def update_screen_items(self):
        """Forces all 'screen' mode items to snap to their viewport anchors."""
        vp_size = self.viewport().size()
        w, h = vp_size.width(), vp_size.height()

        if not hasattr(self, "scene") or not self.scene: return
        
        for item in self.scene.items():
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
        super().scrollContentsBy(dx, dy)
        # THE FIX: Remove the timer here! Panning must be synchronous to avoid flickering!
        self.update_screen_items()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # (Keep the timer here for resizing only)
        QtCore.QTimer.singleShot(0, self.update_screen_items)

    def wheelEvent(self, event):
        # --- NATIVE ZOOM: Restore the mouse wheel zoom! ---
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.scale(factor, factor)
        self.update_screen_items()
        event.accept()