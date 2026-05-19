// Yomitan Bridge - Browser Extension Content Script
// Connects to miner-v2 WebSocket bridge for dictionary lookups on mined sentences
(function() {
    'use strict';

    const WS_URL = 'ws://localhost:8766';
    let ws = null;
    let reconnectTimer = null;

    function connect() {
        if (ws && ws.readyState === WebSocket.OPEN) return;
        try {
            ws = new WebSocket(WS_URL);
            ws.onopen = () => console.log('[Miner Bridge] Connected');
            ws.onclose = () => {
                console.log('[Miner Bridge] Disconnected, reconnecting...');
                reconnectTimer = setTimeout(connect, 3000);
            };
            ws.onerror = (e) => console.error('[Miner Bridge] Error:', e);
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    handleResponse(data);
                } catch (e) {
                    console.error('[Miner Bridge] Parse error:', e);
                }
            };
        } catch (e) {
            console.error('[Miner Bridge] Connection failed:', e);
            reconnectTimer = setTimeout(connect, 3000);
        }
    }

    function sendRequest(action, params) {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            connect();
            return;
        }
        ws.send(JSON.stringify({ action, ...params }));
    }

    function handleResponse(data) {
        const action = data.action;
        if (action === 'find_sentences' && data.results) {
            showSentencePopup(data.results);
        } else if (action === 'word_info' && data.info) {
            showWordInfo(data.info);
        }
    }

    function showSentencePopup(results) {
        // Display mined sentences containing the hovered term
        if (!results.length) return;
        const popup = document.createElement('div');
        popup.id = 'miner-sentence-popup';
        popup.style.cssText = 'position:fixed;top:10px;right:10px;background:#1a1a2e;color:#eee;padding:15px;border-radius:8px;max-width:400px;max-height:300px;overflow-y:auto;z-index:10000;font-family:sans-serif;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,0.5);';
        popup.innerHTML = '<h3 style="margin:0 0 10px;color:#00d4ff;font-size:16px;">Mined Sentences</h3>' +
            results.map(r => `<div style="margin-bottom:8px;padding:8px;background:#16213e;border-radius:4px;">
                <div style="color:#fff;font-size:15px;">${escapeHtml(r.sentence)}</div>
                ${r.pronunciation ? `<div style="color:#ffdd57;font-size:12px;">${escapeHtml(r.pronunciation)}</div>` : ''}
                <div style="color:#00d4ff;font-size:13px;">${escapeHtml(r.translation)}</div>
            </div>`).join('') +
            '<button onclick="this.parentElement.remove()" style="margin-top:8px;padding:4px 12px;background:#4169E1;color:#fff;border:none;border-radius:4px;cursor:pointer;">Close</button>';
        document.body.appendChild(popup);
    }

    function showWordInfo(info) {
        if (!info.words || !info.words.length) return;
        const popup = document.createElement('div');
        popup.id = 'miner-word-popup';
        popup.style.cssText = 'position:fixed;top:10px;right:10px;background:#1a1a2e;color:#eee;padding:15px;border-radius:8px;max-width:350px;z-index:10000;font-family:sans-serif;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,0.5);';
        popup.innerHTML = '<h3 style="margin:0 0 10px;color:#00d4ff;font-size:16px;">Word Breakdown</h3>' +
            info.words.map(w => `<div style="margin-bottom:6px;">
                <span style="color:#fff;font-size:15px;">${escapeHtml(w.word)}</span>
                ${w.pinyin ? `<span style="color:#ffdd57;font-size:12px;"> → ${escapeHtml(w.pinyin)}</span>` : ''}
                ${w.romaji ? `<span style="color:#ffdd57;font-size:12px;"> → ${escapeHtml(w.romaji)}</span>` : ''}
                ${w.definition_short ? `<div style="color:#88ccff;font-size:12px;margin-top:2px;">${escapeHtml(w.definition_short)}</div>` : ''}
            </div>`).join('') +
            '<button onclick="this.parentElement.remove()" style="margin-top:8px;padding:4px 12px;background:#4169E1;color:#fff;border:none;border-radius:4px;cursor:pointer;">Close</button>';
        document.body.appendChild(popup);
    }

    function escapeHtml(s) {
        const div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    // Expose API for Yomitan popup menu
    window.MinerBridge = {
        findSentences: (term, lang) => sendRequest('find_sentences', { term, lang }),
        getWordInfo: (term, lang) => sendRequest('word_info', { term, lang }),
        translate: (text, lang) => sendRequest('translate', { text, lang }),
        connect
    };

    // Auto-connect on load
    connect();
    console.log('[Miner Bridge] Loaded');
})();
