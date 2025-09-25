# gui.py
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from downloader import Downloader
from db import ensure_table, insert_download, fetch_history
from firestore_client import add_record_to_firestore
from utils import human_size, now_str
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DIR = os.getenv('DOWNLOAD_DIR', os.path.join(os.path.expanduser("~"), "Downloads"))

# Optional: use ttkbootstrap if installed for nicer theme
try:
    import ttkbootstrap as tb
    TB = True
except Exception:
    TB = False

class App:
    def __init__(self, root):
        self.root = root
        root.title("Boombae YouTube Downloader")
        root.geometry("800x520")
        self.download_dir = DEFAULT_DIR

        if TB:
            self.style = tb.Style('flatly')
        else:
            self.style = ttk.Style()

        ensure_table()
        self.build_ui()
        self.load_history()

    def build_ui(self):
        pad = 8
        frm = ttk.Frame(self.root, padding=pad)
        frm.pack(fill="both", expand=True)

        # URL entry
        url_lbl = ttk.Label(frm, text="YouTube URL:")
        url_lbl.grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(frm, textvariable=self.url_var, width=70)
        url_entry.grid(row=0, column=1, columnspan=3, sticky="ew", padx=6)

        # Format selection
        self.format_var = tk.StringVar(value="video")
        ttk.Radiobutton(frm, text="Video", variable=self.format_var, value="video").grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(frm, text="Audio (mp3)", variable=self.format_var, value="audio").grid(row=1, column=2, sticky="w")

        # Quality dropdown (basic; we will supply highest/res)
        ttk.Label(frm, text="Quality:").grid(row=2, column=0, sticky="w")
        self.quality_var = tk.StringVar(value="highest")
        quality_cb = ttk.Combobox(frm, textvariable=self.quality_var, values=["highest","720p","480p","360p"], width=12, state="readonly")
        quality_cb.grid(row=2, column=1, sticky="w")

        # Download dir chooser
        dir_btn = ttk.Button(frm, text="Change Folder", command=self.change_folder)
        dir_btn.grid(row=2, column=3, sticky="e")
        self.dir_lbl = ttk.Label(frm, text=f"Save to: {self.download_dir}")
        self.dir_lbl.grid(row=3, column=0, columnspan=4, sticky="w", pady=(2,10))

        # Progressbar & percent
        self.progress_var = tk.IntVar(value=0)
        self.progress = ttk.Progressbar(frm, orient="horizontal", length=500, mode="determinate", variable=self.progress_var)
        self.progress.grid(row=4, column=0, columnspan=3, sticky="w", pady=6)
        self.percent_lbl = ttk.Label(frm, text="0%")
        self.percent_lbl.grid(row=4, column=3, sticky="e")

        # Download button
        dl_btn = ttk.Button(frm, text="Download", command=self.on_download_clicked)
        dl_btn.grid(row=5, column=3, sticky="e", pady=6)

        # Status message
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(frm, textvariable=self.status_var).grid(row=6, column=0, columnspan=4, sticky="w")

        # Separator
        sep = ttk.Separator(frm, orient="horizontal")
        sep.grid(row=7, column=0, columnspan=4, sticky="ew", pady=10)

        # History Table
        ttk.Label(frm, text="Download History:").grid(row=8, column=0, sticky="w")
        columns = ("id","title","format","size","time","path")
        self.tree = ttk.Treeview(frm, columns=columns, show="headings", height=10)
        for col in columns:
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=120, anchor="w")
        self.tree.grid(row=9, column=0, columnspan=4, sticky="nsew")
        # Make rows expandable
        frm.rowconfigure(9, weight=1)
        frm.columnconfigure(1, weight=1)

        # Right click menu for history
        self.tree.bind("<Double-1>", self.on_history_open)

    def change_folder(self):
        path = filedialog.askdirectory(initialdir=self.download_dir)
        if path:
            self.download_dir = path
            self.dir_lbl.config(text=f"Save to: {self.download_dir}")

    def on_download_clicked(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Input required", "Please paste a YouTube URL.")
            return
        fmt = self.format_var.get()
        self.progress_var.set(0)
        self.percent_lbl.config(text="0%")
        self.status_var.set("Preparing download...")

        # Start background thread to prepare & download
        t = threading.Thread(target=self._start_download, args=(url, fmt), daemon=True)
        t.start()

    def _start_download(self, url, fmt):
        try:
            d = Downloader(url, out_dir=self.download_dir, on_progress=self._on_progress, on_complete=self._on_complete)
            meta = d.prepare(audio_only=(fmt=="audio"))
            title = meta['title']
            filesize = meta['filesize'] or 0
            self.status_var.set(f"Downloading: {title}")
            q = d.download()  # returns queue for result
            # wait for result
            while True:
                try:
                    msg, payload = q.get(timeout=0.5)
                    if msg == "done":
                        filepath = payload
                        final_size = os.path.getsize(filepath)
                        size_str = human_size(final_size)
                        # insert into MySQL
                        insert_download(title, url, fmt, size_str, filepath, now_str())
                        # push to firestore (best effort)
                        try:
                            add_record_to_firestore("downloads", {
                                "title": title,
                                "url": url,
                                "format": fmt,
                                "size": size_str,
                                "path": filepath,
                                "download_time": now_str()
                            })
                        except Exception as e:
                            # don't stop app if firestore fails
                            print("Firestore write failed:", e)
                        self.status_var.set(f"Downloaded: {title} ({size_str})")
                        self.load_history()
                        break
                    elif msg == "error":
                        self.status_var.set(f"Error: {payload}")
                        messagebox.showerror("Download error", payload)
                        break
                except Exception:
                    # loop until queue has something
                    pass
        except Exception as e:
            self.status_var.set(f"Failed: {e}")
            messagebox.showerror("Error", str(e))

    def _on_progress(self, percent):
        # called from download thread: use after to update mainloop
        def _update():
            self.progress_var.set(percent)
            self.percent_lbl.config(text=f"{percent}%")
        self.root.after(0, _update)

    def _on_complete(self, filepath, filesize, title):
        # final UI update
        def _done():
            self.progress_var.set(100)
            self.percent_lbl.config(text="100%")
            self.status_var.set(f"Completed: {title}")
        self.root.after(0, _done)

    def load_history(self):
        # clear
        for r in self.tree.get_children():
            self.tree.delete(r)
        rows = fetch_history(limit=200)
        for r in rows:
            self.tree.insert('', 'end', values=(r['id'], r['title'][:40], r['format'], r['size'], r['download_time'], r['path']))

    def on_history_open(self, event):
        sel = self.tree.selection()
        if not sel: return
        item = self.tree.item(sel[0])
        path = item['values'][5]
        if path and os.path.exists(path):
            if messagebox.askyesno("Open file", "Open downloaded file location?"):
                folder = os.path.dirname(path)
                try:
                    if os.name == 'nt':
                        os.startfile(folder)
                    elif os.uname().sysname == 'Darwin':
                        os.system(f'open "{folder}"')
                    else:
                        os.system(f'xdg-open "{folder}"')
                except Exception as ex:
                    messagebox.showinfo("Open", f"Folder: {folder}\n\n{ex}")
        else:
            messagebox.showinfo("Not found", "File path not found on disk.")

def run_app():
    if TB:
        app = tb.Window(themename="flatly")
        App(app)
        app.mainloop()
    else:
        root = tk.Tk()
        App(root)
        root.mainloop()