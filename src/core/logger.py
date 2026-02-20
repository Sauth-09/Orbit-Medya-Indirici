import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from src.settings_manager import get_settings

class OrbitLogger:
    _instance = None

    @staticmethod
    def get_instance():
        if OrbitLogger._instance is None:
            OrbitLogger()
        return OrbitLogger._instance

    def __init__(self):
        if OrbitLogger._instance is not None:
             raise Exception("This class is a singleton!")
        else:
             OrbitLogger._instance = self
             self.logger = logging.getLogger("OrbitLogger")
             self.logger.setLevel(logging.DEBUG) # Catch all, handler decides what to write
             self.setup_handlers()

    def setup_handlers(self):
        # 1. Determine Path (AppData/Roaming/Orbit)
        app_data = os.getenv('APPDATA') # Returns Roaming on Windows
        log_dir = os.path.join(app_data, 'Orbit')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        self.log_file = os.path.join(log_dir, 'orbit_debug.log')
        
        # 2. Check Settings for Enabled/Disabled
        settings = get_settings()
        is_debug = settings.value("debug_mode", "false") == "true"
        
        # 3. Create Handlers
        # File Handler (Rotation: 1MB, 1 Backup - Keeps specific limit, loops over 2 files max)
        self.file_handler = RotatingFileHandler(
            self.log_file, maxBytes=1*1024*1024, backupCount=1, encoding='utf-8'
        )
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.file_handler.setFormatter(formatter)
        
        # Level based on setting
        if is_debug:
            self.file_handler.setLevel(logging.DEBUG)
        else:
            self.file_handler.setLevel(logging.CRITICAL) # Effectively off for normal usage
            
        # Console Handler (Optional, for IDE)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if is_debug else logging.INFO)
        console_handler.setFormatter(formatter)
        
        # Clear existing
        if self.logger.handlers:
            self.logger.handlers.clear()
            
        self.logger.addHandler(self.file_handler)
        self.logger.addHandler(console_handler)
        
        # Session Separator (If debug is on)
        if is_debug:
            self.logger.info("\n" + "="*50 + "\nOrbit Downloader Session Started\n" + "="*50)

    def update_level(self):
        settings = get_settings()
        is_debug = settings.value("debug_mode", "false") == "true"
        
        if is_debug:
            self.file_handler.setLevel(logging.DEBUG)
            # Write separator when enabled
            self.logger.info("\n--- Debug Mode ENABLED ---\n")
        else:
            self.logger.info("\n--- Debug Mode DISABLED ---\n")
            self.file_handler.setLevel(logging.CRITICAL)

    def log(self, message):
        self.logger.info(message)

    def info(self, message):
        self.logger.info(message)

    def error(self, message):
        self.logger.error(message)

    def debug(self, message):
        self.logger.debug(message)

# Global Access
def get_logger():
    return OrbitLogger.get_instance()
