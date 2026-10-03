import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QLineEdit, QSlider, QLabel, QTabWidget
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
        
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)
        self.list_widgets = []
        
        self.scan_templates()

    def scan_templates(self):
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
            list_widget.itemDoubleClicked.connect(self.on_item_clicked)
            
            self.tab_widget.addTab(list_widget, folder_name)
            self.list_widgets.append(list_widget)
            
            for f in os.listdir(folder_path):
                if f.endswith(".json"):
                    item = QListWidgetItem(f.replace(".json", ""))
                    icon_path = os.path.join(folder_path, f.replace(".json", ".png"))
                    
                    if os.path.exists(icon_path):
                        item.setIcon(QIcon(icon_path))
                        
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

    def on_item_clicked(self, item):
        self.list_widget = item.listWidget() 
        self.accept()