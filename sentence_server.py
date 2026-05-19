#!/usr/bin/env python3
"""Sentence Server - Web API for storing and viewing mined sentences with Yomitan integration."""
import json, time, sqlite3
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from config import MINING_DIR, LANG_REGISTRY
from dictionary import get_definition, lookup_chinese, lookup_japanese, enrich_word_breakdown

app = Flask(__name__)
DB_PATH = MINING_DIR / "sentences.db"

def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sentences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, lang TEXT, original TEXT, translation TEXT,
        pronunciation TEXT, source TEXT, audio_path TEXT,
        screenshot_path TEXT, mode TEXT DEFAULT 'normal',
        words TEXT DEFAULT '[]', tags TEXT DEFAULT '[]', character TEXT DEFAULT ''
    )''')
    # Add new columns if they don't exist
    for col in [("words", "TEXT DEFAULT '[]'"), ("tags", "TEXT DEFAULT '[]'"), ("character", "TEXT DEFAULT ''")]:
        try: c.execute(f"ALTER TABLE sentences ADD COLUMN {col[0]} {col[1]}")
        except Exception: pass
    c.execute('''CREATE TABLE IF NOT EXISTS glossary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lang TEXT, term TEXT, translation TEXT, UNIQUE(lang, term)
    )''')
    conn.commit(); conn.close()

def add_sentence(original, lang="zh", translation="", pronunciation="", 
                 source="Game", audio_path="", screenshot_path="", mode="normal",
                 words=None, tags=None, character=""):
    """Add sentence to database."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute('''INSERT INTO sentences (timestamp, lang, original, translation, 
                  pronunciation, source, audio_path, screenshot_path, mode, words, tags, character)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (datetime.now().isoformat(), lang, original, translation,
               pronunciation, source, audio_path, screenshot_path, mode,
               json.dumps(words or []), json.dumps(tags or []), character))
    conn.commit(); row_id = c.lastrowid; conn.close()
    return row_id

