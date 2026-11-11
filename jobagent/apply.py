"""Assisted apply: open a job's application form in Microsoft Edge, fill it from the profile, attach the tailored
resume and cover letter, highlight anything left unanswered, and STOP. The person reviews and clicks Submit.

Works on Greenhouse, Lever and Ashby forms (most company career sites). LinkedIn, Indeed, Dice and others are
never automated (their terms forbid it); for those the app looks for the same job on the company's own site.
"""
import difflib
import os
import re
import threading

import requests

UA = {"User-Agent": "CareerPilotAI/2.1"}
CONTROLS = ("input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=image]):not([type=reset]), "
            "textarea, select")

TEXT_FIELDS = [  # (answer key, label pattern)
    ("first_name", r"first\s*name|given\s*name|preferred\s*first"),
    ("last_name", r"last\s*name|family\s*name|surname"),
    ("full_name", r"^\s*(full\s*|legal\s*)?name\s*\*?\s*$|your\s*name"),
    ("email", r"e-?mail"),
    ("phone", r"phone|mobile|cell"),
    ("linkedin", r"linkedin"),
    ("github", r"github"),
    ("website", r"website|portfolio|personal\s*(site|url)|other\s*url"),
    ("location", r"^\s*(current\s*)?(location|city)|where\s*are\s*you\s*(based|located)|city,\s*state"),
    ("country", r"^\s*country"),
    ("salary", r"salary|compensation\s*expectation|desired\s*(pay|compensation)|expected\s*compensation"),
    ("start_date", r"start\s*date|when\s*can\s*you\s*start|notice\s*period|availability\s*to\s*start"),
    ("how_heard", r"how\s*did\s*you\s*(hear|find)|where\s*did\s*you\s*(hear|find)|referral\s*source"),
]
YES_NO = [  # (answer key, question pattern)
    ("authorized_us", r"(legally\s*)?authori[sz]ed\s*to\s*work|eligible\s*to\s*work|right\s*to\s*work|work\s*authori[sz]ation"),
    ("needs_sponsorship", r"sponsor|visa\s*status|require\s*(a\s*)?visa"),
    ("willing_relocate", r"relocat"),
    ("over_18", r"18\s*years|at\s*least\s*18|of\s*legal\s*age"),
    ("worked_here_before", r"(previously|ever),?\s*(or\s*are\s*you\s*currently\s*)?(been\s*)?(work|employ)\w*\s*(for|at|by|with)|former\s*employee"),
    ("remote_ok", r"(able|willing)\s*to\s*work\s*(remote|on-?site|in\s*(the\s*)?office|hybrid)|commute"),
]
EEO = r"gender|race|ethnic|veteran|disabilit|hispanic|latin|pronoun|sexual\s*orientation|transgender|first-?generation"
DECLINE = r"decline|prefer\s*not|don'?t\s*wish|do\s*not\s*wish|not\s*to\s*(say|answer|disclose|identify)|choose\s*not"


def detect(url):
    u = (url or "").lower()
    if "greenhouse.io" in u or "gh_jid=" in u:
        return "greenhouse"
    if "jobs.lever.co" in u:
        return "lever"
    if "ashbyhq.com" in u:
        return "ashby"
    if "myworkdayjobs.com" in u:
        return "workday"
    if "smartrecruiters.com" in u:
        return "smartrecruiters"
    for site in ("linkedin", "indeed", "dice", "glassdoor", "ziprecruiter"):
        if site in u:
            return site
    return "other"


SUPPORTED = {"greenhouse", "lever", "ashby"}


def apply_url(url, kind):
    u = url.split("#")[0].rstrip("/")
    if kind == "lever" and not u.endswith("/apply"):
        return u + "/apply"
    if kind == "ashby" and not u.endswith("/application"):
        return u + "/application"
    return url


def _slugs(company):
    base = re.sub(r"\b(inc|llc|corp|corporation|ltd|co|the|technologies|labs)\b\.?", "", (company or "").lower())
    words = re.findall(r"[a-z0-9]+", base)
    return list(dict.fromkeys(["".join(words), "-".join(words), words[0] if words else ""]))


def find_direct(company, title):
    """Look for the same job on the company's own Greenhouse / Lever / Ashby board. Returns (url, kind) or (None, None)."""
    want = title.lower()

    def best(cands):
        scored = [(difflib.SequenceMatcher(None, want, t.lower()).ratio(), u) for t, u in cands]
        scored.sort(reverse=True)
        return scored[0][1] if scored and scored[0][0] >= 0.72 else None
    for slug in [s for s in _slugs(company) if s]:
        try:
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", headers=UA, timeout=15)
            if r.ok:
                u = best([(j["title"], j["absolute_url"]) for j in r.json().get("jobs", [])])
                if u:
                    return u, "greenhouse"
            r = requests.get(f"https://api.lever.co/v0/postings/{slug}", headers=UA, timeout=15, params={"mode": "json"})
            if r.ok and isinstance(r.json(), list):
                u = best([(j["text"], j["hostedUrl"]) for j in r.json()])
                if u:
                    return u, "lever"
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", headers=UA, timeout=15)
            if r.ok:
                u = best([(j["title"], j["jobUrl"]) for j in r.json().get("jobs", [])])
                if u:
                    return u, "ashby"
        except (requests.RequestException, ValueError, KeyError):
            continue
    return None, None


