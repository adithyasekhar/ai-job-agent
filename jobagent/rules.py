"""Keyword rules shared by the job agent scripts.

These give quick first-pass labels. During each run Claude reads the job text and makes the
final call, so these only need to be good hints.
"""
import re

AI_TITLE = re.compile(
    r"\b(ai|a\.i\.|artificial intelligence|machine learning|ml|mlops|llm|genai|gen ai|generative|"
    r"nlp|natural language|computer vision|deep learning|data scien\w*|applied scien\w*|"
    r"research scien\w*|prompt engineer\w*|agentic|ai agents?|agent (?:engineer|developer|builder)|neural|perception|ai/ml|ml/ai|copilot)\b", re.I)
AI_DESC = re.compile(
    r"\b(machine learning|deep learning|llms?|large language models?|generative ai|pytorch|tensorflow|"
    r"computer vision|nlp|natural language processing|neural networks?|rag|transformers?|agentic)\b", re.I)
# Mid-level is wanted, so "II" stays in. Clearly senior titles are dropped.
SENIOR = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|manager|director|head of|vp|vice president|"
    r"architect|distinguished|pmts|lmts|smts|principal member|iii|iv|level 3|l5|l6|l7)\b", re.I)

NO_SPONSOR = [
    r"(unable|not able|cannot|can ?not|will not|won'?t|do(es)? not|don'?t|are not able to|is not able to|not in a position to)\s+(to\s+)?(currently\s+)?(offer|provide|support|sponsor|consider)[^.\n]{0,60}sponsor",
    r"(unable|not able|cannot|will not|won'?t|do(es)? not|don'?t)\s+(to\s+)?sponsor",
    r"no\s+(visa\s+)?sponsorship",
    r"sponsorship\s+(is\s+|will\s+)?not\s+(be\s+)?(available|offered|provided|possible|supported|considered)",
    r"not\s+eligible\s+for[^.\n]{0,30}sponsorship",
    r"without\s+(the\s+)?(need\s+for\s+|requiring\s+|requirement\s+(of|for)\s+)?(current\s+or\s+future\s+|now\s+or\s+in\s+the\s+future\s+)?(employer\s+|visa\s+|company\s+)?sponsorship",
    r"without\s+(the\s+)?need\s+for[^.\n]{0,60}(sponsor|immigration|work authorization)",
    r"(must|required to)\s+be\s+(a\s+)?(u\.?s\.?|united states)\s+citizen",
    r"u\.?s\.?\s+citizenship\s+(is\s+)?required",
    r"(active|current|ability to obtain)[^.\n]{0,40}(secret|ts/sci|security)\s+clearance",
    r"(security\s+clearance|secret\s+clearance|ts/sci)\s+(is\s+)?required",
    r"not\s+(open|available)\s+to[^.\n]{0,40}(visa|sponsorship|h-?1b|opt|cpt)",
    r"(h-?1b|opt|cpt|f-?1)[^.\n]{0,40}(not\s+(be\s+)?(accepted|considered|eligible)|ineligible)",
    r"will\s+not\s+pursue[^.\n]{0,30}sponsorship",
    r"not\s+sponsoring",
    r"no\s+visa\s*/?\s*(transfer\s+)?sponsorship",
    r"does\s+not\s+participate\s+in\s+the\s+h-?1b",
    r"unable\s+to\s+(sponsor|provide|offer)",
]
LIMITED_SPONSOR = [
    r"(limited|may\s+(be\s+)?(provide|offer|available)|case[- ]by[- ]case)[^.\n]{0,50}sponsorship",
    r"sponsorship[^.\n]{0,30}(may\s+be|case[- ]by[- ]case|limited)",
    r"supports\s+visa\s+sponsorship",
    r"authorization:[^\n]{0,40}(h-?1b|opt|cpt)",
    r"h-?1b\s+transfers?\s+(supported|accepted|welcome)",
]
YES_SPONSOR = [
    r"(visa|h-?1b|immigration)\s+sponsorship\s+(is\s+)?(available|offered|provided|possible)",
    r"sponsorship\s+(is\s+)?available",
    r"(we|will|can|able to|happy to|open to|willing to)\s+(also\s+)?(provide\s+|offer\s+)?sponsor",
    r"(offer|offers|provide|provides)\s+(visa|h-?1b|immigration)\s+sponsorship",
    r"(stem\s+)?\bopt\b(?![- ]?out)\s*/?\s*(cpt\s+)?(candidates\s+)?(are\s+)?(welcome|eligible|accepted)",
    r"sponsorship\s+(can\s+be\s+)?(considered|provided|offered)",
    r"h-?1b\s+sponsorship\s+provided",
]
NO_RE = [re.compile(p, re.I) for p in NO_SPONSOR]
LIM_RE = [re.compile(p, re.I) for p in LIMITED_SPONSOR]
YES_RE = [re.compile(p, re.I) for p in YES_SPONSOR]

