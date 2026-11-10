"""Keyword rules shared by the job agent scripts.

These give quick first-pass labels. During each run Claude reads the job text and makes the
final call, so these only need to be good hints.
"""
import re

AI_TITLE = re.compile(
    r"\b(ai|a\.i\.|artificial intelligence|machine learning|ml|mlops|llm|genai|gen ai|generative|"
    r"nlp|natural language|computer vision|deep learning|data scien\w*|applied scien\w*|"
    r"research scien\w*|prompt|agentic|agents?|neural|perception|ai/ml|ml/ai|copilot)\b", re.I)
AI_DESC = re.compile(
    r"\b(machine learning|deep learning|llms?|large language models?|generative ai|pytorch|tensorflow|"
    r"computer vision|nlp|natural language processing|neural networks?|rag|transformers?|agentic)\b", re.I)
# Mid-level is wanted, so "II" stays in. Clearly senior titles are dropped.
SENIOR = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|manager|director|head of|vp|vice president|"
    r"architect|distinguished|iii|iv|level 3|l5|l6|l7)\b", re.I)

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
    r"years|experience|degree|bachelor|master|ph\.?d|qualif|require|must|python|sql|java|workday|hris|"
    r"hr tech|integration|api|salary|compensation|\$|pay range|llm|machine learning|genai|cloud|aws|azure", re.I)


def trim_description(desc, limit=2600):
    """Keep the opening plus the lines that matter for fit, sponsorship and remote status."""
    desc = desc or ""
    head = desc[:700]
    rest = [ln.strip() for ln in re.split(r"[\n\r]+|(?<=[.!?])\s+", desc[700:]) if ln.strip()]
    keep = [ln for ln in rest if KEEP_LINE.search(ln)]
    out = head + ("\n...\n" + "\n".join(keep) if keep else "")
    return out[:limit]


# Non-AI titles that fit the candidate's background (kept even without AI keywords).
PROFILE_TITLE = re.compile(
    r"\b(workday|hris|hrit|hr systems?|hr technology|people systems?|people technology|people tech|people analytics|"
    r"business systems?|enterprise (?:applications?|systems)|integration (?:engineer|developer|analyst|specialist)|"
    r"integrations? engineer|solutions? engineer|forward[- ]deployed|implementation (?:engineer|consultant|specialist)|"
    r"automation (?:engineer|developer|specialist))\b", re.I)


def is_relevant(title, desc):
    return is_ai(title, desc) or bool(PROFILE_TITLE.search(title))


def wanted_title(title):
    """Quick title-only check used before fetching full postings."""
    return (bool(AI_TITLE.search(title)) or bool(PROFILE_TITLE.search(title))) and not is_senior(title)
