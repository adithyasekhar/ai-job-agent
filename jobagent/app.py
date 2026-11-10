"""AI Job Agent desktop app: window (pywebview), tray icon (pystray), built-in scheduler."""
import datetime as dt
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

import webview

from . import ai, email_alerts, more_sources, rules, settings as cfg
from .runner import Runner
from .tracker import Store, outlook

SINGLE_PORT = 47321


def resource(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


# ---------------------------------------------------------------- notifications
def notify(title, msg):
    try:
        from winotify import Notification
        n = Notification(app_id=cfg.APP_NAME, title=title, msg=msg[:250], icon=resource("assets", "icon.png"))
        n.show()
    except Exception:
        pass


# ---------------------------------------------------------------- start with Windows
def startup_shortcut():
    return os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup", "AI Job Agent.lnk")


def set_autostart(enabled):
    lnk = startup_shortcut()
    if not enabled:
        if os.path.exists(lnk):
            os.remove(lnk)
        return
    if getattr(sys, "frozen", False):
        target, args = sys.executable, "--minimized"
    else:
        target = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        args = f'"{os.path.abspath(sys.argv[0])}" --minimized'
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
          f"$s.TargetPath='{target}';$s.Arguments='{args}';$s.WorkingDirectory='{os.path.dirname(target)}';$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


# ---------------------------------------------------------------- API exposed to the UI
class Api:
    def __init__(self):
        self._runner = Runner(notify=notify)
        self._window = None
        self._task = ""          # current background action label
        self._task_result = ""
        self._ai_cache = (0, "")

    # ---- helpers
    def _store(self):
        return Store(cfg.load()["data_dir"])

    def _bg(self, label, fn):
        if self._runner.running or self._task:
            return {"ok": False, "message": "Busy. Please wait for the current task to finish."}

        def work():
            self._task, self._task_result = label, ""
            try:
                self._task_result = fn() or ""
            except Exception as e:  # noqa: BLE001
                self._task_result = f"{label} failed: {e}"
            finally:
                self._task = ""
        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    # ---- state & jobs
    def get_state(self):
        s = cfg.load()
        st = self._store().state()
        last = st.get("last_attempt") or st.get("last_success")
        next_run = None
        if s["schedule_enabled"]:
            if last:
                next_run = (dt.datetime.fromisoformat(last) + dt.timedelta(minutes=int(s["interval_minutes"]))).isoformat()
            else:
                next_run = dt.datetime.now().astimezone().isoformat()
        return {
            "running": self._runner.running, "task": self._task, "task_result": self._task_result,
            "lines": self._runner.lines[-80:], "last_summary": self._runner.last_summary,
            "last_success": st.get("last_success"), "next_run": next_run,
            "schedule_enabled": s["schedule_enabled"], "interval": s["interval_minutes"],
            "has_anthropic": bool(cfg.get_secret("anthropic_api_key")),
            "has_apify": bool(cfg.get_secret("apify_token")), "model": s["model"],
            "threshold": s["alert_threshold"], "ai_label": self._ai_label(), "version": cfg.APP_VERSION,
            "profile_blank": "**Your Name**" in self._store().profile(),
        }

    def _ai_label(self):
        """Which AI will be used, cached briefly (checking Ollama takes a moment)."""
        now = time.time()
        if now - self._ai_cache[0] > 30:
            p = self._runner.provider()
            self._ai_cache = (now, p.label if p else "")
        return self._ai_cache[1]

    def get_jobs(self):
        store = self._store()
        store.pull_excel_edits()
        descs = store.descriptions()
        out = []
        for r in store.jobs():
            r = dict(r)
            r["h1b"] = r.get("h1b") or rules.h1b_label(r.get("company", ""))
            r["known_filer"] = "Yes" if rules.known_filer(r.get("company", "")) else r.get("known_filer", "")
            r["outlook"] = outlook(r)
            r["has_desc"] = r["id"] in descs
            out.append(r)
        return out

    def get_description(self, job_id):
        return self._store().descriptions().get(job_id, "")

    def update_job(self, job_id, fields):
        store = self._store()
        rec = store.update_job(job_id, **fields)
        threading.Thread(target=store.render_xlsx, daemon=True).start()
        return rec

    # ---- actions
    def run_now(self):
        return self._bg("Run", self._runner.run)

    def stop_run(self):
        self._runner.stop()
        return True

    def score_unscored(self):
        return self._bg("Scoring", self._runner.score_unscored)

    def write_draft(self, job_id):
        return self._bg("Cover letter", lambda: self._runner.write_draft(job_id))

    def write_outreach(self, job_id):
        return self._bg("Outreach notes", lambda: self._runner.write_outreach(job_id))

    def list_drafts(self):
        store = self._store()
        jobs = {r.get("draft"): r for r in store.jobs() if r.get("draft")}
        out = []
        for name in sorted(os.listdir(store.drafts), key=lambda n: -os.path.getmtime(os.path.join(store.drafts, n))):
            if name.endswith(".md"):
                rel = os.path.join("drafts", name)
                j = jobs.get(rel) or jobs.get(rel.replace("\\", "/")) or {}
                out.append({"rel": rel, "name": name, "title": j.get("title", name[:-3]), "company": j.get("company", ""),
                            "job_id": j.get("id", ""), "modified": dt.datetime.fromtimestamp(
                                os.path.getmtime(os.path.join(store.drafts, name))).strftime("%b %d, %H:%M")})
        return out

    def read_draft(self, rel):
        store = self._store()
        path = os.path.normpath(os.path.join(store.root, rel))
        if not path.startswith(os.path.normpath(store.drafts)):
            return ""
        with open(path, encoding="utf-8") as f:
            return f.read()

    def open_url(self, url):
        if url.startswith(("http://", "https://")):
            webbrowser.open(url)
        return True

    def open_path(self, rel=""):
        store = self._store()
        path = os.path.normpath(os.path.join(store.root, rel)) if rel else store.root
        if path.startswith(os.path.normpath(store.root)) and os.path.exists(path):
            os.startfile(path)
        return True

    def open_excel(self):
        store = self._store()
        store.pull_excel_edits()
        store.render_xlsx()
        os.startfile(store.xlsx)
        return True

    def get_history(self):
        return self._store().run_history()

    # ---- settings
    def get_settings(self):
        s = cfg.load()
        from . import sources
        a, p, g = cfg.get_secret("anthropic_api_key"), cfg.get_secret("apify_token"), cfg.get_secret("gemini_api_key")
        s.update({"anthropic_masked": cfg.masked(a), "apify_masked": cfg.masked(p), "gemini_masked": cfg.masked(g),
                  "models": cfg.MODELS, "ollama_models": ai.ollama_models(),
                  "boards_text": " ".join(s.get("boards") or sources.DEFAULT_BOARDS),
                  "workday_text": " ".join(s.get("workday_sites") or more_sources.DEFAULT_WORKDAY),
                  "secrets_set": {k: bool(cfg.get_secret(k)) for k in cfg.KEYS},
                  "adzuna_id_masked": cfg.masked(cfg.get_secret("adzuna_app_id")),
                  "source_names": ["AI Dev Jobs", "Remote OK", "Company boards", "Hacker News", "Remotive", "Himalayas",
                                   "Workday sites", "SmartRecruiters/Workable", "Adzuna", "Jooble", "JSearch",
                                   "Job-alert emails"],
                  "profile": self._store().profile(), "start_with_windows": os.path.exists(startup_shortcut())})
        return s

    def save_settings(self, data):
        s = cfg.load()
        for k, low in (("interval_minutes", 5), ("alert_threshold", 1), ("max_drafts_per_run", 0)):
            if k in data:
                s[k] = max(low, int(data[k]))
        if "apify_cap_usd" in data:
            s["apify_cap_usd"] = max(0.05, min(5.0, float(data["apify_cap_usd"])))
        for k in ("schedule_enabled", "needs_sponsorship", "notifications", "use_linkedin", "use_boards"):
            if k in data:
                s[k] = bool(data[k])
        if data.get("model") in cfg.MODELS:
            s["model"] = data["model"]
        if data.get("ai_provider") in ("auto", "ollama", "gemini", "claude", "keywords"):
            s["ai_provider"] = data["ai_provider"]
        for k in ("ollama_model", "gemini_model"):
            if k in data:
                s[k] = str(data[k] or "").strip()
        if "workday_text" in data:
            lines = [ln.strip() for ln in data["workday_text"].replace(",", " ").split() if "/" in ln]
            s["workday_sites"] = [] if lines == more_sources.DEFAULT_WORKDAY else lines
        if isinstance(data.get("sources_off"), list):
            s["sources_off"] = [str(x) for x in data["sources_off"]]
        if "gmail_address" in data:
            s["gmail_address"] = str(data["gmail_address"] or "").strip()
        if "boards_text" in data:
            from . import sources
            lines = [ln.strip() for ln in data["boards_text"].replace(",", " ").split() if ":" in ln]
            s["boards"] = [] if lines == sources.DEFAULT_BOARDS else lines
        cfg.save(s)
        self._ai_cache = (0, "")
        if data.get("anthropic_api_key"):
            cfg.set_secret("anthropic_api_key", data["anthropic_api_key"])
        if data.get("apify_token"):
            cfg.set_secret("apify_token", data["apify_token"])
        if data.get("clear_anthropic"):
            cfg.set_secret("anthropic_api_key", "")
        if data.get("clear_apify"):
            cfg.set_secret("apify_token", "")
        for k in ("adzuna_app_id", "adzuna_app_key", "jooble_api_key", "jsearch_api_key", "gmail_app_password"):
            if data.get(k):
                cfg.set_secret(k, data[k])
            if data.get("clear_" + k):
                cfg.set_secret(k, "")
        if data.get("gemini_api_key"):
            cfg.set_secret("gemini_api_key", data["gemini_api_key"])
        if data.get("clear_gemini"):
            cfg.set_secret("gemini_api_key", "")
        if "profile" in data and data["profile"].strip():
            self._store().save_profile(data["profile"])
        if "start_with_windows" in data:
            set_autostart(bool(data["start_with_windows"]))
        return self.get_settings()

    def test_ai(self, kind, key="", model=""):
        names = {"claude": "anthropic_api_key", "gemini": "gemini_api_key"}
        key = key or (cfg.get_secret(names[kind]) if kind in names else "")
        ok, msg, models = ai.test_provider(kind, key, model or cfg.load().get(
            {"claude": "model", "gemini": "gemini_model", "ollama": "ollama_model"}[kind], ""))
        return {"ok": ok, "message": msg, "models": models}

    def test_source(self, name, a="", b=""):
        """Quick live check of a keyed source; uses typed values or the saved ones."""
        sec = cfg.get_secret
        try:
            if name == "gmail":
                addr, pw = a or cfg.load().get("gmail_address", ""), b or sec("gmail_app_password")
                if not addr or not pw:
                    return {"ok": False, "message": "Enter your Gmail address and app password first."}
                n = len(email_alerts.fetch_alerts(addr, pw, 7 * 86400, lambda m: None))
                return {"ok": True, "message": f"Connected. Found {n} jobs in job-alert emails from the last 7 days."}
            if name == "adzuna":
                aid, key = a or sec("adzuna_app_id"), b or sec("adzuna_app_key")
                n = len(more_sources.fetch_adzuna(aid, key, 86400, lambda m: None))
            elif name == "jooble":
                n = len(more_sources.fetch_jooble(a or sec("jooble_api_key"), 86400, lambda m: None))
            elif name == "jsearch":
                n = len(more_sources.fetch_jsearch(a or sec("jsearch_api_key"), 86400, lambda m: None, queries=1))
            else:
                return {"ok": False, "message": "Unknown source."}
            return {"ok": True, "message": f"Working: {n} jobs found in a quick search."}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": str(e)[:200]}

    def test_apify(self, token=""):
        import requests
        token = token or cfg.get_secret("apify_token")
        if not token:
            return {"ok": False, "message": "Enter a token first."}
        try:
            r = requests.get("https://api.apify.com/v2/users/me", headers={"Authorization": f"Bearer {token}"}, timeout=20)
            if r.status_code == 200:
                d = r.json()["data"]
                plan = (d.get("plan") or {}).get("id", "")
                return {"ok": True, "message": f"Connected as {d.get('username', 'Apify user')}" + (f" ({plan} plan)" if plan else "")}
            return {"ok": False, "message": "Apify rejected this token."}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"Couldn't reach Apify: {e}"}

    def set_schedule(self, enabled):
        s = cfg.load()
        s["schedule_enabled"] = bool(enabled)
        cfg.save(s)
        return True


