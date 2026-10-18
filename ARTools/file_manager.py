# ARTools/file_manager.py
import os
import json
import shutil
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, 
                               QLineEdit, QSlider, QLabel, QPushButton, QSplitter, QWidget, 
                               QStyledItemDelegate, QStyle, QMessageBox, QInputDialog)
from PySide6.QtGui import QIcon, QPixmap, QImage, QPainter, QColor
from PySide6.QtCore import QSize, QDir, Qt

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
        self.setWindowTitle("ARTools Vault - Open Layout")
        self.resize(900, 600)
        self.setStyleSheet("QDialog { background-color: #1e1e1e; color: #dfdfdf; } QLabel { color: #dfdfdf; }")
        
        self.history = []
        self.history_index = -1
        
        self.layout = QVBoxLayout(self)
        
        # 1. PATH MAPPER (Top Nav)
        self.nav_layout = QHBoxLayout()
        
        self.btn_back = QPushButton("←")
        self.btn_back.setFixedWidth(30)
        self.btn_back.clicked.connect(self.go_back)
        
        self.btn_forward = QPushButton("→")
        self.btn_forward.setFixedWidth(30)
        self.btn_forward.clicked.connect(self.go_forward)
        
        self.btn_up = QPushButton("↑")
        self.btn_up.setFixedWidth(30)
        self.btn_up.clicked.connect(self.go_up)
        
        self.btn_home = QPushButton("🏠")
        self.btn_home.setFixedWidth(30)
        self.btn_home.clicked.connect(self.go_home)
        
        self.path_edit = QLineEdit()
        self.path_edit.setStyleSheet("background-color: #2b2b2b; border: 1px solid #444; padding: 4px;")
        self.path_edit.returnPressed.connect(self.path_entered)
        
        self.btn_new_dir = QPushButton("New Folder")
        self.btn_new_dir.clicked.connect(self.new_folder)
        
        self.btn_del = QPushButton("Delete")
        self.btn_del.setStyleSheet("background-color: #6b2e2e;")
        self.btn_del.clicked.connect(self.delete_selected)
        
        self.nav_layout.addWidget(self.btn_back)
        self.nav_layout.addWidget(self.btn_forward)
        self.nav_layout.addWidget(self.btn_up)
        self.nav_layout.addWidget(self.btn_home)
        self.nav_layout.addWidget(self.path_edit)
        self.nav_layout.addWidget(self.btn_new_dir)
        self.nav_layout.addWidget(self.btn_del)
        
        self.layout.addLayout(self.nav_layout)
        
        # 2. MAIN SPLITTER
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Left: List Widget
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_widget.setItemDelegate(ThumbnailDelegate(self.list_widget))
        self.list_widget.setMouseTracking(True)
        self.list_widget.viewport().setAttribute(Qt.WA_Hover)
        self.list_widget.setStyleSheet("QListWidget { background: #222; border: 1px solid #333; } QListWidget::item:selected { background: #5285a6; border-radius: 4px; }")
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        
        self.splitter.addWidget(self.list_widget)
        
        # Right: Inspector
        self.inspector = QWidget()
        self.inspector_layout = QVBoxLayout(self.inspector)
        self.inspector_layout.setContentsMargins(10, 0, 0, 0)
        
        self.preview_label = QLabel("No Preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedSize(250, 250)
        self.preview_label.setStyleSheet("background: #111; border: 1px solid #444; border-radius: 6px;")
        
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.info_label.setStyleSheet("font-size: 13px; line-height: 1.5;")
        
        self.inspector_layout.addWidget(self.preview_label)
        self.inspector_layout.addWidget(self.info_label)
        self.inspector_layout.addStretch()
        
        self.splitter.addWidget(self.inspector)
        self.splitter.setSizes([600, 280])
        self.layout.addWidget(self.splitter)
        
        # 3. BOTTOM ACTIONS
        self.bottom_layout = QHBoxLayout()
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(64, 400)
        self.size_slider.setValue(150)
        self.size_slider.setFixedWidth(150)
        self.size_slider.valueChanged.connect(self.update_icon_size)
        
        self.btn_open = QPushButton("Open Selected")
        self.btn_open.setStyleSheet("background-color: #5285a6; font-weight: bold; padding: 6px 15px;")
        self.btn_open.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.bottom_layout.addWidget(QLabel("Thumbnail Size:"))
        self.bottom_layout.addWidget(self.size_slider)
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.btn_open)
        self.bottom_layout.addWidget(self.btn_cancel)
        
        self.layout.addLayout(self.bottom_layout)
        
        self.update_icon_size(150)
        
        if not start_dir or not os.path.exists(start_dir):
            start_dir = os.path.expanduser("~")
        self.load_directory(start_dir)

    def load_directory(self, path, add_to_history=True):
        if path == "Computer":
            self.load_drives(add_to_history)
            return
            
        if not os.path.exists(path) or not os.path.isdir(path): return
        
        self.current_dir = os.path.normpath(path)
        self.path_edit.setText(self.current_dir)
        
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
        
        for f in sorted(os.listdir(self.current_dir)):
            file_path = os.path.join(self.current_dir, f)
            if os.path.isdir(file_path):
                item = QListWidgetItem("📁 " + f)
                item.setData(32, file_path)
                item.setData(33, "folder")
                self.list_widget.addItem(item)
                
        for f in sorted(os.listdir(self.current_dir)):
            file_path = os.path.join(self.current_dir, f)
            if os.path.isfile(file_path) and f.endswith(".json"):
                item = QListWidgetItem(f.replace(".json", ""))
                item.setData(32, file_path)
                item.setData(33, "file")
                
                icon_path = os.path.join(self.current_dir, f.replace(".json", ".png"))
                if os.path.exists(icon_path):
                    color_pixmap = QPixmap(icon_path).scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    gray_image = color_pixmap.toImage().convertToFormat(QImage.Format_Grayscale8)
                    gray_pixmap = QPixmap.fromImage(gray_image)
                    
                    item.setData(Qt.UserRole + 1, color_pixmap)
                    item.setData(Qt.UserRole + 2, gray_pixmap)
                    item.setIcon(QIcon(gray_pixmap))
                else:
                    # --- DYNAMIC PLACEHOLDER FOR MISSING IMAGES ---
                    fallback = QPixmap(400, 400)
                    fallback.fill(QColor("#2a2a2a"))
                    painter = QPainter(fallback)
                    painter.setPen(QColor("#333333"))
                    painter.drawRect(0, 0, 399, 399)
                    
                    painter.setPen(QColor("#666666"))
                    font = painter.font()
                    font.setPointSize(28)
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(fallback.rect(), Qt.AlignCenter, "JSON\nNO PREVIEW")
                    painter.end()
                    
                    item.setData(Qt.UserRole + 1, fallback)
                    item.setData(Qt.UserRole + 2, fallback)
                    item.setIcon(QIcon(fallback))
                    
                self.list_widget.addItem(item)

    def update_icon_size(self, val):
        self.list_widget.setIconSize(QSize(val, val))

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

    def go_home(self):
        self.load_drives()

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
        if parent_dir and parent_dir != self.current_dir:
            self.load_directory(parent_dir)
        else:
            self.load_drives()

    def path_entered(self):
        path = self.path_edit.text()
        if path.lower() in ["my computer", "computer"]:
            self.load_drives()
        elif os.path.exists(path) and os.path.isdir(path):
            self.load_directory(path)

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
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        # 1. Delete the JSON layout file
                        os.remove(path)
                        
                        # 2. Delete the Thumbnail PNG
                        png_path = path.replace(".json", ".png")
                        if os.path.exists(png_path): 
                            os.remove(png_path)
                            
                        # 3. Delete the associated Image Data Folder (where Poses/Backgrounds live)
                        if path.endswith(".json"):
                            img_folder = path.replace(".json", "")
                            if os.path.exists(img_folder) and os.path.isdir(img_folder):
                                shutil.rmtree(img_folder)
                                
            self.load_directory(self.current_dir, False)

    def on_item_double_clicked(self, item):
        if item.data(33) == "folder":
            self.load_directory(item.data(32))
        else:
            self.accept()

    def on_selection_changed(self):
        selected = self.list_widget.selectedItems()
        if not selected:
            self.preview_label.setText("No Preview")
            self.preview_label.setPixmap(QPixmap())
            self.info_label.setText("")
            return
            
        item = selected[-1] 
        file_path = item.data(32)
        is_folder = item.data(33) == "folder"
        
        if is_folder:
            self.preview_label.setText("Folder")
            self.preview_label.setPixmap(QPixmap())
            display_name = os.path.basename(file_path.rstrip('/\\')) or file_path
            self.info_label.setText(f"<h3 style='color:#5285a6; margin-bottom:4px;'>{display_name}</h3><b>Type:</b> Directory")
            return
        
        color_pix = item.data(Qt.UserRole + 1)
        if color_pix:
            self.preview_label.setPixmap(color_pix.scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.preview_label.setText("No Preview")
            self.preview_label.setPixmap(QPixmap())
            
        if not os.path.exists(file_path):
            self.info_label.setText(f"<h3 style='color:#5285a6; margin-bottom:4px;'>{os.path.basename(file_path)}</h3><span style='color:#ff5555;'>File unavailable or deleted.</span>")
            return
            
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
        return [item.data(32) for item in self.list_widget.selectedItems() if item.data(33) == "file"]