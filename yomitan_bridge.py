#!/usr/bin/env python3
"""Yomitan Bridge - WebSocket server for direct Yomitan browser extension communication."""
import sys, json, asyncio, threading, websockets
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from config import MINING_DIR, LANG_REGISTRY
from text import get_pronunciation, get_word_breakdown
from translate import translate_text
from log import log

SENTENCES_DB = MINING_DIR / "sentences.json"
BRIDGE_PORT = 8766

def load_sentences():
    if SENTENCES_DB.exists():
        try:
            return json.loads(SENTENCES_DB.read_text())
        except Exception: pass
    return []

def find_sentences_with_term(term: str, lang: str = "zh") -> list:
    """Find mined sentences containing a specific term."""
    sentences = load_sentences()
    results = []
    for s in sentences:
        if s.get("lang") == lang and term in s.get("sentence", ""):
            results.append({
                "sentence": s["sentence"],
                "translation": s.get("translation", ""),
                "pronunciation": s.get("pronunciation", ""),
                "source": s.get("source", "Game"),
                "timestamp": s.get("timestamp", ""),
                "words": s.get("words", [])
            })
    return results[:50]

def get_word_info(term: str, lang: str = "zh") -> dict:
    """Get word-level info for a term."""
    pron = get_pronunciation(term, lang)
    words = get_word_breakdown(term, lang)
    return {"term": term, "pronunciation": pron, "words": words}

async def handle_client(websocket):
    """Handle Yomitan extension WebSocket connection."""
    log.info(f"Yomitan connected: {websocket.remote_address}")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action", "")
                term = data.get("term", "")
                lang = data.get("lang", "zh")

                if action == "find_sentences":
                    results = find_sentences_with_term(term, lang)
                    await websocket.send(json.dumps({"action": "find_sentences", "results": results}))

                elif action == "word_info":
                    info = get_word_info(term, lang)
                    await websocket.send(json.dumps({"action": "word_info", "info": info}))

                elif action == "translate":
                    text = data.get("text", "")
                    tr = translate_text(text, src=lang, dest="en")
                    await websocket.send(json.dumps({"action": "translate", "original": text, "translation": tr}))

                elif action == "ping":
                    await websocket.send(json.dumps({"action": "pong", "timestamp": datetime.now().isoformat()}))

                else:
                    await websocket.send(json.dumps({"action": "error", "message": f"Unknown action: {action}"}))

            except json.JSONDecodeError:
                await websocket.send(json.dumps({"action": "error", "message": "Invalid JSON"}))
            except Exception as e:
                log.error(f"Yomitan bridge error: {e}")
                await websocket.send(json.dumps({"action": "error", "message": str(e)}))
    except websockets.exceptions.ConnectionClosed:
        log.info("Yomitan disconnected")

async def run_bridge_async(port=BRIDGE_PORT):
    """Run the Yomitan bridge WebSocket server."""
    log.info(f"Yomitan Bridge starting on ws://localhost:{port}")
    async with websockets.serve(handle_client, "localhost", port) as server:
        log.info(f"Yomitan Bridge running on ws://localhost:{port}")
        await asyncio.Future()  # Run forever

def run_bridge(port=BRIDGE_PORT):
    """Run the Yomitan bridge WebSocket server (blocking)."""
    asyncio.run(run_bridge_async(port))

def start_bridge(port=BRIDGE_PORT):
    """Start bridge in background thread."""
    t = threading.Thread(target=run_bridge, args=(port,), daemon=True)
    t.start()
    log.info(f"Yomitan Bridge started (ws://localhost:{port})")
    return t

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=BRIDGE_PORT)
    args = parser.parse_args()
    run_bridge(args.port)
