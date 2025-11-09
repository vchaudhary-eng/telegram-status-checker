import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import parser as dateparser

THIN_SPACES = "\u202f\u00A0"

ISO_DUR_RE = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$', re.I)

def _iso_to_seconds(s: str) -> int | None:
    if not s:
        return None
    m = ISO_DUR_RE.search(s.strip())
    if not m:
        return None
    h = int(m.group(1) or 0)
    m_ = int(m.group(2) or 0)
    sec = int(m.group(3) or 0)
    return h * 3600 + m_ * 60 + sec

def _hhmmss_to_seconds(s: str) -> int | None:
    if not s:
        return None
    parts = s.strip().split(":")
    if not parts:
        return None
    try:
        parts = list(map(int, parts))
    except Exception:
        return None
    if len(parts) == 3:
        return parts[0]*3600 + parts[1]*60 + parts[2]
    if len(parts) == 2:
        return parts[0]*60 + parts[1]
    return parts[0]

def _seconds_to_hhmmss(sec: int | None) -> str | None:
    if sec is None:
        return None
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def _clean_int(txt: str) -> int | None:
    if not txt:
        return None
    cleaned = re.sub(rf"[^\d]", "", txt.replace(THIN_SPACES, ""))
    return int(cleaned) if cleaned.isdigit() else None

def parse_upload_date(txt: str | None) -> str | None:
    if not txt:
        return None
    t = txt.strip().lower()
    # russian relative
    if t.startswith("вчера"):
        d = datetime.now() - timedelta(days=1)
        hhmm = re.search(r"(\d{1,2}:\d{2})", t)
        return d.strftime("%d-%m-%Y ") + (hhmm.group(1) if hhmm else "00:00")
    if t.startswith("сегодня"):
        d = datetime.now()
        hhmm = re.search(r"(\d{1,2}:\d{2})", t)
        return d.strftime("%d-%m-%Y ") + (hhmm.group(1) if hhmm else "00:00")

    # direct dd.mm.yyyy hh:mm
    m = re.search(r"(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\s*(\d{1,2}:\d{2})?", t)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else datetime.now().year
        hhmm = m.group(4) or "00:00"
        return f"{day:02d}-{month:02d}-{year:04d} {hhmm}"

    # try generic
    try:
        dt = dateparser.parse(txt, dayfirst=True, fuzzy=True)
        if dt:
            return dt.strftime("%d-%m-%Y %H:%M")
    except Exception:
        pass
    return None

def extract_vk_fields(html: str, soup: BeautifulSoup) -> dict:
    data = {
        "title": None,
        "duration_seconds": None,
        "views": None,
        "upload_date": None,
        "channel_url": None,
        "channel_name": None,
        "subscribers": None,
    }

    # Title
    og = soup.find("meta", {"property": "og:title"})
    if og and og.get("content"):
        data["title"] = og["content"].strip()
    if not data["title"]:
        tw = soup.find("meta", {"name": "twitter:title"})
        if tw and tw.get("content"):
            data["title"] = tw["content"].strip()
    if not data["title"]:
        h = soup.find(["h1","h2"], {"class": re.compile(r"(mv_title|video_title|mv_info_title)")})
        if h:
            data["title"] = h.get_text(strip=True)

    # Duration (priority order)
    # 1) meta OG
    ogd = soup.find("meta", {"property": "og:video:duration"})
    if ogd and ogd.get("content"):
        try:
            data["duration_seconds"] = int(ogd["content"])
        except Exception:
            pass
    # 2) meta itemprop duration (ISO 8601)
    if data["duration_seconds"] is None:
        meta_iso = soup.find("meta", {"itemprop": "duration"})
        if meta_iso and meta_iso.get("content"):
            data["duration_seconds"] = _iso_to_seconds(meta_iso["content"])
    # 3) JSON `"duration": 184`
    if data["duration_seconds"] is None:
        m = re.search(r'"\bduration\b"\s*:\s*(\d{1,6})', html)
        if m:
            data["duration_seconds"] = int(m.group(1))
    # 4) `data-duration="184"`
    if data["duration_seconds"] is None:
        m = re.search(r'data-duration="(\d{1,6})"', html)
        if m:
            data["duration_seconds"] = int(m.group(1))
    # 5) last resort HH:MM:SS near player controls only (anchor with  m/s)
    if data["duration_seconds"] is None:
        # pick the **last** time pattern to avoid random matches
        times = re.findall(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", html)
        if times:
            data["duration_seconds"] = _hhmmss_to_seconds(times[-1])

    # Views
    # JSON keys first
    m = re.search(r'"\bviews(?:Count)?\b"\s*:\s*(\d{1,12})', html)
    if m:
        data["views"] = int(m.group(1))
    if data["views"] is None:
        # Text like "55 views" or "55 просмотров"
        m = re.search(rf'(\d[\d{THIN_SPACES}\s]*)\s*(views|просмотр|просмотра|просмотров)\b', html, re.I)
        if m:
            data["views"] = _clean_int(m.group(1))

    # Upload date
    # JSON `datePublished`
    m = re.search(r'"\bdate(?:Published)?\b"\s*:\s*"([^"]+)"', html)
    if m:
        parsed = parse_upload_date(m.group(1))
        if parsed:
            data["upload_date"] = parsed
    if data["upload_date"] is None:
        el = soup.select_one(".mv_info_date, .page_video_date, time[datetime]")
        if el:
            txt = el.get("datetime") or el.get_text(strip=True)
            parsed = parse_upload_date(txt)
            if parsed:
                data["upload_date"] = parsed

    # Channel URL / Name (JSON first)
    m = re.search(r'"\bauthorHref\b"\s*:\s*"([^"]+)"', html)
    if m:
        href = m.group(1).encode("utf-8").decode("unicode_escape").replace("\\/","/")
        data["channel_url"] = href
    if not data["channel_url"]:
        a = soup.select_one('a[href^="https://vk.com/"]:not([href$="/video"])')
        if a and a.get("href"):
            data["channel_url"] = a["href"]
    m = re.search(r'"\bauthorName\b"\s*:\s*"([^"]+)"', html)
    if m:
        data["channel_name"] = m.group(1)
    if not data["channel_name"]:
        by = soup.select_one(".mv_info_author, .page_video_author, .pv_author_name")
        if by:
            data["channel_name"] = by.get_text(strip=True)

    # Subscribers (best effort)
    m = re.search(r'"\bauthorFollowers\b"\s*:\s*(\d{1,12})', html)
    if m:
        data["subscribers"] = int(m.group(1))

    return data

def extract_with_selectors(soup: BeautifulSoup, html: str) -> dict:
    return extract_vk_fields(html, soup)

def seconds_to_hhmmss(sec: int | None) -> str | None:
    return _seconds_to_hhmmss(sec)