# ------------------------------------------------------------------ in-page helpers (run inside the form page)
DESCRIBE_JS = r"""(sel) => [...document.querySelectorAll(sel)].map((el, i) => {
  const lab = [];
  if (el.labels) for (const l of el.labels) lab.push(l.innerText);
  const by = el.getAttribute('aria-labelledby');
  if (by) by.split(' ').forEach(id => { const n = document.getElementById(id); if (n) lab.push(n.innerText); });
  if (el.getAttribute('aria-label')) lab.push(el.getAttribute('aria-label'));
  let q = '';
  const box = el.closest('fieldset, [role=group], .field, .application-question, .application-field, li, [class*=field], [class*=question]');
  if (box) { const lg = box.querySelector('legend, label, [class*=label], [class*=question-text], h3, h4'); if (lg) q = lg.innerText; }
  const opts = el.tagName === 'SELECT' ? [...el.options].map(o => o.text.trim()) : [];
  const own = el.closest('label') ? el.closest('label').innerText : '';
  return {i, tag: el.tagName.toLowerCase(), type: (el.type || '').toLowerCase(), name: el.name || '', id: el.id || '',
          label: (lab.join(' ') || el.placeholder || '').trim().slice(0, 300), question: q.trim().slice(0, 300),
          own: own.trim().slice(0, 120), value: el.type === 'file' ? '' : (el.value || ''),
          checked: !!el.checked, required: el.required || el.getAttribute('aria-required') === 'true', options: opts,
          role: el.getAttribute('role') || '', visible: !!(el.offsetWidth || el.offsetHeight || el.type === 'file')};
})"""

BANNER_JS = r"""([filled, missing]) => {
  const b = document.createElement('div');
  b.id = 'careerpilot-banner';
  b.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;background:#1F2937;color:#fff;font:14px/1.4 Segoe UI,Arial,sans-serif;padding:10px 16px;box-shadow:0 2px 8px rgba(0,0,0,.3)';
  b.innerHTML = '<b style="color:#FFC700">CareerPilot AI</b> filled ' + filled + ' fields and attached your files. ' +
    (missing ? '<b style="color:#FCA5A5">' + missing + ' required question(s) need you</b> (outlined in yellow). ' : '') +
    'Review every answer, then click <b>Submit</b> yourself. <a href="#" style="color:#93C5FD;margin-left:8px" onclick="this.parentNode.remove();return false">Hide</a>';
  document.body.appendChild(b);
}"""


def _yes(v):
    return str(v).strip().lower() in ("yes", "true", "1", "y")


