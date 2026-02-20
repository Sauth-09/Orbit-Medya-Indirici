import os
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")


    return os.path.join(base_path, relative_path)

def kill_external_processes():
    """
    Kills potential lingering background processes (ffmpeg, ffprobe, yt-dlp).
    """
    import subprocess
    apps = ["ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe"]
    for app in apps:
        try:
            # /F = Forcefully terminate the process
            # /IM = Image Name (process name)
            # /T = Terminates child processes as well
            subprocess.run(f"taskkill /F /IM {app} /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Process kill error ({app}): {e}")
