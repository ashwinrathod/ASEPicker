# ARTools/link/link_manager_ui.py
from PySide6 import QtWidgets, QtCore, QtGui
import bpy
import os
import sys
from . import logic_link

def _attach_owner_hwnd(qwidget, owner_hwnd):
    if sys.platform != "win32" or not owner_hwnd:
        return
    import ctypes
    qwidget.winId()
    hwnd = int(qwidget.winId())

    GWLP_HWNDPARENT = -8
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOZORDER = 0x0004
    SWP_FRAMECHANGED = 0x0020

    user32 = ctypes.windll.user32
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    user32.GetWindowLongPtrW.restype = ctypes.c_void_p
    user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]

    user32.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, owner_hwnd)
    ex_style = int(user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE))
    if ex_style & WS_EX_TOOLWINDOW:
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_TOOLWINDOW)
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)

class CollectionBrowserDialog(QtWidgets.QDialog):
    """Sleek, borderless floating dialog for intercepting and selecting assets."""
    def __init__(self, filepath, collections, multi_select=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Assets")
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.resize(400, 450)
        
        self.setStyleSheet("""
            QDialog { background-color: #1E2024; border: 1px solid #4FB8A7; border-radius: 6px; }
            QLabel { color: #E0E0E0; font-weight: bold; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
            QLineEdit { background-color: #25282D; border: 1px solid #454A50; color: white; padding: 8px; border-radius: 4px; }
            QListWidget { background-color: #25282D; border: 1px solid #454A50; color: white; border-radius: 4px; outline: none; font-size: 13px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #303338; }
            QListWidget::item:selected { background-color: #4FB8A7; color: #1E2024; font-weight: bold; }
            QPushButton { background-color: #3A3E45; color: white; border: 1px solid #454A50; border-radius: 4px; padding: 8px 16px; font-weight: bold; }
            QPushButton#btn_link { background-color: #4FB8A7; color: #1E2024; border: none; }
            QPushButton#btn_link:hover { background-color: #5ED1C0; }
            QPushButton:hover { background-color: #5285A6; }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Header
        header_lay = QtWidgets.QHBoxLayout()
        header_lay.addWidget(QtWidgets.QLabel("Select Assets to Link" if multi_select else "Select Asset for Swap"))
        header_lay.addStretch()
        layout.addLayout(header_lay)
        
        # Search Bar
        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search collections...")
        self.search_box.textChanged.connect(self._filter_list)
        layout.addWidget(self.search_box)
        
        # List Widget
        self.list_widget = QtWidgets.QListWidget()
        if multi_select:
            self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        else:
            self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            
        for col in collections:
            self.list_widget.addItem(f"📦 {col}")
        layout.addWidget(self.list_widget)
        
        # Bottom Buttons
        btn_lay = QtWidgets.QHBoxLayout()
        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        self.btn_link = QtWidgets.QPushButton("🔗 Link Selected" if multi_select else "🔄 Swap Selected")
        self.btn_link.setObjectName("btn_link")
        self.btn_link.clicked.connect(self.accept)
        
        btn_lay.addWidget(btn_cancel)
        btn_lay.addWidget(self.btn_link)
        layout.addLayout(btn_lay)
        
    def _filter_list(self, text):
        search_term = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(search_term not in item.text().lower())
            
    def get_selected(self):
        return [item.text().replace("📦 ", "") for item in self.list_widget.selectedItems()]


class LinkManagerWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.setWindowTitle("ARTools Asset Manager")
        self.resize(800, 450)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
        
        self._blender_hwnd = None
        if sys.platform == "win32":
            import ctypes
            self._blender_hwnd = ctypes.windll.user32.GetForegroundWindow()

        self.setStyleSheet("""
            QWidget { background-color: #1E2024; color: #E0E0E0; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
            QToolButton { background: transparent; border: 1px solid transparent; padding: 6px; font-size: 16px; border-radius: 4px; }
            QToolButton:hover { background-color: rgba(79, 184, 167, 0.2); border: 1px solid #4FB8A7; }
            QToolButton#btn_remove:hover { background-color: rgba(158, 74, 74, 0.4); border: 1px solid #9E4A4A; }
            QTreeWidget { background-color: #25282D; border: 1px solid #454A50; border-radius: 4px; padding: 4px; alternate-background-color: #2A2D33; }
            QTreeWidget::item { padding: 6px; }
            QTreeWidget::item:selected { background-color: #4FB8A7; color: #1E2024; font-weight: bold; }
            QHeaderView::section { background-color: #303338; border: 1px solid #454A50; padding: 6px; font-weight: bold; }
            QCheckBox { font-weight: bold; color: #E0E0E0; }
        """)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # =========================================================
        # THE STUDIO TOOLBAR
        # =========================================================
        toolbar = QtWidgets.QHBoxLayout()
        
        def create_tool_btn(icon, tooltip, obj_name=""):
            btn = QtWidgets.QToolButton()
            btn.setText(icon)
            btn.setToolTip(tooltip)
            if obj_name: btn.setObjectName(obj_name)
            return btn
            
        def create_vline():
            line = QtWidgets.QFrame()
            line.setFrameShape(QtWidgets.QFrame.VLine)
            line.setStyleSheet("border-left: 1px solid #454A50; margin: 4px 6px;")
            return line

        self.btn_add = create_tool_btn("➕", "Add new linked asset")
        self.btn_add.clicked.connect(self._on_add_link)
        
        self.btn_reload = create_tool_btn("🔄", "Reload selected asset(s)")
        self.btn_reload.clicked.connect(self._on_reload)
        
        self.btn_unload = create_tool_btn("👁️", "Toggle Load/Mute selected asset(s)")
        self.btn_unload.clicked.connect(self._on_unload)
        
        self.btn_duplicate = create_tool_btn("👯", "Duplicate selected asset(s)")
        self.btn_duplicate.clicked.connect(self._on_duplicate)
        
        self.btn_local = create_tool_btn("⬇️", "Import / Make selected asset(s) local")
        self.btn_local.clicked.connect(self._on_make_local)
        
        self.btn_remove = create_tool_btn("🗑️", "Safely purge selected asset(s)", "btn_remove")
        self.btn_remove.clicked.connect(self._on_remove_link)
        
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(create_vline())
        toolbar.addWidget(self.btn_reload)
        toolbar.addWidget(self.btn_unload)
        toolbar.addWidget(self.btn_duplicate)
        toolbar.addWidget(self.btn_local)
        toolbar.addWidget(create_vline())
        toolbar.addWidget(self.btn_remove)
        
        toolbar.addStretch()
        
        self.chk_auto_ns = QtWidgets.QCheckBox("Automatic Namespace")
        self.chk_auto_ns.setChecked(True)
        toolbar.addWidget(self.chk_auto_ns)
        
        main_layout.addLayout(toolbar)
        
        # =========================================================
        # ACTIVE SCENE LINKS DASHBOARD
        # =========================================================
        self.tree_links = QtWidgets.QTreeWidget()
        self.tree_links.setHeaderLabels(["Status", "Namespace (Asset)", "Library File"])
        self.tree_links.setColumnWidth(0, 80)
        self.tree_links.setColumnWidth(1, 180)
        self.tree_links.setAlternatingRowColors(True)
        self.tree_links.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree_links.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree_links.customContextMenuRequested.connect(self._on_context_menu)
        main_layout.addWidget(self.tree_links)
        
        self.refresh_scene_links()

        # =========================================================
        # SAFE SCENE SYNC ENGINE
        # =========================================================
        self._current_blend_filepath = getattr(bpy.data, "filepath", "")
        self._last_lib_count = len(bpy.data.libraries) if hasattr(bpy.data, "libraries") else -1
        
        self.poll_timer = QtCore.QTimer(self)
        self.poll_timer.timeout.connect(self._poll_scene_state)
        self.poll_timer.start(1000)

    def showEvent(self, event):
        QtWidgets.QWidget.showEvent(self, event)
        _attach_owner_hwnd(self, self._blender_hwnd)

    def closeEvent(self, event):
        if hasattr(self, "poll_timer"):
            self.poll_timer.stop()
        QtWidgets.QWidget.closeEvent(self, event)

    def _poll_scene_state(self):
        try:
            if not bpy.context or not bpy.context.scene: return
            
            current_fp = bpy.data.filepath
            if current_fp != getattr(self, "_current_blend_filepath", ""):
                self._current_blend_filepath = current_fp
                self.refresh_scene_links()
                
            current_lib_count = len(bpy.data.libraries)
            if current_lib_count != getattr(self, "_last_lib_count", -1):
                self._last_lib_count = current_lib_count
                self.refresh_scene_links()
        except Exception:
            pass 

    # =========================================================
    # CORE LOGIC BINDINGS
    # =========================================================
    def _on_add_link(self):
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Add Blender File", "", "Blender Files (*.blend)")
        if not filepath: return
        
        collections = logic_link.peek_file(filepath)
        if not collections:
            QtWidgets.QMessageBox.information(self, "No Assets", "No valid collections found in this file.")
            return
            
        dlg = CollectionBrowserDialog(filepath, collections, multi_select=True, parent=self)
        if dlg.exec():
            selected_cols = dlg.get_selected()
            for col_name in selected_cols:
                if self.chk_auto_ns.isChecked():
                    ns_prompt = logic_link.generate_unique_namespace(col_name)
                else:
                    ns_prompt, ok = QtWidgets.QInputDialog.getText(
                        self, "Asset Namespace", 
                        f"Enter a namespace for '{col_name}':",
                        QtWidgets.QLineEdit.Normal, col_name
                    )
                    if not ok or not ns_prompt.strip():
                        continue
                    ns_prompt = ns_prompt.strip()
                    
                logic_link.link_collection(filepath, col_name, ns_prompt)
            self.refresh_scene_links()

    def refresh_scene_links(self):
        self.tree_links.clear()
        links = logic_link.scan_scene_links()
        
        for data in links:
            item = QtWidgets.QTreeWidgetItem(self.tree_links)
            
            if data["is_missing"]: status = "🔴 Missing"
            elif data["is_unloaded"]: status = "⚪ Muted"
            else: status = "🟢 Loaded"
            
            item.setText(0, status)
            item.setText(1, data["name"])
            item.setText(2, data["filepath"])
            item.setData(0, QtCore.Qt.UserRole, data)

    def _get_selected_overrides(self):
        items = self.tree_links.selectedItems()
        if not items:
            QtWidgets.QMessageBox.information(self, "ARTools", "Please select one or more linked assets in the list.")
            return []
        return [item.data(0, QtCore.Qt.UserRole) for item in items]

    def _on_reload(self):
        targets = self._get_selected_overrides()
        if not targets: return
        for data in targets: logic_link.reload_library(data["lib_name"])
        self.refresh_scene_links()

    def _on_unload(self):
        targets = self._get_selected_overrides()
        if not targets: return
        for data in targets: logic_link.toggle_unload(data["name"])
        self.refresh_scene_links()

    def _on_make_local(self):
        targets = self._get_selected_overrides()
        if not targets: return
        
        reply = QtWidgets.QMessageBox.question(self, "Confirm Import", f"Bake {len(targets)} linked asset(s) natively into this scene?\nThis will sever external updates.", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            for data in targets: logic_link.make_local(data["name"])
            self.refresh_scene_links()

    def _on_duplicate(self):
        targets = self._get_selected_overrides()
        if not targets: return
        
        for data in targets:
            filepath = data.get("abs_filepath", data["filepath"])
            source_col = data["source_col"]
            current_name = data["name"]
            
            new_ns = logic_link.generate_unique_namespace(current_name)
            logic_link.link_collection(filepath, source_col, new_ns)
            
        self.refresh_scene_links()

    def _on_remove_link(self):
        targets = self._get_selected_overrides()
        if not targets: return
        
        reply = QtWidgets.QMessageBox.question(self, "Confirm Deletion", f"Permanently purge {len(targets)} asset(s) and all their animations from this scene?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            for data in targets: logic_link.remove_override(data["name"])
            self.refresh_scene_links()

    def _on_context_menu(self, pos):
        targets = self.tree_links.selectedItems()
        if not targets: return
        
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #2A2A2A; color: #E0E0E0; border: 1px solid #444444; } QMenu::item:selected { background-color: #4FB8A7; color: #1E2024; }")
        
        act_rel = menu.addAction("Convert Path to Relative (//)")
        act_abs = menu.addAction("Convert Path to Absolute (C:/)")
        
        action = menu.exec_(self.tree_links.mapToGlobal(pos))
        if action == act_rel or action == act_abs:
            make_rel = (action == act_rel)
            for item in targets:
                data = item.data(0, QtCore.Qt.UserRole)
                logic_link.toggle_path_relativity(data["lib_name"], make_relative=make_rel)
            self.refresh_scene_links()