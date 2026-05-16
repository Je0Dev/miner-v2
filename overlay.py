"""Live OCR Overlay - Draggable box with auto-OCR and mining.

Workflow:
1. User clicks "Select Region" -> slurp selection box appears
2. User selects region over game text
3. Overlay auto-OCRs that region every 2 seconds
4. Shows captured text + translation + pinyin
5. Auto-copies to clipboard for Yomitan
6. User clicks "Mine" to save with audio recording
7. Multi-line buffer combines consecutive dialogue lines
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
from ocr import ocr_image, ocr_long_text
from translate import translate_text, copy_to_clipboard, record_audio, notify
from text import clean_text, format_with_pinyin, sanitize_unicode
from multiline import MultiLineBuffer
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
        self._multiline = MultiLineBuffer(max_lines=20, window_sec=30)
        self._build_ui()

    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title("Live OCR Miner")
        self.root.geometry("850x700")
        self.root.minsize(850, 700)
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

        self.select_btn = tk.Button(btn_frame, text="Select Region", bg="#228B22", fg="white",
                                     font=("Sans", 11, "bold"), command=self._select_region,
                                     activebackground="#33AA33", bd=0, padx=15, pady=5)
        self.select_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.live_btn = tk.Button(btn_frame, text="Start Live", bg="#4169E1", fg="white",
                                   font=("Sans", 11, "bold"), command=self._toggle_live,
                                   activebackground="#5577FF", bd=0, padx=15, pady=5)
        self.live_btn.pack(side=tk.LEFT, padx=8)

        self.mine_btn = tk.Button(btn_frame, text="Mine", bg="#8B4513", fg="white",
                                   font=("Sans", 11, "bold"), command=self._mine,
                                   activebackground="#AA5522", bd=0, padx=15, pady=5)
        self.mine_btn.pack(side=tk.LEFT, padx=8)

        self.combine_btn = tk.Button(btn_frame, text="Combine Lines", bg="#6A5ACD", fg="white",
                                      font=("Sans", 11, "bold"), command=self._combine,
                                      activebackground="#7B68EE", bd=0, padx=15, pady=5)
        self.combine_btn.pack(side=tk.LEFT, padx=8)

        # Options
        opts_frame = tk.Frame(main, bg="#1a1a2e")
        opts_frame.pack(fill=tk.X, pady=(10, 5))

        self.vad_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opts_frame, text="VAD Trim", variable=self.vad_var,
                       bg="#1a1a2e", fg="white", selectcolor="#1a1a2e",
                       activebackground="#1a1a2e").pack(side=tk.LEFT)

        self.long_text_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opts_frame, text="Long Text Mode", variable=self.long_text_var,
                       bg="#1a1a2e", fg="white", selectcolor="#1a1a2e",
                       activebackground="#1a1a2e").pack(side=tk.LEFT, padx=10)

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
            self._multiline.clear()
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
                    # Use long text mode if enabled
                    if self.long_text_var.get():
                        text = clean_text(ocr_long_text(Path(tmp_path), self.ocr_lang))
                    else:
                        text = clean_text(ocr_image(Path(tmp_path), self.ocr_lang))
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                    if text and len(text) > 1:
                        # Add to multi-line buffer
                        self._multiline.add(text)
                        # Get combined text
                        combined = self._multiline.get_combined()
                        display_text = combined if combined else text
                        tr = translate_text(display_text, src=self.ocr_lang, dest=self.translate_to)
                        self.root.after(0, lambda t=display_text, tr=tr: self._update_text(t, tr))
                        self._log(f"New: {text[:50]}")
                        # Auto-copy to clipboard for Yomitan
                        copy_to_clipboard(display_text)
                    time.sleep(2)
                except Exception as e:
                    self._log(f"Error: {e}")
                    time.sleep(2)
        threading.Thread(target=_loop, daemon=True).start()

    def _combine(self):
        """Show combined multi-line text."""
        combined = self._multiline.get_all_text()
        if combined:
            tr = translate_text(combined, src=self.ocr_lang, dest=self.translate_to)
            self._update_text(combined, tr)
            self._log(f"Combined {len(self._multiline.get_recent())} lines")
            copy_to_clipboard(combined)
        else:
            self._log("No lines to combine")

    def _mine(self):
        # Use combined text if available, otherwise current text
        text_to_mine = self._multiline.get_all_text() or self.current_text
        if not text_to_mine:
            messagebox.showwarning("Warning", "No text detected. Capture text first.")
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        sd = Path(__file__).parent / "mining" / ts
        sd.mkdir(parents=True, exist_ok=True)
        for d in ["audio", "images", "video"]:
            (sd / d).mkdir(exist_ok=True)

        dur = self.audio_var.get()
        self.status_var.set(f"Recording {dur}s audio...")
        self._log(f"Mining: {text_to_mine[:50]}")

        def _save():
            af_path = sd / f"audio/audio_{ts}.mp3"
            ok = record_audio(af_path, dur)
            af = f"audio/audio_{ts}.mp3" if ok else ""
            py = format_with_pinyin(text_to_mine) if self.ocr_lang == "zh" else ""
            tr = self.current_translation or translate_text(text_to_mine, src=self.ocr_lang, dest=self.translate_to)

            entry = {
                "sentence": text_to_mine,
                "translation": tr,
                "audio": af,
                "pinyin": py if py != text_to_mine else "",
                "source": self.source_name,
                "timestamp": ts,
            }

            import json
            with open(sd / "entry.json", "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)

            # Append to master
            mining_dir = Path(__file__).parent / "mining"
            sentences_json = mining_dir / "sentences.json"
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

            # Append to history
            with open(mining_dir / "history_sentences.txt", "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {text_to_mine[:100]} | {tr[:100]}\n")

            # Append to Anki CSV
            self._append_to_anki_csv(entry)

            copy_to_clipboard(text_to_mine)
            self.root.after(0, lambda: self._log(f"Mined: {text_to_mine[:60]}"))
            self.root.after(0, lambda: self.status_var.set(f"Mined! Saved to {sd.name}"))
            self.root.after(0, lambda: notify("Sentence Mined",
                f"Text: {text_to_mine[:60]}\nTranslation: {tr[:60]}\nSaved: {sd.name}",
                timeout=10000))
            # Clear buffer after mining
            self._multiline.clear()
        threading.Thread(target=_save, daemon=True).start()

    def _on_close(self):
        self.is_running = False
        self.root.destroy()

    def _append_to_anki_csv(self, entry: dict):
        """Append entry to Anki CSV for direct import."""
        import csv
        from pathlib import Path
        from text import get_pinyin
        
        mining_dir = Path(__file__).parent / "mining"
        csv_path = mining_dir / "anki_export.csv"
        fields = ["Sentence", "Translation", "Pinyin", "Audio", "Source", "Timestamp"]
        
        sentence = entry.get("sentence", "").strip()
        if not sentence:
            return
        
        if not csv_path.exists():
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL)
                writer.writeheader()
        
        pinyin = entry.get("pinyin", "").strip() or get_pinyin(sentence)
        audio_path = entry.get("audio", "").strip()
        audio_tag = f"[sound:{Path(audio_path).name}]" if audio_path and Path(audio_path).exists() else ""
        
        row = {
            "Sentence": sentence, "Translation": entry.get("translation", ""),
            "Pinyin": pinyin, "Audio": audio_tag,
            "Source": entry.get("source", ""), "Timestamp": entry.get("timestamp", ""),
        }
        with open(csv_path, "a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL).writerow(row)

    def run(self):
        self._log(f"OCR: {self.ocr_lang.upper()} -> {self.translate_to.upper()}")
        self._log("Step 1: Click 'Select Region' to choose text area")
        self._log("Step 2: Click 'Start Live' to auto-OCR every 2s")
        self._log("Step 3: Click 'Combine Lines' to merge dialogue")
        self._log("Step 4: Click 'Mine' to save with audio")
        self.root.mainloop()
