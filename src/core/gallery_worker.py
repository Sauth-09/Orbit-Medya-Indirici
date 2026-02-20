import os
import sys
import subprocess
import traceback
from PySide6.QtCore import QThread, Signal
from src.core.logger import get_logger

class GalleryWorker(QThread):
    """
    Worker for downloading image galleries using gallery-dl via Subprocess (CLI).
    """
    progress = Signal(str)      # Progress messages
    finished = Signal(str)      # Completion message
    error = Signal(str)         # Error message
    log = Signal(str)           # detailed logs

    def __init__(self, url, options=None):
        super().__init__()
        self.url = url
        self.options = options if options else {}
        self.process = None
        self.is_running = True

    def run(self):
        try:
            self.log.emit("🔍 Galeri motoru başlatılıyor (CLI Modu)...")
            
            # 1. Prepare Command
            # Priority: Local gallery-dl.exe -> System gallery-dl
            
            gdl_path = os.path.join(os.getcwd(), 'gallery-dl.exe')
            if os.path.exists(gdl_path):
                cmd = [gdl_path]
            # Fallback to python module if exe not found
            # We use '-u' for unbuffered output to update UI real-time
            else:
                 # Check if we are running in a PyInstaller bundle
                 if getattr(sys, 'frozen', False):
                     # In PyInstaller, sys.executable is the app itself. We need system Python.
                     # However, a standalone app shouldn't rely on system python. 
                     # But if we must fallback, let's try 'python' from PATH.
                     python_exe = "python"
                 else:
                     python_exe = sys.executable
                     
                 cmd = [python_exe, "-u", "-m", "gallery_dl"]
                 self.log.emit("⚠️ gallery-dl.exe bulunamadı, Python modülü kullanılıyor.")
            
            self.log.emit(f"⚙️ Motor: {cmd[0]}")
            
            # Destination (Base Folder)
            dest_dir = self.options.get('download_folder')
            if dest_dir:
                cmd.extend(["--destination", dest_dir]) # -d
            
            # Directory Structure: "Instagram_Username"
            # We use --filename to force specific subfolder structure relative to destination
            # format: {category}_{username}/{filename}.{extension}
            cmd.extend(["--filename", "{category}_{username}/{filename}.{extension}"])
            
            # Range
            if 'range' in self.options:
                r = self.options['range']
                # Use --range=R format to avoid negative numbers being interpreted as flags
                cmd.append(f"--range={r}")
                self.log.emit(f"📥 Aralık: {r}")

            # Filter (Date, Type)
            # Combine filters if multiple
            filter_parts = []
            
            # Date
            if 'date_after' in self.options:
                try:
                    y, m, d = self.options['date_after'].split('-')
                    # proper python expr for gallery-dl filter
                    filter_parts.append(f"date >= datetime({int(y)}, {int(m)}, {int(d)})")
                except:
                    pass
            
            # Type
            if 'filter_type' in self.options:
                ft = self.options['filter_type']
                filter_parts.append(f"type == '{ft}'")
                
            if filter_parts:
                full_filter = " and ".join([f"({p})" for p in filter_parts])
                cmd.extend(["--filter", full_filter])
                self.log.emit(f"🔧 Filtre: {full_filter}")

            # URL always last (convention)
            cmd.append(self.url)

            # Log command for debug
            # self.log.emit(f"CMD: {' '.join(cmd)}")

            # 2. Execute Subprocess
            # Hide window on Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr to stdout
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                creationflags=0x08000000 # CREATE_NO_WINDOW
            )
            
            # 3. Read Output Real-time
            while True:
                line = self.process.stdout.readline()
                if not line and self.process.poll() is not None:
                    break
                
                if line:
                    line = line.strip()
                    if line:
                        # Log everything to file via logger
                        get_logger().info(f"GDL: {line}")
                        
                        # UI Feedback
                        if line.startswith('#'):
                            self.log.emit(f"ℹ️ {line}")
                        elif "http" in line and "//" in line:
                             pass # Skip raw URLs
                        else:
                             # Show filename or status
                             # If line is a path, show only filename
                             if "\\" in line or "/" in line:
                                 fname = os.path.basename(line)
                                 self.log.emit(f"⬇️ {fname}")
                             else:
                                 self.log.emit(line)

            # 4. Finish
            ret_code = self.process.poll()
            
            if ret_code == 0:
                self.log.emit("✅ İndirme tamamlandı. Dönüştürme kontrol ediliyor...")
                if dest_dir:
                    self._convert_images(dest_dir)
                self.finished.emit("İşlem başarıyla tamamlandı.")
            else:
                # If killed (-9 or 1), it might be user stop
                if ret_code == 1 or ret_code == -9:
                     self.finished.emit("İşlem durduruldu veya iptal edildi.")
                else:
                     self.error.emit(f"İşlem hata koduyla bitti: {ret_code}")

        except Exception as e:
            get_logger().error(f"Gallery Worker Error:\n{traceback.format_exc()}")
            self.error.emit(f"Motor Hatası: {str(e)}")

    def stop(self):
        """Force kill the process."""
        self.is_running = False
        if self.process:
            try:
                self.log.emit("🛑 İşlem durduruluyor...")
                self.process.kill()
            except:
                pass

    def _convert_images(self, root_dir):
        if not root_dir or not os.path.exists(root_dir):
            return

        ffmpeg_path = os.path.join(os.getcwd(), 'ffmpeg.exe')
        if not os.path.exists(ffmpeg_path):
            # Try system path by calling it
            try:
                subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                ffmpeg_path = 'ffmpeg'
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.log.emit("⚠️ FFmpeg bulunamadı, dönüştürme atlanıyor.")
                return

        self.log.emit("⚙️ WebP dosyaları JPG formatına dönüştürülüyor...")
        
        count = 0

        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if file.lower().endswith('.webp'):
                    webp_path = os.path.join(root, file)
                    jpg_path = os.path.splitext(webp_path)[0] + ".jpg"
                    
                    try:
                        # ffmpeg -i input.webp -q:v 2 output.jpg
                        # -q:v 2 is high quality
                        cmd = [
                            ffmpeg_path, '-y', 
                            '-v', 'error',
                            '-i', webp_path, 
                            '-q:v', '2', 
                            jpg_path
                        ]
                        
                        subprocess.run(cmd, check=True, creationflags=0x08000000)
                        
                        # Delete original
                        os.remove(webp_path)
                        count += 1
                    except Exception as e:
                        # print(f"Convert error: {e}")
                        pass
        
        if count > 0:
             self.log.emit(f"✅ {count} görsel JPG formatına dönüştürüldü.")
