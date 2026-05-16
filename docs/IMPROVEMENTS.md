# Game Sentence Miner - Comprehensive Improvement Plan

## Current State Analysis

The current implementation has several critical issues:
1. **Unicode display issues**: Buttons show garbled characters (▶, ⬇, ↺ render as unicode escapes)
2. **Live OCR broken**: Doesn't actually OCR or show translations properly
3. **Notifications not showing**: notify-send calls fail silently or don't display
4. **Workflow broken**: User can't actually mine sentences while playing
5. **Yomitan integration incomplete**: Clipboard copying doesn't trigger Yomitan

## Reference Analysis: What Works in GSM and LunaTranslator

### GameSentenceMiner (What to Adopt)
1. **OBS replay buffer + VAD pipeline** - Gold standard for mining audio
2. **WebSocket multi-source text intake** - Rate limiting + line merging
3. **Yomitan postMessage bridge** - Dictionary lookups via browser extension
4. **Word-level coordinate overlay** - Clickable text at exact screen positions
5. **Session-based file organization** - Images, audio, video per entry
6. **System tray + desktop notifications** - Real-time feedback
7. **SQLite database** - Persistent history with deduplication

### LunaTranslator (What to Adopt)
1. **Plugin-based text source architecture** - Clean separation of clipboard/OCR/texthook
2. **MSSIM image stability detection** - Avoid OCR during animations
3. **Multi-region OCR** - Visual region selectors
4. **Multi-engine parallel translation** - Ranked display
5. **Auto-disappear on inactivity** - Window hides when not needed
6. **Frameless translucent window** - Acrylic effects, minimal distraction
7. **Native clipboard listener** - Not polling, more reliable
8. **Per-game configuration profiles** - Game-specific settings
9. **Queued TTS player** - Auto-forward after audio

## Phase 1: Critical Fixes (Make It Work)

### 1.1 Fix Unicode Display
- Remove all unicode emoji/symbols from button text (▶, ⬇, ↺)
- Use plain ASCII: "Start", "Mine", "Reset"
- Ensure all text is UTF-8 encoded throughout the pipeline
- Test with CJK characters in tkinter

### 1.2 Fix Notifications
- Verify notify-send works on the system
- Use `notify-send --` to prevent argument parsing issues
- Add fallback logging if notifications fail
- Show notifications IMMEDIATELY after OCR+translation (before audio recording)

### 1.3 Fix Live OCR Workflow
- Simplify to: Select region → Auto-OCR every 2s → Show text + translation → Click Mine
- Remove complexity, make it work reliably first
- Auto-copy to clipboard on each OCR for Yomitan integration

### 1.4 Fix Quick Capture
- Ensure slurp selection works
- OCR → Translate → Notify → Save → Clipboard
- Show pinyin + translation in notification

## Phase 2: Core Workflow Improvements

### 2.1 Streamlined Mining Pipeline
```
User triggers capture (SUPER+X or Live OCR)
  → Select region (slurp)
  → OCR (Tesseract with preprocessing)
  → Translate (multi-engine fallback)
  → IMMEDIATE notification with text + translation + pinyin
  → Auto-copy to clipboard (Yomitan reads it)
  → Record audio (5s with VAD trim)
  → Save to session folder + Anki
  → Second notification confirming save
```

### 2.2 Live OCR Redesign
- Small, draggable overlay window (400x300)
- User drags it over game text area
- Auto-OCRs every 2 seconds
- Shows: captured text, translation, pinyin
- Auto-copies to clipboard for Yomitan
- "Mine" button saves with audio
- "Stop" button pauses OCR
- Auto-hides after 10s of inactivity

### 2.3 Yomitan Integration
- Ensure clipboard copying triggers Yomitan
- Yomitan must have "Scan clipboard content" enabled
- Add notification showing "Copied to clipboard - Yomitan should show definition"
- Test with actual Yomitan extension

## Phase 3: Advanced Features (From References)

### 3.1 From GameSentenceMiner
- [ ] OBS replay buffer integration (if OBS is available)
- [ ] WebSocket text source for external OCR tools
- [ ] SQLite database for persistent history
- [ ] System tray icon with quick actions
- [ ] Gamepad navigation support

### 3.2 From LunaTranslator
- [ ] MSSIM image stability detection before OCR
- [ ] Multi-region OCR support
- [ ] Multi-engine parallel translation display
- [ ] Auto-disappear on inactivity
- [ ] Per-game configuration profiles (expand existing)
- [ ] Queued TTS player with auto-forward

## Phase 4: Polish and UX

### 4.1 Notifications
- Detailed notifications showing:
  - Captured text (first 80 chars)
  - Pinyin (for Chinese)
  - Translation (first 80 chars)
  - Save path
  - Audio recording status

### 4.2 Logging
- Real-time log visible in overlay
- `--debug` flag tails log in terminal
- `--tail-log` shows recent entries
- Log file at ~/Downloads/Mining/miner.log

### 4.3 Settings GUI
- Game selection (auto-detect, custom, game ID)
- OCR language + translation target
- Toggle options: VAD, recording, Anki, clipboard
- Audio duration slider
- Test capture button
- Open log button

## Implementation Priority

1. **Fix unicode display** - 30 min
2. **Fix notifications** - 30 min
3. **Fix Live OCR workflow** - 2 hours
4. **Fix quick capture workflow** - 1 hour
5. **Yomitan clipboard integration** - 1 hour
6. **Add detailed logging** - 1 hour
7. **Polish settings GUI** - 1 hour
8. **Advanced features (Phase 3)** - Future

## Key Principles

1. **Functionality over features**: Make the core workflow work perfectly before adding more
2. **Simple is better**: Reduce complexity, fewer bindings, clearer UI
3. **Immediate feedback**: Notifications should appear instantly after capture
4. **Game-friendly**: Overlay should not interfere with gameplay
5. **Reliable**: Every step should have error handling and user feedback
