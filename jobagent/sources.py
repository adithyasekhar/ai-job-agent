"""Job sources. Each fetcher returns items in one shape:
{id, source, title, companyName, location, publishedAt, salary, contractType, experienceLevel, jobUrl, description}

- AI Dev Jobs (aidevboard.com): free, no key. AI/ML jobs with level and workplace filters.
- Remote OK (remoteok.com): free, no key. Remote jobs; their terms ask apps to credit and link back.
- LinkedIn via Apify (bebity/linkedin-jobs-scraper): needs an Apify token, paid per result.
"""
import html
import re
import time
import urllib.parse

import requests

UA = {"User-Agent": "AIJobAgent/1.0 (desktop job tracker)"}
US_HINT = re.compile(
    r"united states|\busa?\b|\bus-only|remote|anywhere|worldwide|americas|north america|"
    r",\s*(al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy|dc)\b|"
    r"new york|san francisco|seattle|boston|austin|chicago|los angeles|denver|atlanta|dallas|houston|bay area", re.I)
NON_US = re.compile(r"\b(uk|united kingdom|london|canada|toronto|india|bangalore|germany|berlin|europe|emea|apac|"
                    r"australia|singapore|france|paris|netherlands|spain|poland|brazil|mexico|philippines|japan|"
                    r"eu|eea|czech|brno|latam|ireland|dublin|israel|tel aviv|portugal|lisbon|argentina|colombia)\b", re.I)

LINKEDIN_TERMS = [
    "Workday AI", "AI Integration Engineer", "AI Automation Engineer", "AI Solutions Engineer", "AI Engineer",
    "Generative AI Engineer", "AI Specialist", "LLM Engineer", "Machine Learning Engineer", "MLOps Engineer",
    "Data Scientist", "Prompt Engineer", "Applied Scientist", "NLP Engineer", "Computer Vision Engineer",
    "AI Research Engineer",
]


def strip_html(s):
    s = re.sub(r"<(br|/p|/li|/div|/h\d)[^>]*>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t]+", " ", html.unescape(s)).strip()


def looks_us(location):
    loc = location or ""
    if not loc.strip():
        return True
    if NON_US.search(loc) and not re.search(r"united states|\busa?\b", loc, re.I):
        return False
    return bool(US_HINT.search(loc))


