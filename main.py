import sys
import os
from PySide6.QtCore import QtMsgType, qInstallMessageHandler

# -----------------------------------------------------------------------------
# 1. CRITICAL: Environment Configuration
# This MUST happen before any Qt imports to avoid conflicts and scaling issues.
# -----------------------------------------------------------------------------
os.environ["QT_API"] = "pyside6"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0" # Let FluentWidgets handle DPI
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PySide6.QtWidgets import QApplication
import traceback

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    from src.core.logger import get_logger
    logger = get_logger()
    logger.error("Uncaught exception:")
    logger.error("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))

sys.excepthook = handle_exception

def qt_message_handler(mode, context, message):
    from src.core.logger import get_logger
    logger = get_logger()
    
    msg = f"Qt ({context.file}:{context.line}, {context.function}): {message}"
    
    if mode == QtMsgType.QtDebugMsg:
        logger.debug(msg)
    elif mode == QtMsgType.QtInfoMsg:
        logger.log(msg)
    elif mode == QtMsgType.QtWarningMsg:
        logger.error(f"Qt Warning: {msg}")
    elif mode == QtMsgType.QtCriticalMsg:
        logger.error(f"Qt Critical: {msg}")
    elif mode == QtMsgType.QtFatalMsg:
        logger.error(f"Qt Fatal: {msg}")

def main():
    """
    Main Entry Point
    """
    # Install Qt Handler
    qInstallMessageHandler(qt_message_handler)

    # 2. Initialize Application
    # Must be the very first Qt object created.
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    
    # Initialize Logger
    from src.core.logger import get_logger
    get_logger()

    # 3. Late Import of UI components
    # Importing this earlier would trigger 'Must construct a QApplication...' error
    # because some widgets might try to initialize global styles/fonts.
    from src.ui.main_window import MainWindow

    # 4. Create and Show Window
    window = MainWindow()
    window.show()

    # 5. Execute Event Loop
    sys.exit(app.exec())

if __name__ == '__main__':
    main()