# ---------------------------------------------------------------- scheduler
def scheduler(api, quit_event):
    time.sleep(45)  # let the window settle before the first automatic run
    while not quit_event.is_set():
        try:
            s = cfg.load()
            if s["schedule_enabled"] and not api._runner.running and not api._task:
                st = api._store().state()
                last = st.get("last_attempt") or st.get("last_success")
                due = True
                if last:
                    elapsed = (dt.datetime.now().astimezone() - dt.datetime.fromisoformat(last)).total_seconds()
                    due = elapsed >= int(s["interval_minutes"]) * 60
                if due:
                    api._task = "Scheduled run"
                    try:
                        api._task_result = api._runner.run()
                    finally:
                        api._task = ""
        except Exception:
            pass
        quit_event.wait(20)


# ---------------------------------------------------------------- tray
def start_tray(api, quit_event):
    import pystray
    from PIL import Image

    def show(*_):
        if api._window:
            api._window.show()
            api._window.restore()

    def run(*_):
        api.run_now()

    def toggle(icon, item):
        s = cfg.load()
        api.set_schedule(not s["schedule_enabled"])

    def quit_app(icon, *_):
        quit_event.set()
        icon.stop()
        if api._window:
            api._window.destroy()

    menu = pystray.Menu(
        pystray.MenuItem("Open AI Job Agent", show, default=True),
        pystray.MenuItem("Run now", run),
        pystray.MenuItem("Automatic runs", toggle, checked=lambda item: cfg.load()["schedule_enabled"]),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app),
    )
    icon = pystray.Icon("AIJobAgent", Image.open(resource("assets", "icon.png")), "AI Job Agent", menu)
    icon.run_detached()
    return icon


