"""Job tracker storage: tracker_data.json is the source of truth; jobs_tracker.xlsx is an export
the user can also edit (Status / Applied on / Notes are read back in)."""
import datetime as dt
import json
import os
import threading

from . import rules

PROFILE_TEMPLATE = """# Candidate profile

Fill this in under Settings → Your profile in the app (it's saved as profile.md in your data folder).
The AI uses only what's written here to score jobs and draft cover letters, so keep it accurate.

## Preferences
- **Target:** entry-level, associate and mid-level AI roles in the USA
- **Work setup:** remote preferred
- **Visa sponsorship needed:** yes / no
- **Salary:** your minimum
- **Strong-fit areas:** the kinds of roles where your background helps most

## Resume summary
**Your Name**: one-line headline

### Experience
- Title, Company (dates)

### Skills
- Group: skill, skill, skill

### Gaps to be honest about in cover letters
- Skills you don't have yet, so drafts never claim them
"""

STATUSES = ["New", "Interested", "Applied", "Interview", "Offer", "Rejected", "Skip"]
USER_FIELDS = {"Status": "status", "Applied on": "applied_on", "Notes": "notes"}
_lock = threading.RLock()


class Store:
    def __init__(self, data_dir):
        self.root = data_dir
        self.runs = os.path.join(data_dir, "runs")
        self.drafts = os.path.join(data_dir, "drafts")
        os.makedirs(self.runs, exist_ok=True)
        os.makedirs(self.drafts, exist_ok=True)
        self.data_file = os.path.join(data_dir, "tracker_data.json")
        self.desc_file = os.path.join(data_dir, "runs", "descriptions.json")
        self.seen_file = os.path.join(self.runs, "seen_ids.json")
        self.state_file = os.path.join(self.runs, "state.json")
        self.log_file = os.path.join(self.runs, "run_log.csv")
        self.xlsx = os.path.join(data_dir, "jobs_tracker.xlsx")
        self.profile_file = os.path.join(data_dir, "profile.md")
        if not os.path.exists(self.profile_file):  # first run: start from a template the user fills in
            with open(self.profile_file, "w", encoding="utf-8") as f:
                f.write(PROFILE_TEMPLATE)

    # ------------------------------------------------------------ json helpers
    @staticmethod
    def load(path, default):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    @staticmethod
    def save(path, obj):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, ensure_ascii=False)
        os.replace(tmp, path)

    def jobs(self):
        return self.load(self.data_file, [])

    def save_jobs(self, data):
        self.save(self.data_file, data)

    def state(self):
        return self.load(self.state_file, {})

    def save_state(self, st):
        self.save(self.state_file, st)

    def descriptions(self):
        return self.load(self.desc_file, {})

    def add_descriptions(self, mapping):
        with _lock:
            d = self.descriptions()
            d.update(mapping)
            self.save(self.desc_file, d)

    def profile(self):
        try:
            with open(self.profile_file, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def save_profile(self, text):
        with open(self.profile_file, "w", encoding="utf-8") as f:
            f.write(text)

    # ------------------------------------------------------------ edits
    def update_job(self, job_id, **fields):
        allowed = {"status", "notes", "applied_on", "draft", "outreach"}
        with _lock:
            data = self.jobs()
            for r in data:
                if r["id"] == job_id:
                    for k, v in fields.items():
                        if k in allowed:
                            r[k] = v
                    if fields.get("status") == "Applied" and not r.get("applied_on"):
                        r["applied_on"] = dt.date.today().isoformat()
                    break
            else:
                return None
            self.save_jobs(data)
            return r

    def pull_excel_edits(self):
        """Read Status / Applied on / Notes changed in Excel since the app last wrote the file."""
        with _lock:
            if not os.path.exists(self.xlsx):
                return 0
            st = self.state()
            mtime = os.path.getmtime(self.xlsx)
            if mtime <= st.get("xlsx_written_mtime", 0) + 1:
                return 0  # nobody has saved the file since we wrote it
            from openpyxl import load_workbook
            try:
                wb = load_workbook(self.xlsx, read_only=True, data_only=True)
            except Exception:
                return 0
            data = self.jobs()
            by_id = {r["id"]: r for r in data}
            original = {r["id"]: {k: r.get(k) or "" for k in USER_FIELDS.values()} for r in data}
            changed = 0
            for ws in wb.worksheets:
                rows = ws.iter_rows(values_only=True)
                header = next(rows, None)
                if not header or "Job ID" not in header:
                    continue
                idx = {h: i for i, h in enumerate(header)}
                for row in rows:
                    jid = row[idx["Job ID"]]
                    rec = by_id.get(str(jid)) if jid is not None else None
                    if not rec:
                        continue
                    for col, key in USER_FIELDS.items():
                        if col in idx:
                            val = row[idx[col]]
                            val = "" if val is None else (val.strftime("%Y-%m-%d") if hasattr(val, "strftime") else str(val))
                            if val != original[rec["id"]][key]:
                                rec[key] = val
                                changed += 1
            wb.close()
            if changed:
                self.save_jobs(data)
            st["xlsx_written_mtime"] = mtime
            self.save_state(st)
            return changed

    # ------------------------------------------------------------ prefilter
    def prefilter(self, items):
        """Drop already-seen, senior and non-AI jobs. Returns (new_jobs, dropped_counts)."""
        with _lock:
            seen = set(self.load(self.seen_file, []))
            data = self.jobs()
            known = {r["id"] for r in data}
            keys = {(r["title"].lower(), r["company"].lower()) for r in data}
            new, dropped = [], {"seen": 0, "senior": 0, "not_relevant": 0}
            descs = {}
            for j in items:
                jid = str(j.get("id") or "")
                title, desc = j.get("title") or "", j.get("description") or ""
                company = j.get("companyName") or ""
                if not jid:
                    continue
                if jid in seen or jid in known or (title.lower(), company.lower()) in keys:
                    dropped["seen"] += 1
                    continue
                seen.add(jid)
                keys.add((title.lower(), company.lower()))
                if rules.is_senior(title):
                    dropped["senior"] += 1
                    continue
                if not rules.is_relevant(title, desc):
                    dropped["not_relevant"] += 1
                    continue
                sp, ev = rules.sponsorship(desc)
                trimmed = rules.trim_description(desc)
                descs[jid] = trimmed
                new.append({
                    "id": jid, "source": j.get("source") or "LinkedIn", "title": title, "company": company,
                    "location": j.get("location") or "", "posted": j.get("publishedAt") or "",
                    "salary": j.get("salary") or "", "type": j.get("contractType") or "",
                    "level": j.get("experienceLevel") or "",
                    "url": (j.get("jobUrl") or "").split("?")[0],
                    "hint_work_setup": rules.work_setup(title, j.get("location") or "", desc),
                    "hint_sponsorship": sp, "hint_evidence": ev,
                    "known_filer": "Yes" if rules.known_filer(company) else "",
                    "h1b": rules.h1b_label(company),
                    "poster_name": j.get("posterFullName") or "", "poster_url": j.get("posterProfileUrl") or "",
                    "description": trimmed,
                })
            self.save(self.seen_file, sorted(seen))
            self.add_descriptions(descs)
            return new, dropped

    def add_jobs(self, new_jobs, judgments):
        """Merge scored jobs into the tracker. judgments: {id: {...}} (may be missing for some)."""
        with _lock:
            data = self.jobs()
            have = {r["id"] for r in data}
            found = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
            added = []
            for base in new_jobs:
                if base["id"] in have:
                    continue
                jd = judgments.get(base["id"], {})
                rec = {k: base[k] for k in ("id", "source", "title", "company", "location", "posted",
                                             "salary", "type", "level", "url", "known_filer")}
                rec["poster_name"], rec["poster_url"] = base.get("poster_name", ""), base.get("poster_url", "")
                rec["h1b"] = base.get("h1b", "")
                rec.update({
                    "fit": jd.get("fit"), "fit_reason": jd.get("fit_reason", "") or ("" if jd else "Not scored yet"),
                    "work_setup": jd.get("work_setup") or base["hint_work_setup"],
                    "sponsorship": jd.get("sponsorship") or base["hint_sponsorship"],
                    "sponsorship_evidence": jd.get("sponsorship_evidence") or base["hint_evidence"],
                    "found": found, "status": "New", "draft": "", "applied_on": "", "notes": "",
                })
                data.append(rec)
                added.append(rec)
                have.add(rec["id"])
            self.save_jobs(data)
            return added

    def apply_scores(self, judgments):
        """Update fit/sponsorship/work setup on existing jobs (used by 'Score unscored jobs')."""
        with _lock:
            data = self.jobs()
            n = 0
            for r in data:
                jd = judgments.get(r["id"])
                if jd:
                    for k in ("fit", "fit_reason", "work_setup", "sponsorship", "sponsorship_evidence"):
                        if jd.get(k) not in (None, ""):
                            r[k] = jd[k]
                    n += 1
            self.save_jobs(data)
            return n

    # ------------------------------------------------------------ run log
    def log_run(self, result, scraped="", new="", top="", cost="", note=""):
        first = not os.path.exists(self.log_file)
        with open(self.log_file, "a", encoding="utf-8") as f:
            if first:
                f.write("time,result,scraped,new,top,cost_usd,note\n")
            f.write(",".join(str(x).replace(",", ";").replace("\n", " ") for x in
                             [dt.datetime.now().strftime("%Y-%m-%d %H:%M"), result, scraped, new, top, cost, note]) + "\n")

    def run_history(self, limit=100):
        try:
            with open(self.log_file, encoding="utf-8") as f:
                lines = f.read().strip().splitlines()[1:]
        except FileNotFoundError:
            return []
        out = []
        for ln in reversed(lines[-limit:]):
            p = (ln.split(",", 6) + [""] * 7)[:7]
            out.append(dict(zip(["time", "result", "scraped", "new", "top", "cost", "note"], p)))
        return out

    # ------------------------------------------------------------ Excel export
    def render_xlsx(self):
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.datavalidation import DataValidation

        with _lock:
            data = self.jobs()
            for r in data:
                r["outlook"] = outlook(r)
            data.sort(key=lambda r: (r.get("found", ""), r.get("fit") or 0), reverse=True)
            cols = [("Status", "status", 12), ("Fit", "fit", 6), ("Why it fits", "fit_reason", 45),
                    ("Title", "title", 44), ("Company", "company", 24), ("Location", "location", 20),
                    ("Work setup", "work_setup", 14), ("Sponsorship", "outlook", 12),
                    ("Sponsorship detail", "sponsorship_evidence", 50), ("Known H-1B filer", "known_filer", 9),
                    ("Level", "level", 13), ("Type", "type", 11), ("Salary", "salary", 18),
                    ("Posted", "posted", 11), ("Found", "found", 16), ("Cover letter", "draft", 14),
                    ("Applied on", "applied_on", 11), ("Notes", "notes", 30), ("Source", "source", 10),
                    ("Job ID", "id", 13)]
            head_fill = PatternFill("solid", fgColor="1F3864")
            fills = {"Good": "C6EFCE", "Possible": "FFF2CC", "No": "F8CBAD",
                     "Remote": "C6EFCE", "Possibly remote": "E2EFDA", "Hybrid": "DDEBF7"}

            def sheet(wb, name, rows):
                ws = wb.create_sheet(name)
                ws.append([c[0] for c in cols])
                for c in ws[1]:
                    c.font = Font(bold=True, color="FFFFFF")
                    c.fill = head_fill
                for r in rows:
                    ws.append([r.get(k) if r.get(k) is not None else "" for _, k, _ in cols])
                    n = ws.max_row
                    for i, (_, key, _) in enumerate(cols, 1):
                        cell = ws.cell(n, i)
                        v = r.get(key)
                        if key == "title" and r.get("url"):
                            cell.hyperlink = r["url"]
                            cell.font = Font(color="0563C1")
                        elif key == "draft" and v:
                            cell.value = "Open draft"
                            cell.hyperlink = os.path.join(self.root, v)
                            cell.font = Font(color="0563C1", underline="single")
                        elif key in ("outlook", "work_setup") and v in fills:
                            cell.fill = PatternFill("solid", fgColor=fills[v])
                        if key in ("fit_reason", "sponsorship_evidence", "notes"):
                            cell.alignment = Alignment(wrap_text=True, vertical="top")
                for i, (_, _, w) in enumerate(cols, 1):
                    ws.column_dimensions[get_column_letter(i)].width = w
                dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=True)
                ws.add_data_validation(dv)
                dv.add(f"A2:A{max(ws.max_row, 2) + 500}")
                ws.freeze_panes = "E2"
                ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{max(ws.max_row, 1)}"

            wb = Workbook()
            wb.remove(wb.active)
            active = [r for r in data if r.get("status") not in ("Rejected", "Skip")]
            sheet(wb, "Top matches", sorted([r for r in active if (r.get("fit") or 0) >= 7],
                                            key=lambda r: -(r.get("fit") or 0)))
            sheet(wb, "My pipeline", [r for r in data if r.get("status") in ("Interested", "Applied", "Interview", "Offer")])
            sheet(wb, "All jobs", data)
            tmp = self.xlsx.replace(".xlsx", ".tmp.xlsx")
            wb.save(tmp)
            try:
                os.replace(tmp, self.xlsx)
            except PermissionError:
                os.remove(tmp)
                return False
            st = self.state()
            st["xlsx_written_mtime"] = os.path.getmtime(self.xlsx)
            self.save_state(st)
            return True


def outlook(r):
    sp = r.get("sponsorship", "")
    if sp == "No":
        return "No"
    if sp == "Yes":
        return "Good"
    if sp == "Maybe" or r.get("known_filer") == "Yes" or rules.known_filer(r.get("company", "")):
        return "Possible"
    return "Unknown"
