from PySide6.QtCore import QObject, QThread, Signal
from src.version import VERSION
import requests

class CheckUpdateWorker(QThread):
    finished = Signal(dict)
    
    def run(self):
        try:
            # GitHub API for latest release
            url = "https://api.github.com/repos/Sauth-09/Orbit-Medya-Indirici/releases/latest"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.finished.emit({
                    "success": True,
                    "tag": data.get("tag_name", "v0.0"),
                    "url": data.get("html_url", ""),
                    "name": data.get("name", "Update")
                })
            else:
                self.finished.emit({"success": False, "error": f"API Error: {response.status_code}"})
        except Exception as e:
            self.finished.emit({"success": False, "error": str(e)})

class AppUpdateManager(QObject):
    update_available = Signal(str, str) # Tag, URL
    check_finished = Signal(dict) # Raw result (for manual checks)

    def __init__(self):
        super().__init__()
        self.worker = None

    def check_for_updates(self, silent=True):
        self.worker = CheckUpdateWorker()
        self.worker.finished.connect(lambda res: self._on_worker_finished(res, silent))
        self.worker.start()

    def _on_worker_finished(self, result, silent):
        self.check_finished.emit(result)
        
        if not result.get("success"):
            return

        latest_tag = result["tag"]
        download_url = result["url"]
        
        try:
            def parse_ver(v_str):
                return [int(p) for p in v_str.lower().replace("v", "").split(".") if p.isdigit()]

            current_parts = parse_ver(VERSION)
            latest_parts = parse_ver(latest_tag)
            
            if latest_parts > current_parts:
                self.update_available.emit(latest_tag, download_url)
        except Exception:
            pass
