import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QLineEdit, QSlider, QLabel
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize, Qt

class TemplatesBrowser(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Template Browser")
        self.resize(700, 500)
        
        self.layout = QVBoxLayout(self)
        
        self.top_layout = QHBoxLayout()
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search templates...")
        self.search_bar.textChanged.connect(self.update_filter)
        self.top_layout.addWidget(self.search_bar)
        
        self.size_label = QLabel("Thumbnail Size:")
        self.top_layout.addWidget(self.size_label)
        
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(64, 400)
        self.size_slider.setValue(200)
        self.size_slider.setFixedWidth(150)
        self.size_slider.valueChanged.connect(self.update_icon_size)
        self.top_layout.addWidget(self.size_slider)
        
        self.layout.addLayout(self.top_layout)
        
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setIconSize(QSize(200, 200))
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.itemDoubleClicked.connect(self.on_item_clicked)
        self.layout.addWidget(self.list_widget)
        
        self.scan_templates()

    def scan_templates(self):
        base_dir = os.path.dirname(__file__)
        template_dir = os.path.join(base_dir, "templates")
        if not os.path.exists(template_dir): return
        
        for root, _, files in os.walk(template_dir):
            for f in files:
                if f.endswith(".json"):
                    item = QListWidgetItem(f.replace(".json", ""))
                    icon_path = os.path.join(root, f.replace(".json", ".png"))
                    
                    if os.path.exists(icon_path):
                        item.setIcon(QIcon(icon_path))
                        
                    item.setToolTip(f"Category: {os.path.basename(root)}")
                    item.setData(32, os.path.join(root, f))
                    self.list_widget.addItem(item)

    def update_icon_size(self, val):
        self.list_widget.setIconSize(QSize(val, val))

    def update_filter(self, text):
        search_lower = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            is_match = search_lower in item.text().lower()
            item.setHidden(not is_match)

    def on_item_clicked(self, item):
        self.accept()