# ASEPicker/mouse_magic.py
import os

from PySide6 import QtWidgets, QtGui, QtCore
IS_PYSIDE2 = False

def inject_events(ui, shapes):
    """
    Dynamically injects uncompiled Mouse, Keyboard, and Context Menu events 
    into the compiled UI and Shape classes to prevent Cython recursion crashes.
    """

    # =====================================================================
    # 1. UI MODULE EVENTS
    # =====================================================================

    def character_tab_show_tab_menu(self, pos):
        global_pos = QtGui.QCursor.pos()
        local_pos = self.sub_tabs.tabBar().mapFromGlobal(global_pos)
        idx = self.sub_tabs.tabBar().tabAt(local_pos)

        menu = QtWidgets.QMenu(self)
        
        # --- 1. GLOBAL ACTION (Always Visible) ---
        add_act = menu.addAction("Add New Tab")
        
        # --- 2. SUB-TAB ACTIONS (Only visible if you actually clicked a tab) ---
        rename_act = delete_act = act_sel = act_cust = act_clear = None
        sub_tab = None
        
        if idx >= 0:
            rename_act = menu.addAction("Rename Tab")
            delete_act = menu.addAction("Delete Tab")
            menu.addSeparator()
            
            sub_tab = self.sub_tabs.widget(idx)
            current_ns = getattr(sub_tab, 'custom_namespace', '')
            title_act = menu.addAction(f"Current Namespace: {current_ns}" if current_ns else "Current Namespace: [None]")
            title_act.setEnabled(False) # Disabled, just for info
            
            act_sel = menu.addAction("➕ Set Selected Namespace")
            act_cust = menu.addAction("➕ Set Custom Namespace")
            act_clear = menu.addAction("➖ Clear Namespace (Use Absolute)")
            
        action = getattr(menu, "exec", menu.exec_)(global_pos)
        if not action: return
        
        def _process_action():
            if action == add_act:
                text, ok = QtWidgets.QInputDialog.getText(self, "New Tab", "Tab Name:")
                if ok and text:
                    new_tab = self.add_sub_tab(text)
                    self.sub_tabs.setCurrentWidget(new_tab)
                    
            elif action == rename_act and idx >= 0:
                old_name = getattr(sub_tab, "name", self.sub_tabs.tabText(idx))
                text, ok = QtWidgets.QInputDialog.getText(self, "Rename Tab", "New Name:", text=old_name)
                if ok and text:
                    sub_tab.name = text
                    self.sub_tabs.setTabText(idx, text) # NO NAMESPACE BRACKETS
                    
            elif action == delete_act and idx >= 0:
                self.sub_tabs.removeTab(idx)
                
            elif action == act_sel and sub_tab:
                import maya.cmds as cmds
                sel = cmds.ls(sl=True)
                if sel and ":" in sel[0]:
                    ns = sel[0].rsplit(":", 1)[0]
                    sub_tab.custom_namespace = ns
                    cmds.inViewMessage(amg=f"Namespace set to: {ns}", pos="midCenter", fade=True)
                else:
                    cmds.warning("[ASEPicker] Selected object has no namespace.")
                    
            elif action == act_cust and sub_tab:
                text, ok = QtWidgets.QInputDialog.getText(self, "Custom Namespace", "Enter Namespace:", text=getattr(sub_tab, "custom_namespace", ""))
                if ok:
                    sub_tab.custom_namespace = text.strip()
                    
            elif action == act_clear and sub_tab:
                sub_tab.custom_namespace = ""

        QtCore.QTimer.singleShot(10, _process_action)

    def picker_window_show_main_tab_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        open_act = None
        if self.main_tabs.count() == 0:
            open_act = menu.addAction("📂 Open...")
            menu.addSeparator()
        
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
        
        def _process_action():
            if action == open_act:
                self.menu_action_requested.emit("open") 
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
                
        QtCore.QTimer.singleShot(10, _process_action)

    def canvas_wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.scale(factor, factor)
        self.update_screen_items()
        event.accept()

    def canvas_mousePressEvent(self, event):
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

        exclusive = getattr(self, "_exclusive_poly", None)
        if exclusive:
            if event.button() == QtCore.Qt.RightButton:
                QtWidgets.QGraphicsView.mousePressEvent(self, event)
                return
            item = self.itemAt(event.pos())
            if item == exclusive:
                QtWidgets.QGraphicsView.mousePressEvent(self, event)
            event.accept()
            return

        is_edit = getattr(self, "is_edit_mode", False)
        
        if is_edit:
            self._undo_drag_pos = {itm.item_id: itm.pos() for itm in self.scene().items() if hasattr(itm, "item_id")}
        
        item = self.itemAt(event.pos())
        
        if item and getattr(item, "shape_name", "") == "Image":
            win = self.window()
            if win and getattr(win, "bg_locked", False):
                item = None 
                
        is_shape = bool(item and hasattr(item, "shape_name"))
        
        mods = event.modifiers()
        is_shift = bool(mods & QtCore.Qt.ShiftModifier)
        is_ctrl = bool(mods & QtCore.Qt.ControlModifier)
        click_type = "left" if event.button() == QtCore.Qt.LeftButton else "right"

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
                            self.scene().clearSelection()
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
                            event.accept()
                            return
                        elif item.shape_name == "Pose":
                            scene_pt = self.mapToScene(event.pos())
                            item._drag_start_x = item.mapFromScene(scene_pt).x()
                            item._drag_pct = 0.0 
                            self.window().pose_drag_started.emit(item)
                            event.accept()
                            return
                        elif item.shape_name == "Checkbox":
                            event.accept()
                            return
                    else:
                        self._rb_active = True
                        self._rb_origin_scene = self.mapToScene(event.pos())
                        self._rb_origin_vp = event.pos()
                        self._rb_visual_rect = QtCore.QRectF(self._rb_origin_scene, self._rb_origin_scene)
                        self._pre_drag_sel = self.scene().selectedItems()
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
                self._pre_drag_sel = self.scene().selectedItems()
                
                if not (is_shift or is_ctrl):
                    self.scene().clearSelection()
                    if not is_edit:
                        self.item_selected.emit([], "replace") 
                        
                self.viewport().update()
                event.accept()
                return
            elif click_type == "right":
                event.accept()
                return

        QtWidgets.QGraphicsView.mousePressEvent(self, event)

    def canvas_keyPressEvent(self, event):
        from .preferences import PrefManager
        prefs = PrefManager()
        
        k = event.key()
        k_int = k.value if hasattr(k, "value") else int(k)
        mods = event.modifiers()
        mods_int = mods.value if hasattr(mods, "value") else int(mods)
        
        key_int = k_int | mods_int
        is_edit = getattr(self, "is_edit_mode", False)
        
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
        
        if match("hk_animbar"):
            self.window().menu_action_requested.emit("open_anim_bar")
            event.accept(); return
        
        if match("hk_library"):
            self.window().menu_action_requested.emit("open_library")
            event.accept(); return
        
        if match("hk_editor"):
            is_edit = getattr(self, "is_edit_mode", False) or getattr(self.window(), "is_edit_mode", False)
            if is_edit:
                sel = [i for i in self.scene().selectedItems() if hasattr(i, "shape_name")]
                if sel: self.edit_shape_properties(sel)
            event.accept(); return

        if match("hk_focus"):
            target_items = [i for i in self.scene().selectedItems() if hasattr(i, "shape_name")]
            if not target_items: target_items = [i for i in self.scene().items() if hasattr(i, "shape_name")]
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
        
        if is_edit and event.key() == QtCore.Qt.Key_Delete:
            sel_items = [i for i in self.scene().selectedItems() if hasattr(i, "shape_name")]
            for t in sel_items: self.scene().removeItem(t)
            self._update_editor_ui()
            self.window().menu_action_requested.emit("push_undo")
            event.accept()
            return
        
        if is_edit and event.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
            dx, dy = 0, 0
            step = 10 if event.modifiers() & QtCore.Qt.ShiftModifier else 1
            if event.key() == QtCore.Qt.Key_Left: dx = -step
            elif event.key() == QtCore.Qt.Key_Right: dx = step
            elif event.key() == QtCore.Qt.Key_Up: dy = -step
            elif event.key() == QtCore.Qt.Key_Down: dy = step
            
            sel_items = [i for i in self.scene().selectedItems() if hasattr(i, "shape_name")]
            if sel_items:
                for item in sel_items:
                    item.setPos(item.x() + dx, item.y() + dy)
                    if hasattr(item, "prepareGeometryChange"): item.prepareGeometryChange()
                self._update_editor_ui()
                self._arrow_nudged = True
                event.accept() 
                return
        
        if is_edit and event.key() == QtCore.Qt.Key_C and (event.modifiers() & QtCore.Qt.ControlModifier):
            sel_items = [i for i in self.scene().selectedItems() if hasattr(i, "shape_name")]
            if sel_items: self.window().copy_requested.emit(sel_items)
            event.accept()
            return
            
        if is_edit and event.key() == QtCore.Qt.Key_V and (event.modifiers() & QtCore.Qt.ControlModifier):
            self.window().paste_requested.emit(self)
            event.accept()
            return
        
        QtWidgets.QGraphicsView.keyPressEvent(self, event)

    def canvas_keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            if getattr(self, "_hier_mode", None):
                self._hier_mode = None
                self.setCursor(QtCore.Qt.ArrowCursor)
            if getattr(self, "_arrow_nudged", False):
                self.window().menu_action_requested.emit("push_undo")
                self._arrow_nudged = False
        QtWidgets.QGraphicsView.keyReleaseEvent(self, event)

    def canvas_mouseMoveEvent(self, event):
        if getattr(self, "_hier_drag_source", None):
            self._hier_drag_pos = self.mapToScene(event.pos())
            self.viewport().update()
            event.accept()
            return

        if getattr(self, "_is_alt_zooming", False):
            delta = event.pos() - self._zoom_start_pos
            import math
            factor = math.pow(1.005, delta.x() - delta.y())
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
                window = self.window()
                if hasattr(window, "editor_panel_ui") and window.editor_panel_ui:
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

    def canvas_mouseReleaseEvent(self, event):
        is_edit = getattr(self, "is_edit_mode", False) or getattr(self.window(), "is_edit_mode", False)
        
        if is_edit and getattr(self, "_undo_drag_pos", None):
            moved = False
            for itm in self.scene().items():
                if hasattr(itm, "item_id") and itm.item_id in self._undo_drag_pos:
                    if itm.pos() != self._undo_drag_pos[itm.item_id]:
                        moved = True
                        break
            if moved:
                self.window().menu_action_requested.emit("push_undo")
            self._undo_drag_pos = None
        
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

        if getattr(self, "_is_alt_zooming", False):
            self._is_alt_zooming = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            if event.button() == QtCore.Qt.RightButton:
                self._ignore_next_context_menu = True
            event.accept()
            return
        
        is_edit = getattr(self, "is_edit_mode", False) or getattr(self.window(), "is_edit_mode", False)
        if is_edit and hasattr(self, "_scene") and self.scene() and self.scene().selectedItems():
            vp_size = self.viewport().size()
            w, h = vp_size.width(), vp_size.height()
            for item in self.scene().selectedItems():
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
                self._rb_active = False 
                if item.shape_name not in ["Pose", "Slider", "Checkbox"]:
                    if is_shift: mode = "add"
                    elif is_ctrl: mode = "deselect"
                    elif is_alt: mode = "mirror"
                    else: mode = "replace"
                    self.item_selected.emit(item.controls, mode)

                elif item.shape_name == "Pose":
                    self.window().pose_dragged.emit(item, 1.0)
                    item._drag_pct = None
                    self.window().pose_drag_ended.emit(item)
                elif item.shape_name == "Checkbox":
                    item.is_checked = not getattr(item, "is_checked", False)
                    item.update()
                    self.window().checkbox_toggled.emit(item)
                    
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
                
                if not (is_shift or is_ctrl):
                    self.scene().clearSelection()
                    self.item_selected.emit([], "replace")
            else:
                items_in_band = self.scene().items(self._rb_visual_rect, QtCore.Qt.IntersectsItemShape)

                if not is_edit:
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
                    rubber_sel = set(i for i in items_in_band if hasattr(i, "shape_name"))
                    pre_sel = set(i for i in getattr(self, "_pre_drag_sel", []) if hasattr(i, "shape_name"))

                    if is_shift:
                        final_sel = pre_sel.union(rubber_sel)
                    elif is_ctrl:
                        final_sel = pre_sel - rubber_sel
                    else:
                        final_sel = rubber_sel

                    self.scene().clearSelection()
                    for it in final_sel:
                        it.setSelected(True)

                    window = self.window()
                    if hasattr(window, "editor_panel_ui") and window.editor_panel_ui:
                        sel_shapes = [i for i in self.scene().selectedItems() if hasattr(i, "shape_name")]
                        window.editor_panel_ui.set_target_items(sel_shapes)

                if not is_edit:
                    window = self.window()
                    if hasattr(window, "editor_panel_ui") and window.editor_panel_ui:
                        sel_shapes = [i for i in self.scene().selectedItems() if hasattr(i, "shape_name")]
                        window.editor_panel_ui.set_target_items(sel_shapes)

            self._rb_visual_rect = QtCore.QRectF()
            self.viewport().update()
            event.accept()
            return

        QtWidgets.QGraphicsView.mouseReleaseEvent(self, event)

    def canvas_mouseDoubleClickEvent(self, event):
        is_edit = getattr(self, "is_edit_mode", False)
        item = self.itemAt(event.pos())
        
        if item and hasattr(item, "shape_name") and not is_edit:
            all_shapes = {i.item_id: i for i in self.scene().items() if hasattr(i, "item_id")}
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
        
        QtWidgets.QGraphicsView.mouseDoubleClickEvent(self, event)

    def canvas_contextMenuEvent(self, event):
        if getattr(self, "_ignore_next_context_menu", False):
            self._ignore_next_context_menu = False
            event.accept()
            return
            
        if event.modifiers() & QtCore.Qt.AltModifier:
            event.accept()
            return

        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu { background: #2b2b2b; color: #dfdfdf; border: 1px solid #555; } QMenu::item:selected { background: #5285a6; }")
        
        item = self.itemAt(event.pos())
        
        if item and getattr(item, "shape_name", "") == "Image":
            win = self.window()
            if win and getattr(win, "bg_locked", False):
                item = None 

        exclusive = getattr(self, "_exclusive_poly", None)
        if exclusive:
            item = exclusive
            
        self._custom_scr_acts = {}

        script_list = item.scripts if item and hasattr(item, "scripts") else getattr(self, "canvas_scripts", [])

        if script_list:
            right_actions = [s for s in script_list if s.get("trigger") == "Right Click (Action)"]
            if right_actions:
                for scr in right_actions:
                    self.execute_custom_script(scr.get("command", ""), scr.get("type", "python"))
                event.accept()
                return 
                
            right_menus = [s for s in script_list if s.get("trigger") == "Right Click (Menu)"]
            if right_menus:
                for scr in right_menus:
                    act = menu.addAction(scr.get("label", "Script"))
                    self._custom_scr_acts[act] = scr
                menu.addSeparator()
        
        is_edit = getattr(self, "is_edit_mode", False)
        
        selected_items = [i for i in self.scene().selectedItems() if hasattr(i, "shape_name")]
        targets = [item] if item and hasattr(item, "shape_name") else []

        action_add_ctrl = action_rep_ctrl = None
        act_add_attr = act_rep_attr = act_clr_attr = None
        act_pose_sel_ctrl = None 
        act_pose_set = act_pose_upd = act_pose_add_attr = act_pose_rem_attr = act_pose_cap = act_pose_load = None

        if targets:
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
                pass
            else:
                action_add_ctrl = menu.addAction("➕ Add Selection")
                action_rep_ctrl = menu.addAction("🔄 Replace Selection")
            menu.addSeparator()

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
                    ("Image", "image.svg") 
                ]
                
                from .preferences import PrefManager
                icon_folder = PrefManager().get("path_icons")
                
                for shape_name, icon_file in shape_defs:
                    act = None
                    if icon_file:
                        icon_path = os.path.join(icon_folder, icon_file)
                        if os.path.exists(icon_path):
                            act = add_menu.addAction(QtGui.QIcon(icon_path), shape_name)
                    if act is None:
                        act = add_menu.addAction(shape_name)
                    add_actions[act] = shape_name
                
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

        action = getattr(menu, "exec", menu.exec_)(event.globalPos())
        event.accept()
        if not action: return

        if hasattr(self, "_custom_scr_acts") and action in self._custom_scr_acts:
            scr = self._custom_scr_acts[action]
            self.execute_custom_script(scr.get("command", ""), scr.get("type", "python"))
            return

        if action == act_add_attr: self.window().attribute_modified_requested.emit(targets, "add")
        elif action == act_rep_attr: self.window().attribute_modified_requested.emit(targets, "replace")
        elif action == act_clr_attr: self.window().attribute_modified_requested.emit(targets, "clear")
        
        elif action == act_pose_sel_ctrl: self.window().pose_action_requested.emit(targets, "select_controls")
        elif action == act_pose_set: self.window().pose_action_requested.emit(targets, "set_pose")
        elif action == act_pose_upd: self.window().pose_action_requested.emit(targets, "update_pose")
        elif action == act_pose_add_attr: self.window().pose_action_requested.emit(targets, "add_attrs")
        elif action == act_pose_rem_attr: self.window().pose_action_requested.emit(targets, "rem_attrs")
        elif action == act_pose_cap: self.window().pose_action_requested.emit(targets, "capture_image")
        elif action == act_pose_load: self.window().pose_action_requested.emit(targets, "load_image")

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
            
            elif action == act_poly_edit: 
                target_id = targets[0].item_id
                valid = [i for i in self.scene().items() if hasattr(i, "item_id") and i.item_id == target_id]
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
                for t in targets: self.scene().removeItem(t)
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

    # Assign methods to ui.py
    ui.CharacterTab.show_tab_menu = character_tab_show_tab_menu
    ui.PickerWindow.show_main_tab_menu = picker_window_show_main_tab_menu
    ui.PickerCanvas.wheelEvent = canvas_wheelEvent
    ui.PickerCanvas.mousePressEvent = canvas_mousePressEvent
    ui.PickerCanvas.keyPressEvent = canvas_keyPressEvent
    ui.PickerCanvas.keyReleaseEvent = canvas_keyReleaseEvent
    ui.PickerCanvas.mouseMoveEvent = canvas_mouseMoveEvent
    ui.PickerCanvas.mouseReleaseEvent = canvas_mouseReleaseEvent
    ui.PickerCanvas.mouseDoubleClickEvent = canvas_mouseDoubleClickEvent
    ui.PickerCanvas.contextMenuEvent = canvas_contextMenuEvent


    # =====================================================================
    # 2. PICKER_SHAPES MODULE EVENTS
    # =====================================================================

    def base_hoverEnterEvent(self, event):
        scene = self.scene()
        if scene and scene.views() and not getattr(scene.views()[0], "is_edit_mode", False):
            self._visual_state = "hover"
            self.update()
        QtWidgets.QGraphicsObject.hoverEnterEvent(self, event)

    def base_hoverLeaveEvent(self, event):
        self._visual_state = "normal"
        self.update()
        QtWidgets.QGraphicsObject.hoverLeaveEvent(self, event)

    def base_mousePressEvent(self, event):
        scene = self.scene()
        is_edit = getattr(scene.views()[0], "is_edit_mode", False) if scene and scene.views() else False
        if is_edit and not self.locked_edit: self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, True)
        else: self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)

        if not is_edit:
            self._visual_state = "press"
            self.update()
        QtWidgets.QGraphicsObject.mousePressEvent(self, event)

    def base_mouseReleaseEvent(self, event):
        self._visual_state = "hover" if self.isUnderMouse() else "normal"
        self.update()
        QtWidgets.QGraphicsObject.mouseReleaseEvent(self, event)

    def poly_hoverMoveEvent(self, event):
        if self.is_editing_points:
            h = self._get_handle_at(event.pos())
            if h != self.hovered_handle:
                self.hovered_handle = h
                self.update()
        shapes.PickerBaseShape.hoverMoveEvent(self, event)

    def poly_mousePressEvent(self, event):
        if self.is_editing_points and event.button() == QtCore.Qt.LeftButton:
            self.active_handle = self._get_handle_at(event.pos())
            if self.active_handle:
                event.accept()
                return
        shapes.PickerBaseShape.mousePressEvent(self, event)

    def poly_mouseMoveEvent(self, event):
        if self.is_editing_points and self.active_handle:
            idx, htype = self.active_handle
            pt = self.path_points[idx]
            
            if event.modifiers() & QtCore.Qt.ShiftModifier:
                pt["s"] = False
            
            if htype == 'p':
                pt["p"] = event.pos()
            elif htype == 'in':
                pt["in"] = event.pos() - pt["p"]
                if pt["s"]: pt["out"] = -pt["in"]
            elif htype == 'out':
                pt["out"] = event.pos() - pt["p"]
                if pt["s"]: pt["in"] = -pt["out"]
            
            self._calculate_rect()
            self.update()
            event.accept()
            return
            
        shapes.PickerBaseShape.mouseMoveEvent(self, event)

    def poly_mouseReleaseEvent(self, event):
        if self.is_editing_points and self.active_handle:
            self.active_handle = None
            scene = self.scene()
            if scene and scene.views() and hasattr(scene.views()[0].window(), "menu_action_requested"):
                scene.views()[0].window().menu_action_requested.emit("push_undo")
            event.accept()
            return
        shapes.PickerBaseShape.mouseReleaseEvent(self, event)

    def poly_mouseDoubleClickEvent(self, event):
        if self.is_editing_points and event.button() == QtCore.Qt.LeftButton:
            h = self._get_handle_at(event.pos())
            if h and h[1] == 'p':
                pt = self.path_points[h[0]]
                pt["s"] = not pt["s"]
                if pt["s"]:
                    if not pt["in"].isNull(): pt["out"] = -pt["in"]
                    elif not pt["out"].isNull(): pt["in"] = -pt["out"]
                self.update()
                scene = self.scene()
                if scene and scene.views() and hasattr(scene.views()[0].window(), "menu_action_requested"):
                    scene.views()[0].window().menu_action_requested.emit("push_undo")
                event.accept(); return
            else:
                idx = self._get_closest_segment(event.pos())
                if idx is not None:
                    self.context_add_point(self.mapToScene(event.pos()))
                    event.accept()
                    return
        
        shapes.PickerBaseShape.mouseDoubleClickEvent(self, event)

    # Assign methods to picker_shapes.py
    shapes.PickerBaseShape.hoverEnterEvent = base_hoverEnterEvent
    shapes.PickerBaseShape.hoverLeaveEvent = base_hoverLeaveEvent
    shapes.PickerBaseShape.mousePressEvent = base_mousePressEvent
    shapes.PickerBaseShape.mouseReleaseEvent = base_mouseReleaseEvent

    shapes.PickerPolygonItem.hoverMoveEvent = poly_hoverMoveEvent
    shapes.PickerPolygonItem.mousePressEvent = poly_mousePressEvent
    shapes.PickerPolygonItem.mouseMoveEvent = poly_mouseMoveEvent
    shapes.PickerPolygonItem.mouseReleaseEvent = poly_mouseReleaseEvent
    shapes.PickerPolygonItem.mouseDoubleClickEvent = poly_mouseDoubleClickEvent