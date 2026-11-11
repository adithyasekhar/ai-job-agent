"""App settings. API keys live in Windows Credential Manager, never in a file."""
import json
import os

import keyring

APP_NAME = "AI Job Agent"
DISPLAY_NAME = "CareerPilot AI"  # APP_NAME stays: it locates your existing settings and saved keys
APP_VERSION = "2.0.0"
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
DEFAULT_DATA_DIR = os.path.join(os.path.expanduser("~"), "OneDrive", "Documents", APP_NAME)
if not os.path.isdir(DEFAULT_DATA_DIR):
    DEFAULT_DATA_DIR = os.path.join(os.path.expanduser("~"), "Documents", APP_NAME)

MODELS = {
    "claude-opus-5-5": "Claude Opus 5.5 (best judgment, paid)",
    "claude-sonnet-5-5": "Claude Sonnet 5.5 (very good, about half the cost of Opus)",
    "claude-haiku-5-5": "Claude Haiku 5.5 (fastest and cheapest Claude)",
}

DEFAULTS = {
    "data_dir": DEFAULT_DATA_DIR,
    "interval_minutes": 30,
    "schedule_enabled": True,
    "apify_cap_usd": 0.20,
    "use_linkedin": True,
    "ai_provider": "auto",
    "ollama_model": "",
    "gemini_model": "",
    "model": "claude-opus-5-5",
    "use_boards": True,
    "boards": [],
    "workday_sites": [],
    "sources_off": [],
    "gmail_address": "",
    "phone_access": False,
    "alert_threshold": 8,
    "max_drafts_per_run": 3,
    "needs_sponsorship": True,
    "notifications": True,
    "start_with_windows": False,
}

KEYS = ("anthropic_api_key", "gemini_api_key", "apify_token", "adzuna_app_id", "adzuna_app_key", "jooble_api_key",
        "jsearch_api_key", "gmail_app_password")


def load():
    s = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            s.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    if s.get("model") not in MODELS:
        s["model"] = DEFAULTS["model"]
    return s


def save(s):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    clean = {k: s[k] for k in DEFAULTS if k in s}
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=1)
    os.replace(tmp, CONFIG_FILE)


def get_secret(name):
    try:
        return keyring.get_password(APP_NAME, name) or ""
    except Exception:
        return ""


def set_secret(name, value):
    if value:
        keyring.set_password(APP_NAME, name, value.strip())
    else:
        try:
            keyring.delete_password(APP_NAME, name)
        except Exception:
            pass


def masked(value):
    return (value[:7] + "…" + value[-4:]) if len(value) > 14 else ("set" if value else "")
