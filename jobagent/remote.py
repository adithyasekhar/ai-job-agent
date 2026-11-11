"""Phone access over Wi-Fi: serves the same interface to a phone browser, which can be added to the home screen.

Off by default. When on, it listens on your local network only, and every request must carry the pairing code
(from the QR code in Settings). Only a safe subset of actions is available from the phone: no settings, keys or
files on your PC.
"""
import base64
import io
import json
import os
import secrets
import socket
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import settings as cfg

PORT = 8740
ALLOWED = {"get_state", "get_jobs", "get_description", "update_job", "run_now", "stop_run", "write_draft",
           "write_outreach", "write_gap_plan", "list_drafts", "read_draft", "get_history", "get_dashboard",
           "score_unscored"}
SHIM = """<script>
window.CAREERPILOT_REMOTE = true;
window.pywebview = {api: new Proxy({}, {get: (_, name) => (...args) =>
  fetch('/api/' + name, {method: 'POST', credentials: 'same-origin', body: JSON.stringify(args)})
    .then(r => { if (r.status === 401) { document.body.innerHTML = '<p style="font:16px sans-serif;padding:24px">This phone isn\\'t paired. Scan the QR code in CareerPilot AI → Settings → Phone access.</p>'; throw new Error('unpaired'); } return r.json(); })})};
window.addEventListener('load', () => window.dispatchEvent(new Event('pywebviewready')));
</script>"""
MANIFEST = {"name": "CareerPilot AI", "short_name": "CareerPilot", "start_url": "/", "display": "standalone",
            "background_color": "#1F2937", "theme_color": "#1F2937",
            "icons": [{"src": "/assets/icon.png", "sizes": "512x512", "type": "image/png"}]}


def _addresses():
    found = []
    try:
        found += socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; this just picks the default interface
        found.append(s.getsockname()[0])
    except OSError:
        pass
    finally:
        s.close()
    return [a for a in dict.fromkeys(found) if not a.startswith("127.")]


def _rank(a):
    o = [int(x) for x in a.split(".")]
    if o[0] == 192 and o[1] == 168:
        return 0  # typical home Wi-Fi
    if o[0] == 10 or (o[0] == 172 and 16 <= o[1] <= 31):
        return 1
    if o[0] == 100 and 64 <= o[1] <= 127:
        return 3  # Tailscale / carrier NAT: works when the phone is on the same Tailscale network
    return 2


def lan_ip():
    addrs = sorted(_addresses(), key=_rank)
    return addrs[0] if addrs else "127.0.0.1"


def other_ips():
    return [a for a in sorted(_addresses(), key=_rank)[1:]]


def token():
    t = cfg.get_secret("phone_token")
    if not t:
        t = secrets.token_urlsafe(18)
        cfg.set_secret("phone_token", t)
    return t


def reset_token():
    cfg.set_secret("phone_token", "")
    return token()


def pairing_url():
    return f"http://{lan_ip()}:{PORT}/?k={token()}"


def qr_data_uri(text):
    import qrcode
    img = qrcode.make(text, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class _Handler(BaseHTTPRequestHandler):
    api = None
    ui_dir = None
    assets_dir = None

    def log_message(self, *a):
        pass

    def _authed(self, query):
        good = token()
        if secrets.compare_digest(query.get("k", [""])[0], good):
            return True
        c = SimpleCookie(self.headers.get("Cookie", ""))
        return "cp_k" in c and secrets.compare_digest(c["cp_k"].value, good)

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/manifest.webmanifest":
            return self._send(200, json.dumps(MANIFEST).encode(), "application/manifest+json")
        if u.path == "/assets/icon.png":
            with open(os.path.join(self.assets_dir, "icon.png"), "rb") as f:
                return self._send(200, f.read(), "image/png")
        if u.path in ("/", "/ui/index.html"):
            if not self._authed(q):
                return self._send(401, b"<p style='font:16px sans-serif;padding:24px'>Scan the QR code in "
                                       b"CareerPilot AI &rarr; Settings &rarr; Phone access to pair this phone.</p>",
                                  "text/html; charset=utf-8")
            with open(os.path.join(self.ui_dir, "index.html"), encoding="utf-8") as f:
                html = f.read().replace("<head>", "<head>" + SHIM, 1).replace('href="../assets/icon.png"', 'href="/assets/icon.png"')
            extra = {"Set-Cookie": f"cp_k={token()}; Max-Age=31536000; Path=/; HttpOnly; SameSite=Strict"}
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8", extra)
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        u = urlparse(self.path)
        if not self._authed(parse_qs(u.query)):
            return self._send(401, b'{"ok":false,"message":"not paired"}', "application/json")
        name = u.path.rsplit("/", 1)[-1]
        if name not in ALLOWED:
            return self._send(403, b'{"ok":false,"message":"not available from the phone"}', "application/json")
        try:
            args = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)) or b"[]")
            res = getattr(self.api, name)(*args)
        except Exception as e:  # noqa: BLE001
            res = {"ok": False, "message": str(e)[:200]}
        self._send(200, json.dumps(res, default=str).encode(), "application/json")


class PhoneServer:
    def __init__(self, api, ui_dir, assets_dir):
        _Handler.api, _Handler.ui_dir, _Handler.assets_dir = api, ui_dir, assets_dir
        self.httpd = None

    @property
    def running(self):
        return self.httpd is not None

    def start(self):
        if self.httpd:
            return True
        try:
            self.httpd = ThreadingHTTPServer(("0.0.0.0", PORT), _Handler)
        except OSError:
            self.httpd = None
            return False
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return True

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
