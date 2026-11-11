"""More job sources (v1.1). Same item shape as sources.py.

Free, no key: Hacker News "Who is hiring", Remotive, Himalayas, Workday career sites, SmartRecruiters, Workable.
Free key:     Adzuna, Jooble, JSearch (Google Jobs via RapidAPI).
"""
import concurrent.futures as cf
import datetime as dt
import re
import time

import requests

from . import rules
from .sources import UA, _iso_ts, looks_us, strip_html

def search_queries(n=7):
    """API search terms: the profile's target roles."""
    return rules.TARGET_ROLES[:n]


def _cutoff(window_secs):
    return time.time() - max(window_secs, 3600)


def _date(ts):
    try:
        return dt.datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return str(ts or "")[:10]


def _money(lo, hi):
    return f"${lo:,.0f} - ${(hi or lo):,.0f}" if lo else ""


def _relevant_role(text):
    return bool(rules.AI_TITLE.search(text) or rules.PROFILE_TITLE.search(text))


# ---------------------------------------------------------------- Hacker News "Who is hiring"
def fetch_hn(window_secs, log, wanted):
    r = requests.get("https://hn.algolia.com/api/v1/search_by_date", headers=UA, timeout=30,
                     params={"tags": "story,author_whoishiring", "query": "who is hiring", "hitsPerPage": 3})
    r.raise_for_status()
    stories = [s for s in r.json().get("hits", []) if "who is hiring" in s.get("title", "").lower()]
    cutoff, items = _cutoff(window_secs), []
    for s in stories[:1]:
        c = requests.get("https://hn.algolia.com/api/v1/search", headers=UA, timeout=60,
                         params={"tags": f"comment,story_{s['objectID']}", "hitsPerPage": 1000}).json()
        for h in c.get("hits", []):
            if str(h.get("parent_id")) != str(s["objectID"]) or (h.get("created_at_i") or 0) < cutoff:
                continue  # replies to posts aren't job posts
            # HN separates paragraphs with a bare <p>; the first paragraph is the "Company | Role | Place" header.
            text = strip_html((h.get("comment_text") or "").replace("<p>", "\n"))
            header = re.sub(r"https?://\S+|www\.\S+", "", text.split("\n", 1)[0])
            parts = [p.strip(" -–") for p in re.split(r"\s*\|\s*", header) if p.strip(" -–")]
            if len(parts) < 2:
                continue
            roles = [p for p in parts[1:] if len(p) <= 90 and wanted(p)]  # short segments that name a role
            if not roles:
                continue
            title = "; ".join(roles[:2])
            loc = next((p for p in parts[1:] if p not in roles and re.search(
                r"remote|onsite|on-site|hybrid|, ?[A-Z]{2}\b|NYC|SF\b|Bay Area|USA|\bUS\b", p, re.I)), "")
            if loc and not looks_us(loc):
                continue
            items.append({"id": f"hn-{h['objectID']}", "source": "Hacker News", "title": title[:120],
                          "companyName": re.sub(r"\(.*?\)", "", parts[0]).strip()[:60] or "See post",
                          "location": loc[:80] or "See post", "publishedAt": (h.get("created_at") or "")[:10],
                          "salary": "", "contractType": "", "experienceLevel": "",
                          "jobUrl": f"https://news.ycombinator.com/item?id={h['objectID']}", "description": text})
    log(f"Hacker News Who's Hiring: {len(items)} matching posts")
    return items


# ---------------------------------------------------------------- Remotive (credit + link back required)
def fetch_remotive(window_secs, log, wanted):
    cutoff, items, seen = _cutoff(window_secs), [], set()
    for q in ("ai", "machine learning", "llm", "data scientist"):
        r = requests.get("https://remotive.com/api/remote-jobs", headers=UA, timeout=30, params={"search": q, "limit": 100})
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            if (j["id"] in seen or _iso_ts(j.get("publication_date")) < cutoff or not wanted(j.get("title", ""))
                    or not looks_us(j.get("candidate_required_location"))):
                continue
            seen.add(j["id"])
            items.append({"id": f"remotive-{j['id']}", "source": "Remotive", "title": j.get("title", ""),
                          "companyName": j.get("company_name", ""),
                          "location": "Remote · " + (j.get("candidate_required_location") or "Anywhere"),
                          "publishedAt": (j.get("publication_date") or "")[:10], "salary": j.get("salary") or "",
                          "contractType": (j.get("job_type") or "").replace("_", " ").title(), "experienceLevel": "",
                          "jobUrl": j.get("url", ""), "description": "Work type: Remote\n" + strip_html(j.get("description", ""))})
    log(f"Remotive: {len(items)} remote jobs")
    return items


