from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
from PySide6.QtCore import Qt
from qfluentwidgets import (TitleLabel, PushSettingCard, SwitchSettingCard, FluentIcon, ComboBox, 
                            setTheme, setThemeColor, Theme, InfoBar, InfoBarPosition, BodyLabel, CardWidget, themeColor)
import os
from src.settings_manager import get_settings, get_default_download_folder
from src.core.logger import get_logger

class SettingsView(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(" ", "-"))
        
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(40, 40, 40, 40)
        self.v_layout.setSpacing(20)
        self.v_layout.setAlignment(Qt.AlignTop)

        self.title_label = TitleLabel("Ayarlar", self)
        self.v_layout.addWidget(self.title_label)

        # Settings Storage
        self.settings = get_settings()
        
        # Default Path
        self.default_path = get_default_download_folder()
        
        # Current Path
        current_path = self.settings.value("download_folder", self.default_path)

        # Download Folder Card
        self.folder_card = PushSettingCard(
            text="Değiştir",
            icon=FluentIcon.DOWNLOAD,
            title="İndirme Konumu",
            content=current_path,
            parent=self
        )
        self.folder_card.clicked.connect(self.select_folder)
        
        self.v_layout.addWidget(self.folder_card)

        # 3. Subfolder Switch
        self.subfolder_switch = SwitchSettingCard(
            icon=FluentIcon.LIBRARY,
            title="Otomatik Kategorize Et",
            content="İndirilen dosyaları 'Ses' ve 'Video' olarak alt klasörlere ayır.",
            parent=self
        )
        
        # Load state (Default: True)
        use_sub = self.settings.value("use_subfolders", "true") == "true"
        self.subfolder_switch.setChecked(use_sub)
        
        self.subfolder_switch.checkedChanged.connect(self.toggle_subfolders)
        
        self.v_layout.addWidget(self.subfolder_switch)

        # 4. Open Folder Switch
        self.open_folder_switch = SwitchSettingCard(
            icon=FluentIcon.FOLDER,
            title="Klasörü Otomatik Aç",
            content="İndirme tamamlandığında dosyanın bulunduğu klasörü otomatik olarak açar.",
            parent=self
        )
        # Load state (Default: False)
        open_on_complete = self.settings.value("open_folder_on_complete", "false") == "true"
        self.open_folder_switch.setChecked(open_on_complete)
        self.open_folder_switch.checkedChanged.connect(self.toggle_open_folder)
        
        self.v_layout.addWidget(self.open_folder_switch)
        
        # 5. Check Updates on Startup Switch
        self.startup_update_switch = SwitchSettingCard(
            icon=FluentIcon.SYNC,
            title="Açılışta Güncellemeleri Denetle",
            content="Uygulama açıldığında otomatik olarak yeni sürüm kontrolü yap.",
            parent=self
        )
        # Load state (Default: False)
        check_upd = self.settings.value("check_updates_on_startup", "false") == "true"
        self.startup_update_switch.setChecked(check_upd)
        self.startup_update_switch.checkedChanged.connect(self.toggle_startup_update)
        
        self.v_layout.addWidget(self.startup_update_switch)

        # 6. Debug Mode Switch
        self.debug_switch = SwitchSettingCard(
            icon=FluentIcon.FEEDBACK,
            title="Hata Ayıklama Modu",
            content="Uygulama hatalarını ve işlemlerini log dosyasına kaydeder (Geliştirici için).",
            parent=self
        )
        debug_mode = self.settings.value("debug_mode", "false") == "true"
        self.debug_switch.setChecked(debug_mode)
        self.debug_switch.checkedChanged.connect(self.toggle_debug)
        
        self.v_layout.addWidget(self.debug_switch)

        # 7. Premium/Browser Cookie Section
        self.browser_card = CardWidget(self)
        self.browser_card.setFixedHeight(80)
        self.browser_layout = QHBoxLayout(self.browser_card)
        self.browser_layout.setContentsMargins(20, 0, 20, 0)
        
        self.browser_icon = FluentIcon.PEOPLE.icon() # User/Members icon
        self.browser_icon_label = BodyLabel()
        self.browser_icon_label.setPixmap(self.browser_icon.pixmap(20, 20))
        
        self.browser_text_layout = QVBoxLayout()
        self.browser_text_layout.setSpacing(2)
        self.browser_title = BodyLabel("Premium Üyelik (Çerezler)", self)
        self.browser_title.setStyleSheet("font-size: 14px; font-weight: 500;")
        self.browser_desc = BodyLabel("Premium içerikler için tarayıcı oturumunu kullan.", self)
        self.browser_desc.setTextColor("#808080", "#909090")
        self.browser_privacy = BodyLabel("Kişisel verileriniz saklanmaz, sadece indirme yetkisi için kullanılır.", self)
        self.browser_privacy.setStyleSheet("font-size: 10px; color: #606060; margin-top: 2px;")

        self.browser_text_layout.addStretch(1)
        self.browser_text_layout.addWidget(self.browser_title)
        self.browser_text_layout.addWidget(self.browser_desc)
        self.browser_text_layout.addWidget(self.browser_privacy)
        self.browser_text_layout.addStretch(1)

        self.browser_combo = ComboBox(self)
        self.browser_combo.addItems([
            "Kapalı",
            "Chrome", 
            "Firefox", 
            "Edge", 
            "Opera", 
            "Brave", 
            "Vivaldi"
        ])
        self.browser_combo.setFixedWidth(160)
        self.browser_combo.currentIndexChanged.connect(self.change_browser)

        self.browser_layout.addWidget(self.browser_icon_label)
        self.browser_layout.addSpacing(15)
        self.browser_layout.addLayout(self.browser_text_layout)
        self.browser_layout.addStretch(1)
        self.browser_layout.addWidget(self.browser_combo)
        
        self.v_layout.addWidget(self.browser_card)
        
        # Load Browser Setting
        self.load_browser_setting()

        self.v_layout.addSpacing(20) # Add some space instead of the title

        # Custom Theme Card (CardWidget)
        self.theme_card = CardWidget(self)
        self.theme_card.setFixedHeight(80)
        self.theme_card_layout = QHBoxLayout(self.theme_card)
        self.theme_card_layout.setContentsMargins(20, 0, 20, 0)
        
        # Icon + Text
        self.theme_icon = FluentIcon.BRUSH.icon()
        self.theme_icon_label = BodyLabel()
        self.theme_icon_label.setPixmap(self.theme_icon.pixmap(20, 20))
        
        self.theme_text_layout = QVBoxLayout()
        self.theme_text_layout.setSpacing(2)
        self.theme_title = BodyLabel("Renk Teması", self)
        self.theme_title.setStyleSheet("font-size: 14px; font-weight: 500;")
        self.theme_desc = BodyLabel("Uygulama vurgu rengini seçin", self)
        self.theme_desc.setTextColor("#808080", "#909090")
        
        self.theme_text_layout.addStretch(1)
        self.theme_text_layout.addWidget(self.theme_title)
        self.theme_text_layout.addWidget(self.theme_desc)
        self.theme_text_layout.addStretch(1)

        self.theme_combo = ComboBox(self)
        self.theme_combo.addItems([
            "Orbit Varsayılan (Mavi)", 
            "Siber Neon (Mor)", 
            "Lüks Altın (Sarı)",
            "Good Ol' Winamp (Turuncu)",
            "Kızıl Gezegen (Kırmızı)",
            "Zümrüt Yeşili (Yeşil)",
            "Derin Okyanus (Turkuaz)"
        ])
        self.theme_combo.setFixedWidth(240)
        self.theme_combo.currentIndexChanged.connect(self.change_theme)

        self.theme_card_layout.addWidget(self.theme_icon_label)
        self.theme_card_layout.addSpacing(15)
        self.theme_card_layout.addLayout(self.theme_text_layout)
        self.theme_card_layout.addStretch(1)
        self.theme_card_layout.addWidget(self.theme_combo)

        self.v_layout.addWidget(self.theme_card)
        self.v_layout.addStretch(1)

        # Load Initial Theme
        self.load_theme()

    def select_folder(self):
        # User selects the PARENT folder
        folder = QFileDialog.getExistingDirectory(self, "Kaydedilecek Konumu Seç", self.folder_card.contentLabel.text())
        if folder:
            folder = os.path.normpath(folder)
            
            # Enforce 'Orbit İndirilenler' subfolder
            target_subfolder = "Orbit İndirilenler"
            if not folder.endswith(target_subfolder):
                folder = os.path.join(folder, target_subfolder)
            
            self.settings.setValue("download_folder", folder)
            self.folder_card.setContent(folder)

    def toggle_subfolders(self, checked: bool):
        val = "true" if checked else "false"
        self.settings.setValue("use_subfolders", val)

    def toggle_open_folder(self, checked: bool):
        val = "true" if checked else "false"
        self.settings.setValue("open_folder_on_complete", val)

    def toggle_debug(self, checked: bool):
        val = "true" if checked else "false"
        self.settings.setValue("debug_mode", val)
        # Apply immediately
        get_logger().update_level()

    def toggle_startup_update(self, checked: bool):
        val = "true" if checked else "false"
        self.settings.setValue("check_updates_on_startup", val)

    def load_theme(self):
        saved_theme = self.settings.value("theme_color", "blue")
        
        mapping = {
            "blue": 0, "purple": 1, "gold": 2, 
            "winamp": 3, "red": 4, "green": 5, "ocean": 6
        }
        idx = mapping.get(saved_theme, 0)
        
        # Block signals to prevent notification on initial load
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.blockSignals(False)
        
        # Apply initially (just in case)
        self.apply_theme_color(saved_theme)
        self.update_visuals()

    def change_theme(self, index):
        mapping = {
            0: "blue", 1: "purple", 2: "gold",
            3: "winamp", 4: "red", 5: "green", 6: "ocean"
        }
        color_key = mapping.get(index, "blue")
        
        self.settings.setValue("theme_color", color_key)
        self.apply_theme_color(color_key)
        self.update_visuals()
        
        InfoBar.success(
            title='Tema Değiştirildi',
            content="Yeni tema başarıyla uygulandı.",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self.window() # Show on main window
        )

    def apply_theme_color(self, key):
        # Always Dark Mode for elegance
        setTheme(Theme.DARK)
        
        if key == "blue":
            setThemeColor('#009FAA') # Orbit Teal/Blue
        elif key == "purple":
            setThemeColor('#D000FF') # Neon Purple
        elif key == "gold":
            setThemeColor('#FFD700') # Gold
        elif key == "winamp":
            setThemeColor('#E69500') # Winamp Classic Orange
        elif key == "red":
            setThemeColor('#FF3B30') # Mars Red
        elif key == "green":
            setThemeColor('#00CC66') # Emerald Green
        elif key == "ocean":
            setThemeColor('#00B4D8') # Deep Ocean Turquoise

    def update_visuals(self):
        """Force update icons and labels to match the new theme color."""
        c = themeColor()
        
        # Update Standard Cards Icons
        # SettingIconWidget uses 'setIcon' with QIcon
        self.folder_card.iconLabel.setIcon(FluentIcon.DOWNLOAD.icon(color=c))
        self.subfolder_switch.iconLabel.setIcon(FluentIcon.LIBRARY.icon(color=c))
        self.open_folder_switch.iconLabel.setIcon(FluentIcon.FOLDER.icon(color=c))
        self.startup_update_switch.iconLabel.setIcon(FluentIcon.SYNC.icon(color=c))
        self.debug_switch.iconLabel.setIcon(FluentIcon.FEEDBACK.icon(color=c))
        
        # Update Custom Cards Icons & Titles
        
        # Theme Card
        self.theme_icon_label.setPixmap(FluentIcon.BRUSH.icon(color=c).pixmap(20, 20))
        # Keep titles white (standard)
        self.theme_title.setStyleSheet("font-size: 14px; font-weight: 500; color: #f0f0f0;")
        
        # Browser Card
        self.browser_icon_label.setPixmap(FluentIcon.PEOPLE.icon(color=c).pixmap(20, 20))
        self.browser_title.setStyleSheet("font-size: 14px; font-weight: 500; color: #f0f0f0;")

    def load_browser_setting(self):
        saved_browser = self.settings.value("browser_cookies", "disabled")
        
        mapping = {
            "disabled": 0, "chrome": 1, "firefox": 2, 
            "edge": 3, "opera": 4, "brave": 5, "vivaldi": 6
        }
        idx = mapping.get(saved_browser, 0)
        
        self.browser_combo.blockSignals(True)
        self.browser_combo.setCurrentIndex(idx)
        self.browser_combo.blockSignals(False)

    def change_browser(self, index):
        mapping = {
            0: "disabled", 1: "chrome", 2: "firefox",
            3: "edge", 4: "opera", 5: "brave", 6: "vivaldi"
        }
        browser_key = mapping.get(index, "disabled")
        
        self.settings.setValue("browser_cookies", browser_key)
        
        if browser_key != "disabled":
            InfoBar.info(
                title='Tarayıcı Seçildi',
                content=f"{self.browser_combo.currentText()} üzerinden oturum bilgileri kullanılacak.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=3000,
                parent=self.window()
            )

