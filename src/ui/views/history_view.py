from PySide6.QtWidgets import QWidget, QVBoxLayout, QHeaderView, QTableWidgetItem
from PySide6.QtCore import Qt
from qfluentwidgets import TitleLabel, TableWidget, PrimaryPushButton, FluentIcon, InfoBar, InfoBarPosition
from src.core.history_manager import history_manager

class HistoryView(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(" ", "-"))
        
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(40, 40, 40, 40)
        self.v_layout.setSpacing(20)
        
        # Header
        self.title_label = TitleLabel("İndirme Geçmişi", self)
        self.v_layout.addWidget(self.title_label)
        
        # Toolbar
        self.clear_btn = PrimaryPushButton("Geçmişi Temizle", self, FluentIcon.DELETE)
        self.clear_btn.setFixedWidth(160)
        self.clear_btn.clicked.connect(self.clear_history)
        self.v_layout.addWidget(self.clear_btn, 0, Qt.AlignRight)
        
        # Table
        self.table = TableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Dosya Adı", "Tarih", "Bağlantı (URL)"])
        self.table.verticalHeader().hide()
        self.table.setWordWrap(False)
        
        # Calculate width to look good
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch) # Title stretches
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents) # Date fixed
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch) # URL stretches
        
        self.v_layout.addWidget(self.table)
        
        # Connect Signals
        history_manager.history_changed.connect(self.load_data)
        
        # Initial Load
        self.load_data()

    def load_data(self):
        data = history_manager.get_history()
        self.table.setRowCount(len(data))
        
        for i, entry in enumerate(data):
            self.table.setItem(i, 0, QTableWidgetItem(entry.get('title', '-')))
            self.table.setItem(i, 1, QTableWidgetItem(entry.get('date', '-')))
            self.table.setItem(i, 2, QTableWidgetItem(entry.get('url', '-')))

    def clear_history(self):
        history_manager.clear_history()
        
        InfoBar.success(
            title='Başarılı',
            content="Geçmiş temizlendi.",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self.window()
        )