REMOTE_STRONG = re.compile(
    r"(fully\s+remote|100%\s+remote|remote[- ]first|remote\s*\(us|remote\s*-\s*us|remote\s+(within|in|across)\s+(the\s+)?(u\.?s|united states)|"
    r"(this|the)\s+(is\s+a\s+)?(role|position|job)\s+(is\s+)?(fully\s+)?remote|work\s+from\s+home|remote\s+eligible|"
    r"open\s+to\s+remote|work\s+remotely|location:\s*remote|work\s+type:\s*remote|remote\s+position|remote\s+role|remote\s+opportunity)", re.I)
HYBRID = re.compile(r"\bhybrid\b|\d\s*days?\s*(per|a|/)\s*week\s*(in|on)[- ]?(the\s+)?(office|site)", re.I)
ONSITE = re.compile(r"\b(on[- ]?site|in[- ]office|in[- ]person)\b", re.I)

# Companies that file many H-1B petitions each year (public LCA/USCIS data). A hint only:
# a posting that says "no sponsorship" wins.
PAST_H1B_FILERS = {
    "adobe", "american express", "amazon", "amazon web services (aws)", "apple", "asml", "capgemini",
    "capital one", "cisco", "cognizant", "deloitte", "ey", "google", "goldman sachs", "hcltech", "hp",
    "ibm", "infosys", "intel", "jpmorganchase", "jpmorgan chase & co.", "kpmg", "kpmg us", "lenovo",
    "mastercard", "meta", "microsoft", "nvidia", "openai", "optum", "oracle", "pwc", "qualcomm",
    "reddit, inc.", "salesforce", "samsung electronics america", "sap", "siemens", "tata consultancy services",
    "tiktok", "ust", "target", "thomson reuters", "the d. e. shaw group", "zoox", "etsy", "samsara", "scale",
    "htc global services", "uipath", "moody's corporation", "kensho technologies", "upstart", "trimble inc.",
    "walmart", "wipro", "tech mahindra", "ltimindtree", "accenture", "workday", "servicenow", "visa",
}


def snippet(text, m, width=110):
    s = max(0, m.start() - width // 2)
    e = min(len(text), m.end() + width // 2)
    return re.sub(r"\s+", " ", text[s:e]).strip()


def sponsorship(desc):
    """Return (label, evidence). An explicit 'no' wins over everything else."""
    for group, label in ((NO_RE, "No"), (LIM_RE, "Maybe"), (YES_RE, "Yes")):
        for r in group:
            m = r.search(desc)
            if m:
                return label, snippet(desc, m)
    m = re.search(r"visa\s+sponsor|sponsorship|h-?1b|work\s+visa|\bopt\b(?![- ]?out)|\bcpt\b", desc, re.I)
    if m:
        return "Check posting", snippet(desc, m)
    return "Not mentioned", ""


def work_setup(title, location, desc):
    d = re.sub(r"not\s+working\s+100%\s+remote", "", desc, flags=re.I)
    if re.search(r"\bremote\b", f"{title} {location}", re.I) or REMOTE_STRONG.search(d):
        return "Remote"
    if re.search(r"\bhybrid\b", f"{title} {location}", re.I) or HYBRID.search(d):
        return "Hybrid"
    if ONSITE.search(d):
        return "On-site"
    if re.search(r"\bremote\b", d, re.I):
        return "Possibly remote"
    return "Not stated"


def is_ai(title, desc):
    return bool(AI_TITLE.search(title)) or len(AI_DESC.findall(desc)) >= 3


def is_senior(title):
    return bool(SENIOR.search(title))


def known_filer(company):
    return (company or "").strip().lower() in PAST_H1B_FILERS


KEEP_LINE = re.compile(
    r"sponsor|visa|h-?1b|citizen|clearance|authoriz|remote|hybrid|on-?site|in[- ]office|relocat|"
    r"years|experience|degree|bachelor|master|ph\.?d|qualif|require|must|python|sql|java|pytorch|tensorflow|"
    r"hr tech|integration|api|salary|compensation|\$|pay range|llm|machine learning|genai|cloud|aws|azure", re.I)


def trim_description(desc, limit=2600):
    """Keep the opening plus the lines that matter for fit, sponsorship and remote status."""
    desc = desc or ""
    head = desc[:700]
    rest = [ln.strip() for ln in re.split(r"[\n\r]+|(?<=[.!?])\s+", desc[700:]) if ln.strip()]
    keep = [ln for ln in rest if KEEP_LINE.search(ln)]
    out = head + ("\n...\n" + "\n".join(keep) if keep else "")
    return out[:limit]


DEFAULT_TARGET_ROLES = ["AI Engineer", "Machine Learning Engineer", "Generative AI Engineer", "LLM Engineer",
                        "Applied Scientist", "Data Scientist", "MLOps Engineer", "AI Research Engineer", "NLP Engineer",
                        "Computer Vision Engineer", "AI Solutions Engineer", "Prompt Engineer"]
TARGET_ROLES = list(DEFAULT_TARGET_ROLES)
# Extra title words a profile wants kept even without AI keywords (e.g. "data engineer, analytics engineer").
# Empty by default: CareerPilot targets AI engineering roles.
PROFILE_TITLE = re.compile(r"(?!x)x")  # matches nothing until configure() sets it


def configure(target_roles=None, extra_titles=None):
    """Apply a profile's targets: search terms come from target_roles, and extra_titles widen the title filter."""
    global PROFILE_TITLE
    TARGET_ROLES[:] = [r.strip() for r in (target_roles or DEFAULT_TARGET_ROLES) if r.strip()]
    words = [w.strip() for w in (extra_titles or []) if w.strip()]
    words += [r for r in TARGET_ROLES if not AI_TITLE.search(r)]  # non-AI target roles count as relevant too
    PROFILE_TITLE = (re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.I)
                     if words else re.compile(r"(?!x)x"))


def is_relevant(title, desc):
    return is_ai(title, desc) or bool(PROFILE_TITLE.search(title))


def wanted_title(title):
    """Quick title-only check used before fetching full postings."""
    return (bool(AI_TITLE.search(title)) or bool(PROFILE_TITLE.search(title))) and not is_senior(title)


# ---------------------------------------------------------------- H-1B records (USCIS Employer Data Hub)
_H1B_SUFFIX = re.compile(
    r"\b(incorporated|inc|llc|l l c|llp|corp|corporation|co|company|ltd|limited|lp|plc|pc|pllc|pbc|na|n a|the|"
    r"usa|us|u s|america|north america|holdings?|group|technologies|technology|tech|services|service|svcs|svc|"
    r"solutions|systems|software|labs?|global|international|intl)\b")
_h1b_cache = {}


def _h1b_norm(name):
    n = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower().replace("&", " and "))
    return re.sub(r"\s+", " ", _H1B_SUFFIX.sub(" ", n)).strip()


