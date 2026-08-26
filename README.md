# AnkiCapture

Hotkey-driven screenshot capture for Anki. Hit a key while watching a lecture or reading a PDF, and the current screen (or a region you drag-select) gets pushed straight into a new Anki card via [AnkiConnect](https://foosoft.net/projects/anki-connect/) — no alt-tabbing, no manual import.

The card is created with the image on the **Back** field and the **Front** left blank, so you can batch-capture material while watching, then go write the actual questions later in Anki's Browse view.

## Features

- **F9** — capture the full screen, save as a new card
- **F10** — drag-select a specific region (like Snipping Tool / Win+Shift+S), save as a new card
- Runs as a background hotkey listener — works no matter which window has focus
- Talks to Anki over the local AnkiConnect API, so cards land straight in your collection, synced like any other card
- Zero manual steps between "see something worth remembering" and "it's a card"

## How it works

```
 [ F9 / F10 ]  →  grab screenshot (Pillow)  →  AnkiConnect (storeMediaFile + addNote)  →  new card in Anki
```

No cloud services, no third-party servers — everything stays on your machine and talks to your local Anki instance over `localhost:8765`.

## Requirements

- [Anki](https://apps.ankiweb.net/) (desktop)
- [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on installed and enabled
- Python 3.9+
- Windows (uses global hotkeys via the `keyboard` package; screen capture via Pillow)

## Installation

1. **Install AnkiConnect**
   In Anki: `Tools → Add-ons → Get Add-ons...` → paste code `2055492159` → restart Anki.

2. **Clone this repo**
   ```bash
   git clone https://github.com/adarshkshitij/AnkiCapture.git
   cd AnkiCapture
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Open Anki and leave it running in the background.
2. Run the capture tool:
   ```bash
   python capture.py
   ```
   or double-click `run.bat` on Windows.
3. While watching your lecture / reading material:
   - Press **F9** to capture the full screen.
   - Press **F10**, then drag a box around a specific region. Press **Esc** to cancel a selection.
4. Each capture prints a confirmation in the terminal and appears immediately as a new card in Anki.
5. When you're done, press **Ctrl+C** in the terminal to stop the listener.
6. Later, in Anki's **Browse** tab, filter for the capture tag and fill in the `Front` field for each card:
   ```
   tag:screenshot-capture
   ```

> If hotkeys don't register (some apps run elevated and block global hooks), try running your terminal / `run.bat` as Administrator.

## Configuration

All configuration lives at the top of `capture.py`:

```python
ANKI_CONNECT_URL = "http://127.0.0.1:8765"
DECK_NAME = "001 Concepts"
MODEL_NAME = "Basic"
TAG = "screenshot-capture"
```

Change `DECK_NAME` to target a different deck (it's created automatically if it doesn't exist yet), or `MODEL_NAME` to use a different note type, as long as it has `Front` and `Back` fields.

## Project structure

```
AnkiCapture/
├── capture.py        # main hotkey listener + AnkiConnect client
├── run.bat            # double-click launcher (Windows)
├── requirements.txt   # Python dependencies
└── LICENSE
```

## Roadmap

- [ ] Cross-platform hotkey support (macOS/Linux)
- [ ] Config file instead of hardcoded constants
- [ ] Optional OCR pass to pre-fill a suggested question
- [ ] System tray icon instead of a bare terminal window

## Contributing

Issues and PRs welcome. Keep changes scoped and describe the "why," not just the "what."

## License

[MIT](LICENSE)
