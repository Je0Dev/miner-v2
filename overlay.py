"""Live OCR Overlay - Draggable box with auto-OCR and mining.

Workflow:
1. User clicks "Select Region" -> slurp selection box appears
2. User selects region over game text
3. Overlay auto-OCRs that region every 2 seconds
4. Shows captured text + translation + pinyin
5. Auto-copies to clipboard for Yomitan
6. User clicks "Mine" to save with audio recording
"""
import sys, time, tempfile, subprocess, os, threading
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:
    print("ERROR: python-tkinter required"); sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from config import OCR_LANGS, TRANSLATION_LANGS
from ocr import ocr_image
from translate import translate_text, copy_to_clipboard, record_audio, notify
from text import clean_text, format_with_pinyin, sanitize_unicode
from log import log


class LiveOCROverlay:
    def __init__(self, ocr_lang="zh", translate_to="en", source_name="Game"):
        self.ocr_lang = ocr_lang
        self.translate_to = translate_to
        self.source_name = source_name
        self.is_running = False
        self._live_geom = None
        self.current_text = ""
        self.current_translation = ""
        self._build_ui()

    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title("Live OCR Miner")
        self.root.geometry("850x700")
        self.root.minsize(850, 700)
        self.root.attributes("-type", "splash")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        self.root.configure(bg="#1a1a2e")

        main = tk.Frame(self.root, bg="#1a1a2e", padx=10, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(main, text="Live OCR Miner", bg="#1a1a2e", fg="#00d4ff",
                 font=("Sans", 14, "bold")).pack(anchor=tk.W)

        # Status
        self.status_var = tk.StringVar(value="Ready - Select a region to begin")
        tk.Label(main, textvariable=self.status_var, bg="#1a1a2e", fg="#888888",
                 font=("Sans", 9)).pack(anchor=tk.W, pady=(5, 10))

        # Captured Text
        tk.Label(main, text="Captured Text:", bg="#1a1a2e", fg="#ffffff",
                 font=("Sans", 10)).pack(anchor=tk.W)
        self.text_frame = tk.Text(main, height=5, bg="#16213e", fg="#ffffff",
                                   font=("Sans", 14), wrap=tk.WORD, state=tk.DISABLED)
        self.text_frame.pack(fill=tk.X, pady=(0, 8))

        # Translation
        tk.Label(main, text="Translation:", bg="#1a1a2e", fg="#ffffff",
                 font=("Sans", 10)).pack(anchor=tk.W)
        self.trans_frame = tk.Text(main, height=3, bg="#16213e", fg="#00d4ff",
                                    font=("Sans", 14), wrap=tk.WORD, state=tk.DISABLED)
        self.trans_frame.pack(fill=tk.X, pady=(0, 8))

        # Pinyin/Dictionary
        tk.Label(main, text="Pinyin / Dictionary:", bg="#1a1a2e", fg="#ffffff",
                 font=("Sans", 10)).pack(anchor=tk.W)
        self.dict_frame = tk.Text(main, height=2, bg="#16213e", fg="#ffdd57",
                                   font=("Sans", 11), wrap=tk.WORD, state=tk.DISABLED)
        self.dict_frame.pack(fill=tk.X, pady=(0, 8))

        # Action buttons
        btn_frame = tk.Frame(main, bg="#1a1a2e")
        btn_frame.pack(fill=tk.X, pady=5)

        self.start_btn = tk.Button(btn_frame, text="Select Region", bg="#228B22", fg="white",
                                    font=("Sans", 11, "bold"), command=self._select_region,
                                    activebackground="#33AA33", bd=0, padx=15, pady=5)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.live_btn = tk.Button(btn_frame, text="Start Live", bg="#4169E1", fg="white",
                                   font=("Sans", 11, "bold"), command=self._toggle_live,
                                   activebackground="#5577FF", bd=0, padx=15, pady=5)
        self.live_btn.pack(side=tk.LEFT, padx=8)
        self.live_btn.config(state=tk.DISABLED)

        self.mine_btn = tk.Button(btn_frame, text="Mine", bg="#8B4513", fg="white",
                                   font=("Sans", 11, "bold"), command=self._mine,
                                   activebackground="#AA5522", bd=0, padx=15, pady=5)
        self.mine_btn.pack(side=tk.LEFT, padx=8)
        self.mine_btn.config(state=tk.DISABLED)

        # Options
        opts_frame = tk.Frame(main, bg="#1a1a2e")
        opts_frame.pack(fill=tk.X, pady=(10, 5))

        self.vad_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opts_frame, text="VAD Trim", variable=self.vad_var,
                       bg="#1a1a2e", fg="white", selectcolor="#1a1a2e",
                       activebackground="#1a1a2e").pack(side=tk.LEFT)

        tk.Label(opts_frame, text="Audio(s):", bg="#1a1a2e", fg="white").pack(side=tk.LEFT, padx=(15, 3))
        self.audio_var = tk.IntVar(value=5)
        tk.Spinbox(opts_frame, from_=1, to=30, textvariable=self.audio_var,
                   width=3, bg="#16213e", fg="white").pack(side=tk.LEFT)

        # Language selection
        lang_frame = tk.Frame(main, bg="#1a1a2e")
        lang_frame.pack(fill=tk.X, pady=(5, 5))

        tk.Label(lang_frame, text="OCR:", bg="#1a1a2e", fg="white").pack(side=tk.LEFT)
        self.ocr_lang_var = tk.StringVar(value=self.ocr_lang)
        for code in OCR_LANGS:
            tk.Radiobutton(lang_frame, text=code.upper(), variable=self.ocr_lang_var,
                           value=code, bg="#1a1a2e", fg="white", selectcolor="#1a1a2e",
                           activebackground="#1a1a2e", command=self._update_lang).pack(side=tk.LEFT, padx=2)

        tk.Label(lang_frame, text="  To:", bg="#1a1a2e", fg="white").pack(side=tk.LEFT, padx=(5, 1))
        self.trans_lang_var = tk.StringVar(value=self.translate_to)
        for code in TRANSLATION_LANGS:
            tk.Radiobutton(lang_frame, text=code.upper(), variable=self.trans_lang_var,
                           value=code, bg="#1a1a2e", fg="white", selectcolor="#1a1a2e",
                           activebackground="#1a1a2e", command=self._update_lang).pack(side=tk.LEFT, padx=2)

        # Log
        tk.Label(main, text="Log:", bg="#1a1a2e", fg="#ffffff",
                 font=("Sans", 10)).pack(anchor=tk.W)
        self.log_frame = tk.Text(main, height=6, bg="#0f0f23", fg="#88ff88",
                                  font=("Monospace", 8), wrap=tk.WORD, state=tk.DISABLED)
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _log(self, msg):
        f = self.log_frame; f.config(state=tk.NORMAL)
        from datetime import datetime
        f.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {sanitize_unicode(msg)}\n")
        f.see(tk.END); f.config(state=tk.DISABLED)

    def _update_text(self, text, tr):
        self.current_text = sanitize_unicode(text)
        self.current_translation = sanitize_unicode(tr)
        for fr, v in [(self.text_frame, self.current_text), (self.trans_frame, self.current_translation)]:
            fr.config(state=tk.NORMAL); fr.delete("1.0", tk.END); fr.insert("1.0", v)
            fr.config(state=tk.DISABLED)
        py = format_with_pinyin(text) if self.ocr_lang == "zh" else ""
        self.dict_frame.config(state=tk.NORMAL); self.dict_frame.delete("1.0", tk.END)
        if py:
            self.dict_frame.insert("1.0", py)
        self.dict_frame.config(state=tk.DISABLED)
        self.mine_btn.config(state=tk.NORMAL if self.current_text else tk.DISABLED)

    def _update_lang(self):
        self.ocr_lang = self.ocr_lang_var.get()
        self.translate_to = self.trans_lang_var.get()

    def _select_region(self):
        """Show slurp to let user select a region."""
        self.status_var.set("Select region...")
        self.root.iconify()
        time.sleep(0.3)
        try:
            result = subprocess.run(
                ["slurp", "-b", "333333cc", "-c", "ff0000ff", "-s", "ff000044", "-w", "3"],
                capture_output=True, text=True, timeout=30
            )
            self.root.deiconify()
            if result.returncode == 0 and result.stdout.strip():
                self._live_geom = result.stdout.strip()
                self._log(f"Region selected: {self._live_geom}")
                self.status_var.set("Region selected - click Start Live")
                self.live_btn.config(state=tk.NORMAL)
                return True
            else:
                self.status_var.set("Cancelled - try again")
                return False
        except Exception as e:
            self.root.deiconify()
            self.status_var.set(f"Error: {e}")
            return False

    def _toggle_live(self):
        if not self.is_running:
            if not self._live_geom:
                if not self._select_region():
                    return
            self.is_running = True
            self.live_btn.config(text="Stop Live", bg="#CC3333", activebackground="#EE4444")
            self.status_var.set("Live ON - OCRing every 2s")
            self._log("Live mode started")
            self._start_loop()
        else:
            self.is_running = False
            self.live_btn.config(text="Start Live", bg="#4169E1", activebackground="#5577FF")
            self.status_var.set("Live OFF")
            self._log("Live mode stopped")

    def _start_loop(self):
        def _loop():
            while self.is_running:
                try:
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        tmp_path = tmp.name
                    subprocess.run(["grim", "-g", self._live_geom, tmp_path],
                                   check=True, capture_output=True, timeout=5)
                    text = clean_text(ocr_image(Path(tmp_path), self.ocr_lang))
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                    if text and len(text) > 1:
                        tr = translate_text(text, src=self.ocr_lang, dest=self.translate_to)
                        self.root.after(0, lambda t=text, tr=tr: self._update_text(t, tr))
                        self._log(f"New: {text[:50]}")
                        # Auto-copy to clipboard for Yomitan
                        copy_to_clipboard(text)
                    time.sleep(2)
                except Exception as e:
                    self._log(f"Error: {e}")
                    time.sleep(2)
        threading.Thread(target=_loop, daemon=True).start()

    def _mine(self):
        if not self.current_text:
            messagebox.showwarning("Warning", "No text detected. Capture text first.")
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        sd = Path.home() / "Downloads" / "Mining" / ts
        sd.mkdir(parents=True, exist_ok=True)
        for d in ["audio", "images", "video"]:
            (sd / d).mkdir(exist_ok=True)

        dur = self.audio_var.get()
        self.status_var.set(f"Recording {dur}s audio...")
        self._log(f"Mining: {self.current_text[:50]}")

        def _save():
            af_path = sd / f"audio/audio_{ts}.mp3"
            ok = record_audio(af_path, dur)
            af = f"audio/audio_{ts}.mp3" if ok else ""
            py = format_with_pinyin(self.current_text) if self.ocr_lang == "zh" else ""

            entry = {
                "sentence": self.current_text,
                "translation": self.current_translation,
                "audio": af,
                "pinyin": py if py != self.current_text else "",
                "source": self.source_name,
                "timestamp": ts,
            }

            import json
            with open(sd / "entry.json", "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)

            # Append to master
            sentences_json = Path.home() / "Downloads" / "Mining" / "sentences.json"
            all_entries = []
            if sentences_json.exists():
                try:
                    with open(sentences_json, "r", encoding="utf-8") as f:
                        all_entries = json.load(f)
                except Exception:
                    all_entries = []
            all_entries.append(entry)
            with open(sentences_json, "w", encoding="utf-8") as f:
                json.dump(all_entries, f, ensure_ascii=False, indent=2)

            copy_to_clipboard(self.current_text)
            self.root.after(0, lambda: self._log(f"Mined: {self.current_text[:60]}"))
            self.root.after(0, lambda: self.status_var.set(f"Mined! Saved to {sd.name}"))
            self.root.after(0, lambda: notify("Sentence Mined",
                f"Text: {self.current_text[:60]}\nTranslation: {self.current_translation[:60]}\nSaved: {sd.name}",
                timeout=10000))
        threading.Thread(target=_save, daemon=True).start()

    def _on_close(self):
        self.is_running = False
        self.root.destroy()

    def run(self):
        self._log(f"OCR: {self.ocr_lang.upper()} -> {self.translate_to.upper()}")
        self._log("Step 1: Click 'Select Region' to choose text area")
        self._log("Step 2: Click 'Start Live' to auto-OCR every 2s")
        self._log("Step 3: Click 'Mine' to save with audio")
        self.root.mainloop()
