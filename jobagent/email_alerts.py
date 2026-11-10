"""Read job-alert emails (LinkedIn, Indeed, Glassdoor, ZipRecruiter) from Gmail over IMAP, read-only.

You set up job alerts on those sites as usual; the app reads the alert emails with a Gmail app password
(Google Account → Security → 2-Step Verification → App passwords). It never marks mail as read, moves,
deletes or sends anything.
"""
import email
import email.header
import email.utils
import imaplib
import re
from html.parser import HTMLParser

SENDERS = ["jobalerts-noreply@linkedin.com", "jobs-noreply@linkedin.com", "jobs-listings@linkedin.com",
           "alert@indeed.com", "donotreply@jobalert.indeed.com", "jobalerts@indeed.com", "noreply@indeed.com",
           "noreply@glassdoor.com", "alerts@ziprecruiter.com", "noreply@ziprecruiter.com"]

JOB_LINK = [
    ("LinkedIn alert", re.compile(r"linkedin\.com/(?:comm/)?jobs/view/(?:[^/?\"']*?-)?(\d{6,})")),
    ("Indeed alert", re.compile(r"indeed\.com/.*?[?&](?:jk|vjk)=([0-9a-f]{12,})", re.I)),
    ("Glassdoor alert", re.compile(r"glassdoor\.com/.*?(?:jobListingId|jl)=(\d{6,})", re.I)),
    ("ZipRecruiter alert", re.compile(r"ziprecruiter\.com/(?:km|c|jobs)/[^\"'\s]*?([A-Za-z0-9_-]{10,})(?:[?\"']|$)")),
]
CANONICAL = {"LinkedIn alert": "https://www.linkedin.com/jobs/view/{}",
             "Indeed alert": "https://www.indeed.com/viewjob?jk={}"}
SKIP_TEXT = re.compile(r"^(view job|apply|apply now|easy apply|see all jobs|see more jobs|view all|new|promoted|"
                       r"actively recruiting|be an early applicant|\d+ (?:applicants?|connections?).*|.*school alum.*|"
                       r"unsubscribe|manage alerts?|job alert.*|this company is actively hiring)$", re.I)


class _Tokens(HTMLParser):
    """Flattens an email's HTML into ('link', href, text) and ('text', text) tokens."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens, self._href, self._buf = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._flush()
            self._href = dict(attrs).get("href", "")
        elif tag in ("br", "p", "div", "td", "tr", "li", "table", "span"):
            self._flush()

    def handle_endtag(self, tag):
        if tag == "a":
            text = " ".join("".join(self._buf).split())
            self.tokens.append(("link", self._href or "", text))
            self._href, self._buf = None, []
        elif tag in ("p", "div", "td", "tr", "li", "span"):
            self._flush()

    def handle_data(self, data):
        self._buf.append(data)

    def _flush(self):
        if self._href is None:
            text = " ".join("".join(self._buf).split())
            if text:
                self.tokens.append(("text", text))
            self._buf = []


def parse_alert_html(html, received=""):
    """Return job items found in one alert email."""
    p = _Tokens()
    p.feed(html)
    p.close()
    toks = p.tokens
    jobs, seen = [], set()
    for i, t in enumerate(toks):
        if t[0] != "link":
            continue
        for source, rx in JOB_LINK:
            m = rx.search(t[1])
            if not m:
                continue
            jid = m.group(1)
            if (source, jid) in seen:
                # the same job is often linked twice (logo, then title); keep the first one that has a title
                break
            title = t[2]
            if not title or SKIP_TEXT.match(title) or len(title) > 140 or len(title) < 3:
                break  # logo or button link: the job's title link comes next
            # company and location follow the title until the next job link
            details = []
            for x in toks[i + 1:i + 10]:
                if x[0] == "link" and any(r.search(x[1]) for _, r in JOB_LINK):
                    break
                txt = x[-1]
                if txt and txt != title and not SKIP_TEXT.match(txt) and len(txt) < 120:
                    details.append(txt)
            company, location = "", ""
            if details:
                if " · " in details[0]:
                    company, _, location = details[0].partition(" · ")
                else:
                    company = details[0]
                    location = details[1] if len(details) > 1 else ""
            seen.add((source, jid))
            url = CANONICAL.get(source, "{}").format(jid) if source in CANONICAL else t[1].split("?")[0]
            jobs.append({"id": f"{source.split()[0].lower()}-{jid}", "source": source, "title": title,
                         "companyName": company.strip()[:80], "location": location.strip()[:80],
                         "publishedAt": received, "salary": next((d for d in details if "$" in d), ""),
                         "contractType": "", "experienceLevel": "", "jobUrl": url,
                         "description": f"{title}\n{company}\n{location}\n" + "\n".join(details[2:6]) +
                                        "\n(From a job-alert email: open the posting for the full description.)"})
            break
    return jobs


def _html_of(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
    return ""


def fetch_alerts(address, app_password, window_secs, log, max_messages=60):
    days = max(1, min(30, -(-window_secs // 86400)))
    query = "from:(" + " OR ".join(SENDERS) + f") newer_than:{days}d"
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=60)
        imap.login(address, app_password.replace(" ", ""))
    except imaplib.IMAP4.error as e:
        raise RuntimeError("Gmail rejected the login. Use a Gmail app password (not your normal password) "
                           "and make sure IMAP is on.") from e
    items = []
    try:
        imap.select('"[Gmail]/All Mail"', readonly=True)
        typ, data = imap.search(None, "X-GM-RAW", f'"{query}"')
        ids = (data[0] or b"").split()[-max_messages:]
        for mid in ids:
            typ, msgdata = imap.fetch(mid, "(BODY.PEEK[])")  # PEEK: never marks the email as read
            if typ != "OK" or not msgdata or not isinstance(msgdata[0], tuple):
                continue
            msg = email.message_from_bytes(msgdata[0][1])
            try:
                received = email.utils.parsedate_to_datetime(msg.get("Date")).strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                received = ""
            items += parse_alert_html(_html_of(msg), received)
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass
    # the same job often appears in several alerts
    uniq = {i["id"]: i for i in items}
    log(f"Job-alert emails: {len(uniq)} jobs from {len(ids)} emails (last {days} days)")
    return list(uniq.values())