def _h1b_data():
    if not _h1b_cache:
        import json
        import os
        import sys
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(base, "assets", "h1b_employers.json"), encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {"employers": {}, "years": []}
        idx = {}
        for k in d["employers"]:
            idx.setdefault(k.split(" ", 1)[0], []).append(k)
        _h1b_cache.update(data=d["employers"], idx=idx, years=d.get("years", []))
    return _h1b_cache


def h1b_record(company):
    """Approvals per year [FY2022, FY2023] for this employer, or None. Tries legal-name variants
    (e.g. 'Amazon' matches 'Amazon.com Services')."""
    k = _h1b_norm(company)
    if not k:
        return None
    c = _h1b_data()
    best = c["data"].get(k)
    if len(k) >= 4:
        cands = [kk for kk in c["idx"].get(k.split(" ", 1)[0], []) if kk.startswith(k + " ")]
        if cands:
            top = max(cands, key=lambda kk: sum(c["data"][kk]))
            if not best or sum(c["data"][top]) > sum(best):
                best = c["data"][top]
    return best


def h1b_label(company):
    rec = h1b_record(company)
    if not rec or not sum(rec):
        return ""
    return f"{sum(rec):,} H-1B approvals (FY2022-23)"


def known_filer(company):  # noqa: F811 - replaces the hand-made list with USCIS records, list as fallback
    rec = h1b_record(company)
    return bool(rec and sum(rec) >= 5) or (company or "").strip().lower() in PAST_H1B_FILERS



# ---------------------------------------------------------------- OPT / CPT (student work authorization)
_OPT_NO = re.compile(r"(no|not|without|unable to (?:accept|consider))[^.\n]{0,25}\b(opt|cpt|stem opt|f-?1)\b|"
                     r"\b(opt|cpt|f-?1)\b[^.\n]{0,30}(not (?:accepted|eligible|considered)|ineligible)", re.I)
_OPT_YES = re.compile(r"\b(stem opt|opt|cpt|f-?1)\b(?![- ]?out)[^.\n]{0,40}(welcome|accepted|eligible|encouraged|ok\b|considered)|"
                      r"(accept|welcome|consider)[^.\n]{0,25}\b(stem opt|opt|cpt)\b(?![- ]?out)", re.I)


