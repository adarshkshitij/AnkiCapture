"""
Anki Screenshot Capture Tool
-----------------------------
F9  -> capture the FULL screen and add it as a new Anki card (Back = image, Front = empty)
F10 -> drag-select a REGION of the screen and add that as a new Anki card
Ctrl+C in this terminal window -> quit

Requires: Anki running, with the "AnkiConnect" add-on installed and enabled.
"""

import io
import base64
import time
import sys
import queue
from datetime import datetime

import requests
import keyboard
from PIL import ImageGrab
import tkinter as tk

# ---------------- Config ----------------
ANKI_CONNECT_URL = "http://127.0.0.1:8765"
DECK_NAME = "001 Concepts"
MODEL_NAME = "Basic"
TAG = "screenshot-capture"
# -----------------------------------------


def invoke(action, **params):
    payload = {"action": action, "version": 6, "params": params}
    resp = requests.post(ANKI_CONNECT_URL, json=payload, timeout=5)
    resp.raise_for_status()
    result = resp.json()
    if result.get("error"):
        raise RuntimeError(result["error"])
    return result["result"]


def ensure_deck_exists():
    try:
        decks = invoke("deckNames")
        if DECK_NAME not in decks:
            invoke("createDeck", deck=DECK_NAME)
            print(f'[info] Created deck "{DECK_NAME}" (did not exist yet).')
    except Exception as e:
        print(f"[error] Could not reach Anki/AnkiConnect: {e}")
        print("        Make sure Anki is OPEN and the AnkiConnect add-on is enabled.")


def save_image_to_anki(img):
    filename = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64data = base64.b64encode(buf.getvalue()).decode("utf-8")

    try:
        invoke("storeMediaFile", filename=filename, data=b64data)
        # Anki refuses to create a note whose first field (Front, for Basic)
        # is empty -- it treats the whole note as "empty" and rejects it.
        # Use a plain placeholder so the card is created; replace it with the
        # real question later in Browse.
        placeholder = f"(untitled - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
        note = {
            "deckName": DECK_NAME,
            "modelName": MODEL_NAME,
            "fields": {"Front": placeholder, "Back": f'<img src="{filename}">'},
            "options": {"allowDuplicate": True},
            "tags": [TAG],
        }
        note_id = invoke("addNote", note=note)
        print(f'[ok] Saved card {note_id} -> deck "{DECK_NAME}" (image: {filename})')
    except Exception as e:
        print(f"[error] Failed to save card: {e}")
        print("        Is Anki open with AnkiConnect enabled?")


def capture_full_screen():
    time.sleep(0.2)  # let the hotkey keys release before grabbing
    try:
        img = ImageGrab.grab(all_screens=True)
    except TypeError:
        img = ImageGrab.grab()  # older Pillow without all_screens support
    save_image_to_anki(img)


def capture_region(parent):
    # Built as a Toplevel of the main-thread root, and only ever invoked from
    # the main-thread queue poller below. Tkinter's event loop is not
    # thread-safe on Windows -- creating/running it from the keyboard
    # library's hotkey-callback thread caused drag (<B1-Motion>) events to
    # get dropped, which made every region look "too small" and cancel.
    overlay = tk.Toplevel(parent)
    overlay.attributes("-fullscreen", True)
    overlay.attributes("-alpha", 0.3)
    overlay.attributes("-topmost", True)
    overlay.configure(bg="black")
    overlay.focus_force()
    canvas = tk.Canvas(overlay, cursor="cross", bg="grey11", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    coords = {}
    rect_id = {"id": None}

    def on_press(event):
        coords["x1"], coords["y1"] = event.x, event.y
        rect_id["id"] = canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="red", width=2
        )

    def on_drag(event):
        if rect_id["id"] is not None:
            canvas.coords(rect_id["id"], coords["x1"], coords["y1"], event.x, event.y)

    def on_release(event):
        coords["x2"], coords["y2"] = event.x, event.y
        overlay.destroy()

    def on_escape(event):
        coords.clear()
        overlay.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    overlay.bind("<Escape>", on_escape)

    overlay.grab_set()
    parent.wait_window(overlay)

    if "x2" not in coords:
        print("[info] Region capture cancelled.")
        return

    left, right = sorted([coords["x1"], coords["x2"]])
    top, bottom = sorted([coords["y1"], coords["y2"]])

    if right - left < 5 or bottom - top < 5:
        print("[info] Selected region too small, cancelled.")
        return

    time.sleep(0.15)
    img = ImageGrab.grab(bbox=(left, top, right, bottom))
    save_image_to_anki(img)


def main():
    print("=== Anki Screenshot Capture ===")
    print(f'Deck: "{DECK_NAME}"  |  Note type: "{MODEL_NAME}"')
    ensure_deck_exists()
    print("F9  = capture FULL screen")
    print("F10 = drag-select a REGION (Esc to cancel selection)")
    print("Ctrl+C in this window = quit")
    print("--------------------------------")

    # Hotkeys fire on a background thread (owned by the `keyboard` package).
    # Tkinter must run on the main thread, so hotkeys only enqueue a request
    # here; a hidden root polls the queue and does the actual work.
    actions = queue.Queue()
    keyboard.add_hotkey("f9", lambda: actions.put("full"))
    keyboard.add_hotkey("f10", lambda: actions.put("region"))

    root = tk.Tk()
    root.withdraw()  # no visible window; just keeps the main-thread loop alive

    def poll_queue():
        try:
            while True:
                action = actions.get_nowait()
                if action == "full":
                    capture_full_screen()
                elif action == "region":
                    capture_region(root)
        except queue.Empty:
            pass
        root.after(100, poll_queue)

    root.after(100, poll_queue)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n[info] Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
