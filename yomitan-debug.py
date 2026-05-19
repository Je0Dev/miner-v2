#!/usr/bin/env python3
"""Yomitan Hover Debug Monitor - Live view of OCR, translation, and clipboard activity."""
import sys, time, subprocess, os, threading, json
from pathlib import Path
from datetime import datetime
try:
    import tkinter as tk
except ImportError:
    print("ERROR: python-tkinter required"); sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from config import MINING_DIR

CLIPBOARD_FILE = MINING_DIR / "yomitan_clipboard.json"
DEBUG_LOG = MINING_DIR / "yomitan_debug.log"

class DebugMonitor:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Yomitan Hover Debug Monitor")
        self.root.geometry("800x600+50+50")
        self.root.configure(bg="#1a1a1a")
        
        # Title
        tk.Label(self.root, text="Yomitan Hover Debug Monitor", bg="#1a1a1a", 
                 fg="#00d4ff", font=("Sans", 14, "bold")).pack(pady=5)
        
        # Stats frame
        stats_frame = tk.Frame(self.root, bg="#1a1a1a")
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.captures_var = tk.StringVar(value="Captures: 0")
        self.translations_var = tk.StringVar(value="Translations: 0")
        self.errors_var = tk.StringVar(value="Errors: 0")
        self.last_text_var = tk.StringVar(value="Last text: (none)")
        self.last_trans_var = tk.StringVar(value="Last translation: (none)")
        self.clipboard_var = tk.StringVar(value="Clipboard entries: 0")
        
        tk.Label(stats_frame, textvariable=self.captures_var, bg="#1a1a1a", 
                 fg="#00ff88", font=("Sans", 10), anchor=tk.W).pack(fill=tk.X)
        tk.Label(stats_frame, textvariable=self.translations_var, bg="#1a1a1a", 
                 fg="#ffdd57", font=("Sans", 10), anchor=tk.W).pack(fill=tk.X)
        tk.Label(stats_frame, textvariable=self.errors_var, bg="#1a1a1a", 
                 fg="#ff6666", font=("Sans", 10), anchor=tk.W).pack(fill=tk.X)
        tk.Label(stats_frame, textvariable=self.clipboard_var, bg="#1a1a1a", 
                 fg="#88ccff", font=("Sans", 10), anchor=tk.W).pack(fill=tk.X)
        tk.Label(stats_frame, textvariable=self.last_text_var, bg="#1a1a1a", 
                 fg="#ffffff", font=("Sans", 9), anchor=tk.W).pack(fill=tk.X)
        tk.Label(stats_frame, textvariable=self.last_trans_var, bg="#1a1a1a", 
                 fg="#ffdd57", font=("Sans", 9), anchor=tk.W).pack(fill=tk.X)
        
        # Log frame
        tk.Label(self.root, text="Activity Log:", bg="#1a1a1a", 
                 fg="#ffffff", font=("Sans", 11, "bold"), anchor=tk.W).pack(fill=tk.X, padx=10, pady=(5, 0))
        
        log_frame = tk.Frame(self.root, bg="#0f0f0f")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = tk.Text(log_frame, bg="#0f0f0f", fg="#88ff88", 
                                font=("Monospace", 9), wrap=tk.WORD, state=tk.DISABLED)
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Buttons
        btn_frame = tk.Frame(self.root, bg="#1a1a1a")
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(btn_frame, text="Refresh", command=self.refresh_stats,
                  bg="#4169E1", fg="white", font=("Sans", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Clear Log", command=self.clear_log,
                  bg="#666666", fg="white", font=("Sans", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="View Clipboard JSON", command=self.view_clipboard,
                  bg="#228B22", fg="white", font=("Sans", 10)).pack(side=tk.LEFT, padx=5)
        
        self.running = True
        self.capture_count = 0
        self.translation_count = 0
        self.error_count = 0
        
    def log(self, msg, color="#88ff88"):
        self.log_text.config(state=tk.NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n", color)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        # Write to file
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    
    def clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def refresh_stats(self):
        try:
            if CLIPBOARD_FILE.exists():
                with open(CLIPBOARD_FILE, "r", encoding="utf-8") as f:
                    entries = json.load(f)
                self.clipboard_var.set(f"Clipboard entries: {len(entries)}")
                if entries:
                    last = entries[-1]
                    self.last_text_var.set(f"Last text: {last.get('original', '')[:60]}")
                    self.last_trans_var.set(f"Last translation: {last.get('translation', '')[:60]}")
        except Exception as e:
            self.log(f"Error reading clipboard: {e}", "#ff6666")
    
    def view_clipboard(self):
        if CLIPBOARD_FILE.exists():
            os.system(f"xdg-open {CLIPBOARD_FILE}")
        else:
            self.log("No clipboard file yet", "#ff6666")
    
    def monitor_loop(self):
        """Monitor clipboard file for changes."""
        last_size = 0
        while self.running:
            try:
                if CLIPBOARD_FILE.exists():
                    current_size = CLIPBOARD_FILE.stat().st_size
                    if current_size > last_size:
                        last_size = current_size
                        self.refresh_stats()
                        try:
                            with open(CLIPBOARD_FILE, "r", encoding="utf-8") as f:
                                entries = json.load(f)
                            if entries:
                                entry = entries[-1]
                                self.capture_count += 1
                                self.captures_var.set(f"Captures: {self.capture_count}")
                                orig = entry.get('original', '')[:50]
                                trans = entry.get('translation', '')[:50]
                                lang = entry.get('lang', '?')
                                self.log(f"[{lang}] OCR: {orig}")
                                if trans:
                                    self.translation_count += 1
                                    self.translations_var.set(f"Translations: {self.translation_count}")
                                    self.log(f"  -> {trans}", "#ffdd57")
                                else:
                                    self.log(f"  -> (no translation)", "#ff6666")
            except Exception as e:
                self.error_count += 1
                self.errors_var.set(f"Errors: {self.error_count}")
                self.log(f"Monitor error: {e}", "#ff6666")
            time.sleep(0.5)
    
    def run(self):
        self.log("Debug monitor started")
        self.log(f"Watching: {CLIPBOARD_FILE}")
        threading.Thread(target=self.monitor_loop, daemon=True).start()
        self.root.mainloop()
        self.running = False

if __name__ == "__main__":
    DebugMonitor().run()
