# ARTools/file_manager.py
import os
import json
import shutil
from PySide6.QtGui import QIcon, QPixmap, QImage, QPainter, QColor, QPen
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, 
                               QLineEdit, QSlider, QLabel, QPushButton, QSplitter, QWidget, 
                               QStyledItemDelegate, QStyle, QMessageBox, QInputDialog, 
                               QTreeView, QAbstractItemView, QStackedWidget, QFileSystemModel)
from PySide6.QtCore import QSize, Qt, QDir

class ThumbnailDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        is_active = (option.state & QStyle.State_MouseOver) or (option.state & QStyle.State_Selected)
        pixmap = index.data(Qt.UserRole + 1) if is_active else index.data(Qt.UserRole + 2)
        if pixmap:
            option.icon = QIcon(pixmap)

class FileManagerBrowser(QDialog):
    def __init__(self, start_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ARTools Vault - Layout Browser")
        self.resize(1100, 700)
        self.setStyleSheet("QDialog { background-color: #1e1e1e; color: #dfdfdf; } QLabel { color: #dfdfdf; }")
        
        from .preferences import PrefManager
        self.prefs = PrefManager()
        
        self.history = []
        self.history_index = -1
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        
        # ==========================================
        # 1. TOP NAVIGATION BAR
        # ==========================================
        self.nav_layout = QHBoxLayout()
        
        self.btn_toggle_left = QPushButton("◀ Folders")
        self.btn_toggle_left.setCheckable(True)
        self.btn_toggle_left.setChecked(self.prefs.get("vault_show_tree"))
        self.btn_toggle_left.clicked.connect(self.toggle_panels)
        self.btn_toggle_left.setStyleSheet("QPushButton:checked { background-color: #5285a6; }")
        
        self.btn_back = QPushButton("←"); self.btn_back.setFixedWidth(30); self.btn_back.clicked.connect(self.go_back)
        self.btn_forward = QPushButton("→"); self.btn_forward.setFixedWidth(30); self.btn_forward.clicked.connect(self.go_forward)
        self.btn_up = QPushButton("↑"); self.btn_up.setFixedWidth(30); self.btn_up.clicked.connect(self.go_up)
        self.btn_home = QPushButton("🏠"); self.btn_home.setFixedWidth(30); self.btn_home.clicked.connect(self.go_home)
        
        self.path_edit = QLineEdit()
        self.path_edit.setStyleSheet("background-color: #2b2b2b; border: 1px solid #444; padding: 4px;")
        self.path_edit.returnPressed.connect(self.path_entered)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search inside folder...")
        self.search_bar.setStyleSheet("background-color: #2b2b2b; border: 1px solid #444; padding: 4px;")
        self.search_bar.setFixedWidth(200)
        self.search_bar.textChanged.connect(self.update_filter)
        
        self.btn_view_mode = QPushButton("📄 List" if self.prefs.get("vault_view_mode") == "grid" else "☷ Grid")
        self.btn_view_mode.clicked.connect(self.toggle_view_mode)
        
        self.btn_toggle_right = QPushButton("Inspector ▶")
        self.btn_toggle_right.setCheckable(True)
        self.btn_toggle_right.setChecked(self.prefs.get("vault_show_inspector"))
        self.btn_toggle_right.clicked.connect(self.toggle_panels)
        self.btn_toggle_right.setStyleSheet("QPushButton:checked { background-color: #5285a6; }")
        
        self.nav_layout.addWidget(self.btn_toggle_left)
        self.nav_layout.addSpacing(10)
        self.nav_layout.addWidget(self.btn_back)
        self.nav_layout.addWidget(self.btn_forward)
        self.nav_layout.addWidget(self.btn_up)
        self.nav_layout.addWidget(self.btn_home)
        self.nav_layout.addWidget(self.path_edit)
        self.nav_layout.addWidget(self.search_bar)
        self.nav_layout.addWidget(self.btn_view_mode)
        self.nav_layout.addSpacing(10)
        self.nav_layout.addWidget(self.btn_toggle_right)
        
        self.layout.addLayout(self.nav_layout)
        
        # ==========================================
        # 2. MAIN SPLITTER (THREE PANES)
        # ==========================================
        self.splitter = QSplitter(Qt.Horizontal)
        
        # --- LEFT PANE (Tree & Favorites) ---
        self.left_pane = QWidget()
        self.left_layout = QVBoxLayout(self.left_pane)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        
        fav_header = QHBoxLayout()
        fav_header.addWidget(QLabel("<b>⭐ Pinned Folders</b>"))
        self.btn_pin = QPushButton("Pin Current")
        self.btn_pin.clicked.connect(self.pin_folder)
        self.btn_pin.setStyleSheet("padding: 2px;")
        fav_header.addWidget(self.btn_pin)
        
        self.fav_list = QListWidget()
        self.fav_list.setFixedHeight(120)
        self.fav_list.setStyleSheet("QListWidget { background: #222; border: 1px solid #333; } QListWidget::item:selected { background: #5285a6; }")
        self.fav_list.itemClicked.connect(self.on_fav_clicked)
        self.fav_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.fav_list.customContextMenuRequested.connect(self.fav_context_menu)
        
        for fav in self.prefs.get("vault_favorites") or []:
            if os.path.exists(fav):
                item = QListWidgetItem("📁 " + os.path.basename(fav.rstrip('/\\')))
                item.setData(32, fav)
                self.fav_list.addItem(item)
        
        self.dir_model = QFileSystemModel()
        self.dir_model.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)
        self.dir_model.setRootPath("")
        
        self.tree = QTreeView()
        self.tree.setModel(self.dir_model)
        self.tree.setHeaderHidden(True)
        for i in range(1, 4): self.tree.hideColumn(i)
        self.tree.setStyleSheet("QTreeView { background: #222; border: 1px solid #333; } QTreeView::item:selected { background: #5285a6; }")
        self.tree.clicked.connect(self.on_tree_clicked)
        
        self.left_layout.addLayout(fav_header)
        self.left_layout.addWidget(self.fav_list)
        self.left_layout.addWidget(QLabel("<b>🖧 Directory Tree</b>"))
        self.left_layout.addWidget(self.tree)
        self.splitter.addWidget(self.left_pane)
        
        # --- MIDDLE PANE (The Visual Grid) ---
        self.mid_pane = QWidget()
        self.mid_layout = QVBoxLayout(self.mid_pane)
        self.mid_layout.setContentsMargins(0, 0, 0, 0)
        
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_widget.setItemDelegate(ThumbnailDelegate(self.list_widget))
        self.list_widget.setMouseTracking(True)
        self.list_widget.viewport().setAttribute(Qt.WA_Hover)
        self.list_widget.setStyleSheet("QListWidget { background: #1a1a1a; border: 1px solid #333; padding: 5px; } QListWidget::item:selected { background: #5285a6; border-radius: 6px; }")
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        self.list_widget.setWordWrap(True)
        
        if self.prefs.get("vault_view_mode") == "grid":
            self.list_widget.setViewMode(QListWidget.IconMode)
            self.list_widget.setResizeMode(QListWidget.Adjust)
        else:
            self.list_widget.setViewMode(QListWidget.ListMode)
        
        self.mid_layout.addWidget(self.list_widget)
        self.splitter.addWidget(self.mid_pane)
        
        # --- RIGHT PANE (Smart Inspector) ---
        self.inspector = QWidget()
        self.inspector_layout = QVBoxLayout(self.inspector)
        self.inspector_layout.setContentsMargins(10, 0, 0, 0)
        
        self.preview_label = QLabel("No Preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedSize(250, 250)
        self.preview_label.setStyleSheet("background: #111; border: 1px solid #444; border-radius: 6px;")
        
        self.stack_info = QStackedWidget()
        
        self.info_widget = QWidget()
        self.info_lay = QVBoxLayout(self.info_widget)
        self.info_lay.setContentsMargins(0,0,0,0)
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.info_label.setStyleSheet("font-size: 13px; line-height: 1.5;")
        self.info_lay.addWidget(self.info_label)
        
        self.error_widget = QWidget()
        self.error_lay = QVBoxLayout(self.error_widget)
        self.error_lay.setContentsMargins(0,0,0,0)
        self.error_label = QLabel("<b>⚠️ Not Compatible</b><br><br>This file is not a valid ARTools layout structure.")
        self.error_label.setWordWrap(True)
        self.error_label.setAlignment(Qt.AlignTop | Qt.AlignCenter)
        self.error_label.setStyleSheet("color: #ff5555; font-size: 14px; background: rgba(80, 20, 20, 100); padding: 15px; border-radius: 6px; border: 1px solid #ff5555;")
        self.error_lay.addWidget(self.error_label)
        
        self.stack_info.addWidget(self.info_widget)
        self.stack_info.addWidget(self.error_widget)
        
        self.inspector_layout.addWidget(self.preview_label)
        self.inspector_layout.addWidget(self.stack_info)
        self.inspector_layout.addStretch()
        
        self.splitter.addWidget(self.inspector)
        
        self.splitter.setSizes(self.prefs.get("vault_splitter_sizes") or [220, 500, 280])
        self.layout.addWidget(self.splitter)
        
        # ==========================================
        # 3. BOTTOM ACTIONS
        # ==========================================
        self.bottom_layout = QHBoxLayout()
        
        self.btn_new_dir = QPushButton("New Folder")
        self.btn_new_dir.clicked.connect(self.new_folder)
        self.btn_del = QPushButton("Delete Selected")
        self.btn_del.setStyleSheet("background-color: #6b2e2e;")
        self.btn_del.clicked.connect(self.delete_selected)
        
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(64, 400)
        self.size_slider.setValue(180)
        self.size_slider.setFixedWidth(150)
        self.size_slider.valueChanged.connect(self.update_icon_size)
        
        self.btn_open = QPushButton("Open Selected Layout(s)")
        self.btn_open.setStyleSheet("background-color: #5285a6; font-weight: bold; padding: 6px 15px;")
        self.btn_open.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.bottom_layout.addWidget(self.btn_new_dir)
        self.bottom_layout.addWidget(self.btn_del)
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(QLabel("Thumbnail Size:"))
        self.bottom_layout.addWidget(self.size_slider)
        self.bottom_layout.addSpacing(20)
        self.bottom_layout.addWidget(self.btn_open)
        self.bottom_layout.addWidget(self.btn_cancel)
        
        self.layout.addLayout(self.bottom_layout)
        
        self.toggle_panels()
        self.update_icon_size(180)
        
        if not start_dir or not os.path.exists(start_dir): start_dir = os.path.expanduser("~")
        self.load_directory(start_dir)

    # --- Persistence Logic ---
    def save_state(self):
        self.prefs.set("vault_show_tree", self.btn_toggle_left.isChecked())
        self.prefs.set("vault_show_inspector", self.btn_toggle_right.isChecked())
        self.prefs.set("vault_view_mode", "grid" if self.list_widget.viewMode() == QListWidget.IconMode else "list")
        self.prefs.set("vault_splitter_sizes", self.splitter.sizes())
        
        favs = [self.fav_list.item(i).data(32) for i in range(self.fav_list.count())]
        self.prefs.set("vault_favorites", favs)

    def accept(self):
        self.save_state()
        super().accept()

    def reject(self):
        self.save_state()
        super().reject()

    # --- UI Toggles ---
    def toggle_panels(self):
        self.left_pane.setVisible(self.btn_toggle_left.isChecked())
        self.inspector.setVisible(self.btn_toggle_right.isChecked())

    def toggle_view_mode(self):
        if self.list_widget.viewMode() == QListWidget.IconMode:
            self.list_widget.setViewMode(QListWidget.ListMode)
            self.list_widget.setIconSize(QSize(48, 48))
            self.btn_view_mode.setText("☷ Grid")
        else:
            self.list_widget.setViewMode(QListWidget.IconMode)
            self.list_widget.setResizeMode(QListWidget.Adjust)
            self.list_widget.setIconSize(QSize(self.size_slider.value(), self.size_slider.value()))
            self.btn_view_mode.setText("📄 List")

    def update_icon_size(self, val):
        if self.list_widget.viewMode() == QListWidget.IconMode:
            self.list_widget.setIconSize(QSize(val, val))

    def update_filter(self, text):
        search_lower = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(search_lower not in item.text().lower())

    # --- Directory Logic ---
    def load_drives(self, add_to_history=True):
        self.current_dir = "Computer"
        self.path_edit.setText("My Computer")
        
        if add_to_history:
            self.history = self.history[:self.history_index + 1]
            self.history.append(self.current_dir)
            self.history_index += 1
            
        self.btn_back.setEnabled(self.history_index > 0)
        self.btn_forward.setEnabled(self.history_index < len(self.history) - 1)
        
        self.list_widget.clear()
        self.preview_label.setText("No Preview")
        self.preview_label.setPixmap(QPixmap())
        self.info_label.setText("")
        
        for drive in QDir.drives():
            drive_path = drive.absoluteFilePath()
            item = QListWidgetItem("💽 " + drive_path)
            item.setData(32, drive_path)
            item.setData(33, "folder")
            self.list_widget.addItem(item)

    def load_directory(self, path, add_to_history=True):
        if path == "Computer":
            self.load_drives(add_to_history)
            return
            
        if not os.path.exists(path) or not os.path.isdir(path): return
        
        self.current_dir = os.path.normpath(path)
        self.path_edit.setText(self.current_dir)
        
        # Sync the Tree automatically
        idx = self.dir_model.index(self.current_dir)
        if idx.isValid():
            self.tree.blockSignals(True)
            self.tree.setCurrentIndex(idx)
            self.tree.scrollTo(idx)
            self.tree.blockSignals(False)
        
        if add_to_history:
            self.history = self.history[:self.history_index + 1]
            self.history.append(self.current_dir)
            self.history_index += 1
        
        self.btn_back.setEnabled(self.history_index > 0)
        self.btn_forward.setEnabled(self.history_index < len(self.history) - 1)
        
        self.list_widget.clear()
        self.preview_label.setText("No Preview")
        self.preview_label.setPixmap(QPixmap())
        self.info_label.setText("")
        
        # 1. Load JSON Layouts with Smart Validation
        for f in sorted(os.listdir(self.current_dir)):
            file_path = os.path.join(self.current_dir, f)
            if os.path.isfile(file_path) and f.endswith(".json"):
                is_valid = False
                try:
                    with open(file_path, "r") as json_file:
                        data = json.load(json_file)
                        if isinstance(data, dict) and ("subtabs" in data or "items" in data or "ikfk_chains" in data):
                            is_valid = True
                except: pass

                item = QListWidgetItem(f.replace(".json", ""))
                item.setData(32, file_path)
                item.setData(33, "file")
                item.setData(34, is_valid)
                item.setTextAlignment(Qt.AlignBottom | Qt.AlignHCenter)
                
                # Image Engine with Pre-Validation Overlay
                icon_path = os.path.join(self.current_dir, f.replace(".json", ".png"))
                if os.path.exists(icon_path):
                    color_pixmap = QPixmap(icon_path).scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    gray_image = color_pixmap.toImage().convertToFormat(QImage.Format_Grayscale8)
                    gray_pixmap = QPixmap.fromImage(gray_image)
                else:
                    color_pixmap = QPixmap(400, 400)
                    color_pixmap.fill(QColor("#2a2a2a"))
                    painter = QPainter(color_pixmap)
                    painter.setPen(QColor("#333333"))
                    painter.drawRect(0, 0, 399, 399)
                    painter.setPen(QColor("#666666"))
                    font = painter.font()
                    font.setPointSize(28)
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(color_pixmap.rect(), Qt.AlignCenter, "JSON\nNO PREVIEW")
                    painter.end()
                    gray_pixmap = color_pixmap
                
                # Draw Warning Triangle if broken!
                if not is_valid:
                    for px in [color_pixmap, gray_pixmap]:
                        painter = QPainter(px)
                        painter.setBrush(QColor(255, 0, 0, 150))
                        painter.setPen(QPen(QColor(255, 255, 255), 3))
                        painter.drawEllipse(10, 10, 80, 80)
                        painter.setPen(QColor(255, 255, 255))
                        font = painter.font(); font.setPointSize(40); font.setBold(True); painter.setFont(font)
                        painter.drawText(10, 10, 80, 80, Qt.AlignCenter, "!")
                        painter.end()

                item.setData(Qt.UserRole + 1, color_pixmap)
                item.setData(Qt.UserRole + 2, gray_pixmap)
                item.setIcon(QIcon(gray_pixmap))
                
                self.list_widget.addItem(item)

    # --- Navigation Logic ---
    def on_tree_clicked(self, index):
        path = self.dir_model.filePath(index)
        self.load_directory(path)

    def pin_folder(self):
        if self.current_dir == "Computer": return
        for i in range(self.fav_list.count()):
            if self.fav_list.item(i).data(32) == self.current_dir: return
        item = QListWidgetItem("📁 " + os.path.basename(self.current_dir))
        item.setData(32, self.current_dir)
        self.fav_list.addItem(item)

    def on_fav_clicked(self, item):
        self.load_directory(item.data(32))

    def fav_context_menu(self, pos):
        item = self.fav_list.itemAt(pos)
        if not item: return
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background: #2b2b2b; color: #dfdfdf; border: 1px solid #555; } QMenu::item:selected { background: #5285a6; }")
        act_rem = menu.addAction("Remove from Favorites")
        action = menu.exec_(self.fav_list.mapToGlobal(pos))
        if action == act_rem:
            self.fav_list.takeItem(self.fav_list.row(item))

    def go_home(self): self.load_drives()
    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.load_directory(self.history[self.history_index], False)
    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.load_directory(self.history[self.history_index], False)
    def go_up(self):
        if self.current_dir == "Computer": return
        parent_dir = os.path.dirname(self.current_dir)
        if parent_dir and parent_dir != self.current_dir: self.load_directory(parent_dir)
        else: self.load_drives()
    def path_entered(self):
        path = self.path_edit.text()
        if path.lower() in ["my computer", "computer"]: self.load_drives()
        elif os.path.exists(path) and os.path.isdir(path): self.load_directory(path)

    # --- File Management ---
    def new_folder(self):
        if self.current_dir == "Computer": return
        text, ok = QInputDialog.getText(self, "New Folder", "Folder Name:")
        if ok and text:
            new_path = os.path.join(self.current_dir, text)
            if not os.path.exists(new_path):
                os.mkdir(new_path)
                self.load_directory(self.current_dir, False)

    def delete_selected(self):
        if self.current_dir == "Computer": return
        selected = self.list_widget.selectedItems()
        if not selected: return
        
        res = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete {len(selected)} items?", QMessageBox.Yes | QMessageBox.No)
        if res == QMessageBox.Yes:
            for item in selected:
                path = item.data(32)
                if os.path.exists(path):
                    if os.path.isdir(path): shutil.rmtree(path)
                    else:
                        os.remove(path)
                        png_path = path.replace(".json", ".png")
                        if os.path.exists(png_path): os.remove(png_path)
                        if path.endswith(".json"):
                            img_folder = path.replace(".json", "")
                            if os.path.exists(img_folder) and os.path.isdir(img_folder): shutil.rmtree(img_folder)
            self.load_directory(self.current_dir, False)

    def on_item_double_clicked(self, item):
        if item.data(33) == "folder": self.load_directory(item.data(32))
        else:
            if item.data(34): self.accept() # Only accept if valid ARTools file!

    def on_selection_changed(self):
        selected = self.list_widget.selectedItems()
        if not selected:
            self.preview_label.setText("No Preview")
            self.preview_label.setPixmap(QPixmap())
            self.stack_info.setCurrentWidget(self.info_widget)
            self.info_label.setText("")
            return
            
        item = selected[-1] 
        file_path = item.data(32)
        is_folder = item.data(33) == "folder"
        is_valid = item.data(34)
        
        if is_folder:
            self.preview_label.setText("Folder")
            self.preview_label.setPixmap(QPixmap())
            self.stack_info.setCurrentWidget(self.info_widget)
            display_name = os.path.basename(file_path.rstrip('/\\')) or file_path
            self.info_label.setText(f"<h3 style='color:#5285a6; margin-bottom:4px;'>{display_name}</h3><b>Type:</b> Directory")
            return
            
        color_pix = item.data(Qt.UserRole + 1)
        if color_pix: self.preview_label.setPixmap(color_pix.scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else: self.preview_label.setPixmap(QPixmap())
            
        if not os.path.exists(file_path):
            self.stack_info.setCurrentWidget(self.error_widget)
            self.error_label.setText("<b>⚠️ Missing File</b><br><br>File unavailable or deleted.")
            return

        if not is_valid:
            self.stack_info.setCurrentWidget(self.error_widget)
            self.error_label.setText("<b>⚠️ Not Compatible</b><br><br>This file is not a valid ARTools layout structure.")
            return
            
        self.stack_info.setCurrentWidget(self.info_widget)
        size_kb = os.path.getsize(file_path) / 1024.0
        info_text = f"<h3 style='color:#5285a6; margin-bottom:4px;'>{os.path.basename(file_path)}</h3>"
        info_text += f"<span style='color:#aaa;'><b>Size:</b> {size_kb:.1f} KB</span><br><br>"
        
        with open(file_path, "r") as f:
            data = json.load(f)
            char_name = data.get("name", "Unknown Rig")
            info_text += f"<b>Rig Name:</b> <span style='color:#fff;'>{char_name}</span><br>"
            
            meta = data.get("_metadata", {})
            if meta:
                info_text += f"<b>Author:</b> <span style='color:#fff;'>{meta.get('author', 'Unknown')}</span><br>"
                info_text += f"<b>Saved:</b> <span style='color:#fff;'>{meta.get('timestamp', 'Unknown')}</span><br><br>"
                info_text += f"<b>Shapes:</b> <span style='color:#4CAF50;'>{meta.get('shape_count', 0)}</span><br>"
                info_text += f"<b>Scripts:</b> <span style='color:#ff79c6;'>{meta.get('script_count', 0)}</span><br>"
        
        self.info_label.setText(info_text)

    def get_selected_files(self):
        return [item.data(32) for item in self.list_widget.selectedItems() if item.data(33) == "file" and item.data(34)]