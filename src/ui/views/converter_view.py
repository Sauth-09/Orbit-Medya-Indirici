import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from qfluentwidgets import (TitleLabel, BodyLabel, LineEdit, PushButton, 
                            PrimaryPushButton, ComboBox, CheckBox, ProgressBar,
                            FluentIcon, InfoBar, InfoBarPosition, CaptionLabel,
                            ListWidget, CardWidget, StrongBodyLabel, SubtitleLabel)

from src.core.converter_worker import ConverterWorker, MediaInfoWorker
from src.version import VERSION
from src.settings_manager import get_settings, get_default_download_folder

class DropLineEdit(LineEdit):
    """ Özel LineEdit: Sürükle-Bırak destekli """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.setText(path)
            # Eğer parent ConverterView ise on_file_dropped metodunu tetikle
            if hasattr(self.parent(), 'on_file_dropped'):
                self.parent().on_file_dropped(path)

class ConverterView(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(" ", "-"))
        
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(10, 10, 10, 10)
        self.v_layout.setSpacing(10)
        
        self.form_container = QWidget()
        self.form_container.setMaximumWidth(800) 
        self.form_layout = QVBoxLayout(self.form_container)
        self.form_layout.setSpacing(15)
        
        # Header
        self.title_label = TitleLabel("Dönüştürücü", self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.form_layout.addWidget(self.title_label)
        
        self.subtitle_label = BodyLabel("Medya dosyalarınızı formatlayın ve kesin", self)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setTextColor("#808080", "#808080")
        self.form_layout.addWidget(self.subtitle_label)
        self.form_layout.addSpacing(10)
        
        # Input Selection
        self.input_layout = QHBoxLayout()
        self.input_input = DropLineEdit(self)
        self.input_input.setPlaceholderText("Dosyayı buraya sürükleyin veya göz atın...")
        self.input_input.setReadOnly(True)
        self.input_btn = PushButton("Gözat", self, FluentIcon.FOLDER)
        self.input_btn.clicked.connect(self.browse_input)
        
        self.input_layout.addWidget(self.input_input, 1)
        self.input_layout.addWidget(self.input_btn)
        self.form_layout.addLayout(self.input_layout)
        
        # Info Card (Hidden by default)
        from PySide6.QtWidgets import QGridLayout
        
        self.info_card = CardWidget(self)
        self.info_layout = QGridLayout(self.info_card)
        self.info_layout.setContentsMargins(15, 12, 15, 12)
        self.info_layout.setVerticalSpacing(8)
        self.info_layout.setHorizontalSpacing(20)
        
        self.info_type_lbl = StrongBodyLabel("Türü:", self)
        self.info_type_val = BodyLabel("-", self)
        self.info_dur_lbl = StrongBodyLabel("Süre:", self)
        self.info_dur_val = BodyLabel("-", self)
        self.info_res_lbl = StrongBodyLabel("Çözünürlük:", self)
        self.info_res_val = BodyLabel("-", self)
        self.info_size_lbl = StrongBodyLabel("Boyut:", self)
        self.info_size_val = BodyLabel("-", self)
        self.info_extra_lbl = StrongBodyLabel("Diğer:", self)
        self.info_extra_val = BodyLabel("-", self)

        self.info_layout.addWidget(self.info_type_lbl, 0, 0, alignment=Qt.AlignRight)
        self.info_layout.addWidget(self.info_type_val, 0, 1, alignment=Qt.AlignLeft)
        self.info_layout.addWidget(self.info_dur_lbl, 0, 2, alignment=Qt.AlignRight)
        self.info_layout.addWidget(self.info_dur_val, 0, 3, alignment=Qt.AlignLeft)
        self.info_layout.addWidget(self.info_extra_lbl, 0, 4, alignment=Qt.AlignRight)
        self.info_layout.addWidget(self.info_extra_val, 0, 5, alignment=Qt.AlignLeft)
        
        self.info_layout.addWidget(self.info_res_lbl, 1, 0, alignment=Qt.AlignRight)
        self.info_layout.addWidget(self.info_res_val, 1, 1, alignment=Qt.AlignLeft)
        self.info_layout.addWidget(self.info_size_lbl, 1, 2, alignment=Qt.AlignRight)
        self.info_layout.addWidget(self.info_size_val, 1, 3, alignment=Qt.AlignLeft)
        
        self.form_layout.addWidget(self.info_card)
        self.info_card.hide()
        
        # Options Row 1
        self.opts_layout1 = QHBoxLayout()
        self.opts_layout1.setSpacing(20)
        
        self.format_label = BodyLabel("Hedef Format:", self)
        self.format_combo = ComboBox(self)
        self.format_combo.addItems(["MP4 (Video)", "MP3 (Ses)", "M4A (Ses)", "GIF (Animasyon)"])
        self.format_combo.currentIndexChanged.connect(self.on_format_changed)
        
        self.quality_label = BodyLabel("Kalite:", self)
        self.quality_combo = ComboBox(self)
        # Will be populated dynamically
        
        self.opts_layout1.addWidget(self.format_label)
        self.opts_layout1.addWidget(self.format_combo, 1)
        self.opts_layout1.addWidget(self.quality_label)
        self.opts_layout1.addWidget(self.quality_combo, 1)
        
        self.form_layout.addLayout(self.opts_layout1)
        
        # Options Row 2 (Advanced Options: FPS, Video Bitrate, Audio Bitrate)
        self.opts_layout2 = QHBoxLayout()
        self.opts_layout2.setSpacing(20)
        
        self.fps_label = BodyLabel("FPS:", self)
        self.fps_combo = ComboBox(self)
        self.fps_combo.addItems(["Orijinal", "24", "25", "30", "50", "60"])
        
        self.vbitrate_label = BodyLabel("Vid. Bitrate:", self)
        self.vbitrate_combo = ComboBox(self)
        self.vbitrate_combo.addItems(["Orijinal", "500k", "1000k", "2500k", "5000k", "8000k"])
        
        self.abitrate_label = BodyLabel("Ses Bitrate:", self)
        self.abitrate_combo = ComboBox(self)
        self.abitrate_combo.addItems(["Orijinal", "64k", "128k", "192k", "256k", "320k"])
        
        self.opts_layout2.addWidget(self.fps_label)
        self.opts_layout2.addWidget(self.fps_combo, 1)
        self.opts_layout2.addWidget(self.vbitrate_label)
        self.opts_layout2.addWidget(self.vbitrate_combo, 1)
        self.opts_layout2.addWidget(self.abitrate_label)
        self.opts_layout2.addWidget(self.abitrate_combo, 1)
        
        self.form_layout.addLayout(self.opts_layout2)
        
        # Options Row 3 (Speed & Mute)
        self.opts_layout3 = QHBoxLayout()
        self.opts_layout3.setSpacing(20)
        
        self.speed_label = BodyLabel("Hız Seçeneği:", self)
        self.speed_combo = ComboBox(self)
        self.speed_combo.addItems(["Normal (1.0x)", "Hızlı (1.25x)", "Çok Hızlı (1.5x)", "2.0x Hız", "Yavaş (0.75x)", "Çok Yavaş (0.5x)"])
        self.speed_combo.setCurrentIndex(0)
        
        self.mute_check = CheckBox("Videodan Sesi Kaldır (Sessiz)", self)
        self.mute_check.stateChanged.connect(self.on_mute_changed)
        
        self.opts_layout3.addWidget(self.speed_label)
        self.opts_layout3.addWidget(self.speed_combo, 1)
        self.opts_layout3.addWidget(self.mute_check, 1)
        
        self.form_layout.addLayout(self.opts_layout3)

        # Naming Template Row
        self.template_layout = QHBoxLayout()
        self.template_label = BodyLabel("İsim Şablonu:", self)
        self.template_input = LineEdit(self)
        self.template_input.setPlaceholderText("{name}_{quality}_{format}")
        self.template_input.setText(get_settings().value("conv_template", "{name}_converted"))
        self.template_input.textChanged.connect(lambda t: get_settings().setValue("conv_template", t))
        
        self.template_layout.addWidget(self.template_label)
        self.template_layout.addWidget(self.template_input, 1)
        self.form_layout.addLayout(self.template_layout)
        
        # Trim Options
        self.trim_check = CheckBox("Süreyi Kırp/Kes", self)
        self.trim_check.stateChanged.connect(self.on_trim_changed)
        self.form_layout.addWidget(self.trim_check, 0, Qt.AlignCenter)
        
        self.trim_widget = QWidget()
        self.trim_layout = QHBoxLayout(self.trim_widget)
        self.trim_layout.setContentsMargins(0,0,0,0)
        
        self.start_label = BodyLabel("Başlangıç:", self)
        self.start_input = LineEdit(self)
        self.start_input.setInputMask("00:00:00")
        self.start_input.setText("00:00:00")
        self.start_input.setFixedWidth(100)
        self.start_input.setAlignment(Qt.AlignCenter)
        
        self.end_label = BodyLabel("Bitiş:", self)
        self.end_input = LineEdit(self)
        self.end_input.setInputMask("00:00:00")
        self.end_input.setText("00:00:00")
        self.end_input.setFixedWidth(100)
        self.end_input.setAlignment(Qt.AlignCenter)
        
        self.trim_layout.addStretch(1)
        self.trim_layout.addWidget(self.start_label)
        self.trim_layout.addWidget(self.start_input)
        self.trim_layout.addSpacing(20)
        self.trim_layout.addWidget(self.end_label)
        self.trim_layout.addWidget(self.end_input)
        self.trim_layout.addStretch(1)
        
        self.form_layout.addWidget(self.trim_widget)
        self.trim_widget.hide()
        
        self.form_layout.addSpacing(20)
        
        # Action Row
        self.action_layout = QHBoxLayout()
        
        self.start_btn = PrimaryPushButton("Dönüştürmeyi Başlat", self)
        self.start_btn.setFixedHeight(40)
        self.start_btn.clicked.connect(self.start_conversion)
        
        self.folder_btn = PushButton("Dönüştürülenler Klasörü", self, FluentIcon.FOLDER)
        self.folder_btn.setFixedHeight(40)
        self.folder_btn.clicked.connect(self.open_output_folder)
        
        self.action_layout.addWidget(self.start_btn, 3)
        self.action_layout.addWidget(self.folder_btn, 1)
        self.form_layout.addLayout(self.action_layout)
        
        # Progress
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        self.form_layout.addWidget(self.progress_bar)
        
        self.status_label = BodyLabel("Hazır.", self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.form_layout.addWidget(self.status_label)
        
        # Recent Files
        self.recent_container = CardWidget(self)
        self.recent_layout = QVBoxLayout(self.recent_container)
        self.recent_title = SubtitleLabel("Son İşlemler", self)
        self.recent_list = ListWidget(self)
        self.recent_list.setFixedHeight(120)
        self.recent_list.itemDoubleClicked.connect(self.on_recent_item_clicked)
        
        self.recent_layout.addWidget(self.recent_title)
        self.recent_layout.addWidget(self.recent_list)
        self.form_layout.addWidget(self.recent_container)
        
        # Load recent files
        self.load_recent_files()
        
        # Main layout wrap
        self.v_layout.addStretch(1)
        self.v_layout.addWidget(self.form_container, 0, Qt.AlignHCenter)
        self.v_layout.addStretch(1)
        
        self.worker = None
        self.on_format_changed(0) # Init logic

    def browse_input(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Giriş Dosyası Seç", 
            "", 
            "Medya Dosyaları (*.mp4 *.mkv *.webm *.avi *.mp3 *.m4a *.wav);;Tüm Dosyalar (*.*)"
        )
        if file_path:
            self.input_input.setText(file_path)
            self.on_file_dropped(file_path)

    def on_file_dropped(self, path):
        # Medya bilgisini analiz et
        self.info_type_val.setText("Analiz ediliyor...")
        self.info_dur_val.setText("-")
        self.info_res_val.setText("-")
        self.info_size_val.setText("-")
        self.info_extra_val.setText("-")
        self.info_card.show()
        
        self.info_worker = MediaInfoWorker(path)
        self.info_worker.finished.connect(self.on_info_ready)
        self.info_worker.start()

    def on_info_ready(self, info):
        self.info_type_val.setText(info.get('type', '-'))
        self.info_dur_val.setText(info.get('duration', '-'))
        self.info_res_val.setText(info.get('resolution', '-'))
        self.info_size_val.setText(info.get('size', '-'))
        self.info_extra_val.setText(info.get('extra', '-'))

    def load_recent_files(self):
        import json
        settings = get_settings()
        data = settings.value("conv_recent_files", "[]")
        try:
            files = json.loads(data) if isinstance(data, str) else data
            self.recent_list.clear()
            for f in files:
                if os.path.exists(f):
                    self.recent_list.addItem(f)
        except:
            pass

    def add_to_recent(self, path):
        import json
        settings = get_settings()
        data = settings.value("conv_recent_files", "[]")
        try:
            files = json.loads(data) if isinstance(data, str) else data
        except:
            files = []
            
        if path in files:
            files.remove(path)
        files.insert(0, path)
        files = files[:10] # Keep last 10
        
        settings.setValue("conv_recent_files", json.dumps(files))
        self.load_recent_files()

    def on_recent_item_clicked(self, item):
        path = item.text()
        if os.path.exists(path):
            os.startfile(os.path.dirname(path))
        else:
            InfoBar.warning(title="Dosya Bulunamadı", content="Dosya taşınmış veya silinmiş olabilir.", parent=self)

    def on_format_changed(self, idx):
        self.quality_combo.clear()
        self.mute_check.setEnabled(True)
        self.quality_combo.setEnabled(True)
        
        # Enable all advanced options first
        self.fps_combo.setEnabled(True)
        self.vbitrate_combo.setEnabled(True)
        self.abitrate_combo.setEnabled(True)
        
        if idx == 0: # MP4
             self.quality_combo.addItems(["Orijinal", "1080p", "720p", "480p", "360p", "240p"])
             self.abitrate_combo.setEnabled(not self.mute_check.isChecked())
        elif idx == 1: # MP3
             self.quality_combo.addItems(["320k (En İyi)", "192k (Standart)", "128k (Düşük)"])
             self.quality_combo.setCurrentIndex(1)
             self.mute_check.setEnabled(False)
             self.mute_check.setChecked(False)
             self.fps_combo.setEnabled(False)
             self.vbitrate_combo.setEnabled(False)
             self.abitrate_combo.setEnabled(False) # Quality combo dictates this
        elif idx == 2: # M4A
             self.quality_combo.addItems(["320k", "192k", "128k"])
             self.quality_combo.setCurrentIndex(1)
             self.mute_check.setEnabled(False)
             self.mute_check.setChecked(False)
             self.fps_combo.setEnabled(False)
             self.vbitrate_combo.setEnabled(False)
             self.abitrate_combo.setEnabled(False)
        elif idx == 3: # GIF
             self.quality_combo.addItems(["Standart GIF"])
             self.quality_combo.setEnabled(False)
             self.mute_check.setEnabled(False)
             self.mute_check.setChecked(False)
             self.vbitrate_combo.setEnabled(False)
             self.abitrate_combo.setEnabled(False)
             
    def on_mute_changed(self, state):
        idx = self.format_combo.currentIndex()
        if idx == 0: # MP4
            self.abitrate_combo.setEnabled(not self.mute_check.isChecked())

    def on_trim_changed(self, state):
        if self.trim_check.isChecked():
            self.trim_widget.show()
        else:
            self.trim_widget.hide()

    def set_ui_busy(self, busy):
        self.input_btn.setEnabled(not busy)
        self.format_combo.setEnabled(not busy)
        self.quality_combo.setEnabled(not busy)
        self.fps_combo.setEnabled(not busy)
        self.vbitrate_combo.setEnabled(not busy)
        self.abitrate_combo.setEnabled(not busy)
        self.trim_check.setEnabled(not busy)
        self.start_input.setEnabled(not busy)
        self.end_input.setEnabled(not busy)
        
        if busy:
             self.start_btn.setText("İptal Et")
             self.start_btn.setIcon(FluentIcon.CLOSE)
             self.progress_bar.show()
             self.progress_bar.setValue(0)
        else:
             self.start_btn.setText("Dönüştürmeyi Başlat")
             self.start_btn.setIcon(QIcon()) # Remove icon
             self.progress_bar.hide()
             self.progress_bar.setValue(0)

    def start_conversion(self):
        if self.worker and self.worker.isRunning():
             self.worker.stop()
             self.status_label.setText("İptal ediliyor...")
             return
             
        input_path = self.input_input.text().strip()
        if not input_path or not os.path.exists(input_path):
             InfoBar.warning(title="Hata", content="Lütfen geçerli bir dosya seçin.",
                             position=InfoBarPosition.TOP_RIGHT, parent=self)
             return
             
        # Build Options
        opts = {}
        idx = self.format_combo.currentIndex()
        fmt = "mp4"
        if idx == 1: fmt = "mp3"
        elif idx == 2: fmt = "m4a"
        elif idx == 3: fmt = "gif"
        opts['format'] = fmt
        
        q_text = self.quality_combo.currentText()
        if fmt == 'mp4':
             opts['video_quality'] = q_text.lower()
        elif fmt in ['mp3', 'm4a']:
             opts['audio_quality'] = q_text.split()[0]
             
        opts['fps'] = self.fps_combo.currentText()
        opts['vbitrate'] = self.vbitrate_combo.currentText()
        opts['abitrate'] = self.abitrate_combo.currentText()
             
        opts['mute'] = self.mute_check.isChecked()
        
        speed_idx = self.speed_combo.currentIndex()
        speed_vals = [1.0, 1.25, 1.5, 2.0, 0.75, 0.5]
        if 0 <= speed_idx < len(speed_vals):
            opts['speed'] = speed_vals[speed_idx]
             
        if self.trim_check.isChecked():
             opts['trim_start'] = self.start_input.text().strip()
             opts['trim_end'] = self.end_input.text().strip()
             
        # Determine Output Path
        settings = get_settings()
        default_path = get_default_download_folder()
        out_dir = settings.value("download_folder", default_path)
        
        if not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir)
            except:
                out_dir = os.path.dirname(input_path)
                
        base_name = os.path.basename(input_path)
        name_without_ext = os.path.splitext(base_name)[0]
        
        # Use Custom Template
        template = self.template_input.text().strip()
        if not template:
            template = "{name}_converted"
            
        # Replace tokens
        out_name = template.replace("{name}", name_without_ext)
        out_name = out_name.replace("{format}", fmt)
        out_name = out_name.replace("{quality}", q_text.replace(" ", "_").lower())
        
        output_name = f"{out_name}.{fmt}"
        output_path = os.path.join(out_dir, output_name)
        
        # Prevent overwrite by appending numbers
        counter = 1
        while os.path.exists(output_path):
             output_path = os.path.join(out_dir, f"{out_name}_{counter}.{fmt}")
             counter += 1
             
        self.set_ui_busy(True)
        self.status_label.setText("Dönüştürücü başlatılıyor...")
        
        self.worker = ConverterWorker(input_path, output_path, opts)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log.connect(self.status_label.setText)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_error(self, msg):
        self.set_ui_busy(False)
        self.status_label.setText("Hata oluştu.")
        InfoBar.error(title="Dönüştürme Hatası", content=msg,
                      position=InfoBarPosition.BOTTOM_RIGHT, duration=5000, parent=self)

    def on_finished(self, output_path, msg):
        self.set_ui_busy(False)
        self.status_label.setText("Hazır.")
        self.add_to_recent(output_path)
        InfoBar.success(title="Başarılı", content=msg,
                        position=InfoBarPosition.BOTTOM_RIGHT, duration=3000, parent=self)
                        
    def open_output_folder(self):
        settings = get_settings()
        default_path = get_default_download_folder()
        out_dir = settings.value("download_folder", default_path)
        
        if os.path.exists(out_dir):
            os.startfile(out_dir)
        else:
            InfoBar.warning(title="Klasör Bulunamadı", content="Çıktı klasörü henüz oluşturulmamış.", parent=self)
                         
    def stop_workers(self):
        if self.worker and self.worker.isRunning():
             self.worker.stop()
             self.worker.wait()
