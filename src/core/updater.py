import os
import sys
import subprocess
import requests
import shutil
from datetime import datetime
import traceback
from PySide6.QtCore import QObject, Signal, QThread
from src.settings_manager import get_settings
from src.core.logger import get_logger

class UpdateWorker(QThread):
    finished = Signal(dict, str) # {target: result_bool, ...}, msg

    def __init__(self, targets):
        super().__init__()
        self.targets = targets

    def run(self):
        try:
            self._do_work()
        except Exception as e:
            get_logger().error(f"Critical Updater Thread Error:\n{traceback.format_exc()}")
            # Emit a safe failure siqnal
            self.finished.emit({}, f"Kritik Güncelleme Hatası: {e}")

    def _do_work(self):
        results = {}
        final_msg_parts = []
        
        # 1. YT-DLP Update
        if 'yt-dlp' in self.targets:
            try:
                yt_dlp_path = os.path.join(os.getcwd(), 'yt-dlp.exe')
                if os.path.exists(yt_dlp_path):
                    self._update_ytdlp(yt_dlp_path)
                    results['yt-dlp'] = True
                    final_msg_parts.append("yt-dlp güncellendi")
                else:
                    results['yt-dlp'] = False
                    final_msg_parts.append("yt-dlp bulunamadı")
            except Exception as e:
                results['yt-dlp'] = False
                final_msg_parts.append(f"yt-dlp hatası: {e}")

        # 2. Gallery-DL Update
        if 'gallery-dl' in self.targets:
            try:
                self._update_gallerydl()
                results['gallery-dl'] = True
                final_msg_parts.append("gallery-dl güncellendi")
            except Exception as e:
                results['gallery-dl'] = False
                final_msg_parts.append(f"gallery-dl hatası: {e}")

        full_msg = ", ".join(final_msg_parts) if final_msg_parts else "Güncelleme yok."
        self.finished.emit(results, full_msg)

    def _update_ytdlp(self, path):
        # Helper to run update
        def run_update_cmd(extra_args=[]):
            cmd = [path, "-U"] + extra_args
            # Use startupinfo to hide console window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            subprocess.run(
                cmd, 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                startupinfo=startupinfo
            )

        try:
            run_update_cmd()
        except subprocess.CalledProcessError as e:
            # Check stderr for SSL errors safely
            err_output = e.stderr.decode('utf-8', errors='ignore').lower() if e.stderr else ""
            if "ssl" in err_output or "certificate" in err_output:
                 run_update_cmd(["--no-check-certificate"])
            else:
                raise e

    def _update_gallerydl(self):
        # Download gallery-dl.exe directly from GitHub
        url = "https://github.com/mikf/gallery-dl/releases/latest/download/gallery-dl.exe"
        target_path = os.path.join(os.getcwd(), 'gallery-dl.exe')
        temp_path = target_path + ".temp"
        
        try:
             # Streaming download to a temporary file
             with requests.get(url, stream=True) as r:
                 r.raise_for_status()
                 with open(temp_path, 'wb') as f:
                     for chunk in r.iter_content(chunk_size=8192): 
                         f.write(chunk)
             
             # Safely replace the old executable
             os.replace(temp_path, target_path)
        except Exception as e:
             if os.path.exists(temp_path):
                 try:
                     os.remove(temp_path)
                 except:
                     pass
             raise e

class AutoUpdater(QObject):
    update_started = Signal()
    update_finished = Signal(str) # Message

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.worker = None

    def check_and_update(self):
        targets = []
        
        # Check yt-dlp
        if self._should_update("yt_dlp_last_update"):
            targets.append('yt-dlp')
            
        # Check gallery-dl
        if self._should_update("gallery_dl_last_update"):
            targets.append('gallery-dl')

        if targets:
            self.start_update(targets)

    def _should_update(self, key):
        last_check_str = self.settings.value(key, "")
        if not last_check_str:
            return True
        try:
            last_date = datetime.strptime(last_check_str, "%Y-%m-%d")
            if (datetime.now() - last_date).days > 30:
                return True
        except:
            return True
        return False

    def start_update(self, targets):
        self.update_started.emit()
        self.worker = UpdateWorker(targets)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_finished(self, results, msg):
        today = datetime.now().strftime("%Y-%m-%d")
        
        if results.get('yt-dlp'):
            self.settings.setValue("yt_dlp_last_update", today)
            
        if results.get('gallery-dl'):
            self.settings.setValue("gallery_dl_last_update", today)
            
        self.update_finished.emit(msg)
