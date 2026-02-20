import os
import subprocess
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QButtonGroup, 
                               QApplication, QStackedWidget, QListWidgetItem, QListWidget, QMenu)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCursor

# Import Fluent Widgets
from qfluentwidgets import (SubtitleLabel, TitleLabel, LineEdit, PrimaryPushButton, PushButton,
                            ProgressBar, BodyLabel, InfoBar, InfoBarPosition, RadioButton, 
                            ComboBox, CheckBox, FluentIcon, MessageBoxBase, CaptionLabel,
                            CardWidget, StrongBodyLabel, SpinBox, CalendarPicker)
from PySide6.QtCore import QDate
from src.version import VERSION

# Import Core Logic
from src.core.downloader import DownloadWorker
from src.core.gallery_worker import GalleryWorker
from src.detector import get_url_type
from src.settings_manager import get_settings, get_default_download_folder
from src.core.history_manager import history_manager
from src.core.updater import AutoUpdater


class PlaylistDialog(MessageBoxBase):
    """ Custom Dialog for Playlist Selection """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("Oynatma Listesi Tespit Edildi", self)
        self.contentLabel = BodyLabel("Bu bağlantı bir oynatma listesi içeriyor.\nNasıl indirmek istersiniz?", self)
        
        # Configure Existing Buttons (MessageBoxBase adds yes/cancel by default)
        self.yesButton.setText("Tüm Listeyi İndir")
        self.cancelButton.setText("İptal")
        
        # Add Middle Button
        self.singleButton = PushButton("Sadece Bunu İndir", self)
        self.buttonLayout.insertWidget(1, self.singleButton)
        
        # Layout Config (View Layout needs content)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.contentLabel)
        
        # Connections (Reconnect to our logic)
        self.yesButton.clicked.disconnect()
        self.cancelButton.clicked.disconnect()
        
        self.yesButton.clicked.connect(self._on_yes)
        self.singleButton.clicked.connect(self._on_single)
        self.cancelButton.clicked.connect(self._on_cancel)
        
        self.result_mode = None # True: Playlist, False: Single, None: Cancel

    def _on_yes(self):
        self.result_mode = True
        self.accept()
        
    def _on_single(self):
        self.result_mode = False
        self.accept()
        
    def _on_cancel(self):
        self.result_mode = None
        self.reject()

