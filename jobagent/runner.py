"""One agent run: fetch → filter → score → tracker → drafts → notify."""
import datetime as dt
import os
import re
import threading

from . import ai, email_alerts, match, more_sources, rules, settings as cfg, sources
from .tracker import Store, outlook

LOCK_STALE_MIN = 90


def _now():
    return dt.datetime.now().astimezone()


class Runner:
    def __init__(self, notify=None):
        self.notify = notify or (lambda title, msg: None)
        self.running = False
        self.lines = []          # live log for the UI
        self.last_summary = ""
        self._stop = False
        self._mutex = threading.Lock()

    # ------------------------------------------------------------ helpers
    def log(self, msg):
        self.lines.append(f"{dt.datetime.now().strftime('%H:%M:%S')}  {msg}")
        self.lines = self.lines[-300:]

    def store(self):
        return Store(cfg.load()["data_dir"])

    def stop(self):
        self._stop = True

    def provider(self, s=None):
        return ai.pick_provider(s or cfg.load(), cfg.get_secret)

    def _acquire_file_lock(self, store):
        """Shared with the older scheduled-task scripts so two runs never overlap."""
        st = store.state()
        lock = st.get("lock")
        if lock:
            try:
                age = (_now() - dt.datetime.fromisoformat(lock)).total_seconds() / 60
            except ValueError:
                age = 999
            if age < LOCK_STALE_MIN:
                return False
        st["lock"] = _now().isoformat()
        store.save_state(st)
        return True

    def _release(self, store, success):
        st = store.state()
        st.pop("lock", None)
        if success:
            st["last_success"] = _now().isoformat()
        st["last_attempt"] = _now().isoformat()
        store.save_state(st)

    def _exclusive(self, fn):
        """Run fn with the in-process mutex held. Returns a message string."""
        if not self._mutex.acquire(blocking=False):
            return "A run is already in progress."
        self.running, self._stop, self.lines = True, False, []
        try:
            return fn()
        finally:
            self.running = False
            self._mutex.release()

    # ------------------------------------------------------------ main run
    def run(self):
        def go():
            store, s = self.store(), cfg.load()
            if not self._acquire_file_lock(store):
                self.log("Another run is in progress (lock held). Skipping.")
                return "Another run is in progress."
            ok = False
            try:
                summary = self._run(store, s)
                ok = True
                return summary
            except Exception as e:  # noqa: BLE001 - show any failure in the UI and log
                msg = str(e) or e.__class__.__name__
                self.log(f"Run failed: {msg}")
                store.log_run("error", note=msg[:150])
                self.last_summary = f"Last run failed: {msg}"
                return self.last_summary
            finally:
                self._release(store, ok)
        return self._exclusive(go)

    def _fetch(self, store, s):
        st = store.state()
        src_state = st.get("sources", {})
        now = _now()
        items, cost, errors = [], 0.0, []
        boards = [b for b in (s.get("boards") or sources.DEFAULT_BOARDS) if ":" in b]
        # name, fetcher(window_secs), minimum hours between fetches, first-time lookback (days)
        plan = [
            ("AI Dev Jobs", lambda w: sources.fetch_aidevboard(w, self.log), 6, 30),
            ("Remote OK", lambda w: sources.fetch_remoteok(w, self.log), 0, 7),
        ]
        if s.get("use_boards", True) and boards:
            plan.append(("Company boards", lambda w: sources.fetch_boards(boards, w, self.log, rules.wanted_title), 3, 14))
        want = rules.wanted_title
        plan += [
            ("Hacker News", lambda w: more_sources.fetch_hn(w, self.log, want), 6, 30),
            ("Remotive", lambda w: more_sources.fetch_remotive(w, self.log, want), 6, 7),
            ("Himalayas", lambda w: more_sources.fetch_himalayas(w, self.log, want), 3, 7),
            ("Workday sites", lambda w: more_sources.fetch_workday(
                s.get("workday_sites") or more_sources.DEFAULT_WORKDAY, w, self.log, want), 6, 14),
            ("SmartRecruiters/Workable", lambda w: more_sources.fetch_smart_workable(w, self.log, want), 6, 14),
        ]
        sec = cfg.get_secret
        if sec("adzuna_app_id") and sec("adzuna_app_key"):
            plan.append(("Adzuna", lambda w: more_sources.fetch_adzuna(sec("adzuna_app_id"), sec("adzuna_app_key"), w, self.log), 3, 3))
        if sec("jooble_api_key"):
            plan.append(("Jooble", lambda w: more_sources.fetch_jooble(sec("jooble_api_key"), w, self.log), 3, 3))
        if sec("jsearch_api_key"):  # free plan is ~200 requests a month: once a day, 5 searches
            plan.append(("JSearch", lambda w: more_sources.fetch_jsearch(sec("jsearch_api_key"), w, self.log), 24, 3))
        if s.get("gmail_address") and sec("gmail_app_password"):
            plan.append(("Job-alert emails", lambda w: email_alerts.fetch_alerts(
                s["gmail_address"], sec("gmail_app_password"), w, self.log), 0, 7))
        off = set(s.get("sources_off") or [])
        for name, fetch, every_h, first_days in plan:
            if self._stop:
                raise RuntimeError("Stopped")
            if name in off:
                continue
            last_src = src_state.get(name)
            age = (now - dt.datetime.fromisoformat(last_src)).total_seconds() if last_src else first_days * 86400
            if age < every_h * 3600:
                continue
            try:
                items += fetch(int(age) + 900)
                src_state[name] = now.isoformat()
            except Exception as e:  # noqa: BLE001 - one source failing shouldn't stop the run
                errors.append(f"{name}: {e}")
                self.log(f"{name} failed: {e}")

        token = cfg.get_secret("apify_token")
        if token and s.get("use_linkedin", True):
            last_li = src_state.get("LinkedIn") or st.get("last_success")
            window = int((now - dt.datetime.fromisoformat(last_li)).total_seconds()) + 600 if last_li else 86400
            try:
                li, c = sources.fetch_linkedin(token, window, float(s["apify_cap_usd"]), self.log, lambda: self._stop)
                items += li
                cost += c or 0
                src_state["LinkedIn"] = now.isoformat()
            except Exception as e:  # noqa: BLE001
                errors.append(f"LinkedIn: {e}")
                self.log(f"LinkedIn failed: {e}")
        st = store.state()
        st["sources"] = src_state
        store.save_state(st)
        return items, cost, errors

    def _apply_profile(self, store, s):
        prefs = store.prefs()
        rules.configure(prefs.get("target_roles"), prefs.get("extra_titles"))
        if prefs.get("needs_sponsorship") is not None:
            s["needs_sponsorship"] = bool(prefs["needs_sponsorship"])
        s["_profile"] = store.profile()
        return s

    def _run(self, store, s):
        s = self._apply_profile(store, s)
        self.log(f"Run started (profile: {s.get('active_profile', '')})")
        edits = store.pull_excel_edits()
        if edits:
            self.log(f"Pulled {edits} edits from Excel")
        items, cost, errors = self._fetch(store, s)
        new, dropped = store.prefilter(items)
        self.log(f"{len(items)} jobs fetched → {len(new)} new matching jobs (skipped {dropped['seen']} already seen, "
                 f"{dropped['senior']} senior, {dropped['not_relevant']} not relevant)")

        # Meaning-based ranking (fast, local) decides which jobs the slower AI scores first.
        profile = store.profile()
        sem = self._semantic(store, new, profile)
        for j in new:
            if j["id"] not in sem:  # no embedding model: fall back to keywords
                sem[j["id"]] = 10 * ai.keyword_score(dict(j, sponsorship=j["hint_sponsorship"]), j["description"],
                                                     s["needs_sponsorship"], profile)["fit"]
        p = self.provider(s)
        cap = 40 if (p and p.kind == "ollama") else 300
        ranked = sorted(new, key=lambda j: -sem.get(j["id"], 0))
        judgments = self._score(s, ranked[:cap], profile) if p else self._keyword(s, new)
        if p and len(ranked) > cap:
            self.log(f"{len(ranked) - cap} more jobs will be AI-scored in the next runs (best matches first)")
        added = store.add_jobs(new, judgments)

        # Use any spare capacity on older unscored jobs, best semantic match first.
        spare = cap - min(len(ranked), cap)
        if p and spare > 0 and not self._stop:
            descs = store.descriptions()
            all_sem = store.semantic_scores()
            backlog = sorted([dict(r, description=descs.get(r["id"], "")) for r in store.jobs()
                              if r.get("fit") in (None, "") and r["id"] in descs],
                             key=lambda r: -(all_sem.get(r["id"]) or 0))[:spare]
            if backlog:
                self.log(f"Scoring {len(backlog)} older unscored jobs")
                try:
                    store.apply_scores(ai.score_jobs(p, profile, backlog, s["needs_sponsorship"], self.log))
                except ai.AIError as e:
                    self.log(f"Backlog scoring stopped: {e}")
        store.set_semantic(sem)  # refresh match % (semantic + AI fit) for every job
        if (added or spare) and not store.render_xlsx():
            self.log("jobs_tracker.xlsx is open in Excel, so it will update next time")

        threshold = int(s["alert_threshold"])
        top = sorted([r for r in added if (r.get("fit") or 0) >= threshold], key=lambda r: -(r["fit"] or 0))
        drafts = self._drafts(store, s, top)

        if top and s.get("notifications", True):
            names = ", ".join(f"{r['company']}: {r['title'][:40]}" for r in top[:3])
            self.notify(f"{len(top)} new job{'s' if len(top) > 1 else ''} scored {threshold}+",
                        names + (f" · {drafts} cover letter{'s' if drafts != 1 else ''} drafted" if drafts else ""))
        self._remind(store, s)
        note = "; ".join(errors)[:150] or f"{drafts} drafts"
        store.log_run("ok" if not errors else "partial", len(items), len(added), len(top),
                      f"{cost:.2f}" if cost else "", note)
        self.last_summary = (f"{dt.datetime.now().strftime('%H:%M')}: {len(added)} new jobs, {len(top)} top matches"
                             + (f", {drafts} drafts" if drafts else "") + (" (some sources failed)" if errors else ""))
        self.log("Done. " + self.last_summary)
        return self.last_summary

    # ------------------------------------------------------------ scoring
    def _semantic(self, store, new, profile):
        """Embed new (and any not-yet-embedded) jobs; return {id: semantic match %} for every job."""
        if not match.available():
            self.log("Embedding model not installed in Ollama (nomic-embed-text): ranking by keywords")
            return {}
        try:
            m = match.Matcher(store)
            descs = store.descriptions()
            todo = [j for j in store.jobs() if j["id"] not in set(m.ids)][:300] + new
            n = m.ensure_jobs(todo, {**descs, **{j["id"]: j.get("description", "") for j in new}})
            if n:
                self.log(f"Embedded {n} jobs for meaning-based matching")
            return m.scores(profile)
        except Exception as e:  # noqa: BLE001 - matching is an optimisation; never fail the run over it
            self.log(f"Meaning-based matching skipped: {e}")
            return {}

    def _score(self, s, jobs, profile):
        if not jobs:
            return {}
        p = self.provider(s)
        if p and "**Your Name**" in profile:
            self.log("This profile has no resume yet: using keyword matching. Add a resume in My profile.")
            p = None
        if p:
            self.log(f"Scoring {len(jobs)} jobs with {p.label}")
            try:
                out = ai.score_jobs(p, profile, jobs, s["needs_sponsorship"], self.log)
                missing = [j for j in jobs if j["id"] not in out]
                if missing:
                    self.log(f"{len(missing)} jobs couldn't be AI-scored; using keyword scoring for those")
                    out.update(self._keyword(s, missing))
                return out
            except ai.AIError as e:
                self.log(f"{p.label} failed: {e}. Using keyword scoring instead.")
        else:
            self.log("No AI available (Ollama not running, no keys): using free keyword scoring")
        return self._keyword(s, jobs)

    @staticmethod
    def _keyword(s, jobs):
        out = {}
        for j in jobs:
            j2 = dict(j, sponsorship=j.get("hint_sponsorship") or j.get("sponsorship", ""))
            out[j["id"]] = ai.keyword_score(j2, j.get("description", ""), s["needs_sponsorship"], s.get("_profile", ""))
        return out

    # ------------------------------------------------------------ drafts and outreach
    def _drafts(self, store, s, top):
        p = self.provider(s)
        if not p or not top:
            return 0
        n = 0
        for r in top:
            if n >= int(s["max_drafts_per_run"]) or self._stop:
                break
            if s["needs_sponsorship"] and outlook(r) == "No":
                continue
            try:
                self._write_draft(store, p, r["id"])
                n += 1
            except Exception as e:  # noqa: BLE001
                self.log(f"Cover letter for {r['company']} failed: {e}")
        return n

    def _write_draft(self, store, p, job_id):
        job = next((r for r in store.jobs() if r["id"] == job_id), None)
        if not job:
            raise ai.AIError("Job not found.")
        self.log(f"Writing cover letter with {p.label}: {job['title']} at {job['company']}")
        text = ai.write_draft(p, store.profile(), job, store.descriptions().get(job_id, ""))
        safe = lambda x: re.sub(r"[^A-Za-z0-9]+", "-", x).strip("-")[:40]  # noqa: E731
        rel = os.path.join("drafts", f"{safe(job['company'])}_{safe(job['title'])}_{safe(job_id)[-12:]}.md")
        with open(os.path.join(store.root, rel), "w", encoding="utf-8") as f:
            f.write(text + "\n")
        store.update_job(job_id, draft=rel)
        store.render_xlsx()
        return rel

    def write_draft(self, job_id):
        def go():
            p = self.provider()
            if not p:
                raise ai.AIError("No AI available. Start Ollama, or add a Gemini or Anthropic key in Settings.")
            rel = self._write_draft(self.store(), p, job_id)
            return f"Cover letter saved: {os.path.basename(rel)}"
        return self._exclusive(go)

    def _remind(self, store, s):
        """Notify once per application that needs a follow-up, and once per upcoming interview."""
        from .tracker import follow_ups
        due, interviews = follow_ups(store.jobs())
        if not s.get("notifications", True):
            return
        fresh_due = [r for r in due if not r.get("follow_up_notified")]
        if fresh_due:
            names = ", ".join(f"{r['company']} ({r['days_since']} days)" for r in fresh_due[:3])
            self.notify(f"Time to follow up on {len(fresh_due)} application{'s' if len(fresh_due) > 1 else ''}", names)
            for r in fresh_due:
                store.update_job(r["id"], follow_up_notified=dt.date.today().isoformat())
        soon = [r for r in interviews if r["days_until"] <= 1 and r.get("interview_notified") != r.get("interview_on")]
        for r in soon:
            when = "today" if r["days_until"] == 0 else "tomorrow"
            self.notify(f"Interview {when}: {r['company']}", r["title"])
            store.update_job(r["id"], interview_notified=r.get("interview_on"))

    def write_gap_plan(self, job_id):
        def go():
            p = self.provider()
            if not p:
                raise ai.AIError("No AI available. Start Ollama, or add a Gemini or Anthropic key in Settings.")
            store = self.store()
            job = next((r for r in store.jobs() if r["id"] == job_id), None)
            if not job:
                raise ai.AIError("Job not found.")
            self.log(f"Writing a skill-gap plan with {p.label} for {job['title']}")
            store.update_job(job_id, gap_plan=ai.write_gap_plan(p, store.profile(), job,
                                                                 store.descriptions().get(job_id, "")))
            return "Skill-gap plan ready"
        return self._exclusive(go)

    def tailor_resume(self, job_id):
        """ATS-tailor the profile's resume for one job; saves Word + PDF in the profile's resumes folder."""
        def go():
            from . import ats, resume as resmod
            p = self.provider()
            if not p:
                raise ai.AIError("No AI available. Start Ollama, or add a Gemini or Anthropic key in Settings.")
            store = self.store()
            base = resmod.load(store)
            if not base:
                raise ai.AIError("Add your resume first: open My profile and upload it (or fill in the form).")
            job = next((r for r in store.jobs() if r["id"] == job_id), None)
            if not job:
                raise ai.AIError("Job not found.")
            self.log(f"Tailoring your resume with {p.label} for {job['title']} at {job['company']}")
            tailored, rep = ats.tailor(p, base, job["title"], job["company"], store.descriptions().get(job_id, ""))
            folder = os.path.join(store.root, "resumes")
            os.makedirs(folder, exist_ok=True)
            safe = lambda x: re.sub(r"[^A-Za-z0-9]+", "-", x).strip("-")[:40]  # noqa: E731
            stem = f"{safe(base.get('name') or 'Resume')}_{safe(job['company'])}_{safe(job['title'])}"
            docx_path, pdf_path = os.path.join(folder, stem + ".docx"), os.path.join(folder, stem + ".pdf")
            ats.export_docx(tailored, docx_path)
            ats.export_pdf(tailored, pdf_path)
            store.update_job(job_id, ats=rep, ats_docx=os.path.relpath(docx_path, store.root),
                             ats_pdf=os.path.relpath(pdf_path, store.root))
            msg = f"Resume tailored: ATS match {rep['before']}% → {rep['after']}%"
            if rep["after"] < 90 and rep["missing"]:
                msg += f" (missing, not in your resume: {', '.join(rep['missing'][:4])})"
            self.log(msg)
            return msg
        return self._exclusive(go)

    def write_outreach(self, job_id):
        def go():
            p = self.provider()
            if not p:
                raise ai.AIError("No AI available. Start Ollama, or add a Gemini or Anthropic key in Settings.")
            store = self.store()
            job = next((r for r in store.jobs() if r["id"] == job_id), None)
            if not job:
                raise ai.AIError("Job not found.")
            self.log(f"Writing outreach notes with {p.label} for {job['company']}")
            text = ai.write_outreach(p, store.profile(), job, store.descriptions().get(job_id, ""))
            store.update_job(job_id, outreach=text)
            return "Outreach notes ready"
        return self._exclusive(go)

    def score_unscored(self):
        """Score jobs that have no fit yet (e.g. from the first scrape)."""
        def go():
            store, s = self.store(), cfg.load()
            s = self._apply_profile(store, s)
            descs = store.descriptions()
            todo = [dict(r, description=descs.get(r["id"], "")) for r in store.jobs() if r.get("fit") in (None, "")]
            if not todo:
                return "Every job already has a fit score."
            self.log(f"Scoring {len(todo)} unscored jobs")
            n = store.apply_scores(self._score(s, todo, store.profile()))
            store.render_xlsx()
            self.last_summary = f"Scored {n} jobs"
            self.log("Done. " + self.last_summary)
            return self.last_summary
        return self._exclusive(go)
