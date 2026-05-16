#!/usr/bin/env python3
"""Web Text Hooker - Browser viewer for mined sentences.

Simple Flask app to view, search, and export mined sentences.
Run: python3 web_viewer.py
Open: http://localhost:5000
"""
import json, sys
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify

sys.path.insert(0, str(Path(__file__).parent))
from config import MINING_DIR, SENTENCES_FILE

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Miner Text Hooker</title>
    <meta charset="utf-8">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
        .header { max-width: 1200px; margin: 0 auto 20px; }
        h1 { color: #00d4ff; margin-bottom: 10px; }
        .controls { display: flex; gap: 10px; margin-bottom: 20px; }
        input, select, button { padding: 8px 12px; border: none; border-radius: 4px; }
        input { flex: 1; background: #16213e; color: #fff; font-size: 14px; }
        select { background: #16213e; color: #fff; }
        button { background: #4169E1; color: #fff; cursor: pointer; }
        button:hover { background: #5577FF; }
        .stats { color: #888; font-size: 14px; margin-bottom: 15px; }
        .sentence-card { background: #16213e; border-radius: 8px; padding: 15px; margin-bottom: 10px; }
        .sentence { font-size: 18px; color: #fff; margin-bottom: 5px; }
        .pinyin { color: #ffdd57; font-size: 14px; margin-bottom: 5px; }
        .translation { color: #00d4ff; font-size: 16px; }
        .meta { color: #666; font-size: 12px; margin-top: 8px; }
        .actions { margin-top: 8px; }
        .actions button { font-size: 12px; padding: 4px 8px; margin-right: 5px; }
        .export-btn { background: #228B22; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Miner Text Hooker</h1>
        <div class="controls">
            <input type="text" id="search" placeholder="Search sentences..." oninput="filterSentences()">
            <select id="langFilter" onchange="filterSentences()">
                <option value="">All Languages</option>
                <option value="zh">Chinese</option>
                <option value="ja">Japanese</option>
                <option value="de">German</option>
            </select>
            <button class="export-btn" onclick="exportCSV()">Export CSV</button>
        </div>
        <div class="stats" id="stats"></div>
    </div>
    <div id="sentences" style="max-width: 1200px; margin: 0 auto;"></div>
    <script>
        let allSentences = [];
        fetch('/api/sentences').then(r => r.json()).then(data => {
            allSentences = data;
            renderSentences(data);
        });
        function renderSentences(sentences) {
            const container = document.getElementById('sentences');
            document.getElementById('stats').textContent = `Showing ${sentences.length} of ${allSentences.length} sentences`;
            container.innerHTML = sentences.map(s => `
                <div class="sentence-card">
                    <div class="sentence">${escapeHtml(s.sentence)}</div>
                    ${s.pinyin ? `<div class="pinyin">${escapeHtml(s.pinyin)}</div>` : ''}
                    <div class="translation">${escapeHtml(s.translation || '')}</div>
                    <div class="meta">Source: ${escapeHtml(s.source || 'Unknown')} | ${escapeHtml(s.timestamp || '')}</div>
                    <div class="actions">
                        <button onclick="copyText('${escapeJs(s.sentence)}')">Copy</button>
                        <button onclick="copyText('${escapeJs(s.translation || '')}')">Copy Translation</button>
                    </div>
                </div>
            `).join('');
        }
        function filterSentences() {
            const query = document.getElementById('search').value.toLowerCase();
            const filtered = allSentences.filter(s =>
                (s.sentence || '').toLowerCase().includes(query) ||
                (s.translation || '').toLowerCase().includes(query) ||
                (s.pinyin || '').toLowerCase().includes(query)
            );
            renderSentences(filtered);
        }
        function copyText(text) { navigator.clipboard.writeText(text); }
        function exportCSV() { window.open('/api/export/csv', '_blank'); }
        function escapeHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
        function escapeJs(s) { return s.replace(/'/g, "\\'").replace(/"/g, '\\"'); }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/sentences")
def get_sentences():
    path = MINING_DIR / SENTENCES_FILE
    if not path.exists():
        return jsonify([])
    with open(path, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/api/export/csv")
def export_csv():
    import csv, io
    from text import get_pinyin
    
    path = MINING_DIR / SENTENCES_FILE
    if not path.exists():
        return "No sentences found", 404
    
    with open(path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(["Sentence", "Translation", "Pinyin", "Audio", "Source", "Timestamp"])
    
    for e in entries:
        sentence = e.get("sentence", "")
        pinyin = e.get("pinyin", "") or get_pinyin(sentence)
        audio = f"[sound:{Path(e['audio']).name}]" if e.get("audio") and Path(e["audio"]).exists() else ""
        writer.writerow([sentence, e.get("translation", ""), pinyin, audio, e.get("source", ""), e.get("timestamp", "")])
    
    output.seek(0)
    return output.getvalue(), 200, {"Content-Type": "text/csv", "Content-Disposition": "attachment; filename=mined_sentences.csv"}


if __name__ == "__main__":
    print("Starting Miner Text Hooker at http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
