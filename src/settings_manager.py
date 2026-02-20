from PySide6.QtCore import QSettings
import os

def get_settings():
    """
    Returns a standardized QSettings object configured to use an INI file 
    in the user's AppData directory.
    Path: %APPDATA%/Orbit/settings.ini
    """
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "Orbit", "settings")

def get_default_download_folder():
    """
    Returns the centralized path for default downloads.
    """
    return os.path.join(os.path.expanduser("~"), "Desktop", "Orbit İndirilenler")