# ---------------------------------------------------------------- Himalayas (remote jobs, newest first)
def fetch_himalayas(window_secs, log, wanted, max_pages=15):
    cutoff, items = _cutoff(window_secs), []
    for page in range(max_pages):
        r = requests.get("https://himalayas.app/jobs/api", headers=UA, timeout=30, params={"limit": 20, "offset": page * 20})
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
        if not jobs:
            break
        for j in jobs:
            locs = ", ".join(j.get("locationRestrictions") or []) or "Anywhere"
            if (j.get("pubDate") or 0) < cutoff or not wanted(j.get("title", "")) or not looks_us(locs):
                continue
            items.append({"id": "himalayas-" + (j.get("guid") or j.get("applicationLink", "")).rstrip("/").rsplit("/", 1)[-1][:80],
                          "source": "Himalayas", "title": j.get("title", ""), "companyName": j.get("companyName", ""),
                          "location": "Remote · " + locs, "publishedAt": _date(j.get("pubDate")),
                          "salary": _money(j.get("minSalary"), j.get("maxSalary")),
                          "contractType": j.get("employmentType", ""), "experienceLevel": ", ".join(j.get("seniority") or []),
                          "jobUrl": j.get("applicationLink", ""), "description": "Work type: Remote\n" + strip_html(j.get("description", ""))})
        if min((j.get("pubDate") or 0) for j in jobs) < cutoff:
            break  # sorted newest first: later pages are older than the window
        time.sleep(0.3)
    log(f"Himalayas: {len(items)} matching remote jobs")
    return items


# ---------------------------------------------------------------- Workday career sites (big employers)
DEFAULT_WORKDAY = (
    "nvidia.wd5/NVIDIAExternalCareerSite salesforce.wd12/External_Career_Site adobe.wd5/external_experienced "
    "capitalone.wd12/Capital_One intel.wd1/External workday.wd5/Workday paypal.wd1/jobs "
    "mastercard.wd1/CorporateCareers target.wd5/targetcareers visa.wd5/Visa hpe.wd5/Jobsathpe "
    "cvshealth.wd1/CVS_Health_Careers humana.wd5/Humana_External_Career_Site fmr.wd1/FidelityCareers "
    "pfizer.wd1/PfizerCareers boeing.wd1/EXTERNAL_CAREERS att.wd1/ATTGeneral statestreet.wd1/Global 3m.wd1/Search "
    "nike.wd1/nke disney.wd5/disneycareer zoom.wd5/Zoom kla.wd1/Search micron.wd1/External broadcom.wd1/External_Career"
).split()
WORKDAY_NAMES = {"nvidia": "NVIDIA", "hpe": "Hewlett Packard Enterprise", "cvshealth": "CVS Health", "fmr": "Fidelity",
                 "att": "AT&T", "statestreet": "State Street", "3m": "3M", "kla": "KLA", "capitalone": "Capital One",
                 "paypal": "PayPal"}
WORKDAY_SEARCHES = ["AI", "machine learning", "data scientist", "generative AI", "LLM"]


def _posted_days(text):
    t = (text or "").lower()
    if "today" in t:
        return 0
    if "yesterday" in t:
        return 1
    m = re.search(r"(\d+)\+?\s*day", t)
    return int(m.group(1)) if m else 99


def _workday_site(spec, max_days, wanted):
    host, _, site = spec.partition("/")
    tenant = host.split(".")[0]
    base = f"https://{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"
    hdr = {**UA, "Content-Type": "application/json", "Accept": "application/json"}
    found = {}
    for q in WORKDAY_SEARCHES:
        for offset in (0, 20, 40):
            r = requests.post(base + "/jobs", headers=hdr, timeout=30,
                              json={"limit": 20, "offset": offset, "searchText": q, "appliedFacets": {}})
            if not r.ok:
                break
            posts = r.json().get("jobPostings") or []
            for p in posts:
                if _posted_days(p.get("postedOn")) <= max_days and wanted(p.get("title", "")):
                    found[p["externalPath"]] = p
            if len(posts) < 20:
                break
    items = []
    for path, p in list(found.items())[:40]:
        d = requests.get(base + path, headers=hdr, timeout=30)
        if not d.ok:
            continue
        jp = d.json().get("jobPostingInfo", {})
        locs = [jp.get("location", "")] + list(jp.get("additionalLocations") or [])
        country = (jp.get("country") or {}).get("descriptor", "")
        if country and "United States" not in country and not any(re.search(r"\bUS\b|United States", l) for l in locs):
            continue
        loc = "; ".join(l for l in locs if l)
        items.append({"id": f"wd-{tenant}-{jp.get('jobReqId') or path.rsplit('_', 1)[-1]}", "source": "Workday sites",
                      "title": jp.get("title") or p.get("title", ""),
                      "companyName": WORKDAY_NAMES.get(tenant, tenant.title()),
                      "location": loc[:120], "publishedAt": jp.get("startDate", ""), "salary": "",
                      "contractType": jp.get("timeType", ""), "experienceLevel": "", "jobUrl": jp.get("externalUrl", ""),
                      "description": ("Work type: Remote\n" if "remote" in loc.lower() else "") + strip_html(jp.get("jobDescription", ""))})
    return items


