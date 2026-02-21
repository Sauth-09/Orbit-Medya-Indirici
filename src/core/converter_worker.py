import os
import subprocess
import re
import json
from PySide6.QtCore import QThread, Signal
from src.core.logger import get_logger

class MediaInfoWorker(QThread):
    finished = Signal(dict)
    
    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.ffprobe_path = os.path.join(os.getcwd(), 'ffprobe.exe')
        
    def run(self):
        info = {
            'duration': '-',
            'resolution': '-',
            'size': '-',
            'type': '-',
            'extra': '-' # For Bitrate or FPS
        }
        if not os.path.exists(self.ffprobe_path) or not os.path.exists(self.filepath):
            self.finished.emit(info)
            return
            
        try:
            # Get size
            size_bytes = os.path.getsize(self.filepath)
            info['size'] = f"{size_bytes / (1024*1024):.2f} MB"
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            cmd = [
                self.ffprobe_path, 
                '-v', 'error', 
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,r_frame_rate,bit_rate:format=duration', 
                '-of', 'default=noprint_wrappers=1:nokey=1', 
                self.filepath
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startupinfo)
            lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
            
            if len(lines) >= 4:
                # ffprobe output order can vary, but usually formats before streams
                # Let's use JSON format for robust parsing instead of default format
                cmd_json = [
                    self.ffprobe_path, 
                    '-v', 'error', 
                    '-print_format', 'json',
                    '-show_format', '-show_streams',
                    self.filepath
                ]
                res_j = subprocess.run(cmd_json, stdout=subprocess.PIPE, text=True, startupinfo=startupinfo)
                data = json.loads(res_j.stdout)
                
                # Format
                fmt = data.get('format', {})
                dur_sec = float(fmt.get('duration', 0))
                bitrate = int(fmt.get('bit_rate', 0))
                
                m, s = divmod(dur_sec, 60)
                h, m = divmod(m, 60)
                if h > 0:
                    info['duration'] = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
                else:
                    info['duration'] = f"{int(m):02d}:{int(s):02d}"
                    
                # Find Video Stream
                v_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
                if v_stream:
                     info['type'] = 'Video'
                     w = v_stream.get('width', 0)
                     h = v_stream.get('height', 0)
                     info['resolution'] = f"{w}x{h}"
                     
                     fps_str = v_stream.get('r_frame_rate', '0/1')
                     if '/' in fps_str:
                          n, d = fps_str.split('/')
                          fps = round(float(n)/float(d), 2) if float(d) > 0 else 0
                          info['extra'] = f"{fps} FPS"
                else:
                     # Audio only?
                     a_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'audio'), None)
                     if a_stream:
                          info['type'] = 'Ses (Audio)'
                          info['resolution'] = 'Yok'
                          if bitrate > 0:
                               info['extra'] = f"{int(bitrate/1000)} kbps"
                          
        except Exception as e:
            get_logger().error(f"MediaInfo Parse Error: {str(e)}")
            
        self.finished.emit(info)