def get_sentences(limit=100, lang=None, search=None, offset=0):
    """Get sentences from database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query = "SELECT * FROM sentences WHERE 1=1"
    params = []
    if lang:
        query += " AND lang = ?"
        params.append(lang)
    if search:
        query += " AND (original LIKE ? OR translation LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_sentence_by_id(sid):
    """Get single sentence."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM sentences WHERE id = ?", (sid,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

# Yomitan-compatible API endpoints
@app.route("/api/sentences")
def api_sentences():
    """Get sentences for Yomitan/browser viewing."""
    limit = request.args.get("limit", 100, type=int)
    lang = request.args.get("lang")
    search = request.args.get("search")
    offset = request.args.get("offset", 0, type=int)
    sentences = get_sentences(limit=limit, lang=lang, search=search, offset=offset)
    return jsonify({"sentences": sentences, "total": len(sentences)})

@app.route("/api/sentences/<int:sid>", methods=["GET", "DELETE"])
def api_sentence(sid):
    """Get or delete single sentence."""
    if request.method == "DELETE":
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("DELETE FROM sentences WHERE id = ?", (sid,))
        conn.commit(); conn.close()
        return jsonify({"status": "ok"})
    sentence = get_sentence_by_id(sid)
    if sentence: return jsonify(sentence)
    return jsonify({"error": "not found"}), 404

@app.route("/api/add", methods=["POST"])
def api_add():
    """Add sentence (for mining tools)."""
    data = request.json
    if not data or not data.get("original"):
        return jsonify({"error": "original text required"}), 400
    row_id = add_sentence(
        original=data["original"], lang=data.get("lang", "zh"),
        translation=data.get("translation", ""), pronunciation=data.get("pronunciation", ""),
        source=data.get("source", "Game"), audio_path=data.get("audio_path", ""),
        screenshot_path=data.get("screenshot_path", ""), mode=data.get("mode", "normal"),
        words=data.get("words"), tags=data.get("tags"), character=data.get("character", ""))
    return jsonify({"id": row_id, "status": "ok"})

@app.route("/api/stats")
def api_stats():
    """Get sentence statistics."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM sentences")
    total = c.fetchone()[0]
    c.execute("SELECT lang, COUNT(*) as count FROM sentences GROUP BY lang ORDER BY count DESC")
    by_lang = {r[0]: r[1] for r in c.fetchall()}
    conn.close()
    return jsonify({"total": total, "by_lang": by_lang})

# Yomitan-compatible API endpoints
@app.route("/api/yomitan/find", methods=["POST"])
def yomitan_find():
    """Yomitan-compatible endpoint to find sentences containing a term."""
    data = request.json
    term = data.get("term", "")
    lang = data.get("lang", "zh")
    if not term:
        return jsonify([])
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM sentences WHERE lang = ? AND original LIKE ? ORDER BY id DESC LIMIT 50",
              (lang, f"%{term}%"))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    # Format for Yomitan
    results = []
    for r in rows:
        results.append({
            "term": term,
            "sentence": r["original"],
            "translation": r.get("translation", ""),
            "pronunciation": r.get("pronunciation", ""),
            "source": r.get("source", "Game"),
            "timestamp": r.get("timestamp", ""),
            "id": r["id"]
        })
    return jsonify(results)

@app.route("/api/yomitan/term", methods=["POST"])
def yomitan_term():
    """Yomitan-compatible endpoint to get term definitions from glossary."""
    data = request.json
    term = data.get("term", "")
    lang = data.get("lang", "zh")
    if not term:
        return jsonify([])
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM glossary WHERE lang = ? AND term LIKE ? ORDER BY id DESC LIMIT 10",
              (lang, f"%{term}%"))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    results = []
    for r in rows:
        results.append({
            "term": r["term"],
            "definition": r["translation"],
            "lang": r["lang"]
        })
    return jsonify(results)

@app.route("/api/yomitan/recent")
def yomitan_recent():
    """Get recent mined sentences for Yomitan viewing."""
    limit = request.args.get("limit", 20, type=int)
    lang = request.args.get("lang")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if lang:
        c.execute("SELECT * FROM sentences WHERE lang = ? ORDER BY id DESC LIMIT ?", (lang, limit))
    else:
        c.execute("SELECT * FROM sentences ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route("/api/dictionary")
def api_dictionary():
    """Look up word definitions."""
    word = request.args.get("word", "")
    lang = request.args.get("lang", "zh")
    if not word:
        return jsonify({"error": "word required"})
    defs = get_definition(word, lang)
    words = enrich_word_breakdown(word, lang)
    return jsonify({"word": word, "lang": lang, "definitions": defs, "breakdown": words})

# Web viewer
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Miner Sentences</title>
    <meta charset="utf-8">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
        .header { max-width: 1200px; margin: 0 auto 20px; }
        h1 { color: #00d4ff; margin-bottom: 10px; }
        .controls { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        input, select, button { padding: 8px 12px; border: none; border-radius: 4px; }
        input { flex: 1; background: #16213e; color: #fff; font-size: 14px; }
        select { background: #16213e; color: #fff; }
        button { background: #4169E1; color: #fff; cursor: pointer; }
        button:hover { background: #5577FF; }
        .stats { color: #888; font-size: 14px; margin-bottom: 15px; }
        .sentence-card { background: #16213e; border-radius: 8px; padding: 15px; margin-bottom: 10px; }
        .sentence { font-size: 18px; color: #fff; margin-bottom: 5px; }
        .translation { color: #00d4ff; font-size: 16px; }
        .pronunciation { color: #ffdd57; font-size: 14px; }
        .word-breakdown { color: #88ccff; font-size: 13px; margin-top: 4px; }
        .tags { margin-top: 6px; }
        .tag { display: inline-block; background: #6A5ACD; color: #fff; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin-right: 4px; }
        .meta { color: #666; font-size: 12px; margin-top: 8px; }
        .lang-badge { display: inline-block; background: #4169E1; color: #fff; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin-left: 8px; }
        .actions button { font-size: 12px; padding: 4px 8px; margin-right: 5px; margin-top: 8px; }
        .export-btn { background: #228B22; }
        .study-btn { background: #CC6600; }
        .load-more { text-align: center; margin: 20px 0; }
        .hidden { display: none; }
        .study-mode .translation { color: transparent; cursor: pointer; }
        .study-mode .translation:hover { color: #00d4ff; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Miner Sentences</h1>
        <div class="controls">
            <input type="text" id="search" placeholder="Search sentences..." oninput="loadSentences()">
            <select id="langFilter" onchange="loadSentences()">
                <option value="">All Languages</option>
""" + "".join(f'<option value="{k}">{v["name"]}</option>' for k, v in LANG_REGISTRY.items()) + """
            </select>
            <select id="tagFilter" onchange="loadSentences()">
                <option value="">All Tags</option>
                <option value="dialogue">Dialogue</option>
                <option value="narration">Narration</option>
                <option value="quest">Quest</option>
                <option value="item">Item</option>
                <option value="system">System</option>
            </select>
            <button id="studyToggle" onclick="toggleStudyMode()">Study Mode</button>
            <button class="export-btn" onclick="exportCSV()">Export CSV</button>
        </div>
        <div class="stats" id="stats"></div>
    </div>
    <div id="sentences" style="max-width: 1200px; margin: 0 auto;"></div>
    <div class="load-more">
        <button id="loadMore" onclick="loadMore()">Load More</button>
    </div>
    <script>
        let offset = 0, allSentences = [], studyMode = false;
        function loadSentences(reset = true) {
            if (reset) { offset = 0; allSentences = []; }
            const query = document.getElementById('search').value;
            const lang = document.getElementById('langFilter').value;
            const tag = document.getElementById('tagFilter').value;
            let url = `/api/sentences?limit=50&offset=${offset}`;
            if (query) url += `&search=${encodeURIComponent(query)}`;
            if (lang) url += `&lang=${lang}`;
            fetch(url).then(r => r.json()).then(data => {
                if (reset) allSentences = data.sentences;
                else allSentences = allSentences.concat(data.sentences);
                offset += data.sentences.length;
                renderSentences();
                document.getElementById('loadMore').style.display = data.sentences.length < 50 ? 'none' : 'block';
            });
        }
        function renderSentences() {
            const container = document.getElementById('sentences');
            document.getElementById('stats').textContent = `Showing ${allSentences.length} sentences`;
            container.innerHTML = allSentences.map(s => {
                const words = typeof s.words === 'string' ? JSON.parse(s.words || '[]') : (s.words || []);
                const tags = typeof s.tags === 'string' ? JSON.parse(s.tags || '[]') : (s.tags || []);
                const wordHtml = words.length ? `<div class="word-breakdown">${words.map(w => `${w.word}→${w.pinyin || w.romaji || ''}`).join(' | ')}</div>` : '';
                const tagHtml = tags.length ? `<div class="tags">${tags.map(t => `<span class="tag">${t}</span>`).join('')}</div>` : '';
                const charHtml = s.character ? `<span class="tag" style="background:#CC6600">${s.character}</span>` : '';
                return `<div class="sentence-card">
                    <div class="sentence">${escapeHtml(s.original)}<span class="lang-badge">${escapeHtml(s.lang)}</span></div>
                    ${s.pronunciation ? `<div class="pronunciation">${escapeHtml(s.pronunciation)}</div>` : ''}
                    ${wordHtml}
                    <div class="translation">${escapeHtml(s.translation || '')}</div>
                    ${tagHtml}${charHtml}
                    <div class="meta">Source: ${escapeHtml(s.source || 'Unknown')} | ${escapeHtml(s.timestamp || '')}</div>
                    <div class="actions">
                        <button onclick="copyText('${escapeJs(s.original)}')">Copy</button>
                        <button onclick="deleteSentence(${s.id})">Delete</button>
                    </div>
                </div>`;
            }).join('');
            if (studyMode) container.classList.add('study-mode');
        }
        function toggleStudyMode() {
            studyMode = !studyMode;
            document.getElementById('sentences').classList.toggle('study-mode', studyMode);
            document.getElementById('studyToggle').textContent = studyMode ? 'Exit Study' : 'Study Mode';
        }
        function deleteSentence(id) {
            if (!confirm('Delete this sentence?')) return;
            fetch(`/api/sentences/${id}`, {method: 'DELETE'}).then(() => loadSentences());
        }
        function loadMore() { loadSentences(false); }
        function copyText(text) { navigator.clipboard.writeText(text); }
        function exportCSV() { window.open('/api/export/csv', '_blank'); }
        function escapeHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
        function escapeJs(s) { return s.replace(/'/g, "\\'").replace(/"/g, '\\"'); }
        loadSentences();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

YOMITAN_BRIDGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Yomitan Bridge</title>
    <meta charset="utf-8">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #00d4ff; margin-bottom: 15px; }
        .status { padding: 8px 12px; border-radius: 4px; margin-bottom: 15px; font-size: 14px; }
        .status.connected { background: #228B22; color: #fff; }
        .status.disconnected { background: #CC3333; color: #fff; }
        .search-box { display: flex; gap: 10px; margin-bottom: 15px; }
        input, select, button { padding: 10px 12px; border: none; border-radius: 4px; font-size: 14px; }
        input { flex: 1; background: #16213e; color: #fff; }
        select { background: #16213e; color: #fff; }
        button { background: #4169E1; color: #fff; cursor: pointer; }
        button:hover { background: #5577FF; }
        .result-card { background: #16213e; border-radius: 8px; padding: 15px; margin-bottom: 10px; }
        .word { font-size: 20px; color: #fff; margin-bottom: 5px; }
        .pron { color: #ffdd57; font-size: 14px; }
        .defs { color: #88ccff; font-size: 13px; margin-top: 5px; }
        .sentence-card { background: #16213e; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
        .sentence { font-size: 16px; color: #fff; }
        .translation { color: #00d4ff; font-size: 14px; margin-top: 4px; }
        .log { background: #0f0f23; color: #88ff88; font-family: monospace; font-size: 12px; padding: 10px; border-radius: 4px; max-height: 200px; overflow-y: auto; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Yomitan Bridge</h1>
        <div id="status" class="status disconnected">Disconnected</div>
        <div class="search-box">
            <input type="text" id="wordInput" placeholder="Enter word to look up..." onkeydown="if(event.key==='Enter')lookupWord()">
            <select id="langSelect">
                <option value="zh">Chinese</option>
                <option value="ja">Japanese</option>
                <option value="ko">Korean</option>
                <option value="el">Greek</option>
                <option value="ru">Russian</option>
            </select>
            <button onclick="lookupWord()">Lookup</button>
            <button onclick="findSentences()">Find Sentences</button>
        </div>
        <div id="results"></div>
        <div class="log" id="log"></div>
    </div>
    <script>
        let ws = null;
        function connect() {
            const wsUrl = `ws://${location.host.replace(/:\\d+$/, '')}:8766`;
            ws = new WebSocket(wsUrl);
            ws.onopen = () => { setStatus('Connected to Bridge', true); addLog('Connected'); };
            ws.onclose = () => { setStatus('Disconnected', false); addLog('Disconnected, reconnecting...'); setTimeout(connect, 3000); };
            ws.onerror = () => { setStatus('Error', false); addLog('Connection error'); };
            ws.onmessage = (e) => {
                try {
                    const data = JSON.parse(e.data);
                    handleResponse(data);
                } catch(err) { addLog('Parse error: ' + err); }
            };
        }
        function setStatus(msg, ok) {
            const el = document.getElementById('status');
            el.textContent = msg;
            el.className = 'status ' + (ok ? 'connected' : 'disconnected');
        }
        function addLog(msg) {
            const el = document.getElementById('log');
            const time = new Date().toLocaleTimeString();
            el.innerHTML += `[${time}] ${msg}\\n`;
            el.scrollTop = el.scrollHeight;
        }
        function lookupWord() {
            const word = document.getElementById('wordInput').value.trim();
            const lang = document.getElementById('langSelect').value;
            if (!word) return;
            addLog(`Looking up: ${word} (${lang})`);
            ws.send(JSON.stringify({ action: 'word_info', term: word, lang }));
        }
        function findSentences() {
            const word = document.getElementById('wordInput').value.trim();
            const lang = document.getElementById('langSelect').value;
            if (!word) return;
            addLog(`Finding sentences with: ${word} (${lang})`);
            ws.send(JSON.stringify({ action: 'find_sentences', term: word, lang }));
        }
        function handleResponse(data) {
            const results = document.getElementById('results');
            if (data.action === 'word_info' && data.info) {
                const info = data.info;
                let html = '<div class="result-card">';
                html += `<div class="word">${escapeHtml(info.term)}</div>`;
                if (info.pronunciation) html += `<div class="pron">${escapeHtml(info.pronunciation)}</div>`;
                if (info.words && info.words.length) {
                    html += '<div class="defs">';
                    info.words.forEach(w => {
                        html += `<div><strong>${escapeHtml(w.word)}</strong>`;
                        if (w.pinyin) html += ` → ${escapeHtml(w.pinyin)}`;
                        if (w.romaji) html += ` → ${escapeHtml(w.romaji)}`;
                        if (w.definition_short) html += `: ${escapeHtml(w.definition_short)}`;
                        html += '</div>';
                    });
                    html += '</div>';
                }
                html += '</div>';
                results.innerHTML = html;
                addLog(`Found word info for: ${info.term}`);
            } else if (data.action === 'find_sentences' && data.results) {
                if (!data.results.length) {
                    results.innerHTML = '<div class="result-card">No sentences found</div>';
                    addLog('No sentences found');
                    return;
                }
                let html = `<div style="color:#888;margin-bottom:10px;">Found ${data.results.length} sentences</div>`;
                data.results.forEach(r => {
                    html += `<div class="sentence-card">
                        <div class="sentence">${escapeHtml(r.sentence)}</div>
                        ${r.pronunciation ? `<div class="pron">${escapeHtml(r.pronunciation)}</div>` : ''}
                        <div class="translation">${escapeHtml(r.translation)}</div>
                    </div>`;
                });
                results.innerHTML = html;
                addLog(`Found ${data.results.length} sentences`);
            } else if (data.action === 'pong') {
                addLog('Pong received');
            }
        }
        function escapeHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
        connect();
    </script>
</body>
</html>
"""

@app.route("/bridge")
def bridge_page():
    return render_template_string(YOMITAN_BRIDGE_HTML)

@app.route("/api/export/csv")
def export_csv():
    import csv, io
    sentences = get_sentences(limit=10000)
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(["Language", "Original", "Pronunciation", "Translation", "Source", "Timestamp"])
    for s in sentences:
        writer.writerow([s["lang"], s["original"], s.get("pronunciation", ""),
                        s.get("translation", ""), s.get("source", ""), s.get("timestamp", "")])
    output.seek(0)
    return output.getvalue(), 200, {"Content-Type": "text/csv; charset=utf-8",
                                    "Content-Disposition": "attachment; filename=mined_sentences.csv"}

def run_server(port=5002):
    init_db()
    print(f"Sentence Server: http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5002, help="Port to run server on")
    args = parser.parse_args()
    run_server(port=args.port)
