from PySide6.QtGui import QIcon  # En tepeye ekle

# __init__ fonksiyonunun içine, super().__init__() satırından hemen sonra:

from PySide6.QtCore import QSettings, QUrl, Qt, QSize
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import FluentWindow, NavigationItemPosition, FluentIcon as FIF, setTheme, Theme, InfoBar, InfoBarPosition, PushButton
import os
import subprocess
from src.settings_manager import get_settings, get_default_download_folder
from src.version import VERSION
from src.core.app_updater import AppUpdateManager

from src.ui.views.home_view import HomeView
from src.ui.views.settings_view import SettingsView
from src.ui.views.history_view import HistoryView
from src.ui.views.about_view import AboutView
from src.ui.views.converter_view import ConverterView

class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        from src.utils import resource_path
        self.setWindowIcon(QIcon(resource_path("assets/app.ico")))
        setTheme(Theme.DARK)
        
        # Window Setup
        self.setWindowTitle("Orbit")
        self.resize(850, 680) # Increased height for options
        
        # Customize Title Bar
        self.customize_title_bar()
        
        # Create Views
        self.home_view = HomeView("Ana Sayfa")
        self.history_view = HistoryView("Geçmiş")
        self.converter_view = ConverterView("Dönüştürücü")
        self.settings_view = SettingsView("Ayarlar")
        self.about_view = AboutView("Hakkında")
        
        # Init Navigation
        self.init_navigation()

        # Check Updates on Startup
        self.check_updates_on_startup()
        
        # Force Center (Delayed)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self.center_window)

    def customize_title_bar(self):
        # Set a standard slim height
        bar_height = 32
        self.titleBar.setFixedHeight(bar_height)
        
        # Force buttons to match the bar height exactly
        # This prevents the 'thick' look where buttons are smaller than the bar
        for btn in [self.titleBar.minBtn, self.titleBar.maxBtn, self.titleBar.closeBtn]:
            if btn:
                btn.setFixedSize(46, bar_height)
                btn.setIconSize(QSize(10, 10))

    def center_window(self):
        # Allow resizing smaller
        self.setMinimumSize(800, 500)
        
        # Get Available Geometry (Excluded Taskbar)
        screen = QApplication.primaryScreen()
        work_area = screen.availableGeometry()
        
        target_w = 860
        target_h = 680
        
        # Clamp to screen size with explicit margin
        max_h = work_area.height() - 50 # Ensure taskbar clearance
        final_w = min(target_w, work_area.width() - 20)
        final_h = min(target_h, max_h)
        
        # Force resize
        self.resize(final_w, final_h)
        
        w, h = final_w, final_h
        
        # Calculate Center relative to Work Area
        x = work_area.x() + (work_area.width() - w) // 2
        y = work_area.y() + (work_area.height() - h) // 2
        
        # Safety Clamp: Ensure we don't start 'above' the work area
        y = max(work_area.y(), y)
        
        # Ensure we don't go below screen
        if y + h > work_area.bottom():
             y = work_area.bottom() - h

        self.move(x, y)

    def init_navigation(self):
        # 1. Home / Dashboard
        self.addSubInterface(
            self.home_view, 
            FIF.HOME, 
            "Ana Sayfa"
        )

        # 1.3 Converter
        self.addSubInterface(
            self.converter_view,
            FIF.EDIT,
            "Dönüştürücü"
        )

        # 1.5 History
        self.addSubInterface(
            self.history_view,
            FIF.HISTORY,
            "Geçmiş"
        )

        # 2. About (Bottom)
        self.addSubInterface(
            self.about_view,
            FIF.INFO,
            "Hakkında",
            NavigationItemPosition.BOTTOM
        )

        # 3. Settings (Bottom)
        self.addSubInterface(
            self.settings_view,
            FIF.SETTING,
            "Ayarlar",
            NavigationItemPosition.BOTTOM
        )

    def check_updates_on_startup(self):
        settings = get_settings()
        if settings.value("check_updates_on_startup", "false") == "true":
            self.app_updater = AppUpdateManager()
            self.app_updater.update_available.connect(self.on_update_available)
            self.app_updater.check_for_updates(silent=True)

    def on_update_available(self, tag, url):
        # Notify User
        bar = InfoBar.info(
            title=f"Yeni Güncelleme: {tag}",
            content="Daha iyi bir deneyim için güncelleyin.",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=10000, # 10 seconds
            parent=self
        )
        
        # Add Download Button to InfoBar? 
        # InfoBar 'createCustomInfoBar' or default has no button.
        # But we can make clicking it open link or add a button?
        # Actually standard InfoBar doesn't support custom buttons easily in 'info' static method.
        # We can use 'addWidget' if we create instance manually.
        # Use Warning or Success?
        # Let's create an instance to add button.
        
        bar.close() # Close the static one I just thought of.
        
        # Proper Custom InfoBar
        info_bar = InfoBar(
            icon=FIF.Download,
            title=f"Yeni Güncelleme Mevcut: {tag}",
            content="İndirmek için tıklayın.",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=10000,
            parent=self
        )
        
        # Add Button
        btn = PushButton("İndir")
        btn.setFixedWidth(80)
        btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        
        info_bar.addWidget(btn)
        info_bar.show()

    def closeEvent(self, event):
        """
        Handle application close event to clean up resources.
        """
        print("Uygulama kapatılıyor, temizlik yapılıyor...")
        # Stop UI Workers first
        if hasattr(self, 'home_view'):
            self.home_view.stop_workers()
        if hasattr(self, 'converter_view'):
            self.converter_view.stop_workers()
            
        from src.utils import kill_external_processes
        kill_external_processes()
        self.clean_incomplete_downloads()
        super().closeEvent(event)

    def clean_incomplete_downloads(self):
        """
        Deletes .part, .ytdl and temporary files from the download folder.
        """
        try:
            settings = get_settings()
            default_path = get_default_download_folder()
            download_folder = settings.value("download_folder", default_path)
            
            if os.path.exists(download_folder):
                for fname in os.listdir(download_folder):
                    # Check for temporary extensions
                    if fname.endswith(('.part', '.ytdl', '.temp', '.lock')):
                        full_path = os.path.join(download_folder, fname)
                        try:
                            if os.path.isfile(full_path):
                                os.remove(full_path)
                                print(f"Temizlendi: {fname}")
                        except Exception as e:
                            print(f"Silme hatası ({fname}): {e}")
        except Exception as e:
            print(f"Temizlik hatası: {e}")
