# AI Job Agent

A Windows desktop app that finds new entry- to mid-level AI jobs in the USA every 30 minutes, scores them
against your resume, flags remote work and visa sponsorship, drafts cover letters and outreach notes, and
tracks your applications. It runs in the background from the system tray.

## Download
1. Go to [Releases](../../releases/latest) and download `AI-Job-Agent-v1.0.0-windows.zip`.
2. Unzip it anywhere, for example into `Documents`.
3. Open the `AI Job Agent` folder and double-click **AI Job Agent.exe**.
   Windows may show "Windows protected your PC" because the app isn't code-signed: click **More info → Run anyway**.
4. In the app, open **Settings**: fill in **Your profile** (your resume summary) and pick an AI option.
   For free, private scoring install [Ollama](https://ollama.com) and run `ollama pull gemma4`.

Requires Windows 10 or 11 (64-bit) with the Microsoft Edge WebView2 runtime, which Windows 11 includes.
The app stays in the system tray when you close the window; right-click the tray icon → Quit to stop it.

## What it does
- **Finds jobs** from free sources: [AI Dev Jobs](https://aidevboard.com), [Remote OK](https://remoteok.com),
  and 65 company career boards (Greenhouse, Lever, Ashby: Anthropic, OpenAI, Databricks, Scale AI, Samsara and
  more). LinkedIn is optional through an [Apify](https://apify.com) token (paid per result).
- **Filters** out jobs it has already seen, senior titles, and roles unrelated to AI or your background.
- **Scores fit 1–10** with AI, plus sponsorship (Yes / Maybe / No) and work setup (Remote / Hybrid / On-site).
- **Drafts** a cover letter, resume tweaks and gaps list for top matches, and short LinkedIn outreach notes.
- **People to contact:** shows the hiring contact when a posting names one, and one-click LinkedIn and Google
  searches for recruiters, hiring managers, directors and team members. Nothing is sent for you.
- **Tracks** each job's status (New → Interested → Applied → Interview → Offer) with notes, and exports
  `jobs_tracker.xlsx`. Edits made in Excel are read back in.
- **Notifies** you when a new job scores at or above your alert level.

## AI options
| Option | Cost | Notes |
|---|---|---|
| Ollama on your PC | Free | Private, no key. Install [Ollama](https://ollama.com) and pull a model, e.g. `ollama pull gemma4`. |
| Google Gemini | Free tier | Key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Daily limits apply. |
| Claude | Paid | Key from [console.anthropic.com](https://console.anthropic.com). Best quality. |
| Keyword matching | Free | Used automatically when no AI is available. |

"Auto" tries Ollama, then Gemini, then Claude. Keys are stored in Windows Credential Manager, never in files.

## Build and install
```bash
python -m venv %LOCALAPPDATA%\AIJobAgent-build\venv
%LOCALAPPDATA%\AIJobAgent-build\venv\Scripts\pip install -r requirements.txt
%LOCALAPPDATA%\AIJobAgent-build\venv\Scripts\python build.py
```
This installs to `%LOCALAPPDATA%\Programs\AI Job Agent` and adds Desktop and Start-menu shortcuts.
To run from source instead: `python main.py`.

## Your data
Everything personal lives in `Documents\AI Job Agent` (tracker, profile, cover letters, run log) and is not
part of this repository. Start from [profile.example.md](profile.example.md) for your profile.

## Layout
- `main.py`: entry point
- `jobagent/app.py`: window, tray icon, scheduler and the API the UI calls
- `jobagent/runner.py`: one run: fetch, filter, score, track, draft, notify
- `jobagent/sources.py`: job sources
- `jobagent/ai.py`: Claude, Gemini, Ollama and keyword scoring
- `jobagent/tracker.py`: storage and Excel export
- `jobagent/rules.py`: keyword rules for sponsorship, remote work, seniority and relevance
- `jobagent/ui/index.html`: the interface
- `build.py`: PyInstaller build and install