class ConverterWorker(QThread):
    progress = Signal(int)       # 0-100
    finished = Signal(str, str)  # Output path, Message
    error = Signal(str)          # Error message
    log = Signal(str)            # Status log messages

    def __init__(self, input_path, output_path, opts=None):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.opts = opts if opts else {}
        self.is_running = True
        self.process = None
        self.ffmpeg_path = os.path.join(os.getcwd(), 'ffmpeg.exe')
        self.ffprobe_path = os.path.join(os.getcwd(), 'ffprobe.exe')

    def run(self):
        try:
            self.log.emit("Dönüştürme işlemi başlatılıyor...")
            
            if not os.path.exists(self.input_path):
                raise Exception("Giriş dosyası bulunamadı.")
                
            if not os.path.exists(self.ffmpeg_path):
                raise Exception("ffmpeg.exe bulunamadı.")

            # Get video duration
            duration_sec = self._get_duration(self.input_path)
            
            # Start FFMPEG
            cmd = [self.ffmpeg_path, '-y']
            
            trim_start = self.opts.get('trim_start')
            trim_end = self.opts.get('trim_end')
            
            # Sub-second duration difference calculation if trimmed
            process_duration = duration_sec
            start_sec = 0
            if trim_start:
                cmd.extend(['-ss', trim_start])
                start_sec = self._parse_time(trim_start) or 0
                if duration_sec > 0:
                     process_duration = duration_sec - start_sec
                
            cmd.extend(['-i', self.input_path])
            
            if trim_end:
                cmd.extend(['-to', trim_end])
                end_sec = self._parse_time(trim_end)
                if end_sec:
                    process_duration = end_sec - start_sec
                    
            if process_duration <= 0 and duration_sec > 0:
                process_duration = duration_sec # fallback
            
            # Apply speed modifier to process duration
            speed_mult = float(self.opts.get('speed', 1.0))
            if speed_mult > 0:
                 process_duration = process_duration / speed_mult

            out_format = self.opts.get('format', 'mp4')
            mute_audio = self.opts.get('mute', False)
            
            if out_format == 'mp3' or out_format == 'm4a':
                 cmd.extend(['-vn']) # No video
                 if speed_mult != 1.0:
                      cmd.extend(['-filter:a', f'atempo={speed_mult}'])
                      
                 if out_format == 'mp3':
                     cmd.extend(['-acodec', 'libmp3lame'])
                     aq = self.opts.get('audio_quality', '192k')
                     cmd.extend(['-ab', aq])
                 elif out_format == 'm4a':
                     cmd.extend(['-acodec', 'aac'])
                     aq = self.opts.get('audio_quality', '192k')
                     cmd.extend(['-ab', aq])
            elif out_format == 'gif':
                 cmd.extend(['-an'])
                 vf_filters = []
                 if speed_mult != 1.0:
                      vf_filters.append(f'setpts={1.0/speed_mult}*PTS')
                 # High quality GIF palette filter
                 vf_filters.append('fps=15,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse')
                 
                 cmd.extend(['-vf', ','.join(vf_filters)])
                 cmd.extend(['-loop', '0'])
            else: # Video
                 vq = self.opts.get('video_quality', 'original')
                 fps_val = self.opts.get('fps', 'Orijinal')
                 vbitrate_val = self.opts.get('vbitrate', 'Orijinal')
                 abitrate_val = self.opts.get('abitrate', 'Orijinal')
                 
                 vf_filters = []
                 af_filters = []
                 
                 if vq != 'original':
                      vf_filters.append(f'scale=-2:{vq.replace("p","")}')
                      
                 if fps_val != 'Orijinal' and fps_val.isdigit():
                      vf_filters.append(f'fps={fps_val}')
                      
                 if speed_mult != 1.0:
                      vf_filters.append(f'setpts={1.0/speed_mult}*PTS')
                      af_filters.append(f'atempo={speed_mult}')
                      
                 if vf_filters:
                      cmd.extend(['-vf', ','.join(vf_filters)])
                      
                 if mute_audio:
                      cmd.extend(['-an'])
                 elif af_filters and not mute_audio:
                      cmd.extend(['-filter:a', ','.join(af_filters)])

                 if vf_filters or af_filters or mute_audio or trim_start or trim_end or vbitrate_val != 'Orijinal' or (abitrate_val != 'Orijinal' and not mute_audio):
                      cmd.extend(['-c:v', 'libx264', '-preset', 'fast'])
                      if vbitrate_val != 'Orijinal':
                           cmd.extend(['-b:v', vbitrate_val])
                           
                      if not mute_audio:
                           if not af_filters and abitrate_val == 'Orijinal':
                                cmd.extend(['-c:a', 'copy'])
                           else:
                                cmd.extend(['-c:a', 'aac'])
                                if abitrate_val != 'Orijinal':
                                     cmd.extend(['-b:a', abitrate_val])
                 else:
                      cmd.extend(['-c:v', 'copy', '-c:a', 'copy'])
                 
            cmd.extend([self.output_path])
            
            # Overwrite global output progress to read it
            self.log.emit("İşleniyor...")
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding='utf-8',
                errors='ignore',
                startupinfo=startupinfo
            )
            
            time_pattern = re.compile(r"time=(\d+:\d+:\d+\.\d+)")
            
            for line in self.process.stdout:
                if not self.is_running:
                     self.process.kill()
                     raise Exception("Kullanıcı tarafından iptal edildi.")
                
                # Parse progress
                match = time_pattern.search(line)
                if match and process_duration > 0:
                     time_str = match.group(1) # e.g. 00:00:10.50
                     current_sec = self._parse_time(time_str)
                     if current_sec:
                          percent = min(100, int((current_sec / process_duration) * 100))
                          self.progress.emit(percent)

            self.process.wait()
            
            if self.process.returncode != 0 and self.is_running:
                 raise Exception(f"FFMPEG Hatası (Kod: {self.process.returncode})")
                 
            if self.is_running:
                 self.progress.emit(100)
                 self.finished.emit(self.output_path, "Dönüştürme tamamlandı!")
                 
        except Exception as e:
             get_logger().error(f"Converter error: {str(e)}")
             if self.is_running:
                  self.error.emit(str(e))
        finally:
             self.is_running = False

    def _get_duration(self, filepath):
        if not os.path.exists(self.ffprobe_path):
             return 0
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            cmd = [
                self.ffprobe_path, 
                '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'default=noprint_wrappers=1:nokey=1', 
                filepath
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startupinfo)
            return float(result.stdout.strip())
        except:
            return 0

    def _parse_time(self, time_str):
        if not time_str:
            return None
        try:
            parts = [float(p) for p in time_str.split(':')]
            if len(parts) == 1:
                return parts[0]
            elif len(parts) == 2: # MM:SS
                return parts[0] * 60 + parts[1]
            elif len(parts) == 3: # HH:MM:SS
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except:
            return None
        return None

    def stop(self):
        self.is_running = False
        if self.process:
            try:
                self.process.kill()
            except:
                pass
