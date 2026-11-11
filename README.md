# CareerPilot AI

**Discover · Match · Connect · Apply.** A local-first Windows app that finds entry- to mid-level AI jobs in the
USA every 30 minutes, ranks them against your resume, flags remote work and visa sponsorship, drafts cover letters
and outreach notes, reminds you to follow up, and works on your phone over Wi-Fi. It runs from the system tray, and
with Ollama the AI runs on your PC for free.

## Download
1. Go to [Releases](../../releases/latest) and download `CareerPilot-AI-v2.1.0-windows.zip`.
2. Unzip it anywhere, open the `CareerPilot AI` folder and double-click **CareerPilot AI.exe**.
   Windows may show "Windows protected your PC" because the app isn't code-signed: click **More info → Run anyway**.
3. Open **My profile**: upload your resume (Word or PDF) or fill in the form, check your target roles, and save your application answers. Pick an AI option in **Settings**.
4. For free, private AI install [Ollama](https://ollama.com), then run:
   ```
   ollama pull gemma4
   ollama pull nomic-embed-text
   ```

Requires Windows 10 or 11 (64-bit) with the Microsoft Edge WebView2 runtime (included in Windows 11).
Upgrading from AI Job Agent v1.x: your jobs, settings and keys carry over automatically.

## What it does
- **Built for early-career AI engineers:** upload your resume and CareerPilot searches for your target roles
  (AI/ML Engineer, LLM, GenAI, Data Scientist, MLOps… editable), scores every job against your resume, and labels
  each one Internship / Entry / Intermediate / Experienced with the years of experience it asks for.
- **ATS resume tailoring:** for any job, your resume is rewritten for that posting and scored before and after.
  Keywords you genuinely have are surfaced and bullets reworded; anything not in your resume is listed as missing,
  never invented. Saved as an ATS-safe Word file and PDF.
- **Assisted apply:** on Greenhouse, Lever and Ashby forms (most company career sites) the app opens the
  application in Microsoft Edge, fills in your details and screening answers, attaches the tailored resume and
  cover letter, highlights questions only you can answer, and stops. You review and click Submit. For jobs found on
  LinkedIn, Indeed or Dice it looks for the same job on the company's own site; those sites are never automated.
- **Profiles:** each person has their own resume, targets, jobs and files.
- **Dashboard:** greeting, jobs indexed, best matches, new today, applications, top matches, follow-ups,
  skills to learn and new jobs this week.
- **Finds jobs** from free sources: Hacker News "Who is hiring", 25 big-employer Workday career sites (NVIDIA,
  Salesforce, Adobe, Capital One, Visa…), 65 company boards (Greenhouse, Lever, Ashby), SmartRecruiters, Workable,
  Himalayas, Remotive, AI Dev Jobs and Remote OK. Optional: Adzuna, Jooble, JSearch (Google Jobs, which includes
  LinkedIn and Indeed postings), your LinkedIn/Indeed/Glassdoor/ZipRecruiter alert emails (Gmail, read-only), and
  LinkedIn via Apify.
- **Match %:** every job is compared with your resume by meaning (local embeddings, milliseconds per job), and
  the best ones get a full AI fit score. The two are blended into one match %.
- **Sponsorship intelligence:** the posting's wording, OPT/CPT acceptance, and each company's H-1B approvals from
  USCIS (FY2022–23) combine into Sponsors / H-1B likely / Possible / Unknown / No.
- **Contact finder:** the hiring contact when a posting names one, plus one-click LinkedIn and Google searches for
  recruiters, hiring managers, directors and team members at each company. Nothing is sent for you.
- **Application assistant:** cover letters with resume tweaks, LinkedIn outreach notes, and per-job skill-gap plans
  (free courses, a portfolio project, interview prep).
- **Learning hub:** the skills your best matches ask for most that your profile doesn't list yet.
- **Tracker and reminders:** statuses (Interested → Applied → Interview → Offer), notes, applied and interview
  dates; a nudge to follow up 7 days after applying and a reminder the day before an interview. Excel export.
- **Phone access:** turn it on in Settings, scan the QR code with your phone on the same Wi-Fi, and add it to your
  home screen. The phone gets the dashboard, matches, statuses, notes, contacts and drafts; settings, keys and
  files stay on the PC.

## AI options
| Option | Cost | Notes |
|---|---|---|
| Ollama on your PC | Free | Private, no key. `gemma4` for scoring and writing, `nomic-embed-text` for match %. |
| Google Gemini | Free tier | Key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Daily limits apply. |
| Claude | Paid | Key from [console.anthropic.com](https://console.anthropic.com). Best quality. |
| Keyword matching | Free | Used automatically when no AI is available. |

Keys are stored in Windows Credential Manager, never in files.

## Build from source
```bash
python -m venv %LOCALAPPDATA%\AIJobAgent-build\venv
%LOCALAPPDATA%\AIJobAgent-build\venv\Scripts\pip install -r requirements.txt
%LOCALAPPDATA%\AIJobAgent-build\venv\Scripts\python build.py
```
This installs to `%LOCALAPPDATA%\Programs\CareerPilot AI` with Desktop and Start-menu shortcuts. Run from source
with `python main.py`.

## Your data
Everything personal lives in `Documents\AI Job Agent` (tracker, profile, cover letters, run log, embeddings) and is
not part of this repository. Start from [profile.example.md](profile.example.md).

## Layout
- `main.py`: entry point
- `jobagent/app.py`: window, tray, scheduler and the API the interface calls
- `jobagent/runner.py`: one run: fetch, filter, match, score, track, draft, remind
- `jobagent/match.py`: meaning-based matching with local embeddings
- `jobagent/sources.py`, `more_sources.py`, `email_alerts.py`: job sources
- `jobagent/ai.py`: Claude, Gemini, Ollama and keyword scoring; drafts, outreach and skill-gap plans
- `jobagent/rules.py`: sponsorship, OPT/CPT, remote, seniority, relevance, H-1B records, skill gaps
- `jobagent/tracker.py`: storage, follow-ups and Excel export
- `jobagent/resume.py`: resume import and the guided form
- `jobagent/ats.py`: ATS scoring, truthful tailoring, Word/PDF export
- `jobagent/apply.py`: assisted apply in Edge (Greenhouse, Lever, Ashby)
- `jobagent/remote.py`: phone access over Wi-Fi
- `jobagent/ui/index.html`: the interface
- `build.py`: PyInstaller build and install