# ---------------------------------------------------------------- single instance
def already_running():
    """If another copy is running, ask it to show its window and return True."""
    try:
        with socket.create_connection(("127.0.0.1", SINGLE_PORT), timeout=1) as c:
            c.sendall(b"show")
        return True
    except OSError:
        return False


def listen_for_show(api, quit_event):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.bind(("127.0.0.1", SINGLE_PORT))
    except OSError:
        return
    srv.listen(2)
    srv.settimeout(1)
    while not quit_event.is_set():
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            continue
        with conn:
            if conn.recv(16) == b"show" and api._window:
                api._window.show()
                api._window.restore()


# ---------------------------------------------------------------- main
def main():
    minimized = "--minimized" in sys.argv
    if already_running():
        return
    os.makedirs(cfg.load()["data_dir"], exist_ok=True)
    api = Api()
    quit_event = threading.Event()
    window = webview.create_window(
        "AI Job Agent", url=resource("ui", "index.html"), js_api=api, width=1320, height=860,
        min_size=(980, 640), hidden=minimized, background_color="#0f1115")
    api._window = window
    told = {"tray": False}

    def on_closing():
        if quit_event.is_set():
            return True
        threading.Thread(target=window.hide, daemon=True).start()
        if not told["tray"]:
            told["tray"] = True
            notify("AI Job Agent is still running", "It keeps checking for jobs from the system tray. "
                                                     "Right-click the tray icon and choose Quit to stop it.")
        return False

    window.events.closing += on_closing
    tray = start_tray(api, quit_event)
    threading.Thread(target=scheduler, args=(api, quit_event), daemon=True).start()
    threading.Thread(target=listen_for_show, args=(api, quit_event), daemon=True).start()
    webview.start(debug="--debug" in sys.argv, private_mode=False,
                  storage_path=os.path.join(cfg.CONFIG_DIR, "webview"))
    quit_event.set()
    try:
        tray.stop()
    except Exception:
        pass
