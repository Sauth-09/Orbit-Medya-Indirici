from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import (TitleLabel, BodyLabel, SubtitleLabel, CaptionLabel, 
                            StrongBodyLabel, CardWidget, HyperlinkButton, FluentIcon, 
                            ImageLabel, PrimaryPushButton, InfoBar, InfoBarPosition)
from src.version import VERSION
from src.core.app_updater import CheckUpdateWorker


class AboutView(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(" ", "-"))
        
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(40, 40, 40, 40)
        self.v_layout.setSpacing(15)
        self.v_layout.setAlignment(Qt.AlignTop)

        # 1. Title & Version
        self.title_label = TitleLabel(f"Orbit Downloader", self)
        self.v_layout.addWidget(self.title_label)
        
        self.version_layout = QHBoxLayout()
        self.version_label = SubtitleLabel(f"Sürüm: v{VERSION}", self)
        self.version_label.setTextColor("#009faa", "#009faa") # Accent color
        self.version_layout.addWidget(self.version_label)
        
        self.check_update_btn = PrimaryPushButton("Güncellemeleri Denetle", self, FluentIcon.SYNC)
        self.check_update_btn.setFixedWidth(200)
        self.check_update_btn.clicked.connect(self.check_for_updates)
        self.version_layout.addWidget(self.check_update_btn)
        
        self.version_layout.addStretch(1)
        self.v_layout.addLayout(self.version_layout)
        
        # Update Status Label
        self.update_status_lbl = BodyLabel("", self)
        self.update_status_lbl.setTextColor("#808080", "#808080")
        self.v_layout.addWidget(self.update_status_lbl)

        # 2. Developer Info
        self.dev_label = BodyLabel("Geliştirici: S. ERKUT", self)
        self.v_layout.addWidget(self.dev_label)

        self.v_layout.addSpacing(20)

        # 3. Technologies Card
        self.tech_card = CardWidget(self)
        self.tech_layout = QVBoxLayout(self.tech_card)
        
        self.tech_title = StrongBodyLabel("Kullanılan Teknolojiler", self.tech_card)
        self.tech_layout.addWidget(self.tech_title)
        
        techs = [
            "• Python & PySide6 (GUI)",
            "• yt-dlp (Core Engine)",
            "• FFmpeg & FFprobe (Media Conversion)",
            "• QFluentWidgets (Design System)"
        ]
        for t in techs:
            self.tech_layout.addWidget(CaptionLabel(t, self.tech_card))
            
        self.v_layout.addWidget(self.tech_card)
        
        self.v_layout.addSpacing(20)

        # 4. Disclaimer
        self.disclaimer_title = StrongBodyLabel("Yasal Uyarı / Sorumluluk Reddi", self)
        self.v_layout.addWidget(self.disclaimer_title)
        
        disclaimer_text = (
            "Bu yazılım yalnızca kişisel kullanım ve eğitim amaçlı tasarlanmıştır. "
            "Telif hakkı ile korunan materyallerin izinsiz indirilmesi ve dağıtılması "
            "yasaktır. Kullanıcı, indirdiği içeriklerin telif hakkı yasalarına uygunluğundan "
            "bizzat sorumludur. Geliştirici, yazılımın kötüye kullanımından sorumlu tutulamaz."
        )
        self.disclaimer_label = CaptionLabel(disclaimer_text, self)
        self.disclaimer_label.setWordWrap(True)
        self.disclaimer_label.setTextColor("#808080", "#a0a0a0")
        self.v_layout.addWidget(self.disclaimer_label)

        self.v_layout.addStretch(1)

        # 5. Links
        self.github_btn = HyperlinkButton(
            url="https://github.com/Sauth-09/Orbit-Medya-Indirici", 
            text="GitHub'da Projeyi Görüntüle", 
            parent=self,
            icon=FluentIcon.GITHUB
        )
        self.v_layout.addWidget(self.github_btn, 0, Qt.AlignLeft)

    def check_for_updates(self):
        self.update_status_lbl.setText("Güncellemeler kontrol ediliyor...")
        self.check_update_btn.setEnabled(False)
        
        self.worker = CheckUpdateWorker()
        self.worker.finished.connect(self.on_check_finished)
        self.worker.start()

    def on_check_finished(self, result):
        self.check_update_btn.setEnabled(True)
        
        if not result["success"]:
            self.update_status_lbl.setText(f"Kontrol başarısız: {result.get('error')}")
            return
            
        latest_tag = result["tag"] # e.g. "v2.37"
        download_url = result["url"]
        
        # Robust Parse Logic
        try:
            def parse_ver(v_str):
                return [int(p) for p in v_str.lower().replace("v", "").split(".") if p.isdigit()]

            current_parts = parse_ver(VERSION)
            latest_parts = parse_ver(latest_tag)
            
            if latest_parts > current_parts:
                self.update_status_lbl.setText(f"Yeni bir güncelleme mevcut: {latest_tag}")
                self.update_status_lbl.setTextColor("#009faa", "#009faa")
                
                # Change Button to Download
                self.check_update_btn.setText("Güncellemeyi İndir")
                self.check_update_btn.setIcon(FluentIcon.DOWNLOAD)
                self.check_update_btn.clicked.disconnect()
                self.check_update_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(download_url)))
                
            elif latest_parts == current_parts:
                self.update_status_lbl.setText("Sürümünüz güncel.")
                self.update_status_lbl.setTextColor("#00CC66", "#00CC66") # Green
            else:
                # Local is newer (Developer Version)
                self.update_status_lbl.setText(f"Geliştirici sürümü kullanıyorsunuz (Mevcut: v{VERSION} > Bulut: {latest_tag})")
                self.update_status_lbl.setTextColor("#E69500", "#E69500") # Orange
                
        except Exception as e:
            self.update_status_lbl.setText(f"Sürüm kontrolü yapılamadı ({e})")
