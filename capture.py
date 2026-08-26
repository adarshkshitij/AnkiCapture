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
import ctypes
from datetime import datetime

import requests
import keyboard
import mouse
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


def _force_foreground(window):
    # Windows commonly refuses SetForegroundWindow-via-focus_force() from a
    # window that was just created by a background-owned process, and eats
    # the first click as a plain "activate this window" click instead of
    # delivering it to the app -- which is exactly why the first F10 drag
    # was silently dropped and only the second one worked. Asking Windows
    # directly tends to succeed because our process just received real
    # keyboard input (the F10 hotkey itself).
    try:
        hwnd = window.winfo_id()
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def build_region_overlay(root):
    # Built once at startup and reused (shown/hidden) on every F10 press,
    # instead of created fresh each time. A brand-new topmost window is what
    # triggered the "first click just activates the window" problem above;
    # an already-existing window that's simply un-hidden doesn't hit that.
    overlay = tk.Toplevel(root)
    overlay.attributes("-fullscreen", True)
    overlay.attributes("-alpha", 0.3)
    overlay.attributes("-topmost", True)
    overlay.configure(bg="black")
    canvas = tk.Canvas(overlay, cursor="cross", bg="grey11", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)
    overlay.withdraw()
    return overlay, canvas


def capture_region(overlay, canvas):
    # Tkinter's own <ButtonPress-1>/<B1-Motion> events turned out to be
    # unreliable here: Windows sometimes delivers the very first click to a
    # just-shown window as a plain "activate/focus" click and never passes
    # it on to the widget, so on_press never fired (confirmed by a
    # KeyError on coords["x1"] -- release arrived, press never did).
    #
    # Instead we poll the raw OS mouse state via `mouse` (the same kind of
    # global, focus-independent hook `keyboard` uses), on the main thread,
    # driven by Tkinter's own `after()` timer. This can't miss the initial
    # press regardless of window focus.
    canvas.delete("all")
    overlay.deiconify()
    overlay.lift()
    overlay.attributes("-topmost", True)
    overlay.focus_force()
    _force_foreground(overlay)

    ox, oy = overlay.winfo_rootx(), overlay.winfo_rooty()
    state = {"x1": None, "y1": None, "rect": None, "result": None}

    def poll():
        if state["result"] is not None:
            return  # already finished; stop polling

        if keyboard.is_pressed("esc"):
            state["result"] = "cancelled"
            return

        sx, sy = mouse.get_position()  # absolute screen coords
        pressed = mouse.is_pressed("left")

        if pressed and state["x1"] is None:
            state["x1"], state["y1"] = sx, sy
            state["rect"] = canvas.create_rectangle(
                sx - ox, sy - oy, sx - ox, sy - oy, outline="red", width=2
            )
        elif pressed and state["x1"] is not None:
            canvas.coords(state["rect"], state["x1"] - ox, state["y1"] - oy, sx - ox, sy - oy)
        elif not pressed and state["x1"] is not None:
            state["result"] = "done"
            state["x2"], state["y2"] = sx, sy
            return

        overlay.after(15, poll)

    overlay.after(15, poll)

    # Block (without freezing the Tk event loop) until poll() sets a result.
    while state["result"] is None:
        overlay.update()
        time.sleep(0.01)

    overlay.withdraw()

    if state["result"] == "cancelled" or "x2" not in state:
        print("[info] Region capture cancelled.")
        return

    left, right = sorted([state["x1"], state["x2"]])
    top, bottom = sorted([state["y1"], state["y2"]])
    print(f"[debug] press=({state['x1']},{state['y1']}) release=({state['x2']},{state['y2']}) size={right-left}x{bottom-top}")

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
    overlay, canvas = build_region_overlay(root)

    def poll_queue():
        try:
            while True:
                action = actions.get_nowait()
                if action == "full":
                    capture_full_screen()
                elif action == "region":
                    capture_region(overlay, canvas)
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
