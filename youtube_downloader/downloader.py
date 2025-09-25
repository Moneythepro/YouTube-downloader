# downloader.py
import os
from pytube import YouTube
import threading
import queue
from utils import human_size
from dotenv import load_dotenv
import time

load_dotenv()
DEFAULT_DIR = os.getenv('DOWNLOAD_DIR', os.path.join(os.path.expanduser("~"), "Downloads"))

class Downloader:
    def __init__(self, url, out_dir=DEFAULT_DIR, on_progress=None, on_complete=None):
        self.url = url
        self.out_dir = out_dir
        self.on_progress = on_progress  # callback(percent:int)
        self.on_complete = on_complete  # callback(filepath:str, filesize:int, title:str)
        self._yt = None
        self._stream = None

    def _progress_func(self, stream, chunk, bytes_remaining):
        total = stream.filesize
        bytes_downloaded = total - bytes_remaining
        percent = int(bytes_downloaded / total * 100)
        if self.on_progress:
            self.on_progress(percent)

    def prepare(self, audio_only=False, itag=None):
        self._yt = YouTube(self.url, on_progress_callback=self._progress_func)
        if audio_only:
            self._stream = self._yt.streams.filter(only_audio=True).order_by('abr').desc().first()
        elif itag:
            self._stream = self._yt.streams.get_by_itag(itag)
        else:
            self._stream = self._yt.streams.get_highest_resolution()
        return {
            'title': self._yt.title,
            'author': self._yt.author,
            'length': self._yt.length,
            'filesize': self._stream.filesize
        }

    def download(self):
        # run in background thread to avoid blocking
        def _run(q):
            try:
                filepath = self._stream.download(output_path=self.out_dir)
                filesize = os.path.getsize(filepath)
                if self.on_complete:
                    self.on_complete(filepath, filesize, self._yt.title)
                q.put(("done", filepath))
            except Exception as e:
                q.put(("error", str(e)))
        q = queue.Queue()
        t = threading.Thread(target=_run, args=(q,), daemon=True)
        t.start()
        return q  # caller can read queue for done/error