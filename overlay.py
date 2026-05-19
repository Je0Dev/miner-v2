"""Live OCR Overlay - Draggable box with auto-OCR and editable text (multi-language)."""
import sys, time, tempfile, subprocess, os, threading, json, csv
from pathlib import Path
try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:
    print("ERROR: python-tkinter required"); sys.exit(1)
sys.path.insert(0, str(Path(__file__).parent))
from config import LANG_REGISTRY
from ocr import ocr_image, ocr_long_text
from translate import translate_text, copy_to_clipboard, record_audio, notify
from translate_parallel import translate_parallel
from text import clean_text, sanitize_unicode, get_pronunciation, split_sentences, format_word_breakdown, filter_garbage
from text import normalize_repeating_chars, remove_line_duplicates
from text_replace import apply_text_processing
from stability import MSSIMStabilityDetector
from dictionary import format_definition_display, enrich_word_breakdown
from game_profiles import get_profile, create_profile, _detect_active_window, _get_window_class
from multiline import MultiLineBuffer
from universal_log import log_capture
from log import log

class LiveOCROverlay:
    def __init__(self, ocr_lang="zh", translate_to="en", source_name="Game", auto_hide_sec=15):
        # Auto-detect game and apply profile
        window = _detect_active_window()
        window_class = _get_window_class(window) if window else None
        profile = get_profile(window_class)
        if window_class and window_class not in ("", "unknown"):
            create_profile(window_class)
            source_name = window_class

        self.ocr_lang = profile.get("ocr_lang", ocr_lang)
        self.translate_to = profile.get("translate_to", translate_to)
        self.source_name = source_name
        self.is_running = False
        self._live_geom = None
        self.current_text = ""
        self.current_translation = ""
        self.current_pron = ""
        self._multiline = MultiLineBuffer(max_lines=20, window_sec=30)
        self._user_editing = False
        self._auto_hide_sec = profile.get("auto_hide_sec", auto_hide_sec)
        self._parallel_translate = profile.get("parallel_translate", False)
        self._mssim_enabled = profile.get("mssim_enabled", True)
        self._last_capture_time = 0
        self._auto_hidden = False
        self._prev_text = ""
        self._merged_lines = []
        self._stability = MSSIMStabilityDetector() if self._mssim_enabled else None
        self._last_img_path = None
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
        tk.Label(main, text="Live OCR Miner", bg="#1a1a2e", fg="#00d4ff",
                 font=("Sans", 14, "bold")).pack(anchor=tk.W)
        self.status_var = tk.StringVar(value="Ready - Select a region to begin")
        tk.Label(main, textvariable=self.status_var, bg="#1a1a2e", fg="#888888",
                 font=("Sans", 9)).pack(anchor=tk.W, pady=(5, 10))
        # EDITABLE Captured Text
        tk.Label(main, text="Captured Text (editable):", bg="#1a1a2e", fg="#ffffff",
                 font=("Sans", 10)).pack(anchor=tk.W)
        self.text_frame = tk.Text(main, height=5, bg="#16213e", fg="#ffffff",
                                   font=("Sans", 14), wrap=tk.WORD)
        self.text_frame.pack(fill=tk.X, pady=(0, 8))
        self.text_frame.bind("<KeyRelease>", self._on_text_edit)
        # EDITABLE Translation
        tk.Label(main, text="Translation (editable):", bg="#1a1a2e", fg="#ffffff",
                 font=("Sans", 10)).pack(anchor=tk.W)
        self.trans_frame = tk.Text(main, height=3, bg="#16213e", fg="#00d4ff",
                                    font=("Sans", 14), wrap=tk.WORD)
        self.trans_frame.pack(fill=tk.X, pady=(0, 8))
        self.trans_frame.bind("<KeyRelease>", self._on_trans_edit)
        # Pronunciation + Word Breakdown (read-only, updates dynamically)
        self.pron_label_var = tk.StringVar(value=self._get_pron_label())
        tk.Label(main, textvariable=self.pron_label_var, bg="#1a1a2e", fg="#ffffff",
                 font=("Sans", 10)).pack(anchor=tk.W)
        self.dict_frame = tk.Text(main, height=3, bg="#16213e", fg="#ffdd57",
                                   font=("Sans", 11), wrap=tk.WORD, state=tk.DISABLED)
        self.dict_frame.pack(fill=tk.X, pady=(0, 8))
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
        self.split_btn = tk.Button(btn_frame, text="Split Preview", bg="#6A5ACD", fg="white",
                                    font=("Sans", 11, "bold"), command=self._split_preview,
                                    activebackground="#7B68EE", bd=0, padx=15, pady=5)
        self.split_btn.pack(side=tk.LEFT, padx=8)
        self.discard_btn = tk.Button(btn_frame, text="Discard", bg="#CC3333", fg="white",
                                      font=("Sans", 11, "bold"), command=self._discard,
                                      activebackground="#EE4444", bd=0, padx=15, pady=5)
        self.discard_btn.pack(side=tk.LEFT, padx=8)
        opts_frame = tk.Frame(main, bg="#1a1a2e")
        opts_frame.pack(fill=tk.X, pady=(10, 5))
        self.vad_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opts_frame, text="VAD Trim", variable=self.vad_var,
                       bg="#1a1a2e", fg="white", selectcolor="#1a1a2e",
                       activebackground="#1a1a2e").pack(side=tk.LEFT)
        self.long_text_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opts_frame, text="Long Text", variable=self.long_text_var,
                       bg="#1a1a2e", fg="white", selectcolor="#1a1a2e",
                       activebackground="#1a1a2e").pack(side=tk.LEFT, padx=10)
        self.auto_hide_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opts_frame, text="Auto-hide", variable=self.auto_hide_var,
                       bg="#1a1a2e", fg="white", selectcolor="#1a1a2e",
                       activebackground="#1a1a2e").pack(side=tk.LEFT, padx=5)
        tk.Label(opts_frame, text="Audio(s):", bg="#1a1a2e", fg="white").pack(side=tk.LEFT, padx=(15, 3))
        self.audio_var = tk.IntVar(value=5)
        tk.Spinbox(opts_frame, from_=1, to=30, textvariable=self.audio_var,
                   width=3, bg="#16213e", fg="white").pack(side=tk.LEFT)
        lang_frame = tk.Frame(main, bg="#1a1a2e")
        lang_frame.pack(fill=tk.X, pady=(5, 5))
        tk.Label(lang_frame, text="OCR:", bg="#1a1a2e", fg="white").pack(side=tk.LEFT)
        self.ocr_lang_var = tk.StringVar(value=self.ocr_lang)
        for code in LANG_REGISTRY:
            tk.Radiobutton(lang_frame, text=code.upper(), variable=self.ocr_lang_var,
                           value=code, bg="#1a1a2e", fg="white", selectcolor="#1a1a2e",
                           activebackground="#1a1a2e", command=self._update_lang).pack(side=tk.LEFT, padx=2)
        tk.Label(lang_frame, text="  To:", bg="#1a1a2e", fg="white").pack(side=tk.LEFT, padx=(5, 1))
        self.trans_lang_var = tk.StringVar(value=self.translate_to)
        tk.Radiobutton(lang_frame, text="EN", variable=self.trans_lang_var,
                       value="en", bg="#1a1a2e", fg="white", selectcolor="#1a1a2e",
                       activebackground="#1a1a2e", command=self._update_lang).pack(side=tk.LEFT, padx=2)
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

    def _flash_capture(self):
        """Brief visual flash on text and translation frames to indicate new capture."""
        def _flash():
            self.text_frame.config(bg="#1a3a1a")
            self.trans_frame.config(bg="#1a3a1a")
            self.root.after(300, lambda: self.text_frame.config(bg="#16213e"))
            self.root.after(300, lambda: self.trans_frame.config(bg="#16213e"))
        self.root.after(0, _flash)

    def _update_text(self, text, tr, pron=""):
        self.current_text = sanitize_unicode(text)
        self.current_translation = sanitize_unicode(tr)
        self.current_pron = pron
        self._flash_capture()
        if not self._user_editing:
            self.text_frame.config(state=tk.NORMAL)
            self.text_frame.delete("1.0", tk.END)
            self.text_frame.insert("1.0", self.current_text)
        self.trans_frame.config(state=tk.NORMAL)
        self.trans_frame.delete("1.0", tk.END)
        self.trans_frame.insert("1.0", self.current_translation)
        # Show pronunciation + word breakdown WITH DEFINITIONS
        defn_display = format_definition_display(text, self.ocr_lang)
        display = pron
        if defn_display:
            display += f"\n{defn_display}" if pron else defn_display
        elif pron:
            display = pron
        self.dict_frame.config(state=tk.NORMAL)
        self.dict_frame.delete("1.0", tk.END)
        if display: self.dict_frame.insert("1.0", display)
        self.dict_frame.config(state=tk.DISABLED)

    def _on_text_edit(self, event=None):
        """Called when user edits the captured text - re-translate dynamically."""
        if event and event.char == "": return  # Ignore special keys
        try:
            text = self.text_frame.get("1.0", tk.END).strip()
            if text and len(text) > 1 and text != self.current_text:
                self.current_text = text
                self._user_editing = True
                # Translate in background
                def _retranslate():
                    if self._parallel_translate:
                        result = translate_parallel(text, src=self.ocr_lang, dest=self.translate_to)
                        tr = result["best"]
                    else:
                        tr = translate_text(text, src=self.ocr_lang, dest=self.translate_to)
                    pron = get_pronunciation(text, self.ocr_lang)
                    self.current_translation = tr
                    self.current_pron = pron
                    self.root.after(0, lambda: self._update_display_only(tr, pron))
                    self.root.after(0, lambda: self._log(f"Re-translated: {text[:40]}"))
                threading.Thread(target=_retranslate, daemon=True).start()
        except Exception: pass

    def _on_trans_edit(self, event=None):
        """Called when user edits the translation."""
        try:
            self.current_translation = self.trans_frame.get("1.0", tk.END).strip()
        except Exception: pass

    def _update_display_only(self, tr, pron):
        """Update only translation and pronunciation without touching original text."""
        self.trans_frame.config(state=tk.NORMAL)
        self.trans_frame.delete("1.0", tk.END)
        self.trans_frame.insert("1.0", sanitize_unicode(tr))
        defn_display = format_definition_display(self.current_text, self.ocr_lang)
        display = pron
        if defn_display:
            display += f"\n{defn_display}" if pron else defn_display
        elif pron:
            display = pron
        self.dict_frame.config(state=tk.NORMAL)
        self.dict_frame.delete("1.0", tk.END)
        if display: self.dict_frame.insert("1.0", display)
        self.dict_frame.config(state=tk.DISABLED)
        self._user_editing = False

    def _get_pron_label(self):
        """Get language-specific pronunciation label."""
        info = LANG_REGISTRY.get(self.ocr_lang, {})
        romaji_type = info.get("romaji", "")
        labels = {"pinyin": "Pinyin", "romaji": "Romaji", "romanization": "Romanization", "transliteration": "Transliteration"}
        label = labels.get(romaji_type, "Pronunciation")
        return f"{label} / Word Breakdown:"

    def _update_lang(self):
        self.ocr_lang = self.ocr_lang_var.get()
        self.translate_to = self.trans_lang_var.get()
        self.pron_label_var.set(self._get_pron_label())

    def _select_region(self):
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
                if not self._select_region(): return
            self.is_running = True
            self._multiline.clear()
            self._merged_lines = []
            self._prev_text = ""
            self._auto_hidden = False
            self._last_capture_time = time.time()
            self.live_btn.config(text="Stop Live", bg="#CC3333", activebackground="#EE4444")
            self.status_var.set("Live ON - OCRing every 2s")
            self._log("Live mode started")
            self._start_loop()
        else:
            self.is_running = False
            self._merged_lines = []
            self._prev_text = ""
            self._auto_hidden = False
            self.root.deiconify()
            self.live_btn.config(text="Start Live", bg="#4169E1", activebackground="#5577FF")
            self.status_var.set("Live OFF")
            self._log("Live mode stopped")

    def _start_loop(self):
        self._last_resolution = None
        def _loop():
            consecutive_errors = 0
            while self.is_running:
                try:
                    current_res = (self.root.winfo_screenwidth(), self.root.winfo_screenheight())
                    if self._last_resolution and current_res != self._last_resolution:
                        self._log(f"Resolution changed, reselecting region...")
                        self.root.after(0, lambda: self.status_var.set("Resolution changed - reselect region"))
                        self.is_running = False
                        self.live_btn.config(text="Start Live", bg="#4169E1", activebackground="#5577FF")
                        break
                    self._last_resolution = current_res
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        tmp_path = tmp.name
                    result = subprocess.run(["grim", "-g", self._live_geom, tmp_path],
                                   capture_output=True, timeout=5)
                    if result.returncode != 0:
                        consecutive_errors += 1
                        if consecutive_errors > 3:
                            self._log("Too many capture errors, stopping")
                            self.root.after(0, lambda: self._toggle_live())
                        time.sleep(2)
                        continue
                    consecutive_errors = 0
                    # MSSIM stability check - skip OCR during animations
                    if self._stability and not self._stability.check_stability(Path(tmp_path)):
                        try: os.unlink(tmp_path)
                        except Exception: pass
                        self.root.after(0, lambda: self.status_var.set("Unstable - skipping"))
                        time.sleep(1)
                        continue
                    if self.long_text_var.get():
                        text = clean_text(ocr_long_text(Path(tmp_path), self.ocr_lang))
                    else:
                        text = clean_text(ocr_image(Path(tmp_path), self.ocr_lang))
                    # Apply garbage filtering to remove unicode artifacts
                    text = filter_garbage(text, self.ocr_lang)
                    text = normalize_repeating_chars(text)
                    text = remove_line_duplicates(text)
                    text = apply_text_processing(text)
                    try: os.unlink(tmp_path)
                    except Exception: pass
                    if text and len(text) > 1:
                        self._last_capture_time = time.time()
                        # Auto-unhide if hidden
                        if self._auto_hidden:
                            self._auto_hidden = False
                            self.root.after(0, lambda: self.root.deiconify())
                        # Line merging: detect continuing dialogue
                        if self._should_merge(text):
                            self._merged_lines.append(text)
                            merged = " ".join(self._merged_lines)
                            self._log(f"Merged line ({len(self._merged_lines)} parts): {merged[:60]}")
                            display_text = merged
                        else:
                            self._merged_lines = [text]
                            display_text = text
                        self._multiline.add(text)
                        combined = self._multiline.get_combined()
                        if combined and len(combined) > len(display_text):
                            display_text = combined
                        # Use parallel translation if enabled
                        if self._parallel_translate:
                            result = translate_parallel(display_text, src=self.ocr_lang, dest=self.translate_to)
                            tr = result["best"]
                            # Log all engine results
                            for eng in result.get("results", []):
                                self._log(f"  [{eng['engine']}] {eng['text'][:60]}")
                        else:
                            tr = translate_text(display_text, src=self.ocr_lang, dest=self.translate_to)
                        pron = get_pronunciation(display_text, self.ocr_lang)
                        self.root.after(0, lambda t=display_text, tr=tr, p=pron: self._update_text(t, tr, p))
                        self.root.after(0, lambda: self.status_var.set(f"Captured! ({len(display_text)} chars)"))
                        self._log(f"Text: {text[:60]}")
                        if tr: self._log(f"Translation: {tr[:60]}")
                        if pron: self._log(f"{LANG_REGISTRY.get(self.ocr_lang, {}).get('romaji', 'Pron')}: {pron[:60]}")
                        copy_to_clipboard(display_text)
                        log_capture(sentence=display_text, translation=tr, pronunciation=pron,
                                    source=self.source_name, lang=self.ocr_lang)
                    # Auto-hide after inactivity
                    elif self.auto_hide_var.get() and self._auto_hide_sec > 0 and time.time() - self._last_capture_time > self._auto_hide_sec:
                        if not self._auto_hidden:
                            self._auto_hidden = True
                            self.root.after(0, lambda: self.root.iconify())
                            self._log("Auto-hidden (inactive)")
                    time.sleep(2)
                except subprocess.TimeoutExpired:
                    self._log("Capture timeout")
                    consecutive_errors += 1
                    time.sleep(2)
                except Exception as e:
                    self._log(f"Error: {e}")
                    consecutive_errors += 1
                    if consecutive_errors > 5:
                        self._log("Too many errors, stopping")
                        self.root.after(0, lambda: self._toggle_live())
                    time.sleep(2)
        threading.Thread(target=_loop, daemon=True).start()

    def _should_merge(self, text: str) -> bool:
        """Check if new text is a continuation of previous dialogue."""
        if not self._prev_text or not self._merged_lines:
            self._prev_text = text
            return False
        # Merge if: text shares prefix/suffix with previous, or is short continuation
        prev = self._prev_text
        self._prev_text = text
        # Check if new text starts where previous ended (overlap)
        overlap = min(len(prev), len(text), 20)
        if overlap > 3 and prev[-overlap:] == text[:overlap]:
            return True
        # Check if text is a short continuation (< 30 chars and shares chars)
        if len(text) < 30:
            shared = len(set(text) & set(prev))
            if shared > len(set(text)) * 0.5:
                return True
        # Check if previous ended without sentence terminator
        if prev and not any(prev.endswith(c) for c in "。！？.!?\n"):
            return True
        return False

    def _split_preview(self):
        """Show how text will be split into individual sentences."""
        text = self.text_frame.get("1.0", tk.END).strip()
        if not text:
            self._log("No text to split"); return
        sentences = split_sentences(text)
        if len(sentences) <= 1:
            self._log(f"No split needed (1 sentence)"); return
        preview = f"Will split into {len(sentences)} sentences:\n"
        for i, s in enumerate(sentences, 1):
            preview += f"  {i}. {s[:60]}{'...' if len(s) > 60 else ''}\n"
        self._log(preview.strip())
        self.status_var.set(f"Split preview: {len(sentences)} sentences")

    def _discard(self):
        """Discard current capture and clear fields."""
        self._multiline.clear()
        self.text_frame.config(state=tk.NORMAL)
        self.text_frame.delete("1.0", tk.END)
        self.trans_frame.config(state=tk.NORMAL)
        self.trans_frame.delete("1.0", tk.END)
        self.dict_frame.config(state=tk.NORMAL)
        self.dict_frame.delete("1.0", tk.END)
        self.dict_frame.config(state=tk.DISABLED)
        self.current_text = ""
        self.current_translation = ""
        self.current_pron = ""
        self._log("Discarded current capture")
        self.status_var.set("Discarded - ready for new capture")

    def _mine(self):
        text_to_mine = self.text_frame.get("1.0", tk.END).strip()
        if not text_to_mine:
            messagebox.showwarning("Warning", "No text detected. Capture text first."); return
        ts = time.strftime("%Y%m%d_%H%M%S")
        sd = Path(__file__).parent / "mining" / ts
        sd.mkdir(parents=True, exist_ok=True)
        for d in ["audio", "images", "video"]: (sd / d).mkdir(exist_ok=True)
        dur = self.audio_var.get()
        self.status_var.set(f"Recording {dur}s audio...")
        self._log(f"Mining: {text_to_mine[:50]}")
        def _save():
            af_path = sd / f"audio/audio_{ts}.mp3"
            ok = record_audio(af_path, dur)
            af = f"audio/audio_{ts}.mp3" if ok else ""
            tr = self.trans_frame.get("1.0", tk.END).strip()
            if not tr: tr = translate_text(text_to_mine, src=self.ocr_lang, dest=self.translate_to)
            # Split into sentences and save each
            sentences = split_sentences(text_to_mine)
            entries = []
            for sent in (sentences if sentences else [text_to_mine]):
                if len(sent) < 2: continue
                pron = get_pronunciation(sent, self.ocr_lang)
                # Enriched word breakdown with definitions
                words = enrich_word_breakdown(sent, self.ocr_lang)
                sent_tr = tr if len(sentences) <= 1 else translate_text(sent, src=self.ocr_lang, dest=self.translate_to)
                entry = {"sentence": sent, "translation": sent_tr, "audio": af, "pronunciation": pron,
                    "lang": self.ocr_lang, "source": self.source_name, "timestamp": ts,
                    "words": words, "tags": [], "character": ""}
                entries.append(entry)
            for entry in entries:
                with open(sd / f"entry_{entry['sentence'][:20]}.json", "w", encoding="utf-8") as f:
                    json.dump(entry, f, ensure_ascii=False, indent=2)
                mining_dir = Path(__file__).parent / "mining"
                sentences_json = mining_dir / "sentences.json"
                all_entries = json.loads(sentences_json.read_text()) if sentences_json.exists() else []
                all_entries.append(entry)
                sentences_json.write_text(json.dumps(all_entries, ensure_ascii=False, indent=2))
                with open(mining_dir / "history_sentences.txt", "a", encoding="utf-8") as f:
                    f.write(f"[{ts}] {entry['sentence'][:100]} | {entry.get('translation', '')[:100]}\n")
                self._append_to_anki_csv(entry)
                log_capture(sentence=entry["sentence"], translation=entry.get("translation", ""),
                            pronunciation=entry.get("pronunciation", ""), source=self.source_name,
                            lang=self.ocr_lang, audio=af)
            copy_to_clipboard(entries[0]["sentence"] if entries else text_to_mine)
            self.root.after(0, lambda: self._log(f"Mined {len(entries)} sentence(s)"))
            self.root.after(0, lambda: self.status_var.set(f"Mined {len(entries)}! Saved to {sd.name}"))
            self.root.after(0, lambda: notify("Sentence Mined",
                f"Text: {entries[0]['sentence'][:60]}\nSentences: {len(entries)}\nSaved: {sd.name}",
                timeout=10000))
            self._multiline.clear()
        threading.Thread(target=_save, daemon=True).start()

    def _on_close(self):
        self.is_running = False
        self.root.destroy()

    def _append_to_anki_csv(self, entry: dict):
        mining_dir = Path(__file__).parent / "mining"
        csv_path = mining_dir / "anki_export.csv"
        fields = ["Sentence", "Translation", "Pronunciation", "Audio", "Source", "Timestamp", "Language", "WordBreakdown"]
        sentence = entry.get("sentence", "").strip()
        if not sentence: return
        if not csv_path.exists():
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL).writeheader()
        lang = entry.get("lang", "zh")
        pron = entry.get("pronunciation", "").strip() or get_pronunciation(sentence, lang)
        audio_path = entry.get("audio", "").strip()
        audio_tag = f"[sound:{Path(audio_path).name}]" if audio_path and Path(audio_path).exists() else ""
        words = entry.get("words", [])
        word_breakdown = " | ".join(f"{w['word']}→{w.get('pinyin', w.get('romaji', ''))}" for w in words if w.get("word"))
        row = {"Sentence": sentence, "Translation": entry.get("translation", ""),
            "Pronunciation": pron, "Audio": audio_tag,
            "Source": entry.get("source", ""), "Timestamp": entry.get("timestamp", ""),
            "Language": LANG_REGISTRY.get(lang, {}).get("name", lang), "WordBreakdown": word_breakdown}
        with open(csv_path, "a", encoding="utf-8-sig", newline="") as f:
            csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL).writerow(row)

    def run(self):
        self._log(f"OCR: {self.ocr_lang.upper()} -> {self.translate_to.upper()}")
        self._log("Step 1: Click 'Select Region' to choose text area")
        self._log("Step 2: Click 'Start Live' to auto-OCR every 2s")
        self._log("Step 3: Edit text directly if OCR is wrong - translation updates automatically")
        self._log("Step 4: Word breakdown shows per-word pinyin/romaji")
        self._log("Step 5: Click 'Split Preview' to see sentence splits")
        self._log("Step 6: Click 'Mine' to save with audio")
        self.root.mainloop()
