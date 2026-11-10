# AI Job Agent

A Windows desktop app that finds new entry- to mid-level AI jobs in the USA every 30 minutes, scores them
against your resume, flags remote work and visa sponsorship, drafts cover letters and outreach notes, and
tracks your applications. It runs in the background from the system tray.

## Download
1. Go to [Releases](../../releases/latest) and download `AI-Job-Agent-v1.1.0-windows.zip`.
2. Unzip it anywhere, for example into `Documents`.
3. Open the `AI Job Agent` folder and double-click **AI Job Agent.exe**.
   Windows may show "Windows protected your PC" because the app isn't code-signed: click **More info → Run anyway**.
4. In the app, open **Settings**: fill in **Your profile** (your resume summary) and pick an AI option.
   For free, private scoring install [Ollama](https://ollama.com) and run `ollama pull gemma4`.

Requires Windows 10 or 11 (64-bit) with the Microsoft Edge WebView2 runtime, which Windows 11 includes.
The app stays in the system tray when you close the window; right-click the tray icon → Quit to stop it.

## What it does
- **Finds jobs** from many free sources: [AI Dev Jobs](https://aidevboard.com), [Remote OK](https://remoteok.com),
  [Remotive](https://remotive.com), [Himalayas](https://himalayas.app), Hacker News "Who is hiring", 65 company
  career boards (Greenhouse, Lever, Ashby), SmartRecruiters and Workable boards, and 25 big-employer Workday career
  sites (NVIDIA, Salesforce, Adobe, Capital One, Visa and more).
- **Optional free-key sources:** Adzuna, Jooble and JSearch (Google Jobs, which includes LinkedIn and Indeed postings).
- **Your job-alert emails:** reads LinkedIn, Indeed, Glassdoor and ZipRecruiter alert emails from Gmail (read-only,
  with an app password). LinkedIn via [Apify](https://apify.com) is also optional (paid per result).
- **H-1B records:** shows each company's H-1B approvals from USCIS data (fiscal years 2022–2023).
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
