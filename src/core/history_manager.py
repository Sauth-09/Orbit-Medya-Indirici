import json
import os
from datetime import datetime
from PySide6.QtCore import QObject, Signal

class HistoryManager(QObject):
    """
    Manages download history using a JSON file in AppData.
    """
    history_changed = Signal()

    def __init__(self):
        super().__init__()
        self.history_file = os.path.join(
            os.getenv('APPDATA'),
            "Orbit",
            "history.json"
        )
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(os.path.dirname(self.history_file)):
            os.makedirs(os.path.dirname(self.history_file))
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def add_entry(self, title, url, file_path):
        entry = {
            "title": title,
            "url": url,
            "path": file_path,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        history = self.get_history()
        history.insert(0, entry) # Add to top
        
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=4, ensure_ascii=False)
            
        self.history_changed.emit()

    def get_history(self):
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def clear_history(self):
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump([], f)
        self.history_changed.emit()

# Global Instance
history_manager = HistoryManager()
