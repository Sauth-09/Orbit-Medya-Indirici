import yt_dlp
import os
import sys
import re
from PySide6.QtCore import QThread, Signal
import yt_dlp.utils
from src.core.logger import get_logger

# Pre-compiled regex for ANSI escape codes (used in progress hook)
ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-9;]*m')

class DownloadWorker(QThread):
    """
    Worker thread that handles yt-dlp operations.
    Communicates with the UI via Signals.
    Supports MP4, MP3, M4A, Subtitles, and Time Range Trimming.
    """
    progress = Signal(int)       # 0-100
    finished = Signal(str, str)  # Success message (Title, URL)
    error = Signal(str)          # Error message
    log = Signal(str)            # Status log messages

    def __init__(self, url, fmt='mp4', quality='max', sub_opts=None, trim_opts=None, output_folder=None, playlist_mode=False, browser=None):
        super().__init__()
        self.url = url
        self.fmt = fmt # 'mp4', 'mp3', 'm4a'
        self.quality = quality 
        self.sub_opts = sub_opts if sub_opts else {'enabled': False}
        self.trim_opts = trim_opts if trim_opts else {'enabled': False}
        self.output_folder = output_folder
        self.playlist_mode = playlist_mode
        self.browser = browser
        self.is_running = True
        
        # Locate ffmpeg.exe
        self.ffmpeg_path = os.path.join(os.getcwd(), 'ffmpeg.exe')

    def run(self):
        """
        Main execution method for the thread.
        """
        # Base Options
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [self._progress_hook],
            'ffmpeg_location': os.getcwd(), 
        }

        # Browser Cookies (Premium / Members Only)
        if self.browser and self.browser != 'disabled':
            # yt-dlp expects tuple: (browser_name, profile, container, keyring)
            # We just pass the name, letting it use defaults.
            ydl_opts['cookiesfrombrowser'] = (self.browser, )
            self.log.emit(f"Tarayıcı çerezleri kullanılıyor: {self.browser}")

        # Custom Filename Template
        name_tmpl = '%(title)s'
        
        if self.fmt == 'mp4':
            # Video: Append resolution (e.g. [1080p])
            name_tmpl += ' [%(height)sp]'
        elif self.fmt == 'mp3':
            # Audio: Append Quality Tag
            # self.quality is '0' (Best), '2' (High), '6' (Good)
            q_suffix = {'0': ' [HQ]', '2': ' [SQ]', '6': ' [LQ]'}.get(str(self.quality), '')
            name_tmpl += q_suffix

        # Playlist Logic & Final Template
        if self.playlist_mode:
            ydl_opts['noplaylist'] = False
            ydl_opts['outtmpl'] = f'%(playlist_index)s - {name_tmpl}.%(ext)s'
        else:
            ydl_opts['noplaylist'] = True
            ydl_opts['outtmpl'] = f'{name_tmpl}.%(ext)s'

        # Set Output Folder
        if self.output_folder:
             ydl_opts['paths'] = {'home': self.output_folder}

        # Subtitle Options
        if self.sub_opts.get('enabled', False):
            ydl_opts['writesubtitles'] = True
            ydl_opts['writeautomaticsub'] = True
            
            # Language
            lang = self.sub_opts.get('lang', 'tr')
            if lang == 'all':
                ydl_opts['subtitleslangs'] = ['all']
            else:
                ydl_opts['subtitleslangs'] = [lang] 
            
            # Formats
            ydl_opts['subtitlesformat'] = 'best'

            # Embed vs Separate
            if self.sub_opts.get('embed', False) and self.fmt == 'mp4':
                ydl_opts['embedsubtitles'] = True
            else:
                ydl_opts['embedsubtitles'] = False

        # Trim / Time Range Options
        if self.trim_opts.get('enabled', False):
            start_str = self.trim_opts.get('start', '')
            end_str = self.trim_opts.get('end', '')
            
            start_sec = self._parse_time(start_str)
            end_sec = self._parse_time(end_str)
            
            # Setup download ranges callback
            # yt-dlp expects a list of tuples [(start, end)]
            # If end is None, it goes to end of video
            
            # IMPORTANT: yt_dlp.utils.download_range_func handles logic to tell ffmpeg to cut
            if start_sec is not None:
                ydl_opts['download_ranges'] = yt_dlp.utils.download_range_func(None, [(start_sec, end_sec)])
                ydl_opts['force_keyframes_at_cuts'] = True # Re-encode at cuts for precision

        # Format Specific Options
        audio_fmt_pref = 'bestaudio[language^=tr]/bestaudio/best'
        
        if self.fmt == 'mp3':
            ydl_opts.update({
                'format': audio_fmt_pref,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': self.quality,
                }, {
                    'key': 'EmbedThumbnail', # Embeds the thumbnail
                }, {
                    'key': 'FFmpegMetadata', # Writes metadata
                }],
                'writethumbnail': True,
                'addmetadata': True,
            })
        elif self.fmt == 'm4a':
            ydl_opts.update({
                'format': audio_fmt_pref,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                }, {
                    'key': 'EmbedThumbnail',
                }, {
                    'key': 'FFmpegMetadata',
                }],
                'writethumbnail': True,
                'addmetadata': True,
            })
        else: # mp4 (video)
            # Default 'bestvideo+bestaudio/best' implies Max
            # Prioritize Turkish Audio
            fmt_str = 'bestvideo+bestaudio[language^=tr]/bestvideo+bestaudio/best'
            
            if self.quality != 'max':
                # Limit resolution
                # Complex fallback: 
                # 1. Best Video (Limited) + Best Turkish Audio
                # 2. Best Video (Limited) + Best Audio (Any)
                # 3. Best File (Limited)
                fmt_str = (f'bestvideo[height<={self.quality}]+bestaudio[language^=tr]/'
                           f'bestvideo[height<={self.quality}]+bestaudio/'
                           f'best[height<={self.quality}]')
            
            ydl_opts.update({
                'format': fmt_str,
                'merge_output_format': 'mp4',
            })
        
        ydl_opts['sleep_interval'] = 1 # Wait 1s between requests
        
        # Flag to track if we are in fallback mode
        fallback_mode = False
        
        get_logger().log(f"Starting download: {self.url} | Fmt: {self.fmt} | Playlist: {self.playlist_mode}")

        try:
            self.log.emit(f"Analiz ediliyor: {self.url} ({self.fmt.upper()})")
            
            # Helper to run download
            def perform_download(opts):
                with yt_dlp.YoutubeDL(opts) as ydl:
                    # 1. Extract Info
                    info = ydl.extract_info(self.url, download=False)
                    title = info.get('title', 'Unknown Title')
                    
                    if not fallback_mode:
                        self.log.emit(f"Bulundu: {title}")
                    else:
                        self.log.emit(f"Güvenli Mod: {title}")

                    # 2. Download
                    if self.is_running:
                        self.log.emit(f"İndiriliyor: {title}...")
                        ydl.download([self.url])
                    return title

            # First Attempt: Normal
            try:
                title = perform_download(ydl_opts)
                self.finished.emit(str(title), self.url)
                get_logger().log(f"Download finished: {title}")
                
            except Exception as e:
                err_str = str(e).lower()
                
                # CASE 1: Subtitle Error (429 Too Many Requests)
                if "429" in err_str and ("subtitle" in err_str or "caption" in err_str):
                    # Check if we haven't already retried without subs
                    # We can use a flag attribute on the function or similar, but let's just do a nested try
                    
                    self.log.emit("UYARI: Altyazı sunucusu yoğun (429). 2 saniye beklenip tekrar deneniyor...")
                    QThread.sleep(2) # Sleep 2 seconds
                    
                    try:
                         # Retry ONCE with same settings (maybe it was a blip)
                         # Or maybe try to fetch ONLY auto subs?
                         # Let's just retry exact same first.
                         title = perform_download(ydl_opts)
                         self.finished.emit(str(title), self.url)
                         get_logger().log(f"Download finished (retry success): {title}")
                         return # Exit
                    except Exception as e2:
                        # Second failure
                        self.log.emit("UYARI: Altyazı indirilemedi. Video altyazısız indiriliyor...")
                        
                        # Disable subtitles
                        ydl_opts['writesubtitles'] = False
                        ydl_opts['writeautomaticsub'] = False
                        if 'subtitleslangs' in ydl_opts: del ydl_opts['subtitleslangs']
                        
                        # Retry without subs
                        title = perform_download(ydl_opts)
                        self.finished.emit(str(title), self.url)
                        get_logger().log(f"Download finished (no subs): {title}")

                # CASE 2: SSL / Certificate Errors
                elif "ssl" in err_str or "certificate" in err_str or "cert" in err_str:
                    fallback_mode = True
                    self.log.emit("Güvenli bağlantı hatası, Ağ Toleransı Modu devreye giriyor...")
                    
                    # Enable No Check Certificate
                    ydl_opts['nocheckcertificate'] = True
                    
                    # Retry
                    title = perform_download(ydl_opts)
                    self.finished.emit(str(title), self.url)
                    get_logger().log(f"Download finished (fallback mode): {title}")

                # CASE 3: Browser Cookie / DPAPI Error
                # CASE 3: Browser Cookie / DPAPI Error
                elif "dpapi" in err_str or "decrypt" in err_str or "cookie" in err_str:
                     self.log.emit("UYARI: Tarayıcı çerezleri okunamadı (DPAPI/Kilitli).")
                     self.log.emit("Çerez olmadan tekrar deneniyor...")
                     
                     # Disable cookies for retry
                     if 'cookiesfrombrowser' in ydl_opts:
                         del ydl_opts['cookiesfrombrowser']
                     
                     try:
                         # Retry without cookies
                         title = perform_download(ydl_opts)
                         self.finished.emit(str(title), self.url)
                         get_logger().log(f"Download finished (retry without cookies): {title}")
                         return
                     except Exception as e3:
                         # If it fails even without cookies (e.g. valid private video), show error
                         self.error.emit(
                             f"İndirme başarısız:\n{str(e3)}\n\n"
                             "Not: Çerez hatası tarayıcının açık olmasından kaynaklanabilir. Lütfen tarayıcıyı kapatıp tekrar deneyin."
                         )
                         return 

                else:
                    # Re-raise other errors
                    raise e
                    
        except Exception as e:
            get_logger().error(f"Download Error: {str(e)}")
            # Avoid sending double error signals if we already handled specific cases
            # We can check if is_running is false? No, let's just emit generic if not handled above.
            # But the above 'except' catches e from perform_download.
            # If we re-raise e, it comes here.
            self.error.emit(str(e)) # Show actual error to user
        finally:
            self.is_running = False


    def _parse_time(self, time_str):
        """
        Parses 'MM:SS' or 'HH:MM:SS' or 'SS' into seconds (float).
        Returns None if parsing fails or empty.
        """
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
        """Stops the download process."""
        self.is_running = False

    def _progress_hook(self, d):
        if not self.is_running:
            raise Exception("İndirme kullanıcı tarafından iptal edildi.")

        if d['status'] == 'downloading':
            try:
                # Calculate percentage
                p = d.get('_percent_str', '0%').replace('%','')
                # Remove ANSI escape codes that might be present
                p = ANSI_ESCAPE_PATTERN.sub('', p)
                self.progress.emit(float(p))
                
                # Check speed
                s = d.get('_speed_str', 'N/A')
                self.log.emit(f"İndiriliyor... Hız: {s} - {p}%")
            except Exception:
                pass
        elif d['status'] == 'finished':
            self.progress.emit(100)
            self.log.emit("İndirme tamamlandı, işleniyor...")