class Assistant:
    """One Edge window per application; the thread stays alive until the person closes the window."""

    def __init__(self, browser_dir, log):
        self.browser_dir = browser_dir
        self.log = log

    def open_and_fill(self, url, answers, resume_path, cover_path=None, cover_text=""):
        kind = detect(url)
        done = threading.Event()
        result = {}

        def run():
            from playwright.sync_api import sync_playwright
            try:
                with sync_playwright() as pw:
                    ctx = pw.chromium.launch_persistent_context(self.browser_dir, channel="msedge", headless=False,
                                                                no_viewport=True, args=["--start-maximized"])
                    page = ctx.pages[0] if ctx.pages else ctx.new_page()
                    page.goto(apply_url(url, kind), wait_until="domcontentloaded", timeout=60000)
                    try:
                        page.wait_for_selector(CONTROLS, timeout=20000)
                    except Exception:  # noqa: BLE001
                        pass
                    if kind == "greenhouse":  # some boards show the form behind an "Apply" button
                        for txt in ("Apply for this job", "Apply"):
                            btn = page.get_by_role("button", name=re.compile(txt, re.I))
                            if btn.count() and btn.first.is_visible():
                                btn.first.click()
                                page.wait_for_timeout(1200)
                                break
                    result.update(self._fill(page, answers, resume_path, cover_path, cover_text))
                    page.evaluate(BANNER_JS, [result["filled"], len(result["missing"])])
                    done.set()
                    page.wait_for_event("close", timeout=0)  # keep the window until the person closes it
                    ctx.close()
            except Exception as e:  # noqa: BLE001
                result.setdefault("error", str(e)[:300])
                done.set()
        threading.Thread(target=run, daemon=True).start()
        done.wait(120)
        return result or {"error": "The application page took too long to open."}

    # ------------------------------------------------------------------ filling
    def _fill(self, page, a, resume_path, cover_path, cover_text):
        fields = page.evaluate(DESCRIBE_JS, CONTROLS)
        loc = page.locator(CONTROLS)
        filled, missing, seen_radio, handled_q = 0, [], set(), set()
        has_split_name = any(re.search(TEXT_FIELDS[0][1], f["label"] + " " + f["name"], re.I) for f in fields)
        for f in fields:
            text = f"{f['label']} {f['question']} {f['name']} {f['id']}".strip()
            el = loc.nth(f["i"])
            try:
                if f["type"] == "file":
                    want_cover = re.search(r"cover", text, re.I)
                    path = cover_path if want_cover else resume_path
                    if path and os.path.exists(path):
                        el.set_input_files(path)
                        filled += 1
                    continue
                if f["type"] in ("radio", "checkbox"):
                    group = f["name"] or f["question"]
                    if group in seen_radio:
                        continue
                    if self._choose_option_group(page, loc, fields, f, a):
                        seen_radio.add(group)
                        filled += 1
                    continue
                if f["tag"] == "select" or f["role"] == "combobox":
                    handled_q.add(f["question"])
                    if self._choose(el, f, text, a):
                        filled += 1
                    elif f["required"]:
                        missing.append(f["label"] or f["question"])
                    continue
                if not f["visible"] or f["value"]:
                    continue
                if (f["question"] and f["question"] in handled_q) or not (f["label"] or f["question"] or f["name"]):
                    continue  # helper box inside a dropdown we already handled, or an unlabeled input
                val = self._text_answer(text, f, a, has_split_name, cover_text)
                if val:
                    el.fill(str(val))
                    filled += 1
                elif f["required"]:
                    missing.append(f["label"] or f["question"] or f["name"])
                    el.evaluate("e => e.style.outline = '3px solid #FFC700'")
            except Exception:  # noqa: BLE001 - one odd field shouldn't stop the rest
                if f["required"]:
                    missing.append(f["label"] or f["name"])
        return {"filled": filled, "missing": [m for m in missing if m][:15]}

    @staticmethod
    def _text_answer(text, f, a, has_split_name, cover_text):
        if re.search(r"cover\s*letter", text, re.I) and f["tag"] == "textarea":
            return cover_text
        for key, pat in TEXT_FIELDS:
            if key == "full_name" and has_split_name:
                continue
            typed = (key == "email" and f["type"] == "email") or (key == "phone" and f["type"] == "tel")
            if re.search(pat, f["label"] or f["question"] or f["name"], re.I) or typed:
                if key == "full_name":
                    return f"{a.get('first_name', '')} {a.get('last_name', '')}".strip()
                return a.get(key, "")
        if f["type"] == "email":
            return a.get("email", "")
        if f["type"] == "tel":
            return a.get("phone", "")
        return ""

    @staticmethod
    def _wanted_option(text, a):
        """What to pick for a yes/no or EEO style question, as a regex over option text (None = unknown)."""
        if re.search(EEO, text, re.I):
            return DECLINE
        for key, pat in YES_NO:
            if re.search(pat, text, re.I):
                v = a.get(key)
                if v in (None, ""):
                    return None
                return r"^\s*yes\b" if _yes(v) else r"^\s*no\b"
        if re.search(r"how\s*did\s*you\s*(hear|find)", text, re.I):
            return r"company\s*(website|careers?)|career\s*(site|page)|website|job\s*board|other"
        return None

    def _choose(self, el, f, text, a):
        want = self._wanted_option(text, a)
        if f["tag"] == "select":
            if not want:
                return False
            for opt in f["options"]:
                if re.search(want, opt, re.I):
                    el.select_option(label=opt)
                    return True
            return False
        # custom dropdown (combobox): type the answer and pick the first match
        if want:
            guess = {r"^\s*yes\b": "Yes", r"^\s*no\b": "No"}.get(want, "Decline" if want == DECLINE else "Company website")
        else:
            key = next((k for k, pat in TEXT_FIELDS if re.search(pat, text, re.I)), None)
            guess = a.get(key, "") if key else ""
        if not guess:
            return False
        el.click()
        el.fill(guess)
        el.page.wait_for_timeout(500)
        el.press("Enter")
        return True

    def _choose_option_group(self, page, loc, fields, f, a):
        group = [g for g in fields if (g["name"] and g["name"] == f["name"]) or (not f["name"] and g["question"] == f["question"])]
        text = f"{f['question']} {f['label'] if len(group) == 1 else ''}"
        want = self._wanted_option(text, a)
        if not want:
            return False
        for g in group:
            if re.search(want, g["own"] or g["label"], re.I):
                loc.nth(g["i"]).check()
                return True
        return False


def cover_letter_text(md):
    m = re.search(r"##\s*Cover letter\s*\n([\s\S]*?)(\n##\s|$)", md or "")
    return (m.group(1) if m else md or "").strip()


def cover_letter_pdf(text, path, name=""):
    from fpdf import FPDF
    pdf = FPDF(format="Letter")
    pdf.set_margins(22, 22, 22)
    pdf.add_page()
    font = "Helvetica"
    for cand in (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\calibri.ttf"):
        if os.path.exists(cand):
            pdf.add_font("Body", "", cand)
            font = "Body"
            break
    pdf.set_font(font, "", 11)
    clean = text if font == "Body" else text.encode("latin-1", "replace").decode("latin-1")
    pdf.multi_cell(pdf.w - 44, 6, clean)
    pdf.output(path)
