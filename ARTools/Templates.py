import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                               QListWidgetItem, QLineEdit, QSlider, QLabel, 
                               QTabWidget, QPushButton, QStyledItemDelegate, QStyle)
from PySide6.QtGui import QIcon, QPixmap, QImage, QPainter, QColor
from PySide6.QtCore import QSize, Qt

class ThumbnailDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        is_active = (option.state & QStyle.State_MouseOver) or (option.state & QStyle.State_Selected)
        pixmap = index.data(Qt.UserRole + 1) if is_active else index.data(Qt.UserRole + 2)
        if pixmap:
            option.icon = QIcon(pixmap)

class TemplatesBrowser(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ARTools - Template Browser")
        self.resize(750, 550)
        self.setStyleSheet("QDialog { background-color: #1e1e1e; color: #dfdfdf; } QLabel { color: #dfdfdf; }")
        
        self.layout = QVBoxLayout(self)
        self.top_layout = QHBoxLayout()
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search templates...")
        self.search_bar.setStyleSheet("background-color: #2b2b2b; border: 1px solid #444; padding: 4px;")
        self.search_bar.textChanged.connect(self.update_filter)
        self.top_layout.addWidget(self.search_bar)
        
        self.top_layout.addWidget(QLabel("Thumbnail Size:"))
        
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(64, 400)
        self.size_slider.setValue(200)
        self.size_slider.setFixedWidth(150)
        self.size_slider.valueChanged.connect(self.update_icon_size)
        self.top_layout.addWidget(self.size_slider)
        
        self.layout.addLayout(self.top_layout)
        
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)
        self.list_widgets = []
        
        self.scan_templates()

        self.bottom_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load Selected Templates")
        self.btn_load.setStyleSheet("background-color: #5285a6; font-weight: bold; padding: 6px 15px;")
        self.btn_load.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.btn_load)
        self.bottom_layout.addWidget(self.btn_cancel)
        self.layout.addLayout(self.bottom_layout)

    def scan_templates(self):
        from .preferences import PrefManager
        template_dir = PrefManager().get("path_templates")
        
        # Fallback to the default internal directory if the user path is invalid/empty
        if not template_dir or not os.path.exists(template_dir):
            base_dir = os.path.dirname(__file__)
            template_dir = os.path.join(base_dir, "templates")
            
        if not os.path.exists(template_dir): return
        
        for folder_name in os.listdir(template_dir):
            folder_path = os.path.join(template_dir, folder_name)
            if not os.path.isdir(folder_path): continue
            
            list_widget = QListWidget()
            list_widget.setViewMode(QListWidget.IconMode)
            list_widget.setIconSize(QSize(self.size_slider.value(), self.size_slider.value()))
            list_widget.setResizeMode(QListWidget.Adjust)
            list_widget.setSelectionMode(QListWidget.ExtendedSelection)
            list_widget.setItemDelegate(ThumbnailDelegate(list_widget))
            list_widget.setMouseTracking(True)
            list_widget.viewport().setAttribute(Qt.WA_Hover)
            list_widget.setStyleSheet("QListWidget { background: #222; border: 1px solid #333; } QListWidget::item:selected { background: #5285a6; border-radius: 4px; }")
            list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
            
            self.tab_widget.addTab(list_widget, folder_name)
            self.list_widgets.append(list_widget)
            
            for f in os.listdir(folder_path):
                if f.endswith(".json"):
                    item = QListWidgetItem(f.replace(".json", ""))
                    icon_path = os.path.join(folder_path, f.replace(".json", ".png"))
                    
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
                        
                    item.setToolTip(f"Category: {folder_name}")
                    item.setData(32, os.path.join(folder_path, f))
                    list_widget.addItem(item)

    def update_icon_size(self, val):
        for lw in self.list_widgets:
            lw.setIconSize(QSize(val, val))

    def update_filter(self, text):
        search_lower = text.lower()
        for lw in self.list_widgets:
            for i in range(lw.count()):
                item = lw.item(i)
                is_match = search_lower in item.text().lower()
                item.setHidden(not is_match)

    def get_selected_files(self):
        files = []
        for lw in self.list_widgets:
            for item in lw.selectedItems():
                files.append(item.data(32))
        return files
    
    def on_item_double_clicked(self, item):
        self.accept()