# ---------------------------------------------------------------- AI Dev Jobs
def fetch_aidevboard(window_secs, log, max_pages=6):
    # This board's listings trail by a few weeks, so always look back 30 days; seen jobs are skipped later.
    days = max(30, min(90, -(-window_secs // 86400)))
    items = []
    for level in ("junior", "mid"):
        for page in range(1, max_pages + 1):
            r = requests.get("https://aidevboard.com/api/v1/jobs", headers=UA, timeout=30, params={
                "level": level, "posted_within_days": days, "limit": 50, "page": page})
            r.raise_for_status()
            d = r.json()
            for j in d.get("jobs") or []:
                if not looks_us(j.get("location")):
                    continue
                sal = ""
                if j.get("salary_min") or j.get("salary_max"):
                    sal = f"${(j.get('salary_min') or 0):,.0f} - ${(j.get('salary_max') or 0):,.0f}/yr".replace("$0 - ", "up to ")
                work = {"remote": "Work type: Remote", "hybrid": "Work type: hybrid", "onsite": "Work type: on-site"}.get(
                    j.get("workplace") or "", "")
                items.append({
                    "id": "aidev-" + str(j["id"]), "source": "AI Dev Jobs", "title": j.get("title") or "",
                    "companyName": j.get("company_name") or "", "location": j.get("location") or "",
                    "publishedAt": (j.get("created_at") or j.get("published_at") or "")[:10],
                    "salary": sal, "contractType": (j.get("job_type") or "").title(),
                    "experienceLevel": {"junior": "Entry level", "mid": "Mid level"}.get(level, level),
                    "jobUrl": j.get("apply_url") or j.get("url") or "",
                    "description": (work + "\n" if work else "") + strip_html(j.get("description") or ""),
                })
            if not d.get("has_next"):
                break
            time.sleep(0.5)
    log(f"AI Dev Jobs: {len(items)} US jobs (last {days} day{'s' if days > 1 else ''})")
    return items


# ---------------------------------------------------------------- Remote OK
def fetch_remoteok(window_secs, log):
    r = requests.get("https://remoteok.com/api", headers=UA, timeout=30)
    r.raise_for_status()
    rows = [x for x in r.json() if isinstance(x, dict) and x.get("id")]
    cutoff = time.time() - max(window_secs, 3600)
    items = []
    for j in rows:
        if (j.get("epoch") or 0) < cutoff or not looks_us(j.get("location")):
            continue
        sal = ""
        if j.get("salary_min"):
            sal = f"${j['salary_min']:,.0f} - ${j.get('salary_max') or j['salary_min']:,.0f}/yr"
        items.append({
            "id": "remoteok-" + str(j["id"]), "source": "Remote OK", "title": j.get("position") or "",
            "companyName": j.get("company") or "", "location": j.get("location") or "Remote",
            "publishedAt": (j.get("date") or "")[:10], "salary": sal, "contractType": "",
            "experienceLevel": "", "jobUrl": j.get("url") or f"https://remoteok.com/remote-jobs/{j['id']}",
            "description": "Work type: Remote\n" + strip_html(j.get("description") or "") +
                           "\nTags: " + ", ".join(j.get("tags") or []),
        })
    log(f"Remote OK: {len(items)} new US/worldwide remote jobs")
    return items


# ---------------------------------------------------------------- LinkedIn via Apify
APIFY = "https://api.apify.com/v2"
ACTOR = "bebity~linkedin-jobs-scraper"


def fetch_linkedin(token, window_secs, cap_usd, log, stop):
    h = {"Authorization": f"Bearer {token}", **UA}
    secs = max(1800, min(window_secs, 7 * 86400))
    urls = [{"url": "https://www.linkedin.com/jobs/search/?" + urllib.parse.urlencode({
        "keywords": t, "location": "United States", "geoId": "103644278", "f_TPR": f"r{secs}", "f_E": "1,2,3,4"})}
        for t in LINKEDIN_TERMS]
    body = {"startUrls": urls, "maxRowsPerUrl": 25, "companyProfile": False, "enrichCompany": False}
    r = requests.post(f"{APIFY}/acts/{ACTOR}/runs", headers=h, json=body, timeout=60,
                      params={"maxTotalChargeUsd": cap_usd, "timeout": 600})
    if r.status_code == 401:
        raise RuntimeError("Apify token was rejected. Check it in Settings.")
    r.raise_for_status()
    run = r.json()["data"]
    log(f"LinkedIn: scraping the last {secs // 60} minutes (cap ${cap_usd:.2f})…")
    while run["status"] in ("READY", "RUNNING"):
        if stop():
            requests.post(f"{APIFY}/actor-runs/{run['id']}/abort", headers=h, timeout=30)
            raise RuntimeError("Stopped")
        r = requests.get(f"{APIFY}/actor-runs/{run['id']}", headers=h, params={"waitForFinish": 50}, timeout=80)
        r.raise_for_status()
        run = r.json()["data"]
    if run["status"] != "SUCCEEDED":
        raise RuntimeError(f"LinkedIn scrape ended with status {run['status']}")
    r = requests.get(f"{APIFY}/datasets/{run['defaultDatasetId']}/items", headers=h, timeout=120, params={
        "clean": "true", "format": "json",
        "fields": "id,title,companyName,location,publishedAt,contractType,experienceLevel,salary,jobUrl,description,posterFullName,posterProfileUrl"})
    r.raise_for_status()
    items = r.json()
    for j in items:
        j["id"] = str(j.get("id"))
        j["source"] = "LinkedIn"
    cost = run.get("usageTotalUsd")
    log(f"LinkedIn: {len(items)} jobs" + (f" (${cost:.2f})" if cost else ""))
    return items, cost


# ---------------------------------------------------------------- company career boards (free, official APIs)
DEFAULT_BOARDS = (
    "greenhouse:anthropic greenhouse:databricks greenhouse:scaleai greenhouse:samsara greenhouse:figma "
    "greenhouse:stripe greenhouse:airbnb greenhouse:pinterest greenhouse:robinhood greenhouse:instacart "
    "greenhouse:gitlab greenhouse:datadog greenhouse:mongodb greenhouse:elastic greenhouse:okta greenhouse:twilio "
    "greenhouse:cloudflare greenhouse:asana greenhouse:brex greenhouse:affirm greenhouse:lyft greenhouse:reddit "
    "greenhouse:discord greenhouse:duolingo greenhouse:waymo greenhouse:nuro greenhouse:gleanwork greenhouse:gusto "
    "greenhouse:lattice greenhouse:airtable greenhouse:dropbox greenhouse:coreweave greenhouse:vercel greenhouse:checkr "
    "greenhouse:carta greenhouse:flexport greenhouse:toast greenhouse:zscaler greenhouse:togetherai greenhouse:dataiku "
    "greenhouse:c3iot greenhouse:workato lever:palantir lever:zoox lever:shieldai lever:outreach ashby:openai "
    "ashby:notion ashby:ramp ashby:perplexity ashby:cohere ashby:harvey ashby:sierra ashby:elevenlabs ashby:linear "
    "ashby:replit ashby:cursor ashby:mercor ashby:decagon ashby:writer ashby:modal ashby:baseten ashby:pinecone "
    "ashby:lambda ashby:hex"
).split()


def _iso_ts(s):
    import datetime as _dt
    try:
        return _dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0


def _board_jobs(kind, token, cutoff, wanted):
    """Fetch one company board; return items for wanted titles updated since cutoff."""
    out = []
    if kind == "greenhouse":
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs", headers=UA, timeout=30)
        r.raise_for_status()
        meta = r.json().get("meta") or {}
        for j in r.json().get("jobs", []):
            loc = (j.get("location") or {}).get("name", "")
            if _iso_ts(j.get("updated_at")) < cutoff or not wanted(j.get("title", "")) or not looks_us(loc):
                continue
            d = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{j['id']}", headers=UA, timeout=30)
            content = strip_html(html.unescape(d.json().get("content", ""))) if d.ok else ""
            company = (d.json().get("company_name") if d.ok else "") or meta.get("name") or token.title()
            out.append({"id": f"gh-{token}-{j['id']}", "source": "Company boards", "title": j.get("title", ""),
                        "companyName": company, "location": loc,
                        "publishedAt": (j.get("first_published") or j.get("updated_at") or "")[:10], "salary": "",
                        "contractType": "", "experienceLevel": "", "jobUrl": j.get("absolute_url", ""),
                        "description": content})
    elif kind == "lever":
        r = requests.get(f"https://api.lever.co/v0/postings/{token}", headers=UA, timeout=30,
                         params={"mode": "json", "limit": 1000})
        r.raise_for_status()
        for j in r.json():
            cat = j.get("categories") or {}
            loc = cat.get("location", "") or ", ".join(cat.get("allLocations") or [])
            if (j.get("createdAt") or 0) / 1000 < cutoff or not wanted(j.get("text", "")) or not looks_us(loc):
                continue
            work = {"remote": "Work type: Remote", "hybrid": "Work type: hybrid", "on-site": "Work type: on-site"}.get(
                j.get("workplaceType") or "", "")
            sal = j.get("salaryRange") or {}
            out.append({"id": f"lever-{token}-{j['id']}", "source": "Company boards", "title": j.get("text", ""),
                        "companyName": token.title(), "location": loc,
                        "publishedAt": __import__("datetime").datetime.fromtimestamp((j.get("createdAt") or 0) / 1000).strftime("%Y-%m-%d"),
                        "salary": f"${sal.get('min', 0):,.0f} - ${sal.get('max', 0):,.0f}" if sal.get("min") else "",
                        "contractType": cat.get("commitment", ""), "experienceLevel": "",
                        "jobUrl": j.get("hostedUrl", ""),
                        "description": (work + "\n" if work else "") + (j.get("descriptionPlain") or "") + "\n" +
                                       "\n".join(strip_html(x.get("content", "")) for x in j.get("lists") or [])})
    else:  # ashby
        r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{token}", headers=UA, timeout=30,
                         params={"includeCompensation": "true"})
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            loc = j.get("location", "")
            if j.get("isRemote") and "remote" not in loc.lower():
                loc = (loc + " (Remote)").strip()
            if _iso_ts(j.get("publishedAt")) < cutoff or not wanted(j.get("title", "")) or not looks_us(loc):
                continue
            work = {"Remote": "Work type: Remote", "Hybrid": "Work type: hybrid", "OnSite": "Work type: on-site"}.get(
                j.get("workplaceType") or "", "")
            comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
            out.append({"id": f"ashby-{token}-{j.get('id')}", "source": "Company boards", "title": j.get("title", ""),
                        "companyName": token.title(), "location": loc, "publishedAt": (j.get("publishedAt") or "")[:10],
                        "salary": comp, "contractType": j.get("employmentType", ""), "experienceLevel": "",
                        "jobUrl": j.get("jobUrl", ""),
                        "description": (work + "\n" if work else "") + (j.get("descriptionPlain") or "")})
    return out


def fetch_boards(boards, window_secs, log, wanted):
    import concurrent.futures as cf
    cutoff = time.time() - max(window_secs, 3600)
    items, failed = [], []

    def one(b):
        kind, _, token = b.partition(":")
        try:
            return _board_jobs(kind.strip().lower(), token.strip(), cutoff, wanted)
        except Exception:  # noqa: BLE001 - a missing or renamed board shouldn't stop the others
            failed.append(b)
            return []
    with cf.ThreadPoolExecutor(8) as ex:
        for res in ex.map(one, [b for b in boards if ":" in b]):
            items += res
    log(f"Company boards: {len(items)} matching jobs from {len(boards) - len(failed)} companies"
        + (f" ({len(failed)} boards unavailable)" if failed else ""))
    return items
