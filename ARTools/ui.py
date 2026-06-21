# ARTools/ui.py
from maya import cmds
from functools import partial  # <--- CRITICAL IMPORT FOR CYTHON

from PySide6 import QtWidgets, QtGui, QtCore
IS_PYSIDE2 = False

from .picker_shapes import (
    PickerRectangleItem, PickerRoundRectangleItem, PickerCircleItem, 
    PickerPolygonItem, PickerTextItem, PickerSliderItem, 
    PickerPoseItem, PickerCheckboxItem, PickerImageItem,
    PickerHierarchyLayer
)

from . import editor_panel
from .preferences import PrefsWindow

class SubTab(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        name = kwargs.get("name", args[0] if len(args) > 0 else 'Main')
        parent = kwargs.get("parent", args[1] if len(args) > 1 else None)
        QtWidgets.QWidget.__init__(self, parent)
        self.name = name
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = PickerCanvas(self)
        self.main_layout.addWidget(self.canvas)

class CharacterTab(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        name = kwargs.get("name", args[0] if len(args) > 0 else 'Character')
        parent = kwargs.get("parent", None)
        QtWidgets.QWidget.__init__(self, parent)
        self.name = name
        self.ikfk_chains = []
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        
        self.sub_tabs = QtWidgets.QTabWidget(self)
        self.sub_tabs.setMovable(True)
        self.main_layout.addWidget(self.sub_tabs)
        self.sub_tabs.tabBar().setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        
        if hasattr(self, "show_tab_menu"):
            self.sub_tabs.tabBar().customContextMenuRequested.connect(self.show_tab_menu)
            self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self.customContextMenuRequested.connect(self.show_tab_menu)
            
        self.sub_tabs.currentChanged.connect(partial(self._on_subtab_changed))
    
    def add_sub_tab(self, name, *args, **kwargs):
        sub = SubTab(name, self)
        
        # 1. Inherit namespace from the active sub-tab
        current_sub = self.sub_tabs.currentWidget()
        sub.custom_namespace = getattr(current_sub, "custom_namespace", "") if current_sub else ""
        
        # 2. Add Tab cleanly without visual namespace brackets
        self.sub_tabs.addTab(sub, name)
        
        window = self.window()
        
        # THE FIX: We DO NOT connect the context menu here anymore. 
        # mouse_magic.py handles it natively!
        
        if hasattr(window, "selection_requested"): sub.canvas.item_selected.connect(self._route_selection)
        if hasattr(window, "alignment_requested"): sub.canvas.alignment_requested.connect(self._route_alignment)
        if hasattr(window, "item_interacted"): sub.canvas.item_interacted.connect(self._route_interaction)
        if hasattr(window, "slider_moved"): sub.canvas.slider_moved.connect(self._route_slider)

        if window:
            sub.canvas.is_edit_mode = getattr(window, "is_edit_mode", False)
            
        return sub

    def _route_selection(self, lst, mode, *args, **kwargs): 
        if getattr(self, "_route_lock_sel", False): return
        self._route_lock_sel = True
        if self.window(): self.window().selection_requested.emit(lst, mode)
        self._route_lock_sel = False

    def _route_alignment(self, act, lst=None, *args, **kwargs): 
        if getattr(self, "_route_lock_align", False): return
        self._route_lock_align = True
        if self.window(): self.window().alignment_requested.emit(act, lst)
        self._route_lock_align = False

    def _route_interaction(self, item, click, mods, *args, **kwargs): 
        if getattr(self, "_route_lock_int", False): return
        self._route_lock_int = True
        if self.window(): self.window().item_interacted.emit(item, click, mods)
        self._route_lock_int = False

    def _route_slider(self, item, val, *args, **kwargs): 
        if getattr(self, "_route_lock_sli", False): return
        self._route_lock_sli = True
        if self.window(): self.window().slider_moved.emit(item, val)
        self._route_lock_sli = False

    def _on_subtab_changed(self, idx):
        win = self.window()
        if win and win.isVisible():
            # FIX 1: Immediately sync the window title to show the new namespace!
            if hasattr(win, "_trigger_sync_title"):
                from maya import cmds
                cmds.evalDeferred(win._trigger_sync_title)
                
            if hasattr(win, "_trigger_smart_sync") and not getattr(win, "_is_loading", False):
                from maya import cmds
                cmds.evalDeferred(win._trigger_smart_sync)

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

    def __init__(self, *args, **kwargs):
        parent = kwargs.get("parent", args[0] if len(args) > 0 else None)
        if parent is None: parent = get_maya_main_window()
        QtWidgets.QMainWindow.__init__(self, parent)

        self.setWindowTitle("ARTools 1.1.1")
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "icons", "artools.svg")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(__file__), "Icons", "artools.svg")
        
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

        self.prefs_requested.connect(partial(self.show_preferences))
        self.main_tabs.currentChanged.connect(partial(self._on_main_tab_changed))

    # --- SAFE CYTHON SIGNAL HELPERS ---
    def _emit_menu_action(self, action_name, *args):
        self.menu_action_requested.emit(action_name)
    def _trigger_sync_title(self, *args):
        self.menu_action_requested.emit("sync_title")
    def _trigger_smart_sync(self, *args):
        self.menu_action_requested.emit("smart_sync")
    def _emit_prefs(self, *args, **kwargs):
        self.prefs_requested.emit()
    def _close_window(self, _=None):
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
    
    def show_preferences(self, *args, **kwargs):
        if not hasattr(self, "prefs_ui") or self.prefs_ui is None:
            self.prefs_ui = PrefsWindow()                # <--- 0 arguments
            self.prefs_ui.setParent(self)                # <--- Assign parent safely
            self.prefs_ui.setWindowFlags(QtCore.Qt.Tool) # Ensure it floats
        self.prefs_ui.show()
        self.prefs_ui.raise_()
    
    def show_api_help(self, _=None):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("ARTools API & Scripting Guide")
        dialog.resize(850, 750)
        dialog.setWindowFlags(dialog.windowFlags() | QtCore.Qt.WindowMaximizeButtonHint)
        lay = QtWidgets.QVBoxLayout(dialog)
        
        text = QtWidgets.QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("QTextEdit { background-color: #1e1e1e; color: #dfdfdf; font-family: Consolas, monospace; font-size: 13px; border: 1px solid #444; padding: 10px; }")
        
        html = """
        <h1 style='color: #5285a6; margin-bottom: 0px;'>ARTools API Guide</h1>
        <p style='color: #888; margin-top: 0px;'>Use these commands in your <b>Command Presets</b> or <b>Script Editor</b> to create dynamic, interactive UI elements.</p>
        <hr style='border: 1px solid #444;'>
        
        <h3 style='color: #4CAF50;'>1. Getting Started (Always Include This!)</h3>
        <p>At the top of every script, you must import the API:</p>
        <pre style='background: #111; padding: 8px; border-radius: 4px; color: #f1fa8c;'>import ARTools.api as api</pre>
        
        <h3 style='color: #4CAF50;'>2. How to find a Button's ID (Safe Method)</h3>
        <p>Using Names/Labels is risky because they can change. It is safer to use the button's permanent ID. To find an ID:</p>
        <ul>
            <li>Select the button in Edit Mode.</li>
            <li>Open the Script Editor and click <b>Run / Test Script</b> with this code: <br>
            <pre style='background: #111; padding: 8px; display: inline-block; color: #f1fa8c;'>import ARTools.api as api<br>print(api.get_selected_ids())</pre>
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
        <p>Get information about the active sub-tab to run custom Maya commands.</p>
        <pre style='background: #111; padding: 8px; border-radius: 4px; color: #f1fa8c;'>from maya import cmds<br># Get current Sub-Tab namespace (e.g. 'raja_rig')<br>ns = api.get_namespace()<br><br># Get assigned controls for a specific shape<br>ctrls = api.get_controls("YOUR_ID")<br><br># Select ALL controls across the entire current Sub-Tab<br>api.select_all()<br><br># Get ALL assigned controls to run a custom command<br>all_ctrls = api.get_all_character_controls()<br>cmds.setKeyframe(all_ctrls)</pre>

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
    
    def show_release_notes(self, _=None):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Release Notes")
        dialog.resize(550, 450)
        lay = QtWidgets.QVBoxLayout(dialog)
        
        text = QtWidgets.QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("QTextEdit { background-color: #1e1e1e; color: #dfdfdf; font-family: Consolas, monospace; font-size: 13px; border: 1px solid #444; padding: 10px; }")
        
        html = """
        <h2 style='color: #5285a6; margin-bottom: 0px;'>ARTools v1.1.1 (Current Update)</h2>
        <ul style='color: #888; margin-top: 5px;'>
            <li><b>Smart Library Navigation:</b> Replaced the legacy breadcrumb trail with a sleek, space-saving Smart Folder button. Clicking it spawns a fully interactive library tree that smartly highlights your active path while auto-collapsing inactive branches.</li>
            <li><b>Code-Based Icon Engine:</b> Eliminated dependencies on external Maya SVGs by introducing a 100% pure-code Unicode icon engine. Folders now dynamically flood-fill with custom colors and unbreakable, high-resolution icons.</li>
            <li><b>Deep Namespace X-Ray Scanner:</b> The Library now utilizes an aggressive memory structural scan to flawlessly detect active namespaces from the Picker, even when heavily docked or nested inside Maya's UI. Dynamically disables namespace UI options if the Picker is closed.</li>
            <li><b>Self-Cleaning Tag System:</b> Unified tag memory IDs between the Property Panel and Global Filters. Introduced a silent auto-cleanup protocol that instantly sweeps and removes "ghost tags" left behind by deleted OS folders.</li>
            <li><b>AnimBar Memory & Safeties:</b> The AnimBar now persistently remembers your last-used dynamics tool (e.g., Smooth, Tweener) across Maya restarts. Added robust failsafes to prevent Progress Bar crashes when applying animation to empty selections.</li>
            <li><b>Workflow Enhancements:</b> Added interactive Ascending/Descending sorting to the Editor's Layer Tab. Reduced the "F" hotkey viewport focus padding to 2% for incredibly tight and precise camera framing around selections.</li>
        </ul>
        <hr style='border: 1px solid #444;'>
        <h3 style='color: #5285a6;'>ARTools v1.1.0</h3>
        <ul style='color: #888; margin-top: 5px;'>
            <li><b>AnimBar Dynamics Suite:</b> Introduced a complete, stateless curve dynamics engine featuring 7 professional animation tools (Tweener, Neighbor, Push/Pull, Scale Avg, Linearize, Smooth, and an S-Curve Ease In/Out).</li>
            <li><b>Context-Aware Animation Engine:</b> The AnimBar now intelligently targets edits based on Maya's UI focus, seamlessly supporting Graph Editor curves, Time Slider blocks, and active Viewport selections.</li>
            <li><b>Live Viewport & Modifier Drag:</b> Instantly swap tools mid-drag using Global Shortcuts (Shift, Ctrl, Alt). Maya's viewport now evaluates and redraws character poses in real-time without breaking the Undo Queue.</li>
            <li><b>High-Fidelity Snapshots:</b> Pose snapshots now capture at 3x resolution to match exact shape aspect ratios, utilizing a dynamic background scaling loop to retain PNG alphas while strictly keeping file sizes under 200KB.</li>
            <li><b>Canvas Workflow Overhaul:</b> Implemented 'Smart Target Split', allowing layout actions (Mirror, Z-Depth, Delete) to safely apply to multiple grouped shapes simultaneously, while restricting data actions to hovered shapes.</li>
            <li><b>Checkbox Execution Engine:</b> Reprogrammed the Checkbox toggle API to fully support Sub-Tab Namespaces and reliably execute embedded Python/MEL custom scripts.</li>
        </ul>
        <hr style='border: 1px solid #444;'>
        <h3 style='color: #5285a6;'>ARTools v1.0.4</h3>
        <ul style='color: #888; margin-top: 5px;'>
            <li><b>Modular Enterprise Architecture:</b> The Picker, AnimBar, and Library tools are now completely decoupled, operating independently with a seamless Smart Routing system.</li>
            <li><b>Safe Geometry Serialization:</b> Optimized window size and position tracking, fully migrating away from legacy raw-byte outputs to clean JSON parameters across all tools.</li>
            <li><b>Universal License Dashboard:</b> Added dynamic tracking UI for modules, days remaining, and live status checking, fully updated to securely process the new 3-Part Tiered License format.</li>
        </ul>
        <hr style='border: 1px solid #444;'>
        <h3 style='color: #5285a6;'>ARTools v1.0.3</h3>
        <ul style='color: #888; margin-top: 5px;'>
            <li><b>Relative Namespace Engine:</b> Namespaces are now exclusively assigned to Sub-Tabs, enabling multi-rig and multi-namespace workflows to perfectly coexist on a single canvas.</li>
            <li><b>Smart Stripper & Rebuilder:</b> Nested namespaces are dynamically stripped upon assignment and flawlessly rebuilt during selection, fully supporting complex nested rig hierarchies.</li>
            <li><b>Robust Sub-Tab Menus:</b> Upgraded Context Menus with mathematically accurate mouse-projection. "Set Namespace", "Rename", and "Delete" now accurately target Sub-Tabs without main-tab interference.</li>
            <li><b>"Select All" Overhaul:</b> The selection engine now fully integrates with the Smart Rebuilder, completely eliminating missing control errors when using multi-rig canvases.</li>
        </ul>
        <hr style='border: 1px solid #444;'>
        <h3 style='color: #5285a6;'>ARTools v1.0.2</h3>
        <ul style='color: #888;'>
            <li><b>Hierarchy Z-Layer Engine:</b> Hierarchy connection lines now render independently on a dedicated Z-Layer, ensuring they display beautifully above Background Images but safely below interactive buttons.</li>
            <li><b>Smart Sync API for Checkboxes:</b> Checkboxes using custom <i>api.match_ikfk</i> commands now dynamically read rig states via Regex, syncing visual canvas updates without standard Maya attributes.</li>
            <li><b>Custom Command UI Refresh:</b> Custom shape scripts (e.g., right-click to zero-out attributes) can now trigger instant UI refreshes by calling the Smart Sync API.</li>
            <li><b>Background Image Selection Fix:</b> Resolved Qt bounding box interference, allowing seamless click-selection of Background Images and transparent PNGs.</li>
            <li><b>In-App Release Notes:</b> Added this dedicated UI to track version history and updates.</li>
        </ul>
        <hr style='border: 1px solid #444;'>
        <h3 style='color: #5285a6;'>ARTools v1.0.1</h3>
        <ul style='color: #888;'>
            <li>Implemented dynamic visual Shape Picker popup for Checkbox Shape linking.</li>
            <li>Upgraded cross-platform C-Extension compiler setup (Cython) for Mac, Windows, and Linux.</li>
            <li>Fixed Qt event recursion bugs to stabilize compiled context menus.</li>
            <li>Added Bezier tangent breaking via Shift-Drag for Custom Polygons.</li>
        </ul>
        """
        text.setHtml(html)
        lay.addWidget(text)
        
        btn = QtWidgets.QPushButton("Close")
        btn.setStyleSheet("padding: 8px; font-weight: bold; background: #333;")
        btn.clicked.connect(dialog.accept)
        lay.addWidget(btn)
        
        getattr(dialog, "exec", dialog.exec_)()
    
    def show_about(self, _=None):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("About ARTools")
        dialog.resize(550, 400)
        lay = QtWidgets.QVBoxLayout(dialog)
        
        text = QtWidgets.QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("QTextEdit { background-color: #1e1e1e; color: #dfdfdf; font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; border: 1px solid #444; padding: 15px; }")
        
        html = """
        <h2 style='color: #5285a6; margin-bottom: 5px;'>ARTools v1.1.1</h2>
        <p style='color: #888; font-size: 12px; margin-top: 0px;'>Professional Animation Picker & Workflow Suite</p>
        
        <h3 style='color: #5285a6; border-bottom: 1px solid #444; padding-bottom: 5px;'>Creator & Developer</h3>
        <p><b>Ashwin V Rathod</b><br>
        <i>Animation Technical Lead & Supervisor</i><br>
        With extensive experience directing and supervising high-end animated series across the industry, Ashwin developed ARTools to solve the most complex workflow bottlenecks faced by professional animators in production environments.</p>
        
        <h3 style='color: #5285a6; border-bottom: 1px solid #444; padding-bottom: 5px;'>Tool Workflow & Architecture</h3>
        <p>ARTools is a premium, highly customizable animation interface designed specifically for Autodesk Maya. It goes beyond standard selection tools by offering an advanced <b>Smart Sync API</b> that bi-directionally communicates with complex rig attributes. Featuring custom bezier-driven polygons, independent hierarchy rendering layers. ARTools is engineered to significantly accelerate the daily animation pipeline.</p>
        """
        text.setHtml(html)
        lay.addWidget(text)
        
        btn = QtWidgets.QPushButton("Close")
        btn.setStyleSheet("padding: 8px; font-weight: bold; background: #333;")
        btn.clicked.connect(dialog.accept)
        lay.addWidget(btn)
        
        getattr(dialog, "exec", dialog.exec_)()

    def show_eula(self, _=None):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("End User License Agreement (EULA)")
        dialog.resize(600, 500)
        lay = QtWidgets.QVBoxLayout(dialog)
        
        text = QtWidgets.QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("QTextEdit { background-color: #1e1e1e; color: #b0b0b0; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #444; padding: 15px; }")
        
        html = """
        <h2 style='color: #dfdfdf; text-align: center;'>END USER LICENSE AGREEMENT</h2>
        <p><b>IMPORTANT - READ CAREFULLY:</b> This End User License Agreement ("EULA") is a legal agreement between you (either an individual or a single entity) and Ashwin V Rathod for the ARTools software product.</p>
        
        <p><b>1. GRANT OF LICENSE</b><br>
        ARTools is licensed, not sold. Upon activation, you are granted a non-exclusive, non-transferable right to use the software on a single workstation corresponding to the registered System ID.</p>
        
        <p><b>2. RESTRICTIONS & TAMPERING</b><br>
        You may not reverse engineer, decompile, or disassemble the software. The software utilizes advanced cryptographic temporal tracking. Any attempt to artificially alter, roll back, or modify the system clock or license files to bypass expiration dates is strictly prohibited and will result in the immediate and permanent revocation of your license.</p>
        
        <p><b>3. COPYRIGHT & OWNERSHIP</b><br>
        All title and copyrights in and to the software, including but not limited to any images, algorithms, and UI designs incorporated into the software, are owned by Ashwin V Rathod.</p>
        
        <p><b>4. DISCLAIMER OF WARRANTY</b><br>
        The software is provided "AS IS" without warranty of any kind. The entire risk arising out of the use or performance of the software remains with you. In no event shall the author be liable for any damages whatsoever arising out of the use of or inability to use this software.</p>
        """
        text.setHtml(html)
        lay.addWidget(text)
        
        btn = QtWidgets.QPushButton("I Agree - Close")
        btn.setStyleSheet("padding: 8px; font-weight: bold; background: #333;")
        btn.clicked.connect(dialog.accept)
        lay.addWidget(btn)
        
        getattr(dialog, "exec", dialog.exec_)()

    def show_license_status(self, *args):
        from . import security
        security.show_license_status_ui(self)

    def _init_canvas_area(self):
        self.main_tabs = QtWidgets.QTabWidget()
        self.main_tabs.setMovable(True)
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
        self.btn_edit.clicked.connect(partial(self._on_edit_toggled))
        
        self.btn_bg_lock = QtWidgets.QToolButton()
        self.btn_bg_lock.setText("🖼️")
        self.btn_bg_lock.setToolTip("Lock BG Images")
        self.btn_bg_lock.setCheckable(True)
        self.btn_bg_lock.clicked.connect(partial(self._on_bg_lock_toggled))
        
        self.btn_hier = QtWidgets.QToolButton()
        self.btn_hier.setText("🔗")
        self.btn_hier.setToolTip("Toggle Hierarchy Visibility")
        self.btn_hier.setCheckable(True)
        self.btn_hier.clicked.connect(partial(self._on_hier_toggled))
        
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
        
        from . import security
        has_animbar = security.enforce_license("animbar")
        has_library = security.enforce_license("library")

        anim_menu = self.main_menu.addMenu("🎬 Anim Tools")
        
        # --- ANIMBAR MENU ITEMS ---
        act_ab = anim_menu.addAction("Floating Anim Bar")
        act_ab.triggered.connect(partial(self._emit_menu_action, "open_anim_bar"))
        act_ab_shelf = anim_menu.addAction("  ↳ Add AnimBar to Shelf")
        act_ab_shelf.triggered.connect(partial(self._emit_menu_action, "shelf_animbar"))
        
        if not has_animbar:
            act_ab.setEnabled(False)
            act_ab_shelf.setEnabled(False)
            act_ab.setToolTip("Requires AnimBar License. Mail to ashwinrathod@zohomail.com to upgrade!")
            act_ab_shelf.setToolTip("Requires AnimBar License.")
        
        anim_menu.addSeparator()
        
        # --- LIBRARY MENU ITEMS ---
        act_lib = anim_menu.addAction("Animation Library")
        act_lib.triggered.connect(partial(self._emit_menu_action, "open_library"))
        act_lib_shelf = anim_menu.addAction("  ↳ Add Library to Shelf")
        act_lib_shelf.triggered.connect(partial(self._emit_menu_action, "shelf_library"))
        
        if not has_library:
            act_lib.setEnabled(False)
            act_lib_shelf.setEnabled(False)
            act_lib.setToolTip("Requires Library License. Mail to ashwinrathod@zohomail.com to upgrade!")
            act_lib_shelf.setToolTip("Requires Library License.")
        
        self.main_menu.addSeparator()

        self.main_menu.addAction("⚙️ Preferences").triggered.connect(partial(self._emit_prefs))
        self.main_menu.addSeparator()
        
        self.main_menu.addAction("📖 Help / API Guide").triggered.connect(partial(self.show_api_help))
        self.main_menu.addAction("📝 Release Notes").triggered.connect(partial(self.show_release_notes))
        self.main_menu.addSeparator()

        self.main_menu.addAction("📜 EULA").triggered.connect(partial(self.show_eula))
        self.main_menu.addAction("🔑 License Status").triggered.connect(partial(self.show_license_status))
        self.main_menu.addSeparator()

        self.main_menu.addAction(getattr(self.window(), "app_icon", QtGui.QIcon()), "About ARTools").triggered.connect(partial(self.show_about))
        self.main_menu.addSeparator()
        
        self.main_menu.addAction("❌ Close").triggered.connect(partial(self._close_window))
        self.main_menu.addAction("💀 Kill ARTools").triggered.connect(partial(self._emit_menu_action, "kill"))
        
        self.btn_menu.setMenu(self.main_menu)
        
        self.corner_layout.addWidget(self.btn_edit)
        self.corner_layout.addWidget(self.btn_bg_lock)
        self.corner_layout.addWidget(self.btn_hier)
        self.corner_layout.addWidget(self.btn_menu)
        
        self.main_tabs.setCornerWidget(self.corner_widget, QtCore.Qt.TopRightCorner)

    def _on_edit_toggled(self, *args, **kwargs):
        checked = self.btn_edit.isChecked()
        self.btn_edit.setText("Edit" if checked else "Pose")
        self.is_edit_mode = checked
        
        # Hard clear Maya Selection Highlights when entering Edit Mode
        if checked:
            for i in range(self.main_tabs.count()):
                char_tab = self.main_tabs.widget(i)
                for j in range(char_tab.sub_tabs.count()):
                    canvas = char_tab.sub_tabs.widget(j).canvas
                    for item in canvas.scene().items():
                        if hasattr(item, "maya_selection_state"):
                            item.maya_selection_state = "none" # Wipe Maya blue highlight
                    canvas.scene().clearSelection() # Wipe Qt selection
                    canvas.viewport().update()

        self.edit_mode_toggled.emit(checked)
    
    def _on_bg_lock_toggled(self, *args, **kwargs):
        checked = self.btn_bg_lock.isChecked()
        self.btn_bg_lock.setStyleSheet("color: #4CAF50;" if checked else "")
        self.bg_locked = checked
        self.bg_lock_toggled.emit(checked)

    def _on_hier_toggled(self, *args, **kwargs):
        checked = self.btn_hier.isChecked()
        self.btn_hier.setStyleSheet("color: #4CAF50;" if checked else "")
        self.hier_toggled.emit(checked)
        for i in range(self.main_tabs.count()):
            char_tab = self.main_tabs.widget(i)
            for j in range(char_tab.sub_tabs.count()):
                char_tab.sub_tabs.widget(j).canvas.viewport().update()

    def _on_main_tab_changed(self, idx):
        cmds.evalDeferred(self._trigger_sync_title)
        if not getattr(self, "_is_loading", False):
            self.namespace_changed.emit("")

    def add_character_tab(self, name, *args, **kwargs):
        tab = CharacterTab(name=name, parent=self)
        self.main_tabs.addTab(tab, name)
        return tab

    def show_editor_panel(self, items):
        if not hasattr(self, "editor_panel_ui") or self.editor_panel_ui is None:
            self.editor_panel_ui = editor_panel.EditorPanel(self)  # <-- Added prefix
            self.editor_panel_ui.setWindowFlags(QtCore.Qt.Tool)
            
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

    def __init__(self, *args, **kwargs):
        parent = kwargs.get("parent", args[0] if len(args) > 0 else None)
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
            print(f"ARTools Script Execution Error: {e}")
    
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

            if item_type == "Image" and "image_path" in data:
                shape_item.image_path = str(data["image_path"])
            
            # --- Add to scene FIRST so it can access the window's image directory! ---
            self.scene().addItem(shape_item)
            
            if item_type == "Image" and getattr(shape_item, "image_path", ""):
                try:
                    if hasattr(shape_item, "load_image"): shape_item.load_image(shape_item.image_path)
                    elif hasattr(shape_item, "update_image"): shape_item.update_image()
                except Exception: pass
            
            self.update_item_flags(shape_item)
            new_items.append(shape_item)
        
        if not any(getattr(i, "is_hierarchy_layer", False) for i in self.scene().items()):
            self.hier_layer = PickerHierarchyLayer()
            self.scene().addItem(self.hier_layer)
        
        return new_items
    
    # FIX: Added *args to properly absorb the C++ arguments
    def update_screen_items(self, *args):
        if getattr(self, "_updating_screen", False): return
        self._updating_screen = True
        
        vp_size = self.viewport().size()
        w, h = vp_size.width(), vp_size.height()

        if self.scene() is None: 
            self._updating_screen = False
            return
        
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
                
        self._updating_screen = False

    def scrollContentsBy(self, dx, dy):
        if getattr(self, "_scroll_lock", False): return
        self._scroll_lock = True
        
        super().scrollContentsBy(dx, dy)
        self.update_screen_items()
        
        self._scroll_lock = False

    def resizeEvent(self, event):
        QtWidgets.QGraphicsView.resizeEvent(self, event)
        cmds.evalDeferred(self.update_screen_items)