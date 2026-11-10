"""AI Job Agent - desktop app entry point."""
import ctypes
import os
import traceback


def _crash(exc_text):
    folder = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AI Job Agent")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "error.log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(exc_text + "\n")
    ctypes.windll.user32.MessageBoxW(None, f"AI Job Agent hit a problem and had to close.\n\nDetails were saved to:\n{path}",
                                     "AI Job Agent", 0x10)


if __name__ == "__main__":
    try:
        from jobagent.app import main
        main()
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 - last-resort crash report for a windowed app
        _crash(traceback.format_exc())