def fetch_workday(sites, window_secs, log, wanted):
    max_days = max(1, min(30, -(-window_secs // 86400)))
    items, failed = [], []

    def one(spec):
        try:
            return _workday_site(spec, max_days, wanted)
        except Exception:  # noqa: BLE001 - one site failing shouldn't stop the rest
            failed.append(spec)
            return []
    with cf.ThreadPoolExecutor(6) as ex:
        for res in ex.map(one, sites):
            items += res
    log(f"Workday career sites: {len(items)} matching jobs from {len(sites) - len(failed)} companies")
    return items


# ---------------------------------------------------------------- SmartRecruiters and Workable boards
DEFAULT_SMARTRECRUITERS = ["ServiceNow", "BoschGroup", "Experian", "Wix2", "LinkedIn3"]
DEFAULT_WORKABLE = ["huggingface"]


def fetch_smart_workable(window_secs, log, wanted, smart=None, workable=None):
    cutoff, items, ids = _cutoff(window_secs), [], set()
    for cid in smart or DEFAULT_SMARTRECRUITERS:
        try:
            for q in ("AI", "machine learning", "data scientist"):
                r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{cid}/postings", headers=UA, timeout=30,
                                 params={"q": q, "limit": 100, "country": "us"})
                if not r.ok:
                    break
                for p in r.json().get("content", []):
                    jid = f"sr-{cid}-{p['id']}"
                    if jid in ids or _iso_ts(p.get("releasedDate")) < cutoff or not wanted(p.get("name", "")):
                        continue
                    ids.add(jid)
                    loc = p.get("location") or {}
                    d = requests.get(f"https://api.smartrecruiters.com/v1/companies/{cid}/postings/{p['id']}", headers=UA, timeout=30)
                    sec = ((d.json().get("jobAd") or {}).get("sections") or {}) if d.ok else {}
                    desc = "\n".join(strip_html((sec.get(k) or {}).get("text", ""))
                                     for k in ("jobDescription", "qualifications", "additionalInformation"))
                    items.append({"id": jid, "source": "Company boards", "title": p.get("name", ""),
                                  "companyName": (p.get("company") or {}).get("name") or cid,
                                  "location": ", ".join(x for x in (loc.get("city"), loc.get("region")) if x)
                                              + (" (Remote)" if loc.get("remote") else ""),
                                  "publishedAt": (p.get("releasedDate") or "")[:10], "salary": "", "contractType": "",
                                  "experienceLevel": (p.get("experienceLevel") or {}).get("label", ""),
                                  "jobUrl": f"https://jobs.smartrecruiters.com/{cid}/{p['id']}",
                                  "description": ("Work type: Remote\n" if loc.get("remote") else "") + desc})
        except Exception:  # noqa: BLE001
            continue
    for acct in workable or DEFAULT_WORKABLE:
        try:
            w = requests.get(f"https://apply.workable.com/api/v1/widget/accounts/{acct}", headers=UA, timeout=30).json()
            for j in w.get("jobs", []):
                loc = ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
                if _iso_ts(j.get("published_on")) < cutoff or not wanted(j.get("title", "")):
                    continue
                if not (looks_us(loc) or (j.get("telecommuting") and "emea" not in j.get("title", "").lower())):
                    continue
                items.append({"id": f"workable-{acct}-{j['shortcode']}", "source": "Company boards", "title": j["title"],
                              "companyName": w.get("name") or acct.title(),
                              "location": loc + (" (Remote)" if j.get("telecommuting") else ""),
                              "publishedAt": j.get("published_on", ""), "salary": "", "contractType": j.get("employment_type", ""),
                              "experienceLevel": j.get("experience", ""), "jobUrl": j.get("url", ""),
                              "description": f"{j.get('department', '')} · {j.get('function', '')}"})
        except Exception:  # noqa: BLE001
            continue
    log(f"SmartRecruiters/Workable boards: {len(items)} matching jobs")
    return items


# ---------------------------------------------------------------- free-key job APIs
def fetch_adzuna(app_id, app_key, window_secs, log):
    days = max(1, min(30, -(-window_secs // 86400)))
    items = []
    for q in search_queries():
        r = requests.get("https://api.adzuna.com/v1/api/jobs/us/search/1", headers=UA, timeout=30, params={
            "app_id": app_id, "app_key": app_key, "what": q, "max_days_old": days, "results_per_page": 50,
            "content-type": "application/json"})
        if r.status_code in (401, 403):
            raise RuntimeError("Adzuna rejected the app ID or key. Check them in Settings.")
        r.raise_for_status()
        for j in r.json().get("results", []):
            items.append({"id": f"adzuna-{j['id']}", "source": "Adzuna", "title": strip_html(j.get("title", "")),
                          "companyName": (j.get("company") or {}).get("display_name", ""),
                          "location": (j.get("location") or {}).get("display_name", ""),
                          "publishedAt": (j.get("created") or "")[:10], "salary": _money(j.get("salary_min"), j.get("salary_max")),
                          "contractType": (j.get("contract_time") or "").replace("_", " ").title(), "experienceLevel": "",
                          "jobUrl": j.get("redirect_url", ""), "description": strip_html(j.get("description", ""))})
        time.sleep(0.5)
    log(f"Adzuna: {len(items)} jobs")
    return items


def fetch_jooble(key, window_secs, log):
    cutoff, items = _cutoff(max(window_secs, 86400)), []
    for q in search_queries():
        r = requests.post(f"https://jooble.org/api/{key}", headers={**UA, "Content-Type": "application/json"}, timeout=30,
                          json={"keywords": q, "location": "United States", "page": 1})
        if r.status_code in (401, 403):
            raise RuntimeError("Jooble rejected the key. Check it in Settings.")
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            upd = _iso_ts((j.get("updated") or "")[:19])
            if upd and upd < cutoff:
                continue
            items.append({"id": f"jooble-{j.get('id')}", "source": "Jooble", "title": strip_html(j.get("title", "")),
                          "companyName": j.get("company", ""), "location": j.get("location", ""),
                          "publishedAt": (j.get("updated") or "")[:10], "salary": j.get("salary", ""),
                          "contractType": j.get("type", ""), "experienceLevel": "", "jobUrl": j.get("link", ""),
                          "description": strip_html(j.get("snippet", ""))})
        time.sleep(0.5)
    log(f"Jooble: {len(items)} jobs")
    return items


def fetch_jsearch(key, window_secs, log, queries=5):
    """Google Jobs (which includes LinkedIn and Indeed postings) via JSearch on RapidAPI.
    The free plan is about 200 requests a month, so the runner calls this once a day with 5 queries."""
    span = "today" if window_secs <= 86400 else "3days" if window_secs <= 3 * 86400 else "week"
    items = []
    for q in search_queries(queries):
        r = requests.get("https://jsearch.p.rapidapi.com/search", timeout=40,
                         params={"query": f"{q} in USA", "page": 1, "num_pages": 1, "date_posted": span, "country": "us"},
                         headers={**UA, "X-RapidAPI-Key": key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"})
        if r.status_code in (401, 403):
            raise RuntimeError("JSearch rejected the key, or you haven't subscribed to its free plan on RapidAPI.")
        if r.status_code == 429:
            raise RuntimeError("JSearch free monthly limit reached.")
        r.raise_for_status()
        for j in r.json().get("data", []):
            loc = ", ".join(x for x in (j.get("job_city"), j.get("job_state")) if x) or j.get("job_country", "")
            items.append({"id": f"jsearch-{j.get('job_id')}", "source": f"JSearch · {j.get('job_publisher') or 'Google Jobs'}",
                          "title": j.get("job_title", ""), "companyName": j.get("employer_name", ""),
                          "location": loc + (" (Remote)" if j.get("job_is_remote") else ""),
                          "publishedAt": (j.get("job_posted_at_datetime_utc") or "")[:10],
                          "salary": _money(j.get("job_min_salary"), j.get("job_max_salary")),
                          "contractType": (j.get("job_employment_type") or "").title(), "experienceLevel": "",
                          "jobUrl": j.get("job_apply_link") or j.get("job_google_link", ""),
                          "description": ("Work type: Remote\n" if j.get("job_is_remote") else "") + (j.get("job_description") or "")})
    log(f"JSearch: {len(items)} jobs")
    return items
