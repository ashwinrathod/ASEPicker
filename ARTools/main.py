# ARTools/main.py
from functools import partial

from PySide6 import QtWidgets, QtGui, QtCore

import tempfile
import shutil
import os
from maya import cmds
from . import core
from . import ui
from . import layout_io
from . import picker_shapes
from . import mouse_magic

# INJECT THE UNCOMPILED MOUSE EVENTS BEFORE BOOTING UI!
mouse_magic.inject_events(ui, picker_shapes)

# Temporary directory for images before saving
TEMP_ART_DIR = os.path.join(tempfile.gettempdir(), "ARTools_Cache")
if not os.path.exists(TEMP_ART_DIR): os.makedirs(TEMP_ART_DIR)

# Global variable to hold our app so Maya's garbage collector doesn't delete it
_app_instance = None

class PickerController:
    def __init__(self):
        self.core = core.PickerCore()
        
        # INIT PREFERENCES
        from .preferences import PrefManager
        self.prefs = PrefManager()
        
        self.window = ui.PickerWindow()
        
        # --- LICENSE ENFORCEMENT FRONT DOOR ---
        from . import security
        
        # [SECURITY LAYER 1] Block uncompiled text file replacements
        if hasattr(security, '__file__') and security.__file__.endswith(('.py', '.pyc', '.pyw')):
            import maya.cmds as mc
            mc.warning("[ARTools] Security module tampering detected. Boot aborted.")
            self.window.close()
            return

        # Fetch the LayoutManager from the security module
        self.io = security.enforce_license(self.window)
        
        # [SECURITY LAYER 2] The Compiled-to-Compiled Handshake
        expected_stamp = "JAY_SHREE_KRISHNA_1986"
        if not self.io or getattr(self.io, "_ase_secure_stamp", "") != expected_stamp:
            import maya.cmds as mc
            mc.warning("[ARTools] Invalid memory allocation. Boot aborted.")
            self.window.close()
            return
        # --------------------------------------
        
        self.undo_stacks = {}

        # --- APPLY WINDOW PREFS SAFELY (The Office PC Fix) ---
        w = self.prefs.get("win_w")
        h = self.prefs.get("win_h")
        
        # 1. Fallback for missing/empty sizes! Prevents 0x0 invisibility!
        if w is None or h is None or w < 100 or h < 100:
            self.window.resize(1000, 700)
        else:
            self.window.resize(w, h)
            
        # 2. Phantom Monitor Fix (Auto-Teleport Off-Screen Windows)
        wx = self.prefs.get("win_x")
        wy = self.prefs.get("win_y")
        
        try:
            screens = QtWidgets.QApplication.screens()
            primary_geo = screens[0].availableGeometry() if screens else QtCore.QRect(0, 0, 1920, 1080)
            
            if wx is not None and wy is not None and wx != -9999 and wy != -9999:
                self.window.move(wx, wy)
                
                # Check if the saved position is trapped off-screen
                win_geo = self.window.frameGeometry()
                is_on_screen = any(screen.availableGeometry().intersects(win_geo) for screen in screens)
                    
                if not is_on_screen:
                    self.window.move(primary_geo.center() - self.window.rect().center())
            else:
                # First time booting on a new PC: Auto-Center perfectly!
                self.window.move(primary_geo.center() - self.window.rect().center())
        except Exception:
            pass # Failsafe
        # -----------------------------------------------------
        
        self.window.btn_edit.setChecked(self.prefs.get("startup_mode") == "Edit")
        self.window.btn_bg_lock.setChecked(self.prefs.get("startup_bg_lock"))
        self.window.btn_hier.setChecked(self.prefs.get("startup_hier"))
        
        # WIRING ALL BRIDGES (Protected with partial to bypass PySide2 signature bugs)
        self.window.selection_requested.connect(partial(self.on_item_selected))
        self.window.alignment_requested.connect(partial(self.align_ui_shapes))
        self.window.item_interacted.connect(partial(self.on_item_interacted))
        self.window.slider_moved.connect(partial(self.on_slider_moved))
        self.window.controls_modified_requested.connect(partial(self.handle_control_modification))
        self.window.attribute_modified_requested.connect(partial(self.handle_attribute_modification))
        self.window.pose_drag_started.connect(partial(self.on_pose_drag_started))
        self.window.pose_dragged.connect(partial(self.on_pose_dragged))
        self.window.pose_drag_ended.connect(partial(self.on_pose_drag_ended))
        self.window.pose_action_requested.connect(partial(self.handle_pose_action))
        self.window.edit_mode_toggled.connect(partial(self.on_edit_mode_toggled))
        self.window.bg_lock_toggled.connect(partial(self.on_bg_lock_toggled))
        self.window.namespace_refresh_requested.connect(partial(self.on_namespace_refresh))
        self.window.namespace_changed.connect(partial(self.on_namespace_changed))
        self.window.menu_action_requested.connect(partial(self.on_menu_action))
        self.window.window_closed.connect(partial(self.cleanup))
        self.window.copy_requested.connect(partial(self.on_copy_requested))
        self.window.paste_requested.connect(partial(self.on_paste_requested))
        self.window.checkbox_action_requested.connect(partial(self.handle_checkbox_action))
        self.window.checkbox_toggled.connect(partial(self.on_checkbox_toggled))
        self.window.image_action_requested.connect(partial(self.handle_image_action))
        self.window.mirror_requested.connect(partial(self.handle_mirror_action))

        # Safely kill the old job before creating a new one to prevent memory leaks!
        if getattr(self, 'sel_job', None):
            try: cmds.scriptJob(kill=self.sel_job, force=True)
            except Exception: pass
            
        self.sel_job = cmds.scriptJob(event=["SelectionChanged", self.on_maya_selection_changed], protected=True)

        self.on_edit_mode_toggled(self.prefs.get("startup_mode") == "Edit")
        self.on_bg_lock_toggled(self.prefs.get("startup_bg_lock"))
        self.window.btn_hier.setChecked(self.prefs.get("startup_hier"))
        
        # Auto-Load Saved Picker
        loaded_any = False
        if cmds.objExists("ARToolsStorage"):
            saved_chars = cmds.listAttr("ARToolsStorage", userDefined=True) or []
            for char_name in saved_chars:
                scene_data = self.io.load_from_scene(char_name)
                if scene_data:
                    source_path = scene_data.get("source_file_path", "")
                    print(f"ARTools: Successfully loaded '{char_name}' from scene.")
                    self.load_character_layout(scene_data, file_path=source_path)
                    loaded_any = True

        if not loaded_any:
            print("ARTools: No saved layout found. Starting empty.")
            
        self.update_window_title()

    def on_edit_mode_toggled(self, is_enabled):
        for char_idx in range(self.window.main_tabs.count()):
            char_tab = self.window.main_tabs.widget(char_idx)
            for sub_idx in range(char_tab.sub_tabs.count()):
                canvas = char_tab.sub_tabs.widget(sub_idx).canvas
                canvas.is_edit_mode = is_enabled
                for canvas_item in canvas.scene().items():
                    if hasattr(canvas_item, "item_id"):
                        canvas_item.setVisible(True)

                if hasattr(canvas, "apply_layer_visibility"):
                    canvas.apply_layer_visibility()
                
                canvas.update_all_flags()
                canvas.viewport().update()
                
        if is_enabled:
            self.push_undo_snapshot()

    def on_bg_lock_toggled(self, is_enabled):
        for char_idx in range(self.window.main_tabs.count()):
            char_tab = self.window.main_tabs.widget(char_idx)
            for sub_idx in range(char_tab.sub_tabs.count()):
                char_tab.sub_tabs.widget(sub_idx).canvas.update_all_flags()

    def on_namespace_refresh(self):
        ns_list = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
        ignore_list = ["UI", "shared"]
        self.window.available_namespaces = [n for n in ns_list if n not in ignore_list]

    def on_namespace_changed(self, ns):
        self.update_window_title()
        self.get_image_dir()
        if hasattr(self, "smart_sync_all"):
            # Use Maya's native deferred evaluation instead of Qt Timers
            cmds.evalDeferred(partial(self.smart_sync_all))

    def update_window_title(self):
        title = "ARTools 1.4.0"
        
        # Check multiple possible keys just to be safe!
        show_name = self.prefs.get("io_show_name") or self.prefs.get("show_char_name")
        show_ns = self.prefs.get("io_show_ns") or self.prefs.get("show_namespace_title")
        
        if show_name:
            char_tab = self.window.main_tabs.currentWidget()
            if char_tab: 
                title += f" - {char_tab.name}"
        
        if show_ns:
            try:
                from . import api
                ns = api.get_namespace()
                if ns: 
                    title += f" ({ns})"
            except Exception: 
                pass
        
        self.window.setWindowTitle(title)
    
    def _clean_unused_images(self):
        """Deletes images from the disk folder that are no longer assigned to any shape."""
        import os
        img_dir = self.get_image_dir()
        if not img_dir or not os.path.exists(img_dir): return
        
        # Scan current layout for all active image names
        used_images = set()
        data = self.get_current_layout_data()
        for tab in data.get("subtabs", []):
            for item in tab.get("items", []):
                path = item.get("image_path")
                if path:
                    used_images.add(os.path.basename(path))
        
        # Remove files from folder that aren't in our 'used' set
        for filename in os.listdir(img_dir):
            if filename not in used_images:
                try:
                    os.remove(os.path.join(img_dir, filename))
                except Exception as e:
                    print(f"Cleanup Error: {e}")
    
    def on_menu_action(self, action):
        import os

        if action == "sync_title":
            if hasattr(self, "update_window_title"):
                self.update_window_title()
            return
            
        if action == "open":
            start_dir = self.prefs.get("path_picker") if hasattr(self, "prefs") and self.prefs.get("path_picker") else ""
            
            filepath, _ = QtWidgets.QFileDialog.getOpenFileName(self.window, "Open Picker Layout", start_dir, "ARTools JSON (*.json)")
            if filepath:
                data = self.io.load_from_file(filepath)
                if data:
                    self.load_character_layout(data, file_path=filepath)
                    self.get_image_dir() # Instantly update image engine for new tab
                    print(f"ARTools: Successfully loaded {filepath}")
        
        elif action == "save":
            char_tab = self.window.main_tabs.currentWidget()
            if not char_tab: return
            
            filepath = getattr(char_tab, "file_path", "")
            if not filepath:
                self.on_menu_action("save_as")
                return
                
            final_img_dir = self.get_image_dir()
            self.migrate_temp_images(final_img_dir)
            data = self.get_current_layout_data()
            self.io.save_to_file(filepath, data)
            self._clean_unused_images()
            print(f"ARTools: Saved to {filepath}")
        
        elif action == "save_as":
            char_tab = self.window.main_tabs.currentWidget()
            if not char_tab: return
            
            filepath, _ = QtWidgets.QFileDialog.getSaveFileName(self.window, "Save Picker Layout", "", "ARTools JSON (*.json)")
            if filepath:
                if not filepath.endswith(".json"): filepath += ".json"
                
                # Grab the old image directory BEFORE changing the path!
                old_img_dir = self.get_image_dir()
                
                # Bind the new path strictly to the active tab
                char_tab.file_path = filepath
                
                final_img_dir = self.get_image_dir()
                
                # 1. Migrate any brand new unsaved temp images
                self.migrate_temp_images(final_img_dir)
                
                # 2. Copy all previously saved images from the old folder to the new folder!
                if old_img_dir and os.path.exists(old_img_dir) and old_img_dir != final_img_dir:
                    import shutil
                    if not os.path.exists(final_img_dir): os.makedirs(final_img_dir)
                    for filename in os.listdir(old_img_dir):
                        src = os.path.join(old_img_dir, filename)
                        dst = os.path.join(final_img_dir, filename)
                        if os.path.isfile(src) and not os.path.exists(dst):
                            try: shutil.copy(src, dst)
                            except Exception: pass
                
                data = self.get_current_layout_data()
                self.io.save_to_file(filepath, data)
                print(f"ARTools: Saved to {filepath}")
        
        elif action == "save_scene":
            saved_names = []
            original_idx = self.window.main_tabs.currentIndex()
            for i in range(self.window.main_tabs.count()):
                self.window.main_tabs.setCurrentIndex(i)
                data = self.get_current_layout_data()
                char_tab = self.window.main_tabs.widget(i)
                filepath = getattr(char_tab, "file_path", "")
                
                if data:
                    char_name = data.get("name", f"Character_{i}")
                    if filepath:
                        data["source_file_path"] = filepath
                    self.io.save_to_scene(char_name, data)
                    saved_names.append(char_name)
                    
            self.window.main_tabs.setCurrentIndex(original_idx)
            print(f"ARTools: Saved tabs directly into the Maya Scene: {', '.join(saved_names)}")
        
        elif action == "kill":
            import maya.cmds as cmds
            print("💀 ARTools: Process and all connected tools Terminated.")
            
            # 1. Kill the background scriptJob before deleting the UI!
            if getattr(self, "sel_job", None):
                try: cmds.scriptJob(kill=self.sel_job, force=True)
                except Exception: pass
                self.sel_job = None
                
            # 2. Safely destroy the widgets
            if hasattr(self.window, "editor_panel_ui") and self.window.editor_panel_ui:
                try: self.window.editor_panel_ui.close(); self.window.editor_panel_ui.deleteLater()
                except Exception: pass
            
            if hasattr(self.window, "prefs_ui") and self.window.prefs_ui:
                try: self.window.prefs_ui.close(); self.window.prefs_ui.deleteLater()
                except Exception: pass
            
            if hasattr(self, "window") and self.window is not None:
                try: self.window.close(); self.window.deleteLater()
                except Exception: pass
            
            for widget in QtWidgets.QApplication.allWidgets():
                if type(widget).__name__ in ["AnimBar", "PickerWindow", "RibbonBrowser", "ModernSaver", "PropertySatellite"]:
                    try:
                        widget.close()
                        widget.deleteLater()
                    except Exception: pass
            
            import ARTools
            if hasattr(ARTools.main, "_app_instance"):
                ARTools.main._app_instance = None
        
        elif action == "smart_sync":
            self.smart_sync_all()

        elif action == "sync_title":
            self.update_window_title()

        elif action == "open_anim_bar":
            import ARTools
            ARTools.launch("animbar")

        elif action == "open_library":
            import ARTools
            ARTools.launch("library")
    
        elif action == "shelf_animbar":
            cmd = "import ARTools\nARTools.launch('animbar')"
            self._create_tool_shelf_button("AnimBar", "animbar.svg", cmd)
        
        elif action == "shelf_library":
            cmd = "import ARTools\nARTools.launch('library')"
            self._create_tool_shelf_button("Library", "library.svg", cmd)
        
        elif action == "close":
            if hasattr(self.window, "editor_panel_ui") and self.window.editor_panel_ui:
                self.window.editor_panel_ui.hide()
            if hasattr(self.window, "prefs_ui") and self.window.prefs_ui:
                self.window.prefs_ui.hide()

        elif action == "undo": self.perform_undo()
        elif action == "redo": self.perform_redo()
        elif action == "push_undo": self.push_undo_snapshot()
    
    def cleanup(self):
        """Executes Prefs tasks on Close."""
        # 1. Store Window Resizing (If allowed)
        if self.prefs.get("win_remember_size") and not self.prefs.get("win_lock_size"):
            self.prefs.set("win_w", self.window.width())
            self.prefs.set("win_h", self.window.height())
            
        # 2. ALWAYS Save Main Window Placement
        self.prefs.set("win_x", self.window.x())
        self.prefs.set("win_y", self.window.y())
        
        # 3. ALWAYS Save Editor Placement & Size (if it was opened)
        if hasattr(self.window, "editor_panel_ui") and self.window.editor_panel_ui:
            self.prefs.set("editor_w", self.window.editor_panel_ui.width())
            self.prefs.set("editor_h", self.window.editor_panel_ui.height())
            self.prefs.set("editor_x", self.window.editor_panel_ui.x())
            self.prefs.set("editor_y", self.window.editor_panel_ui.y())
            
        # 4. Auto Save to Scene!
        if self.prefs.get("io_auto_save"):
            self.on_menu_action("save_scene")
        
        # Clean Temp Images
        if os.path.exists(TEMP_ART_DIR):
            try: shutil.rmtree(TEMP_ART_DIR)
            except Exception: pass
        
        if getattr(self, 'sel_job', None):
            try: cmds.scriptJob(kill=self.sel_job, force=True)
            except Exception: pass
            self.sel_job = None

    def _sync_ui_to_selection(self, sel_list):
        """High-Speed Native Qt Highlighting Engine"""
        if not self.window.isVisible(): return
        
        sel_set = set(sel_list)
        
        char_tab = self.window.main_tabs.currentWidget()
        if not char_tab: return
        sub_tab = char_tab.sub_tabs.currentWidget()
        if not sub_tab: return
        
        canvas = sub_tab.canvas
        
        if getattr(canvas, "is_edit_mode", False):
            return 
            
        current_ns = getattr(sub_tab, "custom_namespace", "")
        ns_clean = current_ns.strip()
        if ns_clean and ns_clean.endswith(":"): ns_clean = ns_clean[:-1]
        ns_prefix = f"{ns_clean}:" if ns_clean else ""
        
        scene = canvas.scene()
        scene.blockSignals(True)
        
        for item in scene.items():
            shape_name = getattr(item, "shape_name", "none")
            if shape_name in ["Image", "Text", "none", "HierarchyLayer", "Line"]:
                continue
                
            ctrls = getattr(item, "controls", None)
            
            if not ctrls:
                new_state = "none"
            else:
                ctrls_tuple = tuple(ctrls)
                ctrls_hash = hash(ctrls_tuple)
                
                # --- INTELLIGENT CACHING ENGINE ---
                if not hasattr(item, "_fast_sel_cache") or getattr(item, "_fast_ns_cache", None) != current_ns or getattr(item, "_fast_ctrl_hash", None) != ctrls_hash:
                    ctrl_set = set(str(c).strip() for c in ctrls if str(c).strip())
                    if ns_prefix:
                        prefixed = {f"{ns_prefix}{c}" for c in ctrl_set}
                        stripped = {f"{ns_prefix}{c.split(':')[-1]}" for c in ctrl_set if ":" in c}
                        item._fast_sel_cache = ctrl_set.union(prefixed, stripped)
                    else:
                        item._fast_sel_cache = ctrl_set
                        
                    item._fast_ns_cache = current_ns
                    item._fast_ctrl_count = len(ctrl_set)
                    item._fast_ctrl_hash = ctrls_hash
                
                # --- O(1) Instant C-Level Intersection ---
                matched_count = len(item._fast_sel_cache.intersection(sel_set))
                
                if matched_count == 0:
                    new_state = "none"
                elif matched_count >= item._fast_ctrl_count:
                    new_state = "full"
                else:
                    new_state = "partial"
            
            if getattr(item, "maya_selection_state", "none") != new_state:
                item.maya_selection_state = new_state
                item.update()
            
            is_full = (new_state == "full")
            if item.isSelected() != is_full:
                item.setSelected(is_full)
                
        scene.blockSignals(False)
        canvas.viewport().update()

    def on_maya_selection_changed(self):
        """Triggered by Maya's native selection events (e.g., clicking in Viewport)."""
        if getattr(self, "_ignore_selection_job", False): return
        sel_list = cmds.ls(selection=True) or []
        self._sync_ui_to_selection(sel_list)

    def on_item_selected(self, controls_list, select_mode):
        from . import api
        current_ns = api.get_namespace()
        
        if select_mode == "mirror":
            controls_list = self.core.get_mirrored_controls(controls_list)
            actual_mode = "replace"
        else:
            actual_mode = select_mode
            
        # 1. Calculate selection natively in Python
        new_sel = self.core.smart_select(controls_list, current_ns, actual_mode)
        if new_sel is None: new_sel = []
        
        # 2. Update UI internal states instantly
        self._ignore_selection_job = True
        self._sync_ui_to_selection(new_sel)
        
        # 3. Force Qt to draw the blue borders immediately!
        QtWidgets.QApplication.processEvents()
        
        # 4. Now let Maya do the heavy lifting
        current_sel = cmds.ls(selection=True) or []
        if set(current_sel) != set(new_sel):
            if new_sel: cmds.select(new_sel, replace=True)
            else: cmds.select(clear=True)
            
        self._ignore_selection_job = False
    
        # 5. Return focus to Maya viewport after mouse click finishes so W/E/R hotkeys work!
        if not self.window.is_edit_mode:
            QtCore.QTimer.singleShot(10, self._focus_maya_viewport)

    def _focus_maya_viewport(self):
        self.window.clearFocus()
        panel = cmds.getPanel(withFocus=True)
        if not panel or "modelPanel" not in panel:
            panels = cmds.getPanel(visiblePanels=True)
            if panels:
                for p in panels:
                    if "modelPanel" in p:
                        panel = p
                        break
            else:
                panel = "MayaWindow"
        if not panel:
            panel = "MayaWindow"
        cmds.setFocus(panel)
    
    def handle_control_modification(self, shapes, action):
        """Secure Logic: Processes Maya selections and updates shape data without exposing logic to the UI."""
        from . import api
        maya_sel = cmds.ls(selection=True) or []
        active_ns = api.get_namespace()

        maya_sel_short = [self.core.strip_namespace_for_save(str(x), active_ns) for x in maya_sel]
        
        for item in shapes:
            current_ctrls = getattr(item, "controls", [])
            if current_ctrls is None: current_ctrls = []
            
            if action == "add":
                new_ctrls = current_ctrls.copy()
                for c in maya_sel_short:
                    if c not in new_ctrls: 
                        new_ctrls.append(c)
            elif action == "remove":
                new_ctrls = [c for c in current_ctrls if c not in maya_sel_short]
            elif action == "replace":
                new_ctrls = maya_sel_short
            elif action == "clear":
                new_ctrls = []
            else:
                continue
                
            # Apply math and force UI update
            item.controls = new_ctrls
            item.update()
        
        # Tell the Editor Panel to refresh the ListBox visually
        if hasattr(self.window, "editor_panel_ui") and self.window.editor_panel_ui:
            self.window.editor_panel_ui.set_target_items(shapes)
        self.push_undo_snapshot()
    
    def align_ui_shapes(self, mode, items, *args, **kwargs):
        if getattr(self, "_align_execution_lock", False): return
        self._align_execution_lock = True
        
        if len(items) < 1: 
            self._align_execution_lock = False
            return
        
        # 1. Handle Z-depth natively in the Core (Strict 1-to-N Logic)
        if mode in ["z_front", "z_back", "z_forward", "z_backward"]:
            scene = items[0].scene()
            if scene:
                # Gather all valid shapes
                all_shapes = [itm for itm in scene.items() if hasattr(itm, "shape_name")]
                # Sort by current Z to establish the stack
                all_shapes.sort(key=lambda x: x.zValue())
                
                stack = list(all_shapes)
                
                if mode == "z_front":
                    for item in items:
                        if item in stack:
                            stack.remove(item)
                            stack.append(item)
                elif mode == "z_back":
                    # Process in reverse so multiple selections keep their relative order
                    for item in reversed(items):
                        if item in stack:
                            stack.remove(item)
                            stack.insert(0, item)
                elif mode == "z_forward":
                    # Move up the stack (towards the end of the list)
                    items_sorted = sorted(items, key=lambda x: stack.index(x), reverse=True)
                    for item in items_sorted:
                        idx = stack.index(item)
                        if idx < len(stack) - 1:
                            stack[idx], stack[idx+1] = stack[idx+1], stack[idx]
                elif mode == "z_backward":
                    # Move down the stack (towards the beginning of the list)
                    items_sorted = sorted(items, key=lambda x: stack.index(x))
                    for item in items_sorted:
                        idx = stack.index(item)
                        if idx > 0:
                            stack[idx], stack[idx-1] = stack[idx-1], stack[idx]
                            
                # Re-assign strict Z-values (Locking Images to Absolute Background)
                images = [i for i in stack if i.shape_name == "Image"]
                normals = [i for i in stack if i.shape_name != "Image"]
                
                for idx, item in enumerate(images):
                    item.setZValue(float(-1000 + idx))
                for idx, item in enumerate(normals):
                    item.setZValue(float(idx + 1))
            self.push_undo_snapshot()
            self._align_execution_lock = False
            return

        if len(items) < 2: 
            self._align_execution_lock = False
            return
        
        # 2. Extract pure math data for X/Y Alignment
        shape_data = []
        for i, item in enumerate(items):
            w = getattr(item, "width", 60.0)
            h = getattr(item, "height", 30.0)
            shape_data.append({
                "id": i, "x": item.pos().x(), "y": item.pos().y(), "w": w, "h": h
            })
        
        # 3. Let the secure core calculate the new positions
        updated_data = self.core.calculate_alignment(mode, shape_data)
        
        # 4. Apply back to the canvas
        for data in updated_data:
            item = items[data["id"]]
            item.setPos(data["x"], data["y"])

        self.push_undo_snapshot()
        self._align_execution_lock = False
    
    def get_current_layout_data(self):
        char_tab = self.window.main_tabs.currentWidget()
        if not char_tab: return None
        
        layout_data = {
            "name": self.window.main_tabs.tabText(self.window.main_tabs.currentIndex()),
            "ikfk_chains": getattr(char_tab, "ikfk_chains", []),
            "subtabs": []
        }
        
        for i in range(char_tab.sub_tabs.count()):
            sub_tab = char_tab.sub_tabs.widget(i)
            sub_data = {
                "name": char_tab.sub_tabs.tabText(i), 
                "custom_namespace": getattr(sub_tab, "custom_namespace", ""),
                "bg_color": sub_tab.canvas.background_color.name(),
                "items": [],
                "layer_data": getattr(sub_tab.canvas, "layer_data", []),
                "canvas_scripts": getattr(sub_tab.canvas, "canvas_scripts", [])
            }

            # 1. Gather all valid shapes and sort by current Z-Depth (bottom to top)
            valid_items = [itm for itm in sub_tab.canvas.scene().items() if hasattr(itm, "shape_name")]
            valid_items.sort(key=lambda x: x.zValue())

            # Split to ensure Images are strictly saved as background layers
            images = [i for i in valid_items if i.shape_name == "Image"]
            normals = [i for i in valid_items if i.shape_name != "Image"]

            for z_count, item in enumerate(images):
                item_dict = self.serialize_item(item)
                item_dict["z_index"] = float(-1000 + z_count)
                sub_data["items"].append(item_dict)

            for z_count, item in enumerate(normals):
                item_dict = self.serialize_item(item)
                item_dict["z_index"] = float(z_count + 1)
                sub_data["items"].append(item_dict)
                
            layout_data["subtabs"].append(sub_data)

        return layout_data

    def serialize_item(self, item):
        """Helper to convert a shape object into a pure data dictionary."""
        item_dict = {
            "id": str(getattr(item, "item_id", "")),
            "type": str(item.shape_name),
            "label": str(getattr(item, "label", "")),
            "controls": getattr(item, "controls", []),
            "pos": [float(item.pos().x()), float(item.pos().y())],
            "width": float(getattr(item, "width", 60.0)),
            "height": float(getattr(item, "height", 30.0)),
            "rotation": float(item.rotation()),
            "z_index": float(item.zValue()),
            
            "parent_links": getattr(item, "parent_links", []),
            "child_links": getattr(item, "child_links", []),
            "scripts": getattr(item, "scripts", []),
            
            "movable_edit": bool(getattr(item, "movable_edit", True)),
            "locked": not bool(getattr(item, "movable_edit", True)),
            "locked_edit": not bool(getattr(item, "movable_edit", True)),
            "selectable_pose": bool(getattr(item, "selectable_pose", True)),
            "placement_mode": str(getattr(item, "placement_mode", "world")),
            "screen_anchor": str(getattr(item, "screen_anchor", "center")),
            "screen_offset_px": list(getattr(item, "screen_offset_px", [0, 0])),
            
            "font_size": int(getattr(item, "font_point_size", 10)),
            "font_bold": bool(getattr(item, "font_bold", False)),
            "font_italic": bool(getattr(item, "font_italic", False)),
            "text_align_h": str(getattr(item, "text_align_h", "center")),
            "text_align_v": str(getattr(item, "text_align_v", "center")),
            
            "command_type": str(getattr(item, "command_type", "python")),
            "command_left": str(getattr(item, "command_left", "")),
            "command_right": str(getattr(item, "command_right", ""))
        }

        bg = getattr(item, "bg", {})
        item_dict["bg_normal"] = str(bg.get("normal", "#3c6e71"))
        item_dict["bg_hover"] = str(bg.get("hover", "#4d8c90"))
        item_dict["bg_press"] = str(bg.get("press", "#2a4d4f"))

        ed = getattr(item, "edge_color", {})
        item_dict["edge_normal"] = str(ed.get("normal", "#111111"))
        item_dict["edge_hover"] = str(ed.get("hover", "#ffffff"))
        item_dict["edge_press"] = str(ed.get("press", "#000000"))

        tx = getattr(item, "text_color", {})
        item_dict["text_normal"] = str(tx.get("normal", "#ffffff"))
        item_dict["text_hover"] = str(tx.get("hover", "#ffffff"))
        item_dict["text_press"] = str(tx.get("press", "#cccccc"))

        item_dict["edge_visible"] = bool(getattr(item, "edge_visible", True))
        eth = getattr(item, "edge_thickness", {"normal": 1.5, "hover": 2.0, "press": 1.5})
        if not isinstance(eth, dict): eth = {"normal": eth, "hover": eth, "press": eth}
        item_dict["edge_thick_n"] = float(eth.get("normal", 1.5))
        item_dict["edge_thick_h"] = float(eth.get("hover", 2.0))
        item_dict["edge_thick_p"] = float(eth.get("press", 1.5))

        if item.shape_name == "Pose":
            import os
            item_dict["pose_data"] = getattr(item, "pose_data", {})
            img = str(getattr(item, "image_path", ""))
            item_dict["image_path"] = os.path.basename(img) if img else ""
            item_dict["inside_text"] = bool(getattr(item, "inside_text", False))
            item_dict["pose_shape"] = str(getattr(item, "pose_shape", "Rectangle"))
            item_dict["pose_scale_mode"] = str(getattr(item, "pose_scale_mode", "Fit"))
            item_dict["pose_padding"] = float(getattr(item, "pose_padding", 0.0))
            item_dict["pose_roundness"] = float(getattr(item, "pose_roundness", 8.0))
        
        elif item.shape_name == "Text":
            item_dict["text_orientation"] = str(getattr(item, "text_orientation", "Horizontal"))
            item_dict["text_v_gap"] = float(getattr(item, "text_v_gap", 0.0))
        
        elif item.shape_name == "Slider":
            item_dict["attribute"] = str(getattr(item, "attribute", ""))
            item_dict["inside_text"] = bool(getattr(item, "inside_text", False))
            item_dict["min_value"] = float(getattr(item, "min_value", 0.0))
            item_dict["max_value"] = float(getattr(item, "max_value", 1.0))
            item_dict["value"] = float(getattr(item, "value", 0.0))
            item_dict["handle_scale"] = float(getattr(item, "handle_scale", 1.0))
            
            hc = getattr(item, "handle_color", "#bfbfbf")
            if isinstance(hc, QtGui.QColor): hc = hc.name(QtGui.QColor.HexArgb)
            item_dict["handle_color"] = str(hc)
        
        elif item.shape_name == "Dropdown":
            item_dict["attribute"] = str(getattr(item, "attribute", ""))
            item_dict["inside_text"] = bool(getattr(item, "inside_text", True))
            item_dict["dd_shape"] = str(getattr(item, "dd_shape", "Round Rectangle"))
            item_dict["dd_roundness"] = float(getattr(item, "dd_roundness", 6.0))
            item_dict["dyn_text_color"] = str(getattr(item, "dyn_text_color", "#ffffff"))
            item_dict["dyn_font_size"] = float(getattr(item, "dyn_font_size", 11.0))
            item_dict["dyn_font_bold"] = bool(getattr(item, "dyn_font_bold", True))
            item_dict["dyn_font_italic"] = bool(getattr(item, "dyn_font_italic", False))
            item_dict["dyn_align_h"] = str(getattr(item, "dyn_align_h", "Center"))
        
        elif item.shape_name == "Checkbox":
            item_dict["is_checked"] = bool(getattr(item, "is_checked", False))
            item_dict["show_mark"] = bool(getattr(item, "show_mark", True))
            item_dict["inside_text"] = bool(getattr(item, "inside_text", False))
            item_dict["cb_shape"] = str(getattr(item, "cb_shape", "Rectangle"))
            item_dict["cb_roundness"] = float(getattr(item, "cb_roundness", 8.0))
            
            mc = getattr(item, "mark_color", "#ffffff")
            if isinstance(mc, QtGui.QColor): mc = mc.name(QtGui.QColor.HexArgb)
            item_dict["mark_color"] = str(mc)
            item_dict["cb_data"] = getattr(item, "cb_data", {})
        
        elif item.shape_name == "Image":
            import os
            img = str(getattr(item, "image_path", ""))
            item_dict["image_path"] = os.path.basename(img) if img else ""
            item_dict["image_opacity"] = float(getattr(item, "image_opacity", 1.0))
            item_dict["image_scale_mode"] = str(getattr(item, "image_scale_mode", "Fit"))
            item_dict["image_padding"] = float(getattr(item, "image_padding", 0.0))
            item_dict["image_alignment"] = str(getattr(item, "image_alignment", "Center"))
            item_dict["image_mask_shape"] = str(getattr(item, "image_mask_shape", "Rectangle"))
            item_dict["image_roundness"] = float(getattr(item, "image_roundness", 8.0))
        
        elif item.shape_name == "Line":
            item_dict["line_style"] = str(getattr(item, "line_style", "Solid"))
            item_dict["line_orient"] = str(getattr(item, "line_orient", "Horizontal"))
            item_dict["line_start_cap"] = str(getattr(item, "line_start_cap", "None"))
            item_dict["line_end_cap"] = str(getattr(item, "line_end_cap", "None"))
            item_dict["line_cap_scale"] = float(getattr(item, "line_cap_scale", 1.0))
            item_dict["line_wave_count"] = int(getattr(item, "line_wave_count", 5))
        
        if item.shape_name == "Polygon" and hasattr(item, "path_points"):
            path_data = []
            for pt in item.path_points:
                path_data.append({
                    "p": [float(pt["p"].x()), float(pt["p"].y())],
                    "in": [float(pt["in"].x()), float(pt["in"].y())],
                    "out": [float(pt["out"].x()), float(pt["out"].y())],
                    "s": bool(pt["s"])
                })
            item_dict["path_data"] = path_data
        
        elif item.shape_name == "Round Rectangle":
            item_dict["rad_tl"] = float(getattr(item, "rad_tl", 4.0))
            item_dict["rad_tr"] = float(getattr(item, "rad_tr", 4.0))
            item_dict["rad_bl"] = float(getattr(item, "rad_bl", 4.0))
            item_dict["rad_br"] = float(getattr(item, "rad_br", 4.0))

        return item_dict

    def on_copy_requested(self, items):
        """Securely serializes shapes and pushes them to the system clipboard."""
        import json
        data = [self.serialize_item(item) for item in items]
        QtWidgets.QApplication.clipboard().setText(json.dumps(data))
        print(f"ARTools: Copied {len(items)} shapes.")

    def on_paste_requested(self, canvas):
        """Reads clipboard, pastes at exact original position, and selects them."""
        import json
        import uuid
        try:
            clipboard_text = QtWidgets.QApplication.clipboard().text()
            if not clipboard_text: return
            
            data = json.loads(clipboard_text)
            if isinstance(data, list) and len(data) > 0 and "type" in data[0]:
                
                # --- FIX: Generate new UUIDs for pasted shapes to prevent duplicate ID crashes! ---
                id_map = {}
                for d in data:
                    old_id = d.get("id", "")
                    new_id = str(uuid.uuid4())
                    d["id"] = new_id
                    id_map[old_id] = new_id
                    
                for d in data:
                    # Remap hierarchy links so copied groups stay linked together
                    d["parent_links"] = [id_map[p] for p in d.get("parent_links", []) if p in id_map]
                    d["child_links"] = [id_map[c] for c in d.get("child_links", []) if c in id_map]
                    
                    # Remap Checkbox target IDs so copied checkboxes stay linked to copied shapes
                    if d.get("type") == "Checkbox" and "cb_data" in d:
                        for state in ["ON", "OFF"]:
                            if state in d["cb_data"]:
                                new_shapes = []
                                for s_str in d["cb_data"][state].get("shapes", []):
                                    parts = s_str.split("::")
                                    if len(parts) == 2 and parts[0] in id_map:
                                        new_shapes.append(f"{id_map[parts[0]]}::{parts[1]}")
                                    else:
                                        new_shapes.append(s_str)
                                d["cb_data"][state]["shapes"] = new_shapes
                # ----------------------------------------------------------------------------------
                
                # Clear existing selection before pasting
                canvas.scene().clearSelection()
                
                # Build items
                new_items = canvas.build_items_from_data(data)
                
                # Immediately select pasted items and push them to the very top!
                if new_items:
                    max_z = 0.0
                    for scene_item in canvas.scene().items():
                        if hasattr(scene_item, "shape_name") and scene_item not in new_items:
                            max_z = max(max_z, float(scene_item.zValue()))
                            
                    for item in new_items:
                        item.setSelected(True)
                        if item.shape_name == "Image":
                            item.setZValue(-1000.0) # Lock pasted images to background
                        else:
                            max_z += 1.0
                            item.setZValue(max_z) # Push pasted shapes to absolute top
                            
                    canvas._update_editor_ui()
                
                canvas.update_all_flags()
                print(f"ARTools: Pasted {len(data)} shapes.")
        except Exception as e:
            pass # Clipboard data was not valid ARTools JSON
    
        self.push_undo_snapshot()
    
    def load_character_layout(self, layout_dict, *args, **kwargs):
        self.window._is_loading = True
        char_name = layout_dict.get("name", "Unknown")
        char_tab = self.window.add_character_tab(char_name)
        char_tab.ikfk_chains = layout_dict.get("ikfk_chains", [])
        char_tab.file_path = kwargs.get("file_path", "")
        self.get_image_dir()

        for sub_data in layout_dict.get("subtabs", []):
            sub_name = sub_data.get("name", "Main")
            sub_tab = char_tab.add_sub_tab(sub_name)

            # --- Restore the Sub-Tab Namespace ---
            ns = sub_data.get("custom_namespace", "")
            sub_tab.custom_namespace = ns

            # Restore Canvas Background Color if saved
            if "bg_color" in sub_data:
                sub_tab.canvas.background_color = QtGui.QColor(sub_data["bg_color"])
                
            # Restore Layers
            if "layer_data" in sub_data:
                sub_tab.canvas.layer_data = sub_data.get("layer_data", [])
            
            # Restore Canvas Scripts
            if "canvas_scripts" in sub_data:
                sub_tab.canvas.canvas_scripts = sub_data.get("canvas_scripts", [])
                
            sub_tab.canvas.build_items_from_data(sub_data.get("items", []))
            
            # Apply loaded layer visibilities immediately
            if hasattr(sub_tab.canvas, "apply_layer_visibility"):
                sub_tab.canvas.apply_layer_visibility()

        # 1. Force new tabs to sync with Edit Mode state
        self.on_edit_mode_toggled(self.window.is_edit_mode)
        
        # 2. Grab the lock preference
        lock_state = self.prefs.get("startup_bg_lock")
        
        # 3. Visually update the UI button safely
        if hasattr(self.window, "btn_bg_lock"):
            self.window.btn_bg_lock.blockSignals(True)
            self.window.btn_bg_lock.setChecked(lock_state)
            self.window.btn_bg_lock.blockSignals(False)
        
        # 4. Trigger the standard backend logic
        if hasattr(self, "on_bg_lock_toggled"):
            self.on_bg_lock_toggled(lock_state)
        
        # Explicitly iterate ALL tabs and force the lock directly onto the shapes!
        if hasattr(self.window, "main_tabs"):
            self.window.bg_locked = lock_state # Ensure global variable is strictly set
            
            for i in range(self.window.main_tabs.count()):
                tab = self.window.main_tabs.widget(i)
                if hasattr(tab, "canvas"):
                    # Loop through all shapes in this specific canvas
                    for item in tab.canvas.scene().items():
                        if getattr(item, "shape_name", "") in ["Image", "Line"]:
                            # Physically remove the ability to select the image if locked!
                            item.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, not lock_state)
                            if lock_state: 
                                item.setSelected(False)
                    
                    # Force the Canvas Graphics Engine to physically redraw the screen!
                    tab.canvas.scene().update()
                    tab.canvas.viewport().update()
        
        # 5. Sync Titlebar
        if hasattr(self, "update_window_title"):
            self.update_window_title()
            
        # THE FIX: Force the Sticky Engine to snap all HUD elements to the corners!
        if hasattr(self.window, "main_tabs"):
            for i in range(self.window.main_tabs.count()):
                tab = self.window.main_tabs.widget(i)
                if hasattr(tab, "canvas") and hasattr(tab.canvas, "update_screen_items"):
                    tab.canvas.update_screen_items()
                    
        # --- THE SMART MIRROR AUTO-SYNC ---
        self.window._is_loading = False
        self.smart_sync_all()
        self.push_undo_snapshot()

    def on_item_interacted(self, item, click_type, modifiers):
        if getattr(item, "shape_name", "") == "Pose":
            return

        if getattr(item, "shape_name", "") == "Dropdown" and click_type == "left":
            self._handle_dropdown_click(item)
            return
        
        cmd_type = getattr(item, "command_type", "python").lower()
        if cmd_type == "menu":
            menu_data = getattr(item, f"menu_data_{click_type}", [])
            if not menu_data: menu_data = getattr(item, "menu_data", [])
            if menu_data: self.show_custom_menu(menu_data, item)
            return

        cmd_string = getattr(item, f"command_{click_type}", "")
        if cmd_string:
            if cmd_type == "python":
                try: exec(cmd_string, {"cmds": cmds})
                except Exception as e: print(f"ARTools Python Error: {e}")
            elif cmd_type == "mel":
                import maya.mel as mel
                try: mel.eval(cmd_string)
                except Exception as e: print(f"ARTools MEL Error: {e}")

    def show_custom_menu(self, menu_data, item=None):
        from ARTools.preferences import Prefs
        menu = Prefs.create_styled_menu(self.window)
        
        from . import api
        current_ns = api.get_namespace()
        
        actions = {}
        for data in menu_data:
            if data.get("is_separator"):
                menu.addSeparator()
            else:
                act = menu.addAction(data.get("label", "Item"))
                font = act.font()
                if data.get("is_bold"): font.setBold(True)
                act.setFont(font)
                
                if data.get("is_checkable"):
                    act.setCheckable(True)
                    linked_attr = data.get("linked_attr", "").strip()
                    is_checked = False
                    read_success = False
                    plug_cache = ""
                    
                    if linked_attr:
                        try:
                            import maya.cmds as cmds
                            node_attr = ""
                            if item and getattr(item, "controls", []):
                                resolved = self.core.resolve_control_names(item.controls, current_ns)
                                if resolved:
                                    clean_attr = linked_attr.split(".")[-1] if "." in linked_attr else linked_attr
                                    node_attr = f"{resolved[0]}.{clean_attr}"
                            else:
                                if current_ns and ":" not in linked_attr:
                                    if "." in linked_attr:
                                        parts = linked_attr.split(".", 1)
                                        node_attr = f"{current_ns}:{parts[0]}.{parts[1]}"
                                    else:
                                        node_attr = f"{current_ns}:{linked_attr}"
                                else:
                                    node_attr = linked_attr
                                    
                            if node_attr and cmds.objExists(node_attr):
                                is_checked = bool(cmds.getAttr(node_attr))
                                read_success = True
                                plug_cache = node_attr
                        except: pass
                        
                    if not read_success:
                        state_cache = getattr(item, "_menu_check_states", {}) if item else {}
                        is_checked = state_cache.get(data.get("label"), False)
                        
                    act.setChecked(is_checked)
                    data["_resolved_plug"] = plug_cache
                
                actions[act] = data
        
        # --- Defer execution to protect Canvas mouse loop! ---
        def _execute_custom():
            try:
                # Force the Canvas to drop the mouse lock before the menu opens
                if item:
                    canvas = item.scene().views()[0]
                    if getattr(canvas, "_pressed_item", None) == item:
                        canvas._pressed_item = None
                    item._visual_state = "normal"
                    item.update()
            except: pass
            
            action = getattr(menu, "exec", menu.exec_)(QtGui.QCursor.pos())
            if action and action in actions:
                data = actions[action]
                
                is_checked = False
                if data.get("is_checkable"):
                    is_checked = action.isChecked()
                    if item:
                        if not hasattr(item, "_menu_check_states"): item._menu_check_states = {}
                        item._menu_check_states[data.get("label")] = is_checked
                        
                    plug = data.get("_resolved_plug", "")
                    if plug:
                        try:
                            import maya.cmds as cmds
                            cmds.undoInfo(openChunk=True, chunkName="ARTools_MenuToggle")
                            autokey = cmds.autoKeyframe(q=True, state=True)
                            key_count = cmds.keyframe(plug, q=True, keyframeCount=True)
                            is_animated = (key_count is not None and key_count > 0)
                            if autokey: cmds.autoKeyframe(state=False)
                            cmds.setAttr(plug, is_checked)
                            if autokey:
                                if is_animated: cmds.setKeyframe(plug)
                                cmds.autoKeyframe(state=True)
                            cmds.undoInfo(closeChunk=True)
                        except: pass
                
                from . import api
                api._ACTIVE_MENU_STATE = is_checked
                
                script = data.get("command", "")
                if script:
                    try: exec(script, {"cmds": cmds, "MENU_CHECKED": is_checked, "api": api})
                    except Exception as e: print(f"Menu Script Error: {e}")
        
        QtCore.QTimer.singleShot(10, _execute_custom)

    def _handle_dropdown_click(self, item):
        from . import api
        attr_string = getattr(item, "attribute", "")
        if not attr_string: return
        
        current_ns = api.get_namespace()
        target_attr = attr_string.split(",")[0].strip()
        
        # 1. Resolve Target exactly like the sync engine
        node_attr = ""
        resolved_plugs = []
        if item.controls:
            resolved = self.core.resolve_control_names(item.controls, current_ns)
            for r in resolved:
                clean_attr = target_attr.split(".")[-1] if "." in target_attr else target_attr
                resolved_plugs.append(f"{r}.{clean_attr}")
            if resolved_plugs:
                node_attr = resolved_plugs[0]
        else:
            if current_ns and ":" not in target_attr:
                if "." in target_attr:
                    parts = target_attr.split(".", 1)
                    node_attr = f"{current_ns}:{parts[0]}.{parts[1]}"
                else:
                    node_attr = f"{current_ns}:{target_attr}"
            else:
                node_attr = target_attr
            resolved_plugs.append(node_attr)

        # 2. Strict Cython-Safe Validation
        if not node_attr or not cmds.objExists(node_attr):
            return
            
        node, attr = node_attr.split(".", 1)
        if not cmds.attributeQuery(attr, node=node, exists=True):
            return
            
        enum_strings = cmds.attributeQuery(attr, node=node, listEnum=True)
        if not enum_strings or not enum_strings[0]:
            return # Safety abort: Attribute is not an Enum!
            
        enum_list = enum_strings[0].split(":")
        current_val = int(cmds.getAttr(node_attr))
        
        # 3. Build the Beautiful QMenu
        from ARTools.preferences import Prefs
        menu = Prefs.create_styled_menu(self.window)

        actions = {}
        for idx, e_name in enumerate(enum_list):
            # Visually highlight the currently active costume!
            display_name = f"► {e_name}" if idx == current_val else f"  {e_name}"
            act = menu.addAction(display_name)
            if idx == current_val:
                font = act.font()
                font.setBold(True)
                act.setFont(font)
            actions[act] = idx
        
        # --- 3: Wrap execution in QTimer to prevent Mouse Loop Blocking! ---
        def _execute_menu():
            # Artificially clear the pressed state so the canvas doesn't freeze
            try:
                canvas = item.scene().views()[0]
                if getattr(canvas, "_pressed_item", None) == item:
                    canvas._pressed_item = None
            except: pass
            
            item._visual_state = "normal"
            item.update()
            
            # Wait for user selection
            action = getattr(menu, "exec", menu.exec_)(QtGui.QCursor.pos())
            if action and action in actions:
                new_val = actions[action]
                
                # Buttery Smooth Execution
                cmds.undoInfo(openChunk=True, chunkName="ARTools_DropdownSet")
                cmds.scriptEditorInfo(e=True, suppressWarnings=True, suppressInfo=True, suppressErrors=True, suppressResults=True)
                
                autokey = cmds.autoKeyframe(q=True, state=True)
                if autokey:
                    cmds.autoKeyframe(state=False)
                
                for plug in resolved_plugs:
                    if cmds.objExists(plug):
                        key_count = cmds.keyframe(plug, q=True, keyframeCount=True)
                        is_animated = (key_count is not None and key_count > 0)
                        cmds.setAttr(plug, new_val)
                        if autokey and is_animated:
                            cmds.setKeyframe(plug)
                
                if autokey:
                    cmds.autoKeyframe(state=True)
                
                cmds.undoInfo(closeChunk=True)
                cmds.scriptEditorInfo(e=True, suppressWarnings=False, suppressInfo=False, suppressErrors=False, suppressResults=False)
                
                if hasattr(item, "scripts"):
                    try:
                        canvas = item.scene().views()[0]
                        for scr in item.scripts:
                            if scr.get("trigger") == "On Value Change":
                                canvas.execute_custom_script(scr.get("command", ""), scr.get("type", "python"))
                    except: pass
                
                cmds.refresh(cv=True, f=True)
                self.smart_sync_all() 
        
        QtCore.QTimer.singleShot(10, _execute_menu)
    
    def handle_attribute_modification(self, shapes, action):
        """Securely reads Maya Channel Box or prompts user to assign full attributes to Sliders."""
        if action == "clear":
            for item in shapes:
                if getattr(item, "shape_name", "") == "Slider":
                    item.attribute = ""
                    item.update()
        else:
            # 1. Magically steal the Selected Object + Selected Attribute from the Maya Channel Box
            attrs = []
            try:
                from . import api
                active_ns = api.get_namespace()
                objs = cmds.ls(selection=True) or []
                cb_attrs = cmds.channelBox('mainChannelBox', q=True, selectedMainAttributes=True) or []
                if objs and cb_attrs:
                    for obj in objs:
                        short_obj = self.core.strip_namespace_for_save(obj, active_ns)
                        for attr in cb_attrs:
                            attrs.append(f"{short_obj}.{attr}")
            except: pass
            
            # 2. Manual fallback prompt
            if not attrs:
                text, ok = QtWidgets.QInputDialog.getText(self.window, "Assign Attribute", "Enter Attribute Name(s) (comma separated):\n(e.g., pCube1.rx, pSphere1.ty)")
                if ok and text.strip(): attrs = [a.strip() for a in text.split(",") if a.strip()]
                else: return 
                    
            # 3. Apply to the sliders & dropdowns
            for item in shapes:
                if getattr(item, "shape_name", "") not in ["Slider", "Dropdown"]: continue
                
                current_attr = getattr(item, "attribute", "")
                current_list = [a.strip() for a in current_attr.split(",") if a.strip()]
                
                if action == "add":
                    for a in attrs:
                        if a not in current_list: current_list.append(a)
                    item.attribute = ", ".join(current_list)
                elif action == "replace":
                    item.attribute = ", ".join(attrs)
                    
                item.update()
                
        # Instantly update Editor UI
        if hasattr(self.window, "editor_panel_ui") and self.window.editor_panel_ui:
            self.window.editor_panel_ui.set_target_items(shapes)
        self.push_undo_snapshot()
    
    def on_slider_moved(self, item, value):
        # --- THE SMART DEBOUNCE ENGINE ---
        if not hasattr(self, "_slider_timer"):
            self._slider_timer = QtCore.QTimer()
            self._slider_timer.setSingleShot(True)
            self._slider_timer.timeout.connect(self._on_slider_drag_ended)
            
        if not self._slider_timer.isActive():
            self._slider_drag_item = item
            
            cmds.scriptEditorInfo(e=True, suppressWarnings=True, suppressInfo=True, suppressErrors=True, suppressResults=True)
            
            self._slider_autokey = cmds.autoKeyframe(q=True, state=True)
            if self._slider_autokey:
                cmds.autoKeyframe(state=False)
            
            cmds.undoInfo(openChunk=True, chunkName="ARTools_SliderDrag")
            
        self._slider_timer.start(150)

        from . import api
        attr_string = getattr(item, "attribute", "")
        
        if attr_string:
            current_ns = api.get_namespace()
            
            # 2. INTELLIGENT CACHING
            if not hasattr(item, "_fast_plugs_cache") or getattr(item, "_fast_ns_cache", None) != current_ns or getattr(item, "_fast_attr_cache", None) != attr_string:
                controls = getattr(item, "controls", [])
                attr_list = [a.strip() for a in attr_string.split(",") if a.strip()]
                plugs = []
                
                if controls:
                    resolved = self.core.resolve_control_names(controls, current_ns)
                    for ctrl in resolved:
                        for attr in attr_list:
                            clean_attr = attr.split(".")[-1] if "." in attr else attr
                            plugs.append(f"{ctrl}.{clean_attr}")
                else:
                    for attr in attr_list:
                        if current_ns and ":" not in attr:
                            if "." in attr:
                                parts = attr.split(".", 1)
                                plugs.append(f"{current_ns}:{parts[0]}.{parts[1]}")
                            else:
                                plugs.append(f"{current_ns}:{attr}")
                        else:
                            plugs.append(attr)
                            
                item._fast_plugs_cache = plugs
                item._fast_ns_cache = current_ns
                item._fast_attr_cache = attr_string

            # 3. LIGHTNING FAST EXECUTION (Safely checked!)
            for plug in item._fast_plugs_cache:
                if cmds.objExists(plug):
                    cmds.setAttr(plug, value)
                
            cmds.refresh(cv=True, f=True)

    def _on_slider_drag_ended(self):
        if getattr(self, "_slider_autokey", False):
            cmds.autoKeyframe(state=True)
            if hasattr(self, "_slider_drag_item") and hasattr(self._slider_drag_item, "_fast_plugs_cache"):
                for plug in self._slider_drag_item._fast_plugs_cache:
                    if cmds.objExists(plug):
                        if cmds.keyframe(plug, q=True, keyframeCount=True) > 0:
                            cmds.setKeyframe(plug)
        
        cmds.undoInfo(closeChunk=True)
        cmds.scriptEditorInfo(e=True, suppressWarnings=False, suppressInfo=False, suppressErrors=False, suppressResults=False)
    
    def show(self):
        self.window.show()

    def smart_sync_all(self):
        """The Smart Mirror Engine: Reads Maya attributes to magically update the Picker UI."""
        active_main = self.window.main_tabs.currentWidget()
        active_sub = active_main.sub_tabs.currentWidget() if active_main and hasattr(active_main, "sub_tabs") else None
        
        for char_idx in range(self.window.main_tabs.count()):
            char_tab = self.window.main_tabs.widget(char_idx)
            
            for sub_idx in range(char_tab.sub_tabs.count()):
                sub_tab = char_tab.sub_tabs.widget(sub_idx)
                canvas = sub_tab.canvas
                current_ns = getattr(sub_tab, "custom_namespace", "")
                
                # We collect visibility updates so they can be processed safely at the end
                shapes_to_show = set()
                shapes_to_hide = set()
                
                for item in canvas.scene().items():
                    if not hasattr(item, "shape_name"): continue
                    
                    # 1. Sync Sliders
                    if item.shape_name == "Slider":
                        attr_string = getattr(item, "attribute", "")
                        if not attr_string: continue
                        
                        attr_list = [a.strip() for a in attr_string.split(",") if a.strip()]
                        if not attr_list: continue
                        
                        target_attr = attr_list[0] # Just read the first one to sync the visual UI
                        ctrls = getattr(item, "controls", [])
                        read_success = False
                        val = 0.0
                        
                        try:
                            if ctrls:
                                resolved = self.core.resolve_control_names(ctrls, current_ns)
                                if resolved:
                                    clean_attr = target_attr.split(".")[-1] if "." in target_attr else target_attr
                                    val = cmds.getAttr(f"{resolved[0]}.{clean_attr}")
                                    read_success = True
                            else:
                                if current_ns and ":" not in target_attr:
                                    if "." in target_attr:
                                        parts = target_attr.split(".", 1)
                                        val = cmds.getAttr(f"{current_ns}:{parts[0]}.{parts[1]}")
                                    else:
                                        val = cmds.getAttr(f"{current_ns}:{target_attr}")
                                else:
                                    val = cmds.getAttr(target_attr)
                                read_success = True
                        except: pass
                            
                        if read_success:
                            item.value = val
                            item.update()
                    
                    # 2. Sync Checkboxes
                    elif item.shape_name == "Checkbox":
                        data = getattr(item, "cb_data", {})
                        on_attrs = data.get("ON", {}).get("attributes", {})
                        on_cmd = data.get("ON", {}).get("command", "")
                        
                        is_on = True
                        
                        # A. Check standard Maya attributes first
                        if on_attrs:
                            for obj_attr, target_val in on_attrs.items():
                                try:
                                    if current_ns and ":" not in obj_attr:
                                        if "." in obj_attr:
                                            obj, at = obj_attr.split(".", 1)
                                            val = cmds.getAttr(f"{current_ns}:{obj}.{at}")
                                        else:
                                            val = cmds.getAttr(f"{current_ns}:{obj_attr}")
                                    else:
                                        val = cmds.getAttr(obj_attr)
                                        
                                    if abs(val - target_val) > 0.0001:
                                        is_on = False
                                        break
                                except:
                                    is_on = False
                                    break
                                    
                        # B. Fallback: Parse Custom API Checkbox Commands dynamically!
                        elif "api.match_ikfk" in on_cmd:
                            import re
                            # Extract the chain name and target mode using Regex
                            match = re.search(r'api\.match_ikfk\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']', on_cmd)
                            if match:
                                chain_name = match.group(1)
                                target_mode = match.group(2) # "to_ik" or "to_fk"
                                
                                chains = getattr(char_tab, "ikfk_chains", [])
                                chain = next((c for c in chains if c.get("name") == chain_name), None)
                                if chain:
                                    node, attr = chain.get("sw_node", ""), chain.get("sw_attr", "")
                                    full_attr = f"{current_ns}:{node}.{attr}" if current_ns and ":" not in node else f"{node}.{attr}"
                                    try:
                                        val = cmds.getAttr(full_attr)
                                        target_val = chain.get("ik_val", 1.0) if target_mode == "to_ik" else chain.get("fk_val", 0.0)
                                        if abs(val - target_val) > 0.0001: is_on = False
                                    except: is_on = False
                                else: is_on = False
                            else: is_on = False
                        
                        else:
                            continue # Cannot determine state

                        item.is_checked = is_on
                        item.update()
                        
                        # Map out the exact shape visibilities required for this updated state
                        state = "ON" if is_on else "OFF"
                        anti_state = "OFF" if is_on else "ON"
                        
                        s_show = [s.split("::")[0] for s in data.get(state, {}).get("shapes", [])]
                        s_hide = [s.split("::")[0] for s in data.get(anti_state, {}).get("shapes", []) if s.split("::")[0] not in s_show]
                        
                        shapes_to_show.update(s_show)
                        shapes_to_hide.update(s_hide)
                
                    # 3. Sync Dropdowns (Read Maya Enums dynamically!)
                    elif item.shape_name == "Dropdown":
                        attr_string = getattr(item, "attribute", "")
                        if not attr_string: continue
                        
                        target_attr = attr_string.split(",")[0].strip()
                        read_success = False
                        current_text = "None"
                        
                        node_attr = ""
                        if item.controls:
                            resolved = self.core.resolve_control_names(item.controls, current_ns)
                            if resolved:
                                clean_attr = target_attr.split(".")[-1] if "." in target_attr else target_attr
                                node_attr = f"{resolved[0]}.{clean_attr}"
                        else:
                            if current_ns and ":" not in target_attr:
                                if "." in target_attr:
                                    parts = target_attr.split(".", 1)
                                    node_attr = f"{current_ns}:{parts[0]}.{parts[1]}"
                                else:
                                    node_attr = f"{current_ns}:{target_attr}"
                            else:
                                node_attr = target_attr

                        # Strict Cython Check
                        if node_attr and cmds.objExists(node_attr):
                            node, attr = node_attr.split(".", 1)
                            if cmds.attributeQuery(attr, node=node, exists=True):
                                val = cmds.getAttr(node_attr)
                                enum_strings = cmds.attributeQuery(attr, node=node, listEnum=True)
                                
                                if enum_strings and enum_strings[0]:
                                    enum_list = enum_strings[0].split(":")
                                    if isinstance(val, int) and 0 <= val < len(enum_list):
                                        current_text = enum_list[val]
                                    else:
                                        current_text = str(val)
                                else:
                                    current_text = str(val) # Integer Fallback if not an enum
                                read_success = True
                        
                        if read_success and getattr(item, "current_text", "") != current_text:
                            if sub_tab == active_sub:
                                item.current_text = current_text
                                item.update()
                    
                                if hasattr(item, "scripts"):
                                    for scr in item.scripts:
                                        if scr.get("trigger") == "On Value Change":
                                            canvas.execute_custom_script(scr.get("command", ""), scr.get("type", "python"))
                    
                    # ---------------------------------------------------------
                    # 4. Sync Script Checkable Menus (NOW SAFELY INSIDE THE LOOP)
                    # ---------------------------------------------------------
                    if hasattr(item, "scripts") and item.scripts:
                        for scr in item.scripts:
                            if scr.get("is_checkable"):
                                linked_attr = scr.get("linked_attr", "").strip()
                                if not linked_attr: continue
                                
                                node_attr = ""
                                if getattr(item, "controls", []):
                                    resolved = self.core.resolve_control_names(item.controls, current_ns)
                                    if resolved:
                                        clean_attr = linked_attr.split(".")[-1] if "." in linked_attr else linked_attr
                                        node_attr = f"{resolved[0]}.{clean_attr}"
                                else:
                                    if current_ns and ":" not in linked_attr:
                                        if "." in linked_attr:
                                            parts = linked_attr.split(".", 1)
                                            node_attr = f"{current_ns}:{parts[0]}.{parts[1]}"
                                        else:
                                            node_attr = f"{current_ns}:{linked_attr}"
                                    else:
                                        node_attr = linked_attr

                                if node_attr and cmds.objExists(node_attr):
                                    val = bool(cmds.getAttr(node_attr))
                                    if not hasattr(item, "_menu_check_states"): item._menu_check_states = {}
                                    
                                    # FIX: Default to None so the script ALWAYS executes on first pass to sync the UI!
                                    old_val = item._menu_check_states.get(scr.get("label"), None)
                                    
                                    if val != old_val:
                                        item._menu_check_states[scr.get("label")] = val
                                        cmd = scr.get("command", "")
                                        cmd_type = scr.get("type", "python")
                                        if cmd:
                                            canvas.execute_custom_script(cmd, cmd_type, val)

                # ---------------------------------------------------------
                # 5. Sync Canvas Scripts Checkable Menus (OUTSIDE THE LOOP)
                # ---------------------------------------------------------
                if hasattr(canvas, "canvas_scripts") and canvas.canvas_scripts:
                    for scr in canvas.canvas_scripts:
                        if scr.get("is_checkable"):
                            linked_attr = scr.get("linked_attr", "").strip()
                            if not linked_attr: continue
                            
                            node_attr = ""
                            if current_ns and ":" not in linked_attr:
                                if "." in linked_attr:
                                    parts = linked_attr.split(".", 1)
                                    node_attr = f"{current_ns}:{parts[0]}.{parts[1]}"
                                else:
                                    node_attr = f"{current_ns}:{linked_attr}"
                            else:
                                node_attr = linked_attr

                            if node_attr and cmds.objExists(node_attr):
                                val = bool(cmds.getAttr(node_attr))
                                if not hasattr(canvas, "_menu_check_states"): canvas._menu_check_states = {}
                                
                                # FIX: Default to None so the script ALWAYS executes on first pass to sync the UI!
                                old_val = canvas._menu_check_states.get(scr.get("label"), None)
                                
                                if val != old_val:
                                    canvas._menu_check_states[scr.get("label")] = val
                                    cmd = scr.get("command", "")
                                    cmd_type = scr.get("type", "python")
                                    if cmd:
                                        canvas.execute_custom_script(cmd, cmd_type, val)

                # Ensure any layer changes and Checkbox visibility logic are visually applied immediately!
                if hasattr(canvas, "apply_layer_visibility"):
                    canvas.apply_layer_visibility()
        
        # Instantly update Editor Panel if it happens to be open while syncing
        if hasattr(self.window, "editor_panel_ui") and self.window.editor_panel_ui:
            try:
                sel = [i for i in self.window.main_tabs.currentWidget().sub_tabs.currentWidget().canvas.scene().selectedItems() if hasattr(i, "shape_name")]
                self.window.editor_panel_ui.set_target_items(sel)
            except: pass
        
        self.on_maya_selection_changed()

        print("ARTools: Smart Sync Complete!")
    
    # =========================================================================
    # ULTIMATE POSE BLENDING & FILE ENGINE
    # =========================================================================
    def get_image_dir(self):
        char_tab = self.window.main_tabs.currentWidget()
        filepath = getattr(char_tab, "file_path", "") if char_tab else ""
        
        # Fallback to temp if this specific tab has not been saved yet
        if not filepath:
            self.window.image_base_dir = TEMP_ART_DIR
            return TEMP_ART_DIR
        
        base_dir = os.path.dirname(filepath)
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        img_dir = os.path.join(base_dir, base_name)
        if not os.path.exists(img_dir): os.makedirs(img_dir)
        
        self.window.image_base_dir = img_dir
        return img_dir

    def migrate_temp_images(self, final_dir):
        """Copies any files from Temp to the final project folder."""
        if not os.path.exists(final_dir): os.makedirs(final_dir)
        if not os.path.exists(TEMP_ART_DIR): return

        for filename in os.listdir(TEMP_ART_DIR):
            src = os.path.join(TEMP_ART_DIR, filename)
            dst = os.path.join(final_dir, filename)
            if not os.path.exists(dst): shutil.copy(src, dst)

    def handle_pose_action(self, shapes, action):
        import os, uuid, shutil
        from . import api
        active_ns = api.get_namespace()
        maya_sel = cmds.ls(selection=True) or []
        short_sel = [self.core.strip_namespace_for_save(x, active_ns) for x in maya_sel]
        
        # --- NEW: SELECT CONTROLS LOGIC ---
        if action == "select_controls":
            ctrls_to_select = []
            for item in shapes:
                if hasattr(item, "pose_data"):
                    for c in item.pose_data.keys():
                        if c not in ctrls_to_select: ctrls_to_select.append(c)
            
            # Route through the live API namespace
            self.core.smart_select(ctrls_to_select, active_ns, mode="replace")
            return
        
        # --- 1. IMAGE HANDLING ---
        if action in ["capture_image", "load_image"]:
            img_dir = self.get_image_dir()
            if not img_dir:
                QtWidgets.QMessageBox.warning(self.window, "Save Picker First", "Please Save your Picker (File > Save) once before adding images so the tool can create a dedicated image folder!")
                return
            
            # 1. Back to PNG to preserve the Alpha Transparency!
            filename = f"pose_{uuid.uuid4().hex[:8]}.png"
            img_path = os.path.join(img_dir, filename)
            
            if action == "capture_image":
                # 2. Read the EXACT X and Y aspect ratio of the UI shape!
                target_w = float(getattr(shapes[0], "width", 100.0))
                target_h = float(getattr(shapes[0], "height", 100.0))
                
                # 3. Multiply by 3 for crisp zooming, but cap at 512px max to prevent massive files
                multiplier = 3.0
                capture_w = int(target_w * multiplier)
                capture_h = int(target_h * multiplier)
                
                if capture_w > 512 or capture_h > 512:
                    scale = 512.0 / max(capture_w, capture_h)
                    capture_w = int(capture_w * scale)
                    capture_h = int(capture_h * scale)
                
                try:
                    # 4. Playblast the raw, transparent PNG
                    cmds.playblast(format="image", compression="png", completeFilename=img_path,
                                   forceOverwrite=True, viewer=False, frame=cmds.currentTime(q=True), 
                                   showOrnaments=False, offScreen=True, widthHeight=(capture_w, capture_h), percent=100)
                    
                    # 5. Background Engine: Dynamic Resolution Scaling for the 200KB Limit
                    from PySide6 import QtCore, QtGui
                    while os.path.exists(img_path) and os.path.getsize(img_path) > 200 * 1024:
                        img = QtGui.QImage(img_path)
                        if img.isNull(): break
                        
                        # Scale the image down by 10% smoothly and resave
                        new_w = int(img.width() * 0.9)
                        new_h = int(img.height() * 0.9)
                        
                        # Stop shrinking if it gets smaller than the actual UI shape
                        if new_w <= target_w or new_h <= target_h: break 
                        
                        scaled_img = img.scaled(new_w, new_h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                        scaled_img.save(img_path, "PNG")
                
                except Exception as e:
                    print(f"ARTools Image Capture Error: {e}")
              
            elif action == "load_image":
                source_path, _ = QtWidgets.QFileDialog.getOpenFileName(self.window, "Select Image", "", "Images (*.png *.jpg *.jpeg *.svg *.tga)")
                if source_path:
                    ext = os.path.splitext(source_path)[1]
                    filename = f"pose_{uuid.uuid4().hex[:8]}{ext}"
                    img_path = os.path.join(img_dir, filename)
                    shutil.copy(source_path, img_path)
                else: return
            
            for item in shapes:
                item.image_path = filename 
                item.update()
        
        # --- 2. DATA MANIPULATION ---
        elif action == "update_pose":
            for item in shapes: item.pose_data = {}
            action = "set_pose" # Fallthrough to clear and replace!
            
        if action == "set_pose":
            for obj in maya_sel:
                short_obj = self.core.strip_namespace_for_save(obj, active_ns)
                attrs = cmds.listAttr(obj, keyable=True, unlocked=True, scalar=True) or []
                for item in shapes:
                    if short_obj not in item.pose_data: item.pose_data[short_obj] = {}
                    for a in attrs:
                        try: item.pose_data[short_obj][a] = cmds.getAttr(f"{obj}.{a}")
                        except: pass
            for item in shapes: item.update()
        
        elif action == "add_attrs":
            cb_attrs = cmds.channelBox('mainChannelBox', q=True, selectedMainAttributes=True) or []
            for obj in maya_sel:
                short_obj = self.core.strip_namespace_for_save(obj, active_ns)
                for item in shapes:
                    if short_obj not in item.pose_data: item.pose_data[short_obj] = {}
                    for a in cb_attrs:
                        try:
                            # Force Maya to use the official Long Name (e.g. 'tx' becomes 'translateX')
                            long_a = cmds.attributeQuery(a, node=obj, longName=True)
                            item.pose_data[short_obj][long_a] = cmds.getAttr(f"{obj}.{long_a}")
                        except: pass
            for item in shapes: item.update()
        
        elif action == "rem_attrs":
            cb_attrs = cmds.channelBox('mainChannelBox', q=True, selectedMainAttributes=True) or []
            for obj in maya_sel:
                short_obj = self.core.strip_namespace_for_save(obj, active_ns)
                for item in shapes:
                    if short_obj in item.pose_data:
                        for a in cb_attrs:
                            try: long_a = cmds.attributeQuery(a, node=obj, longName=True)
                            except: long_a = a
                            
                            # Cleanly remove using the long name, fallback to short name if needed
                            if long_a in item.pose_data[short_obj]:
                                del item.pose_data[short_obj][long_a]
                            elif a in item.pose_data[short_obj]:
                                del item.pose_data[short_obj][a]
                                
                        if not item.pose_data[short_obj]: del item.pose_data[short_obj]
            for item in shapes: item.update()
        
        elif action == "rem_ctrl_ui":
            ui_panel = getattr(self.window, "editor_panel_ui", None)
            if ui_panel and ui_panel.po_ctrl_list.currentItem():
                c_name = ui_panel.po_ctrl_list.currentItem().text()
                for item in shapes:
                    if c_name in item.pose_data: del item.pose_data[c_name]
                for item in shapes: item.update()
                
        elif action == "rem_attr_ui":
            ui_panel = getattr(self.window, "editor_panel_ui", None)
            if ui_panel and ui_panel.po_ctrl_list.currentItem() and ui_panel.po_attr_list.currentItem():
                c_name = ui_panel.po_ctrl_list.currentItem().text()
                a_name = ui_panel.po_attr_list.currentItem().text().split(":")[0].strip()
                for item in shapes:
                    if c_name in item.pose_data and a_name in item.pose_data[c_name]:
                        del item.pose_data[c_name][a_name]
                        if not item.pose_data[c_name]: del item.pose_data[c_name]
                for item in shapes: item.update()
                
        if hasattr(self.window, "editor_panel_ui") and self.window.editor_panel_ui:
            self.window.editor_panel_ui.set_target_items(shapes)
        self.push_undo_snapshot()
    
    def on_pose_drag_started(self, item):
        cmds.undoInfo(openChunk=True, chunkName="ARTools_PoseDrag")
        cmds.scriptEditorInfo(e=True, suppressWarnings=True, suppressInfo=True, suppressErrors=True, suppressResults=True)
        
        self._pose_autokey = cmds.autoKeyframe(q=True, state=True)
        if self._pose_autokey:
            cmds.autoKeyframe(state=False)
        
        from . import api
        current_ns = api.get_namespace()
        maya_sel = [self.core.strip_namespace_for_save(x, current_ns) for x in cmds.ls(selection=True)]
        
        self._active_pose_start = {}
        self._active_pose_target = {}
        pose_data = getattr(item, "pose_data", {})
        if not pose_data: return
        
        for ctrl, attrs in pose_data.items():
            if maya_sel and ctrl not in maya_sel: continue
                
            resolved = self.core.resolve_control_names([ctrl], current_ns)
            if not resolved: continue
            real_ctrl = resolved[0]
            
            self._active_pose_start[real_ctrl] = {}
            self._active_pose_target[real_ctrl] = {}
            
            for a, target_val in attrs.items():
                if cmds.objExists(f"{real_ctrl}.{a}"):
                    self._active_pose_start[real_ctrl][a] = cmds.getAttr(f"{real_ctrl}.{a}")
                    self._active_pose_target[real_ctrl][a] = float(target_val)

    def on_pose_dragged(self, item, pct):
        if not hasattr(self, "_active_pose_start"): return
        self._last_pose_pct = pct 

        for real_ctrl, attrs in self._active_pose_start.items():
            for a, start_val in attrs.items():
                target_val = self._active_pose_target[real_ctrl][a]
                if abs(target_val - start_val) > 0.00001:
                    current_val = start_val + (target_val - start_val) * pct
                    if cmds.objExists(f"{real_ctrl}.{a}"):
                        cmds.setAttr(f"{real_ctrl}.{a}", current_val)
                    
        cmds.refresh(cv=True, f=True)

    def on_pose_drag_ended(self, item):
        if getattr(self, "_pose_autokey", False):
            cmds.autoKeyframe(state=True)
            if hasattr(self, "_active_pose_start"):
                for real_ctrl, attrs in self._active_pose_start.items():
                    for a in attrs.keys():
                        if cmds.objExists(f"{real_ctrl}.{a}"):
                            if cmds.keyframe(f"{real_ctrl}.{a}", q=True, keyframeCount=True) > 0:
                                cmds.setKeyframe(f"{real_ctrl}.{a}")
        
        self._active_pose_start = {}
        self._active_pose_target = {}
        
        pct = getattr(self, "_last_pose_pct", 0.0)
        if hasattr(self, "_last_pose_pct"): del self._last_pose_pct
        
        cmds.undoInfo(closeChunk=True)
        cmds.scriptEditorInfo(e=True, suppressWarnings=False, suppressInfo=False, suppressErrors=False, suppressResults=False)
        
        label = getattr(item, "label", "Unknown")
        pct_str = int(pct * 100)
        msg = f"<span style='color:#00ff00; font-size:16px;'>Pose <b>{label}</b> is applied <b>{pct_str}%</b></span>"
        if not cmds.about(query=True, batch=True):
            cmds.inViewMessage(amg=msg, pos='midCenterTop', fade=True, fadeStayTime=1500)

    # =========================================================================
    # CHECKBOX TOGGLE & DATA ENGINE
    # =========================================================================
    def handle_checkbox_action(self, shapes, state, action):
        from . import api
        active_ns = api.get_namespace()
        maya_sel = cmds.ls(selection=True) or []
        short_sel = [self.core.strip_namespace_for_save(x, active_ns) for x in maya_sel]

        for item in shapes:
            if not hasattr(item, "cb_data"): 
                item.cb_data = {
                    "ON": {"attributes":{}, "shapes":[], "text":"ON", "color":"#4d8c90"}, 
                    "OFF": {"attributes":{}, "shapes":[], "text":"OFF", "color":"#3c6e71"}
                }
            data = item.cb_data[state]
            
            if action == "add_attr":
                cb_attrs = cmds.channelBox('mainChannelBox', q=True, selectedMainAttributes=True) or []
                for obj in maya_sel:
                    short_obj = self.core.strip_namespace_for_save(obj, active_ns)
                    for a in cb_attrs:
                        try:
                            long_a = cmds.attributeQuery(a, node=obj, longName=True)
                            data["attributes"][f"{short_obj}.{long_a}"] = cmds.getAttr(f"{obj}.{long_a}")
                        except: pass
            elif action == "rem_attr":
                ui_panel = getattr(self.window, "editor_panel_ui", None)
                if ui_panel:
                    lst = ui_panel.cb_on_attr if state == "ON" else ui_panel.cb_off_attr
                    if lst.currentItem():
                        attr_key = lst.currentItem().text().rsplit(":", 1)[0].strip()
                        if attr_key in data["attributes"]: 
                            del data["attributes"][attr_key]
            elif action == "clr_attr":
                data["attributes"].clear()

            # --- THE FLOATING VISUAL SHAPE PICKER! ---
            elif action == "add_shape":
                # Close any existing picker first so they don't pile up
                if hasattr(self.window, "_shape_picker_dlg") and self.window._shape_picker_dlg:
                    try: self.window._shape_picker_dlg.close()
                    except: pass
                    
                dlg = QtWidgets.QDialog(self.window)
                dlg.setWindowTitle(f"Assign Shapes to {state}")
                
                # CRITICAL FIX: Make it a floating tool window that doesn't block Maya!
                dlg.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
                dlg.resize(320, 380) 
                
                lay = QtWidgets.QVBoxLayout(dlg)
                
                inst_lbl = QtWidgets.QLabel(
                    "<b>Visual Selection Mode</b><br>"
                    "1. Click shapes on the Canvas behind this window.<br>"
                    "2. Click 'Add Selected' below to queue them.<br>"
                    "3. Click 'Done' to assign them to the Checkbox."
                )
                inst_lbl.setWordWrap(True)
                inst_lbl.setStyleSheet("color: #cccccc; padding-bottom: 5px;")
                lay.addWidget(inst_lbl)
                
                btn_add = QtWidgets.QPushButton("+ Add Selected Canvas Shapes")
                btn_add.setStyleSheet("background-color: #5285a6; font-weight: bold; padding: 6px;")
                lay.addWidget(btn_add)
                
                lay.addWidget(QtWidgets.QLabel("Queued Shapes:"))
                lst = QtWidgets.QListWidget()
                lay.addWidget(lst)

                queued_ids = set()

                def _add_selected_from_canvas():
                    canvas = item.scene()
                    if not canvas: return
                    
                    sel_items = [i for i in canvas.selectedItems() if hasattr(i, "shape_name")]
                    added_count = 0
                    
                    for s in sel_items:
                        # Prevent a Checkbox from assigning itself to its own toggle state
                        if s in shapes: continue 
                        
                        disp_name = getattr(s, "label", "").strip() or f"Unnamed ({s.shape_name})"
                        s_str = f"{s.item_id}::{disp_name}"
                        
                        # Prevent duplicates in the queue OR the existing saved data
                        existing_shapes = data.get("shapes", [])
                        if s_str not in existing_shapes and s_str not in queued_ids:
                            queued_ids.add(s_str)
                            
                            li = QtWidgets.QListWidgetItem(disp_name)
                            li.setData(QtCore.Qt.UserRole, s_str)
                            lst.addItem(li)
                            added_count += 1
                            
                    if added_count > 0:
                        btn_add.setText(f"+ Added {added_count} Shapes (Total Queued: {len(queued_ids)})")
                    else:
                        btn_add.setText("No new valid shapes selected")

                btn_add.clicked.connect(_add_selected_from_canvas)

                btn_layout = QtWidgets.QHBoxLayout()
                btn_done = QtWidgets.QPushButton("✔ Done")
                btn_done.setStyleSheet("background-color: #4CAF50; font-weight: bold; padding: 4px;")
                btn_cancel = QtWidgets.QPushButton("Cancel")
                btn_layout.addWidget(btn_done)
                btn_layout.addWidget(btn_cancel)
                lay.addLayout(btn_layout)

                def _commit_and_close():
                    if "shapes" not in data: data["shapes"] = []
                    for i in range(lst.count()):
                        data["shapes"].append(lst.item(i).data(QtCore.Qt.UserRole))
                        
                    # MAGIC UX UX: Re-select the checkbox so the Editor Panel instantly shows the new list!
                    try:
                        canvas = item.scene()
                        if canvas:
                            canvas.clearSelection()
                            for s in shapes:
                                if s.scene(): # Ensure it hasn't been deleted
                                    s.setSelected(True)
                    except Exception:
                        pass
                        
                    dlg.accept()

                btn_done.clicked.connect(_commit_and_close)
                btn_cancel.clicked.connect(dlg.reject)

                # Store the dialog reference and SHOW it (modeless) instead of exec_()
                self.window._shape_picker_dlg = dlg
                dlg.show()

            elif action == "rem_shape":
                ui_panel = getattr(self.window, "editor_panel_ui", None)
                if ui_panel:
                    lst = ui_panel.cb_on_shape if state == "ON" else ui_panel.cb_off_shape
                    if lst.currentItem():
                        s_str = lst.currentItem().data(QtCore.Qt.UserRole)
                        if "shapes" in data and s_str in data["shapes"]:
                            data["shapes"].remove(s_str)
            elif action == "clr_shape":
                data["shapes"] = []
                
            item.update()
            
        if hasattr(self.window, "editor_panel_ui") and self.window.editor_panel_ui:
            self.window.editor_panel_ui.set_target_items(shapes)
        self.push_undo_snapshot()

    def on_checkbox_toggled(self, item):
        state = "ON" if getattr(item, "is_checked", False) else "OFF"
        anti_state = "OFF" if state == "ON" else "ON"
        
        data = getattr(item, "cb_data", {}).get(state, {})
        anti_data = getattr(item, "cb_data", {}).get(anti_state, {})
        
        try: cmds.undoInfo(openChunk=True, chunkName="ARTools_CheckboxToggle")
        except: pass
        
        from . import api
        current_ns = api.get_namespace()

        # --- 1: Execute Custom Command FIRST ---
        # This ensures api.match_space grabs the exact World Matrix BEFORE any attributes flip!
        cmd_str = data.get("command", "")
        if cmd_str:
            cmd_type = data.get("cmd_type", "python").lower()
            canvas = item.scene().views()[0]
            if hasattr(canvas, "execute_custom_script"):
                # Pass the exact checkbox state securely to the API engine
                canvas.execute_custom_script(cmd_str, cmd_type, getattr(item, "is_checked", False))

        # 2. Apply Standard Attributes
        attrs = data.get("attributes", {})
        for obj_attr, val in attrs.items():
            try:
                if current_ns and ":" not in obj_attr:
                    if "." in obj_attr:
                        obj, at = obj_attr.split(".", 1)
                        cmds.setAttr(f"{current_ns}:{obj}.{at}", val)
                    else: 
                        cmds.setAttr(f"{current_ns}:{obj_attr}", val)
                else: 
                    cmds.setAttr(obj_attr, val)
            except Exception as e: 
                print(f"ARTools Attribute Error: {e}")
                
        # 3. Apply Shape Visibility Overrides
        canvas = item.scene().views()[0]
        if hasattr(canvas, "apply_layer_visibility"):
            canvas.apply_layer_visibility()
            
        try: cmds.undoInfo(closeChunk=True)
        except: pass

    # =========================================================================
    # IMAGE PORTABLE LOADING ENGINE
    # =========================================================================
    def handle_image_action(self, shapes, action):
        import os, uuid, shutil
        if action == "load_image":
            img_dir = self.get_image_dir()
            if not img_dir:
                QtWidgets.QMessageBox.warning(self.window, "Save Picker First", "Please Save your Picker (File > Save) once before adding images so the tool can create a dedicated image folder!")
                return
            
            source_path, _ = QtWidgets.QFileDialog.getOpenFileName(self.window, "Select Image", "", "Images (*.png *.jpg *.jpeg *.svg *.tga)")
            if source_path:
                filename = f"img_{uuid.uuid4().hex[:8]}.png"
                img_path = os.path.join(img_dir, filename)
                shutil.copy(source_path, img_path)
                
                for item in shapes:
                    item.image_path = filename
                    item.update()
                    
            if hasattr(self.window, "editor_panel_ui") and self.window.editor_panel_ui:
                self.window.editor_panel_ui.set_target_items(shapes)
        self.push_undo_snapshot()

    # =========================================================================
    # MIRRORING ENGINE (BOTH TRANSFORM & SHAPE DATA)
    # =========================================================================
    def handle_mirror_action(self, shapes, direction, is_copy):
        if not shapes: return
        
        canvas = shapes[0].scene().views()[0]
        canvas_rect = [0, 0, canvas.sceneRect().width(), canvas.sceneRect().height()]
        use_canvas = getattr(canvas, "_mirror_use_canvas", False)
        
        # Use the existing serialization method instead of to_dict()
        shape_data_list = [self.serialize_item(s) for s in shapes]
        
        cmds.undoInfo(openChunk=True, chunkName="ARTools Mirror")
        mirrored_data = self.core.mirror_shapes_data(shape_data_list, direction, use_canvas, canvas_rect, is_copy)
        
        # --- Deep mirror Slider & Checkbox attributes safely! ---
        for m_data in mirrored_data:
            # 1. Mirror Slider & Dropdown Attributes
            if m_data.get('type') in ['Slider', 'Dropdown'] and m_data.get('attribute'):
                attr_list = [a.strip() for a in m_data['attribute'].split(",") if a.strip()]
                mirrored_attrs = []
                for attr in attr_list:
                    if "." in attr:
                        obj, at = attr.split(".", 1)
                        m_obj = self.core.get_mirrored_controls([obj])
                        mirrored_attrs.append(f"{m_obj[0]}.{at}" if m_obj else attr)
                    else:
                        m_obj = self.core.get_mirrored_controls([attr])
                        mirrored_attrs.append(m_obj[0] if m_obj else attr)
                m_data['attribute'] = ", ".join(mirrored_attrs)

            # 2. Mirror Checkbox Attributes
            if m_data.get('type') == 'Checkbox' and 'cb_data' in m_data:
                for state in ["ON", "OFF"]:
                    if state in m_data['cb_data'] and "attributes" in m_data['cb_data'][state]:
                        old_attrs = m_data['cb_data'][state]["attributes"]
                        new_attrs = {}
                        for attr_name, val in old_attrs.items():
                            if "." in attr_name:
                                obj, at = attr_name.split(".", 1)
                                m_obj = self.core.get_mirrored_controls([obj])
                                new_name = f"{m_obj[0]}.{at}" if m_obj else attr_name
                            else:
                                m_obj = self.core.get_mirrored_controls([attr_name])
                                new_name = m_obj[0] if m_obj else attr_name
                            new_attrs[new_name] = val
                        m_data['cb_data'][state]["attributes"] = new_attrs

        canvas.scene().clearSelection()
        
        if is_copy:
            # Deselect the original items before adding the new ones!
            for s in shapes:
                s.setSelected(False)
                
            # Use the canvas's built-in item builder to construct the new shapes safely
            new_items = canvas.build_items_from_data(mirrored_data)
            
            if new_items:
                max_z = 0.0
                for scene_item in canvas.scene().items():
                    if hasattr(scene_item, "shape_name") and scene_item not in new_items:
                        max_z = max(max_z, float(scene_item.zValue()))
                
                for item in new_items:
                    item.setSelected(True)
                    if item.shape_name == "Image":
                        item.setZValue(-1000.0) 
                    else:
                        max_z += 1.0
                        item.setZValue(max_z) 
            
            if hasattr(self.window, "editor_panel_ui") and self.window.editor_panel_ui:
                self.window.editor_panel_ui.set_target_items(new_items)
        else:
            # Apply mirrored properties directly to existing shapes
            for i, s in enumerate(shapes):
                m_data = mirrored_data[i]
                if 'pos' in m_data:
                    s.setPos(m_data['pos'][0], m_data['pos'][1])
                
                # --- NEW FIX: Ensure label and controls rename applies to standard mirroring too! ---
                if 'label' in m_data:
                    s.label = m_data['label']
                if 'controls' in m_data:
                    s.controls = m_data['controls']
                if 'rotation' in m_data:
                    s.setRotation(m_data['rotation'])
                if s.shape_name in ['Slider', 'Dropdown'] and 'attribute' in m_data:
                    s.attribute = m_data['attribute']
                if s.shape_name == 'Checkbox' and 'cb_data' in m_data:
                    s.cb_data = m_data['cb_data']
                
                # Apply Alignment flips
                if 'text_align_h' in m_data: s.text_align_h = m_data['text_align_h']
                if 'text_align_v' in m_data: s.text_align_v = m_data['text_align_v']
                
                # Apply Round Rectangle Corner flips
                if s.shape_name == 'Round Rectangle':
                    if 'rad_tl' in m_data: s.rad_tl = m_data['rad_tl']
                    if 'rad_tr' in m_data: s.rad_tr = m_data['rad_tr']
                    if 'rad_bl' in m_data: s.rad_bl = m_data['rad_bl']
                    if 'rad_br' in m_data: s.rad_br = m_data['rad_br']
                
                # Apply Polygon geometry flipping with Bezier tangents!
                if s.shape_name == 'Polygon' and 'path_data' in m_data:
                    for p_idx, pt_data in enumerate(s.path_points):
                        if p_idx < len(m_data['path_data']):
                            m_pt = m_data['path_data'][p_idx]
                            pt_data['p'] = QtCore.QPointF(m_pt['p'][0], m_pt['p'][1])
                            pt_data['in'] = QtCore.QPointF(m_pt['in'][0], m_pt['in'][1])
                            pt_data['out'] = QtCore.QPointF(m_pt['out'][0], m_pt['out'][1])
                    
                    if hasattr(s, '_calculate_rect'):
                        s._calculate_rect()
                
                s.setSelected(True)
                s.update()
            
            # Instantly update Editor UI so user sees the new labels/controls
            if hasattr(self.window, "editor_panel_ui") and self.window.editor_panel_ui:
                self.window.editor_panel_ui.set_target_items(shapes)
        
        cmds.undoInfo(closeChunk=True)
        canvas.viewport().update()

        self.push_undo_snapshot()

    # =========================================================================
    # UNDOS/REDOS ENGINE (PER CHARACTER TAB WITH UP TO 30 STEPS EACH)
    # =========================================================================

    def push_undo_snapshot(self):
        if not self.window.is_edit_mode: return
        char_tab = self.window.main_tabs.currentWidget()
        if not char_tab: return
        
        char_name = char_tab.name
        if char_name not in self.undo_stacks:
            self.undo_stacks[char_name] = {"stack": [], "index": -1}
            
        history = self.undo_stacks[char_name]
        data = self.get_current_layout_data()
        
        import json
        state_str = json.dumps(data)
        
        if history["index"] >= 0 and history["stack"][history["index"]] == state_str:
            return # Ignore if nothing changed
            
        history["stack"] = history["stack"][:history["index"] + 1]
        history["stack"].append(state_str)
        history["index"] += 1
        
        if len(history["stack"]) > 30: # Cap at 30 undo steps
            history["stack"].pop(0)
            history["index"] -= 1

    def perform_undo(self):
        if not self.window.is_edit_mode: return
        char_tab = self.window.main_tabs.currentWidget()
        if not char_tab or char_tab.name not in self.undo_stacks: return
        
        history = self.undo_stacks[char_tab.name]
        if history["index"] > 0:
            history["index"] -= 1
            import json
            self.refresh_current_layout(json.loads(history["stack"][history["index"]]))

    def perform_redo(self):
        if not self.window.is_edit_mode: return
        char_tab = self.window.main_tabs.currentWidget()
        if not char_tab or char_tab.name not in self.undo_stacks: return
        
        history = self.undo_stacks[char_tab.name]
        if history["index"] < len(history["stack"]) - 1:
            history["index"] += 1
            import json
            self.refresh_current_layout(json.loads(history["stack"][history["index"]]))

    def _create_tool_shelf_button(self, tool_name, icon_name, command_str):
        import maya.cmds as cmds
        import maya.mel as mel
        import os
        
        current_shelf = mel.eval("tabLayout -q -selectTab $gShelfTopLevel")
        if not current_shelf:
            cmds.warning("[ARTools] No active shelf found.")
            return
            
        cmds.setParent(current_shelf)
        
        buttons = cmds.shelfLayout(current_shelf, q=True, childArray=True) or []
        for btn in buttons:
            if cmds.control(btn, exists=True) and cmds.objectTypeUI(btn) == "shelfButton":
                if cmds.shelfButton(btn, q=True, annotation=True) == f"Launch {tool_name}":
                    cmds.deleteUI(btn)
                    
        target_scripts_dir = cmds.internalVar(userScriptDir=True)
        icon_path = os.path.join(target_scripts_dir, "ARTools", "icons", icon_name)
        if not os.path.exists(icon_path):
            icon_path = os.path.join(target_scripts_dir, "ARTools", "Icons", icon_name)
            
        icon_path = icon_path.replace("\\", "/")
        if not os.path.exists(icon_path):
            icon_path = "commandButton.png"
          
        cmds.shelfButton(
            label=tool_name[:3].upper(),
            annotation=f"Launch {tool_name}",
            image1=icon_path, 
            command=command_str,
            sourceType="python"
        )
        cmds.inViewMessage(amg=f"Added <b>{tool_name}</b> to current shelf!", pos="midCenterTop", fade=True, fadeStayTime=1500)

    def refresh_current_layout(self, data):
        """Silently rebuilds the current tab from a snapshot for Undo/Redo."""
        char_tab = self.window.main_tabs.currentWidget()
        if not char_tab: return
        
        # Safely pause Maya Sync
        if getattr(self, 'sel_job', None):
            try: cmds.scriptJob(kill=self.sel_job, force=True)
            except Exception: pass
            self.sel_job = None
        
        # 1. Save current selection state and EXCLUSIVE POLY state before clearing
        sel_ids = []
        editing_poly_id = None
        
        if char_tab.sub_tabs.currentWidget():
            canvas = char_tab.sub_tabs.currentWidget().canvas
            sel_ids = [i.item_id for i in canvas.scene().selectedItems() if hasattr(i, "item_id")]
            
            # --- CRITICAL FIX: Destroy dangling C++ pointers before clearing scene ---
            for view in canvas.scene().views():
                if hasattr(view, "_exclusive_poly") and view._exclusive_poly:
                    try:
                        # Safely check if the C++ object is still alive
                        editing_poly_id = view._exclusive_poly.item_id 
                    except RuntimeError:
                        pass
                    view._exclusive_poly = None # Sever the link to prevent crash!
            # -------------------------------------------------------------------------
        
        for i in range(char_tab.sub_tabs.count()):
            sub_tab = char_tab.sub_tabs.widget(i)
            if i < len(data.get("subtabs", [])):
                sub_data = data["subtabs"][i]
                
                # Double-check sanitation for all views in this sub tab
                for view in sub_tab.canvas.scene().views():
                    if hasattr(view, "_exclusive_poly"):
                        view._exclusive_poly = None

                sub_tab.canvas.scene().clear()
                if "bg_color" in sub_data: sub_tab.canvas.background_color = QtGui.QColor(sub_data["bg_color"])
                sub_tab.canvas.layer_data = sub_data.get("layer_data", [])
                sub_tab.canvas.canvas_scripts = sub_data.get("canvas_scripts", [])
                
                sub_tab.canvas.build_items_from_data(sub_data.get("items", []))
                if hasattr(sub_tab.canvas, "apply_layer_visibility"): sub_tab.canvas.apply_layer_visibility()
                sub_tab.canvas.update_all_flags()
        
        # 2. Restore selection and Edit Mode seamlessly
        restored_sel = []
        if char_tab.sub_tabs.currentWidget():
            canvas = char_tab.sub_tabs.currentWidget().canvas
            for item in canvas.scene().items():
                if hasattr(item, "item_id"):
                    if item.item_id in sel_ids:
                        item.setSelected(True)
                        restored_sel.append(item)
                    
                    # --- CRITICAL FIX: Put the newly generated polygon back into Edit Mode! ---
                    if item.item_id == editing_poly_id and hasattr(item, "toggle_edit_mode"):
                        item.toggle_edit_mode()
                    # --------------------------------------------------------------------------
                    
        if hasattr(self.window, "editor_panel_ui") and self.window.editor_panel_ui:
            self.window.editor_panel_ui.set_target_items(restored_sel) 
            
        self.sel_job = cmds.scriptJob(event=["SelectionChanged", self.on_maya_selection_changed], protected=True)
        
        # --- Force Screen/Sticky shapes to snap to their UI corners after an Undo ---
        if hasattr(char_tab.sub_tabs.currentWidget().canvas, "update_screen_items"):
            char_tab.sub_tabs.currentWidget().canvas.update_screen_items()
        
        char_tab.sub_tabs.currentWidget().canvas.viewport().update()