def opt_status(desc):
    """'Not accepted', 'Welcome' or '' (not mentioned) for OPT/CPT candidates."""
    if _OPT_NO.search(desc or ""):
        return "Not accepted"
    if _OPT_YES.search(desc or ""):
        return "Welcome"
    return ""


# ---------------------------------------------------------------- skills seen in job postings (for gap analysis)
SKILL_TERMS = {
    "Python": r"python", "SQL": r"sql", "Java": r"java(?!script)", "JavaScript/TypeScript": r"javascript|typescript",
    "React": r"react", "Node.js": r"node\.?js", "PyTorch": r"pytorch", "TensorFlow": r"tensorflow",
    "scikit-learn": r"scikit|sklearn", "pandas": r"pandas", "Spark": r"spark", "LangChain/LangGraph": r"langchain|langgraph",
    "RAG / vector databases": r"\brag\b|vector (?:db|database|store)|pinecone|weaviate|chroma",
    "Prompt engineering": r"prompt engineering", "LLM APIs (OpenAI/Anthropic)": r"openai|anthropic|claude|gpt-?4|llm api",
    "Fine-tuning": r"fine-?tun", "MLOps": r"mlops|mlflow|kubeflow", "Docker": r"docker", "Kubernetes": r"kubernetes|k8s",
    "AWS": r"\baws\b|amazon web services", "Azure": r"azure", "GCP": r"\bgcp\b|google cloud", "Databricks": r"databricks",
    "Snowflake": r"snowflake", "dbt": r"\bdbt\b", "Airflow": r"airflow", "Tableau/Power BI": r"tableau|power bi",
    "Statistics": r"statistic", "REST APIs": r"rest(?:ful)? api", "Workday": r"workday", "ServiceNow": r"servicenow",
    "Salesforce": r"salesforce", "Git": r"\bgit\b|github", "CI/CD": r"ci/cd|continuous integration",
}


def skill_gaps(profile, job_texts, top=12):
    """Skills that job postings ask for but the profile doesn't list: [(skill, how many jobs)]."""
    known = re.split(r"#+\s*gaps", profile or "", flags=re.I)[0].lower()
    counts = {}
    for text in job_texts:
        t = (text or "").lower()
        for name, pat in SKILL_TERMS.items():
            if re.search(r"(?<![a-z])(?:" + pat + r")", t) and not re.search(r"(?<![a-z])(?:" + pat + r")", known):
                counts[name] = counts.get(name, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])[:top]


# ---------------------------------------------------------------- experience level (Internship / Entry / Intermediate / Experienced)
_YEARS = re.compile(r"(?<![\d.$])(\d{1,2})\s*(?:\+|plus)?\s*(?:-|–|to)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)\b"
                    r"(?:\s+of)?(?:\s+[\w/&-]+){0,5}?\s+(?:experience|exp\b|industry|work)", re.I)
_INTERN = re.compile(r"\b(intern|internship|co-?op|summer 20\d\d)\b", re.I)
_ENTRY = re.compile(r"\b(new grad|new graduate|graduate|entry[- ]level|entry|junior|jr\.?|associate|apprentice|"
                    r"early[- ]career|level 1|l1|i)\b", re.I)
_MID = re.compile(r"\b(ii|level 2|l2|l3|mid[- ]level|mid)\b", re.I)


def years_required(desc):
    """Smallest 'X years of experience' the posting asks for (None when it doesn't say)."""
    found = []
    for m in _YEARS.finditer(desc or ""):
        n = int(m.group(1))
        if 0 <= n <= 15:
            found.append(n)
    return min(found) if found else None


def experience_level(title, level_field="", desc=""):
    """(label, years) where label is Internship / Entry / Intermediate / Experienced / Not stated."""
    t, lv = title or "", (level_field or "").lower()
    years = years_required(desc)
    if _INTERN.search(t) or "intern" in lv:
        return "Internship", years
    m = re.search(r"\b(?:engineer|scientist|developer|analyst|researcher|specialist)\s+([1-9])\b", t, re.I)
    if m:  # level numbers in titles: 1-2 entry, 3 intermediate, 4+ senior
        n = int(m.group(1))
        return ("Entry" if n <= 2 else "Intermediate" if n == 3 else "Experienced"), years
    if _ENTRY.search(t) or any(k in lv for k in ("entry", "junior", "associate")):
        label = "Entry"
    elif _MID.search(t) or "mid" in lv:
        label = "Intermediate"
    else:
        label = None
    if years is not None:  # the posting's own number is the strongest signal
        by_years = "Entry" if years <= 2 else "Intermediate" if years <= 5 else "Experienced"
        if label is None or (label == "Entry" and years > 3) or (label == "Intermediate" and years > 6):
            label = by_years
    return label or "Not stated", years