class HomeView(QWidget):
    """
    Dashboard View:
    - URL Input
    - Format Selection (Radio Buttons)
    - Quality Selection (ComboBox)
    - Download Button
    - Progress visualization
    """
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(" ", "-"))
        
        # Main Layout
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(10, 10, 10, 10)
        self.v_layout.setSpacing(10)

        # Container for the central form to limit width (Responsive)
        self.form_container = QWidget()
        self.form_container.setMaximumWidth(900) 
        self.form_layout = QVBoxLayout(self.form_container)
        self.form_layout.setContentsMargins(0, 0, 0, 0) 
        self.form_layout.setSpacing(12) # Relaxed spacing
        self.form_layout.setSizeConstraint(QVBoxLayout.SetMinimumSize) # Allow resizing based on content

        
        # 0. Removed Top Bar to save space
        
        # 1. Header
        self.title_label = TitleLabel("ORBIT", self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("""
            QLabel {
                font-family: 'Segoe UI Black', 'Arial Black', sans-serif;
                font-size: 26px;
                font-weight: bold;
                background: transparent;
                margin-bottom: 2px;
                margin-top: 10px;
            }
        """)
        self.form_layout.addWidget(self.title_label, 0, Qt.AlignCenter)

        # Subtitle
        self.subtitle_label = BodyLabel("Gelişmiş Medya İndirici", self)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #e0e0e0; margin-bottom: 2px;")
        self.form_layout.addWidget(self.subtitle_label, 0, Qt.AlignCenter)

        # Site List (Slogan)
        self.slogan_label = CaptionLabel("YouTube • Instagram • TikTok • Twitch • Spotify", self)
        self.slogan_label.setAlignment(Qt.AlignCenter)
        self.slogan_label.setTextColor("#808080", "#808080")
        self.slogan_label.setStyleSheet("font-size: 10px; font-weight: 400; margin-top: 0px; margin-bottom: 10px;")
        self.form_layout.addWidget(self.slogan_label, 0, Qt.AlignCenter)

        # 2. Input Field & Paste Button
        self.input_layout = QHBoxLayout()
        self.input_layout.setSpacing(10)

        # Left Buttons Container (Hidden by default)
        self.left_buttons_container = QWidget()
        self.left_buttons_layout = QVBoxLayout(self.left_buttons_container)
        self.left_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.left_buttons_layout.setSpacing(5)
        self.left_buttons_layout.setAlignment(Qt.AlignTop)

        self.delete_btn = PushButton("Sil", self, FluentIcon.REMOVE)
        self.delete_btn.setToolTip("Seçili Satırı Sil")
        self.delete_btn.setFixedWidth(115)
        self.delete_btn.setFixedHeight(36)
        self.delete_btn.clicked.connect(self.delete_selected_item)

        self.clear_btn = PushButton("Temizle", self, FluentIcon.DELETE)
        self.clear_btn.setToolTip("Tüm Listeyi Temizle")
        self.clear_btn.setFixedWidth(115)
        self.clear_btn.setFixedHeight(36)
        self.clear_btn.clicked.connect(self.clear_batch_list)

        self.left_buttons_layout.addWidget(self.delete_btn)
        self.left_buttons_layout.addWidget(self.clear_btn)
        
        self.left_buttons_container.hide() # Start hidden
        self.input_layout.addWidget(self.left_buttons_container)

        # Stack for Single vs Multi input
        self.input_stack = QStackedWidget(self)
        self.input_stack.setMinimumHeight(42)
        self.input_stack.setMaximumHeight(42) # Start with single line height
        self.input_stack.setMinimumWidth(400) # Ensure URL input is wide enough

        # A. Single Line
        self.url_input = LineEdit(self)
        self.url_input.setPlaceholderText("Linki buraya yapıştır...")
        self.url_input.setClearButtonEnabled(True)
        self.input_stack.addWidget(self.url_input)
        
        # B. Multi Line (List)
        self.batch_list = QListWidget(self)
        self.batch_list.setAlternatingRowColors(False) 
        self.batch_list.setStyleSheet("""
            QListWidget {
                background-color: #202020;
                border: 1px solid #404040;
                border-radius: 6px;
                color: #f0f0f0;
                font-size: 12px;
                outline: none;
            }
            QListWidget::item {
                height: 30px;
                padding-left: 8px;
                border-bottom: 1px solid #2d2d2d;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)
        self.batch_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.batch_list.customContextMenuRequested.connect(self.show_list_context_menu)
        
        self.input_stack.addWidget(self.batch_list)

        # Action Buttons Container (Vertical layout for buttons to stay at top)
        self.buttons_layout = QVBoxLayout()
        self.buttons_layout.setSpacing(5)
        self.buttons_layout.setAlignment(Qt.AlignTop)
        
        self.paste_btn = PushButton("Yapıştır", self, FluentIcon.PASTE)
        self.paste_btn.setToolTip("Panodan Yapıştır")
        self.paste_btn.setFixedWidth(115)
        self.paste_btn.setFixedHeight(36)
        self.paste_btn.clicked.connect(self.paste_clipboard)
        
        self.batch_btn = PushButton("Toplu İndir", self, FluentIcon.LIBRARY)
        self.batch_btn.setToolTip("Toplu İndirme Modu")
        self.batch_btn.setCheckable(True)
        self.batch_btn.setFixedWidth(115) 
        self.batch_btn.setFixedHeight(36)
        self.batch_btn.clicked.connect(self.toggle_batch_mode)
        
        self.buttons_layout.addWidget(self.paste_btn)
        self.buttons_layout.addWidget(self.batch_btn)

        self.input_layout.addWidget(self.input_stack, 1) 
        self.input_layout.addLayout(self.buttons_layout)
        
        self.form_layout.addLayout(self.input_layout)

        # 2.5 Format Selection
        self.radio_layout = QHBoxLayout()
        self.radio_layout.setSpacing(20) 
        self.radio_layout.setAlignment(Qt.AlignCenter)

        self.radio_mp4 = RadioButton("Video (MP4)", self)
        self.radio_mp3 = RadioButton("Ses (MP3)", self)
        self.radio_m4a = RadioButton("Ses (M4A)", self)
        
        self.radio_mp4.setChecked(True)

        self.radio_layout.addWidget(self.radio_mp4)
        self.radio_layout.addWidget(self.radio_mp3)
        self.radio_layout.addWidget(self.radio_m4a)
        
        self.format_group = QButtonGroup(self)
        self.format_group.addButton(self.radio_mp4, 0)
        self.format_group.addButton(self.radio_mp3, 1)
        self.format_group.addButton(self.radio_m4a, 2)
        
        self.format_group.buttonToggled.connect(self.update_format_options)

        self.form_layout.addLayout(self.radio_layout)

        # 2.5.5 Gallery Type Selection (Hidden by default, replaces format selection in Gallery Mode)
        self.gallery_type_widget = QWidget()
        self.gallery_type_layout = QHBoxLayout(self.gallery_type_widget)
        self.gallery_type_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery_type_layout.setSpacing(20)
        self.gallery_type_layout.setAlignment(Qt.AlignCenter)
        
        self.radio_gal_all = RadioButton("Tümü", self)
        self.radio_gal_photo = RadioButton("Fotoğraf", self)
        self.radio_gal_video = RadioButton("Video", self)
        
        self.radio_gal_all.setChecked(True)
        
        self.gallery_type_group = QButtonGroup(self)
        self.gallery_type_group.addButton(self.radio_gal_all, 0)
        self.gallery_type_group.addButton(self.radio_gal_photo, 1)
        self.gallery_type_group.addButton(self.radio_gal_video, 2)
        
        self.gallery_type_layout.addWidget(self.radio_gal_all)
        self.gallery_type_layout.addWidget(self.radio_gal_photo)
        self.gallery_type_layout.addWidget(self.radio_gal_video)
        
        self.form_layout.addWidget(self.gallery_type_widget)
        self.gallery_type_widget.hide()

        # 2.6 Quality Selection
        self.quality_combo = ComboBox(self)
        self.quality_combo.setFixedWidth(180)
        self.quality_combo.setFixedHeight(30)
        self.form_layout.addWidget(self.quality_combo, 0, Qt.AlignCenter)
        
        # 2.7 Checkbox Row (Subtitle + Trim side by side)
        self.checkbox_row = QHBoxLayout()
        self.checkbox_row.setSpacing(40)
        self.checkbox_row.setAlignment(Qt.AlignCenter)
        
        self.sub_check = CheckBox("Altyazı İndir", self)
        self.sub_check.stateChanged.connect(self.toggle_sub_options)
        
        self.trim_check = CheckBox("Belli bir kısmını indir (Kırp/Kes)", self)
        self.trim_check.stateChanged.connect(self.toggle_trim_options)
        
        self.checkbox_row.addWidget(self.sub_check)
        self.checkbox_row.addWidget(self.trim_check)
        
        self.form_layout.addLayout(self.checkbox_row)

        # Subtitle Options
        self.sub_options_widget = QWidget()
        self.sub_layout = QHBoxLayout(self.sub_options_widget)
        self.sub_layout.setContentsMargins(0, 0, 0, 0)
        self.sub_layout.setSpacing(10)
        
        self.sub_lang_combo = ComboBox(self)
        self.sub_lang_combo.addItems(["Türkçe", "İngilizce", "Tüm Diller"])
        self.sub_lang_combo.setFixedWidth(130)
        
        self.sub_mode_combo = ComboBox(self)
        self.sub_mode_combo.addItems(["Videoya Göm", "Ayrı Dosya (.srt)"])
        self.sub_mode_combo.setFixedWidth(130)

        self.sub_layout.addWidget(self.sub_lang_combo)
        self.sub_layout.addWidget(self.sub_mode_combo)
        
        self.form_layout.addWidget(self.sub_options_widget, 0, Qt.AlignCenter)
        self.sub_options_widget.hide()

        # Trim Options
        self.trim_options_widget = QWidget()
        self.trim_layout = QHBoxLayout(self.trim_options_widget)
        self.trim_layout.setContentsMargins(0, 0, 0, 0)
        self.trim_layout.setSpacing(15) 

        self.start_group_layout = QVBoxLayout()
        self.start_group_layout.setSpacing(2)
        self.start_label = BodyLabel("Başlangıç", self)
        self.start_label.setAlignment(Qt.AlignCenter)
        
        self.start_time_input = LineEdit(self)
        self.start_time_input.setInputMask("00:00:00")
        self.start_time_input.setText("00:00:00")
        self.start_time_input.setFixedWidth(100)
        self.start_time_input.setAlignment(Qt.AlignCenter)
        
        self.start_group_layout.addWidget(self.start_label, 0, Qt.AlignCenter)
        self.start_group_layout.addWidget(self.start_time_input, 0, Qt.AlignCenter)

        self.end_group_layout = QVBoxLayout()
        self.end_group_layout.setSpacing(2)
        self.end_label = BodyLabel("Bitiş", self)
        self.end_label.setAlignment(Qt.AlignCenter)

        self.end_time_input = LineEdit(self)
        self.end_time_input.setInputMask("00:00:00")
        self.end_time_input.setText("00:00:00")
        self.end_time_input.setFixedWidth(100)
        self.end_time_input.setAlignment(Qt.AlignCenter)
        
        self.end_group_layout.addWidget(self.end_label, 0, Qt.AlignCenter)
        self.end_group_layout.addWidget(self.end_time_input, 0, Qt.AlignCenter)

        self.trim_sep = BodyLabel("➜", self)

        self.trim_layout.addLayout(self.start_group_layout)
        self.trim_layout.addWidget(self.trim_sep)
        self.trim_layout.addLayout(self.end_group_layout)

        self.form_layout.addWidget(self.trim_options_widget, 0, Qt.AlignCenter)
        self.trim_options_widget.hide()

        # 2.8 Gallery Options Card (Hidden by default)
        # 2.8 Gallery Options Card (Enriched)
        self.gallery_card = CardWidget(self)
        self.gallery_card_layout = QVBoxLayout(self.gallery_card)
        self.gallery_card_layout.setContentsMargins(16, 16, 16, 16)
        self.gallery_card_layout.setSpacing(15) # Increased spacing
        
        # Header
        self.gallery_title = StrongBodyLabel("Galeri Seçenekleri", self.gallery_card)
        self.gallery_card_layout.addWidget(self.gallery_title)
        
        # Limit / Range Section
        self.range_layout = QHBoxLayout()
        self.range_layout.setSpacing(10)
        
        self.range_mode_combo = ComboBox(self.gallery_card)
        self.range_mode_combo.addItems(["Tüm Galeriyi İndir", "Son X Gönderi (En Yeni)", "Belirli Aralık"])
        self.range_mode_combo.setFixedWidth(160)
        self.range_mode_combo.currentIndexChanged.connect(self.update_gallery_ui)
        
        # Input for "X" (Shared by Newest/Oldest)
        self.limit_spin = SpinBox(self.gallery_card)
        self.limit_spin.setRange(1, 10000)
        self.limit_spin.setValue(10)
        self.limit_spin.setFixedWidth(140)
        self.limit_spin.hide()
        
        # Inputs for "Range" (Start - End)
        self.range_start_spin = SpinBox(self.gallery_card)
        self.range_start_spin.setRange(1, 10000)
        self.range_start_spin.setValue(1)
        self.range_start_spin.setFixedWidth(140)
        self.range_start_spin.hide()
        
        self.range_sep = BodyLabel("-", self.gallery_card)
        self.range_sep.hide()
        
        self.range_end_spin = SpinBox(self.gallery_card)
        self.range_end_spin.setRange(1, 10000)
        self.range_end_spin.setValue(10)
        self.range_end_spin.setFixedWidth(140)
        self.range_end_spin.hide()
        
        self.range_layout.addWidget(self.range_mode_combo)
        self.range_layout.addWidget(self.limit_spin)
        self.range_layout.addWidget(self.range_start_spin)
        self.range_layout.addWidget(self.range_sep)
        self.range_layout.addWidget(self.range_end_spin)
        self.range_layout.addStretch(1)
        
        self.gallery_card_layout.addLayout(self.range_layout)
        
        # Date Filter Section
        self.date_layout = QHBoxLayout()
        self.date_layout.setSpacing(10)
        
        self.date_check = CheckBox("Şu Tarihten İtibaren:", self.gallery_card)
        self.date_check.stateChanged.connect(self.update_gallery_ui)
        
        # Replaced CalendarPicker with fast LineEdit
        self.date_input = LineEdit(self.gallery_card)
        self.date_input.setPlaceholderText("YYYY-AA-GG")
        self.date_input.setInputMask("0000-00-00") # YYYY-MM-DD
        # Default value: 1 month ago
        self.date_input.setText(QDate.currentDate().addMonths(-1).toString("yyyy-MM-dd"))
        self.date_input.setFixedWidth(120)
        self.date_input.setAlignment(Qt.AlignCenter)
        self.date_input.setEnabled(False)

        self.date_layout.addWidget(self.date_check)
        self.date_layout.addWidget(self.date_input)
        self.date_layout.addStretch(1)
        
        self.gallery_card_layout.addLayout(self.date_layout)
        
        self.form_layout.addWidget(self.gallery_card)
        self.gallery_card.hide()

        # 2.9 Post-Download Action + Open Folder
        self.action_layout = QHBoxLayout()
        self.action_layout.setSpacing(10)
        self.action_layout.setAlignment(Qt.AlignCenter)
        
        self.action_label = BodyLabel("İşlem Sonrası:", self)
        self.action_combo = ComboBox(self)
        self.action_combo.addItems(["Bekle", "Programı Kapat", "Bilgisayarı Kapat"])
        self.action_combo.setFixedWidth(160)
        
        # Moved open folder button here
        self.open_folder_btn = PushButton("İndirilenler", self, FluentIcon.FOLDER)
        self.open_folder_btn.setFixedWidth(130)
        self.open_folder_btn.clicked.connect(self.open_downloads_folder)
        
        self.action_layout.addWidget(self.action_label)
        self.action_layout.addWidget(self.action_combo)
        self.action_layout.addWidget(self.open_folder_btn)
        
        self.form_layout.addLayout(self.action_layout)
        
        # Spacer before button
        self.form_layout.addSpacing(10)

        # 3. Action Button
        self.download_btn = PrimaryPushButton("Analiz Et ve İndir", self)
        self.download_btn.setFixedWidth(220)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: qlinear-gradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00d2df, stop:1 #0078d4);
                color: white;
                border: 1px solid #005a9e;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlinear-gradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00e5f2, stop:1 #008ae6);
                border: 1px solid #0078d4;
            }
            QPushButton:pressed {
                background: qlinear-gradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0078d4, stop:1 #005a9e);
                border: 1px solid #004578;
                padding-top: 2px;
                padding-left: 2px;
            }
        """)
        self.download_btn.setFixedHeight(40)
        self.download_btn.clicked.connect(self.start_download)
        self.form_layout.addWidget(self.download_btn, 0, Qt.AlignCenter)

        # 4. Progress Section (Hidden by default)
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        self.form_layout.addWidget(self.progress_bar)

        # 5. Status Log
        self.status_label = BodyLabel("İndirmeye hazır.", self)
        self.status_label.setTextColor('#707070', '#aaaaaa')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.form_layout.addWidget(self.status_label, 0, Qt.AlignCenter)

        # Add container to main layout (Center Horizontally, expand vertically)
        self.v_layout.addSpacing(0)
        self.v_layout.addWidget(self.form_container, 0, Qt.AlignHCenter)
        self.v_layout.addStretch(1)

        # Version Label (Subtle, Bottom Right)
        self.version_label = CaptionLabel(f"v{VERSION}", self)
        self.version_label.setTextColor('#505050', '#707070') # Very subtle grey
        self.version_label.setAlignment(Qt.AlignRight)
        self.v_layout.addWidget(self.version_label)

        # Init options based on default MP4 (Must be called after all widgets are created)
        self.update_format_options()

        # Worker Reference
        self.worker = None

        # Batch Queue State
        self.download_queue = []
        self.total_batch_count = 0
        self.current_batch_index = 0
        self.is_batch_mode = False

        # Auto Updater

        # Auto Updater
        self.updater = AutoUpdater()
        self.updater.update_started.connect(self.on_update_started)
        self.updater.update_finished.connect(self.on_update_finished)
        
        # Trigger update check after 2 seconds
        QTimer.singleShot(2000, self.updater.check_and_update)

        # Connect URL Change for Dynamic Mode
        self.url_input.textChanged.connect(self.on_url_changed)

    def on_url_changed(self, text):
        """Detects URL type and switches UI mode."""
        if not text:
            # Reset to default if empty
            # But maybe keep last state? No, default to Video makes sense.
            return

        mode = get_url_type(text)
        
        if mode == "gallery":
            # Switch to Gallery Mode
            self.gallery_card.show()
            
            # Hide Video-Specific Options
            self.radio_layout.setEnabled(False) 
            # Actually hide the layout items or the container?? 
            # radio_layout is a layout, can't hide directly easily without a widget wrapper.
            # But we can hide the widgets inside it.
            # Better way: Toggle visibility of the container widget if it existed.
            # Current implementation added radio_layout directly to form_layout.
            # Let's just Loop hide.
            for i in range(self.radio_layout.count()):
                w = self.radio_layout.itemAt(i).widget()
                if w: w.hide()
            
            # Show Gallery Types
            self.gallery_type_widget.show()
            
            self.quality_combo.hide()
            self.sub_check.hide()
            self.trim_check.hide()
            self.sub_options_widget.hide()
            self.trim_options_widget.hide()
            
            self.download_btn.setText("Galeriyi İndir")
            self.status_label.setText("Galeri modu aktif.")
            
        else: # Video
            # Switch to Video Mode
            self.gallery_card.hide()
            self.gallery_type_widget.hide()
            
            # Show/Enable Video Options
            self.radio_layout.setEnabled(True)
            for i in range(self.radio_layout.count()):
                w = self.radio_layout.itemAt(i).widget()
                if w: w.show()

            self.update_format_options() # Restore format/quality visibility logic
            self.trim_check.show()
            
            self.download_btn.setText("Analiz Et ve İndir")
            self.status_label.setText("İndirmeye hazır.")

    def on_update_started(self):
        self.status_label.setText("İndirme motoru güncelleniyor...")

    def on_update_finished(self, msg):
        self.status_label.setText("İndirmeye hazır.")
        # Optional: Show InfoBar if updated
        if "güncellendi" in msg:
            InfoBar.success(
                title='Otomatik Güncelleme',
                content=msg,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=3000,
                parent=self
            )

    def toggle_sub_options(self, state):
        if self.sub_check.isChecked():
            self.sub_options_widget.show()
        else:
            self.sub_options_widget.hide()

    def toggle_trim_options(self, state):
        if self.trim_check.isChecked():
            self.trim_options_widget.show()
        else:
            self.trim_options_widget.hide()

    def toggle_batch_mode(self):
        self.is_batch_mode = self.batch_btn.isChecked()
        
        if self.is_batch_mode:
            self.input_stack.setCurrentIndex(1) # Show Multi
            self.input_stack.setMinimumHeight(140) # Reduced height to keep download button visible
            self.input_stack.setMaximumHeight(140)
            self.batch_btn.setIcon(FluentIcon.REMOVE) # Icon to close batch
            self.batch_btn.setToolTip("Tekli Moda Dön")
            self.left_buttons_container.show() # Show Left Buttons
        else:
            self.input_stack.setCurrentIndex(0) # Show Single
            self.input_stack.setMinimumHeight(42)
            self.input_stack.setMaximumHeight(42)
            self.batch_btn.setIcon(FluentIcon.LIBRARY)
            self.batch_btn.setToolTip("Toplu İndirme Modu")
            self.left_buttons_container.hide() # Hide Left Buttons
        
        # Force layout recalculation
        self.input_stack.updateGeometry()
        self.form_container.updateGeometry()
        self.form_layout.invalidate()
        self.form_layout.activate()

    def show_list_context_menu(self, pos):
        menu = QMenu(self)
        
        delete_action = QAction("Seçileni Sil", self)
        delete_action.triggered.connect(self.delete_selected_item)
        
        clear_action = QAction("Listeyi Temizle", self)
        clear_action.triggered.connect(self.clear_batch_list)
        
        menu.addAction(delete_action)
        menu.addSeparator()
        menu.addAction(clear_action)
        
        menu.exec(QCursor.pos())

    def delete_selected_item(self):
        # Remove selected items
        for item in self.batch_list.selectedItems():
            self.batch_list.takeItem(self.batch_list.row(item))
            
        # Re-number items to keep them clean (1. 2. 3...)
        self.renumber_list()

    def clear_batch_list(self):
        self.batch_list.clear()

    def renumber_list(self):
        for i in range(self.batch_list.count()):
            item = self.batch_list.item(i)
            text = item.text()
            # If text has prefix like "1. https...", split and re-add
            parts = text.split(" ", 1)
            if len(parts) > 1:
                clean_text = parts[1]
                item.setText(f"{i+1}. {clean_text}")

    def paste_clipboard(self):
        text = QApplication.clipboard().text()
        if text:
            if self.is_batch_mode:
                # Add to ListWidget
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                start_idx = self.batch_list.count() + 1
                
                for i, line in enumerate(lines):
                    # Item with Icon
                    item_text = f"{start_idx + i}. {line}"
                    item = QListWidgetItem(FluentIcon.DATE_TIME.icon(), item_text) # Clock icon for waiting
                    self.batch_list.addItem(item)
            else:
                self.url_input.setText(text)

    def update_gallery_ui(self):
        # 1. Update Range UI
        mode = self.range_mode_combo.currentIndex()
        # 0: All
        # 1: En Yeni X
        # 2: En Eski X
        # 3: Range
        
        if mode == 1: # Son X (Limit)
            self.limit_spin.show()
            self.range_start_spin.hide()
            self.range_sep.hide()
            self.range_end_spin.hide()
        elif mode == 2: # Range
            self.limit_spin.hide()
            self.range_start_spin.show()
            self.range_sep.show()
            self.range_end_spin.show()
        else: # All
            self.limit_spin.hide()
            self.range_start_spin.hide()
            self.range_sep.hide()
            self.range_end_spin.hide()
            
        # 2. Update Date UI
        self.date_input.setEnabled(self.date_check.isChecked())

    def update_format_options(self):
        """Update UI options based on selected format."""
        if not self.format_group.checkedButton():
            return
            
        checked_id = self.format_group.checkedId()
        
        # 1. Update Quality Combo
        self.quality_combo.clear()
        
        if checked_id == 0: # MP4
            self.quality_combo.show()
            self.quality_combo.addItems(["Maksimum Kalite", "1080p Full HD", "720p HD", "480p SD"])
            self.quality_combo.setCurrentIndex(0)
            
            # Show Subtitles for Video
            self.sub_check.show()
            if self.sub_check.isChecked():
                self.sub_options_widget.show()
            
        elif checked_id == 1: # MP3
            self.quality_combo.show()
            self.quality_combo.addItems(["En İyi", "Standart", "Konuşma / Podcast"])
            self.quality_combo.setCurrentIndex(1) # Default to Standard
            
            # Hide Subtitles for Audio
            self.sub_check.hide()
            self.sub_options_widget.hide()
            
        else: # M4A
            self.quality_combo.hide()
            
            # Hide Subtitles for Audio
            self.sub_check.hide()
            self.sub_options_widget.hide()

    def start_download(self):
        # 0. Check if Shutdown Timer active -> Cancel Shutdown
        if hasattr(self, 'shutdown_timer') and self.shutdown_timer.isActive():
            self.cancel_download()
            return

        # 0.1 Check if already running -> Cancel
        if self.worker and self.worker.isRunning(): 
             self.cancel_download()
             return

        # 1. Gather URLs based on mode
        urls_to_process = []
        
        if self.is_batch_mode:
            # Read from ListWidget
            for i in range(self.batch_list.count()):
                item = self.batch_list.item(i)
                # Extract URL (Remove "1. " prefix)
                # Format: "12. https://..."
                text = item.text()
                parts = text.split(" ", 1)
                if len(parts) > 1:
                    urls_to_process.append(parts[1])
                else:
                    urls_to_process.append(text)
        else:
            url = self.url_input.text().strip()
            if url:
                urls_to_process = [url]

        if not urls_to_process:
            InfoBar.warning(
                title='Uyarı',
                content="Lütfen en az bir bağlantı girin.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )
            return

        # 2. Init Queue
        self.download_queue = urls_to_process
        self.total_batch_count = len(urls_to_process)
        self.current_batch_index = 0
        
        # 3. Start Queue Processing
        self.set_ui_busy(True)
        self.process_queue()

    def process_queue(self):
        """Picks the next URL from queue and starts worker."""
        if not self.download_queue:
            # Queue Finished!
            self.on_all_finished()
            return

        # Get next url
        next_url = self.download_queue.pop(0)
        
        # Update UI for Batch Item
        if self.is_batch_mode:
            item = self.batch_list.item(self.current_batch_index)
            item.setIcon(FluentIcon.SYNC.icon()) # Spinner/Sync icon for processing
            self.batch_list.scrollToItem(item)
            self.batch_list.setCurrentItem(item)

        self.current_batch_index += 1
        
        # Update Status
        if self.total_batch_count > 1:
            self.status_label.setText(f"Toplu İndirme: {self.current_batch_index}/{self.total_batch_count} başlatılıyor...")
        else:
            self.status_label.setText("İşlem başlatılıyor...")
            
        # Check Playlist (Only for single or first item to avoid spamming? 
        # Actually proper way is to check each, but for batch it might be annoying.
        # Let's assume for Batch mode we default to NO playlist to be safe, or ask?
        # User request implies per link check. But blocking UI in loop is tricky.
        # For now, let's implement the check inside _init_worker (or before it)
        
        # Determine Mode
        mode = get_url_type(next_url)
        
        if mode == "gallery":
            self._init_gallery_worker(next_url)
            return

        # We need to act differently based on user response, so we can't just fire and forget.
        
        # We need to act differently based on user response, so we can't just fire and forget.
        # Let's do the check here.
        
        playlist_choice = False # Default: Single video
        if "list=" in next_url and "youtube.com" in next_url:
             # Only ask if NOT in batch mode (Batch defaults to Single)
             if not self.is_batch_mode:
                 # Ask User
                 playlist_choice = self.ask_playlist_mode(next_url)
                 if playlist_choice is None: # Cancelled
                     # User wants to stop/cancel check.
                     # Stop processing, don't clear inputs.
                     self.set_ui_busy(False)
                     self.status_label.setText("İşlem kullanıcı tarafından iptal edildi.")
                     return

        self._init_worker(next_url, playlist_choice)

    def ask_playlist_mode(self, url):
        """Returns True for Playlist, False for Single, None for Cancel"""
        dlg = PlaylistDialog(self)
        if dlg.exec():
            return dlg.result_mode
        else:
            return None # Cancelled

    def _init_worker(self, url, download_playlist=False):
        # Logic extracted from old start_download
        
        # Determine Format
        checked_id = self.format_group.checkedId()
        fmt_map = {0: 'mp4', 1: 'mp3', 2: 'm4a'}
        selected_fmt = fmt_map.get(checked_id, 'mp4')

        # Determine Quality
        q_idx = self.quality_combo.currentIndex()
        quality_val = 'max' # Default fallback
        
        if checked_id == 0: # MP4
            # 0: Max, 1: 1080, 2: 720, 3: 480
            q_map = {0: 'max', 1: '1080', 2: '720', 3: '480'}
            quality_val = q_map.get(q_idx, 'max')
        elif checked_id == 1: # MP3
            # VBR Quality: 0=Best, 2=Standard (High), 6=Good/Speech
            q_map = {0: '0', 1: '2', 2: '6'}
            quality_val = q_map.get(q_idx, '2')
        # m4a ignores quality_val

        # Subtitle Options
        sub_opts = {
            'enabled': self.sub_check.isChecked() and self.sub_check.isVisible(),
            'lang': 'tr',
            'embed': True
        }
        
        if sub_opts['enabled']:
            # Lang
            l_idx = self.sub_lang_combo.currentIndex()
            if l_idx == 0: sub_opts['lang'] = 'tr'
            elif l_idx == 1: sub_opts['lang'] = 'en'
            else: sub_opts['lang'] = 'all'
            
            # Mode
            m_idx = self.sub_mode_combo.currentIndex()
            sub_opts['embed'] = (m_idx == 0)

        # Trim Options
        s_text = self.start_time_input.text()
        e_text = self.end_time_input.text()
        
        # Handle Masked Defaults
        if s_text == "00:00:00": s_text = "0"
        if e_text == "00:00:00": e_text = "" # Empty implies end of video
        
        trim_opts = {
            'enabled': self.trim_check.isChecked(),
            'start': s_text,
            'end': e_text
        }

        # Validation: Check Time Range
        if trim_opts['enabled'] and trim_opts['end']:
            s_sec = self._parse_time_ui(trim_opts['start'])
            e_sec = self._parse_time_ui(trim_opts['end'])
            
            if s_sec is not None and e_sec is not None and s_sec >= e_sec:
                InfoBar.warning(
                    title='Hatalı Süre',
                    content="Başlangıç süresi, bitiş süresinden büyük veya eşit olamaz.",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )
                # If validating failed, we should probably stop the queue or skip?
                # For now let's skip current
                self.process_queue()
                return

        try:
            settings = get_settings()
            default_path = get_default_download_folder()
            base_folder = settings.value("download_folder", default_path)
            
            # Subfolder Logic
            use_sub = settings.value("use_subfolders", "true") == "true"
            
            if use_sub:
                if selected_fmt in ['mp3', 'm4a']:
                    download_folder = os.path.join(base_folder, "Ses")
                else:
                    download_folder = os.path.join(base_folder, "Video")
            else:
                download_folder = base_folder
            
            if not os.path.exists(download_folder):
                os.makedirs(download_folder)
            
            # Save for cleanup usage
            self.current_download_folder = download_folder

        except Exception as e:
            # Fallback
            print(f"Klasör hatası: {e}")
            download_folder = None
            self.current_download_folder = None

        # Threading
        # Subopts might need update if playlist? No, keep same.
        # We need to pass playlist info to worker. 
        # But DownloadWorker constructor signature needs update OR we pass in options.
        # Since I can't easily change constructor in this step without touching core, 
        # I will inject the option into 'trim_opts' or similar hack, OR better:
        # Update DownloadWorker is safer. But for now let's assume I can't see DownloadWorker file in this context easily.
        # Wait, I have to update DownloadWorker to support 'playlist_items' opt.
        
        # Browser Cookie Check
        browser_choice = get_settings().value("browser_cookies", "disabled")
        
        # Actually, let's pass a 'playlist' key in sub_opts for now to avoid breaking signature widely, 
        # OR just update constructor in next step. For now let's assume constructor update comes next.
        # I'll pass it as a keyword argument if I could, but I'll stick to updating signature in next tool call.
        # For this step, I will just pass `playlist: download_playlist` inside a new dict or existing one.
        # Let's assume I'll add `playlist_mode` as new arg to DownloadWorker.
        
        self.worker = DownloadWorker(url, selected_fmt, quality_val, sub_opts, trim_opts, output_folder=download_folder, playlist_mode=download_playlist, browser=browser_choice)
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.update_status)
        self.worker.finished.connect(self.on_success)
        self.worker.error.connect(self.on_error)
        
        # Start Thread
        self.worker.start()

    def _init_gallery_worker(self, url):
        # Prepare Options
        opts = {}
        
        # 1. Range / Limit Options
        r_mode = self.range_mode_combo.currentIndex()
        
        if r_mode == 1: # En Yeni X (First X in list: 1-X)
            opts['range'] = f"1-{self.limit_spin.value()}"
            
        elif r_mode == 2: # Custom Range
            s = self.range_start_spin.value()
            e = self.range_end_spin.value()
            if s > e: s, e = e, s # Swap if wrong
            opts['range'] = f"{s}-{e}"
        # else: All (No range)
            
        # 2. Date Filter
        if self.date_check.isChecked():
            # Text from LineEdit is already "YYYY-MM-DD" due to mask
            d = self.date_input.text()
            # Simple validation to ensure it's not empty/partial due to mask
            if len(d) == 10:
                opts['date_after'] = d
            else:
                self.worker.log.emit("⚠️ Geçersiz tarih formatı, filtre yoksayılıyor.")
        
        # 3. Type Filter (Photo/Video)
        g_type = self.gallery_type_group.checkedId()
        # 0: All, 1: Photo, 2: Video
        if g_type == 1:
            opts['filter_type'] = 'image'
        elif g_type == 2:
            opts['filter_type'] = 'video'
        
        # Get Download Folder
        try:
            settings = get_settings()
            default_path = get_default_download_folder()
            base_folder = settings.value("download_folder", default_path)
            
            # Subfolder
            # User requested "Orbit İndirilenler/Instagram_User" structure.
            # So we pass the base "Orbit İndirilenler" as root, and let gallery-dl handle the subfolder.
            # We don't add "Galeri" here anymore.
            dest_folder = base_folder
            if not os.path.exists(dest_folder):
                os.makedirs(dest_folder)
            
            opts['download_folder'] = dest_folder
            self.current_download_folder = dest_folder 
            
        except Exception:
            opts['download_folder'] = None 

        from src.core.logger import get_logger
        logger = get_logger()
        logger.info(f"[UI] Starting Gallery Download. URL: {url}")
        logger.info(f"[UI] Options: {opts}")

        self.worker = GalleryWorker(url, opts)
        
        self.worker.log.connect(self.update_status)
        self.worker.finished.connect(lambda msg: self.on_success(msg, url)) 
        self.worker.error.connect(self.on_error)
        self.worker.progress.connect(self.update_status) 
        
        self.worker.start()

    def _parse_time_ui(self, time_str):
        try:
            parts = [float(p) for p in time_str.split(':')]
            if len(parts) == 1: return parts[0]
            elif len(parts) == 2: return parts[0] * 60 + parts[1]
            elif len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except:
            return 0
        return 0

    def set_ui_busy(self, busy: bool):
        self.open_folder_btn.setEnabled(not busy)
        self.url_input.setEnabled(not busy)
        self.batch_list.setEnabled(not busy)      # Added list
        self.batch_btn.setEnabled(not busy)       # Added batch btn
        self.radio_mp4.setEnabled(not busy)
        self.radio_mp3.setEnabled(not busy)
        self.radio_m4a.setEnabled(not busy)
        self.quality_combo.setEnabled(not busy)
        self.sub_check.setEnabled(not busy)
        self.sub_lang_combo.setEnabled(not busy)
        self.sub_mode_combo.setEnabled(not busy)
        
        self.trim_check.setEnabled(not busy)
        self.start_time_input.setEnabled(not busy)
        self.end_time_input.setEnabled(not busy)
        
        self.action_combo.setEnabled(not busy)
        
        # Download Button acts as Cancel button when busy
        self.download_btn.setEnabled(True) 
        if busy:
            self.download_btn.setText("İPTAL ET")
            self.download_btn.setIcon(FluentIcon.CANCEL)
            self.progress_bar.setValue(0)
            self.progress_bar.show()
        else:
            self.download_btn.setText("Analiz Et ve İndir")
            self.download_btn.setIcon(FluentIcon.DOWNLOAD)
            self.progress_bar.hide()

    def update_progress(self, val):
        self.progress_bar.setValue(val)

    def update_status(self, msg):
        # Translate some specific technical status messages if needed, 
        # but mostly they come from the worker.
        if "Analyzing" in msg: msg = "Analiz ediliyor..."
        if "Found" in msg: msg = f"Bulundu: {msg.replace('Found:', '')}"
        if "Downloading" in msg: msg = "İndiriliyor..."
        if "Processing complete" in msg: msg = "İşlem tamamlandı."
        
        # Truncate Long Messages to prevent UI Jitter
        if len(msg) > 75:
            msg = msg[:72] + "..."
            
        self.status_label.setText(msg)

    def on_success(self, title, url):
        # Don't unlock UI yet if queue is still running
        # self.set_ui_busy(False) 
        
        self.status_label.setText(f"Tamamlandı: {title}")
        
        # Update Batch Item Icon
        if self.is_batch_mode and self.current_batch_index > 0:
            # Index is 1-based in counter, but 0-based in list
            # current_batch_index was incremented in process_queue BEFORE worker start
            # So item index is (current_batch_index - 1)
            item = self.batch_list.item(self.current_batch_index - 1)
            item.setIcon(FluentIcon.ACCEPT.icon()) # Checkmark
        
        # Add to History
        history_manager.add_entry(title, url, "")
        
        # Optional: InfoBar (Too many popups if batch?)
        # Let's show popups but transient
        InfoBar.success(
            title='İndirme Başarılı',
            content=f"{title}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=self
        )
        
        # Check 'Open Folder' setting (Single Mode Only)
        # For batch, we open it once at the end.
        if not self.is_batch_mode:
            self._check_and_open_folder()
        
        # Trigger Next
        self.process_queue()

    def on_all_finished(self):
        """Called when queue is empty"""
        self.set_ui_busy(False)
        self.status_label.setText("Hazır")
        self.progress_bar.hide()
        
        # Only show "Batch Complete" if we were in batch mode
        # Single downloads show their own success/error messages individually
        if self.is_batch_mode:
            InfoBar.success(
                title='Tümü Tamamlandı',
                content="Listedeki tüm dosyalar indirildi.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self
            )
            
            # Check 'Open Folder' setting (Batch Mode End)
            self._check_and_open_folder()

        # Check Post-Download Action (Common for both, but maybe only if successful?)
        # Logic remains: Queue empty -> Action.
        action_idx = self.action_combo.currentIndex()
        if action_idx > 0:
            # 0: None, 1: Close App, 2: Shutdown PC
            self.perform_post_action(action_idx)

    def _check_and_open_folder(self):
        try:
            settings = get_settings()
            if settings.value("open_folder_on_complete", "false") == "true":
                path = getattr(self, 'current_download_folder', None)
                if path and os.path.exists(path):
                    os.startfile(path)
        except Exception as e:
            print(f"Otomatik klasör açma hatası: {e}")

    def cancel_download(self):
        # 1. Check if we are in Shutdown Countdown
        if hasattr(self, 'shutdown_timer') and self.shutdown_timer.isActive():
            self.shutdown_timer.stop()
            self.status_label.setText("Otomatik işlem iptal edildi.")
            self.set_ui_busy(False)
            return

        # 2. Cancel Download Worker
        if self.worker:
            self.status_label.setText("İndirme iptal ediliyor...")
            
            # Safe Stop logic
            if hasattr(self.worker, 'stop'):
                 self.worker.stop()
                 self.worker.wait(2000) # Give it 2 seconds to gracefully stop
            
            # Force Kill Processes to unlock files immediately
            try:
                from src.utils import kill_external_processes
                kill_external_processes()
                
                # Aggressively kill gallery-dl if it persists
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                subprocess.call(["taskkill", "/F", "/IM", "gallery-dl.exe", "/T"], 
                              startupinfo=startupinfo, creationflags=0x08000000)
            except:
                pass

            # Clear Queue
            self.download_queue = []
            
            # Reset UI
            self.set_ui_busy(False)
            self.status_label.setText("İndirme iptal edildi.")
            
            # If batch mode, mark current as cancelled
            if self.is_batch_mode and self.current_batch_index > 0:
                 item = self.batch_list.item(self.current_batch_index - 1)
                 item.setIcon(FluentIcon.CANCEL.icon())
            
            # Trigger Cleanup (Delayed to allow thread to release locks)
            QTimer.singleShot(2000, self._cleanup_after_cancel)

    def _cleanup_after_cancel(self):
        """Removes partial files after cancellation (Recursively)"""
        try:
            folder = getattr(self, 'current_download_folder', None)
            if not folder or not os.path.exists(folder):
                return
            
            # Walk through all subdirectories to find trash
            for root, dirs, files in os.walk(folder):
                for fname in files:
                    if fname.endswith(('.part', '.ytdl', '.temp')):
                        try:
                            os.remove(os.path.join(root, fname))
                            print(f"[Temizlik] Silindi: {fname}")
                        except OSError:
                            pass 
        except Exception as e:
            print(f"Temizlik hatası: {e}")

    def on_error(self, err_msg):
        # Friendly Error Mapping
        friendly_msg = str(err_msg)
        lower_err = friendly_msg.lower()
        
        if "unsupported url" in lower_err:
            friendly_msg = "Bu bağlantı desteklenmiyor veya geçersiz."
        elif "video unavailable" in lower_err:
            friendly_msg = "Video mevcut değil veya erişilemiyor."
        elif "private video" in lower_err:
            friendly_msg = "Bu video gizli veya özel (Giriş yapmanız gerekebilir)."
        elif "sign in" in lower_err:
            friendly_msg = "Bu videoyu indirmek için oturum açılması gerekiyor."
        elif "network is unreachable" in lower_err or "urlopen error" in lower_err:
            friendly_msg = "İnternet bağlantısı yok veya sunucuya ulaşılamıyor."
        elif "http error 403" in lower_err:
            friendly_msg = "Erişim reddedildi (403). Sunucu isteği engelledi."
        elif "ffmpeg" in lower_err:
            friendly_msg = "Dönüştürme aracı (FFmpeg) hatası."
        elif "playlist" in lower_err and "does not exist" in lower_err:
             friendly_msg = "Oynatma listesi bulunamadı."
        elif "incomplete" in lower_err:
             friendly_msg = "İndirme tam olarak bitirilemedi (İnternet kopmuş olabilir)."
        elif "is not a valid url" in lower_err:
             friendly_msg = "Girdiğiniz bağlantı geçersiz."
        elif "çerez" in lower_err or "dpapi" in lower_err:
             # Keep custom cookie/DPAPI error messages as they are already localized and detailed
             friendly_msg = str(err_msg)
        else:
            # General fallback for ANY other english error to avoid scaring users
            # Unless we are in debug mode? No, UI should be clean.
            # Convert unknown errors to generic message.
            friendly_msg = "İşlem sırasında beklenmedik bir hata oluştu."
        
        InfoBar.error(
            title='İndirme Başarısız',
            content=friendly_msg,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=3000,
            parent=self
        )
        
        # Update Batch Item Icon to Error
        if self.is_batch_mode and self.current_batch_index > 0:
            item = self.batch_list.item(self.current_batch_index - 1)
            item.setIcon(FluentIcon.CANCEL.icon()) # X icon

        # Continue Queue
        self.process_queue()

    def perform_post_action(self, action_idx):
        self.pending_action_idx = action_idx
        self.countdown_seconds = 10
        
        self.status_label.setText(f"Otomatik işlem: {self.countdown_seconds} sn... (İptal için 'İPTAL ET')")
        
        # We reuse 'busy' state to show Cancel button
        self.set_ui_busy(True) 
        
        # Create a timer for countdown
        if hasattr(self, 'shutdown_timer') and self.shutdown_timer.isActive():
            self.shutdown_timer.stop()
            
        self.shutdown_timer = QTimer(self)
        self.shutdown_timer.timeout.connect(self._on_shutdown_tick)
        self.shutdown_timer.start(1000) # Every 1 second

    def _on_shutdown_tick(self):
        self.countdown_seconds -= 1
        if self.countdown_seconds > 0:
            self.status_label.setText(f"Otomatik işlem: {self.countdown_seconds} sn... (İptal için 'İPTAL ET')")
        else:
            self.shutdown_timer.stop()
            self._execute_shutdown(self.pending_action_idx)

    def _execute_shutdown(self, action_idx):
        if action_idx == 1: # Close App
            QApplication.quit()
        elif action_idx == 2: # Shutdown PC
            self.status_label.setText("Bilgisayar kapatılıyor...")
            os.system("shutdown /s /t 1")



    def open_downloads_folder(self):
        try:
            settings = get_settings()
            default_path = get_default_download_folder()
            path = settings.value("download_folder", default_path)
            
            if not os.path.exists(path):
                os.makedirs(path)
                
            os.startfile(path)
        except Exception as e:
            print(f"Klasör açma hatası: {e}")

    def stop_workers(self):
        """Stops any active worker threads safely."""
        # Stop Gallery/Download Worker
        if hasattr(self, 'worker') and self.worker:
            try:
                if self.worker.isRunning():
                    if hasattr(self.worker, 'stop'):
                        self.worker.stop()
                    
                    # Wait gracefully before resorting to terminate if absolutely needed
                    if not self.worker.wait(2000):
                        self.worker.terminate()
                        self.worker.wait(1000)
            except Exception as e:
                print(f"Worker stop error: {e}")

        # Stop Shutdown Timer
        if hasattr(self, 'shutdown_timer') and self.shutdown_timer.isActive():
            self.shutdown_timer.stop()
