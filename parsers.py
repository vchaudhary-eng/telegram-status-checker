import re
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

RUS_RELATIVE = {
    "сегодня": 0,
    "вчера": -1,
}

ISO_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", re.I)


def iso8601_to_seconds(val: Optional[str]) -> Optional[int]:
    if not val:
        return None
    m = ISO_DURATION_RE.fullmatch(val.strip())
    if not m:
        return None
    h = int(m.group(1) or 0)
    m_ = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h * 3600 + m_ * 60 + s


def hhmmss_to_seconds(val: Optional[str]) -> Optional[int]:
    if not val:
        return None
    parts = [p for p in val.strip().split(":") if p]
    try:
        parts = list(map(int, parts))
    except ValueError:
        return None
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]


def seconds_to_hhmmss(sec: Optional[int]) -> Optional[str]:
    if sec is None:
        return None
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def parse_upload_date(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.strip().lower()

    # relative Russian words (e.g., сегодня 14:35 / вчера 09:12)
    for key, offset in RUS_RELATIVE.items():
        if t.startswith(key):
            hhmm = re.search(r"(\d{1,2}:\d{2})", t)
            now = datetime.now()
            d = now + timedelta(days=offset)
            time_part = hhmm.group(1) if hhmm else "00:00"
            return d.strftime("%d-%m-%Y ") + time_part

    # DD.MM.YYYY HH:MM or DD-MM etc
    m = re.search(r"(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\s*(\d{1,2}:\d{2})?", t)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else datetime.now().year
        hhmm = m.group(4) or "00:00"
        return f"{day:02d}-{month:02d}-{year:04d} {hhmm}"

    try:
        dt = dateparser.parse(text, dayfirst=True, fuzzy=True)
        if dt:
            return dt.strftime("%d-%m-%Y %H:%M")
    except Exception:
        pass
    return None


def extract_with_selectors(soup: BeautifulSoup, html: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "title": None,
        "duration_seconds": None,
        "views": None,
        "upload_date": None,
        "channel_url": None,
        "channel_name": None,
        "subscribers": None,
    }

    # Title
    og_title = soup.find("meta", {"property": "og:title"})
    if og_title and og_title.get("content"):
        data["title"] = og_title["content"].strip()
    if not data["title"]:
        tw = soup.find("meta", {"name": "twitter:title"})
        if tw and tw.get("content"):
            data["title"] = tw["content"].strip()

    # Duration (ISO 8601 / og:video:duration / inline)
    meta_dur = soup.find("meta", {"itemprop": "duration"})
    if meta_dur and meta_dur.get("content"):
        data["duration_seconds"] = iso8601_to_seconds(meta_dur["content"])

    if data["duration_seconds"] is None:
        og_dur = soup.find("meta", {"property": "og:video:duration"})
        if og_dur and og_dur.get("content"):
            try:
                data["duration_seconds"] = int(og_dur["content"])
            except Exception:
                pass

    if data["duration_seconds"] is None:
        m = re.search(r'data-duration="(\d+)"', html)
        if m:
            data["duration_seconds"] = int(m.group(1))

    if data["duration_seconds"] is None:
        m = re.search(r'\b"duration"\s*:\s*(\d{1,7})\b', html)
        if m:
            data["duration_seconds"] = int(m.group(1))

    if data["duration_seconds"] is None:
        m = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)", html)
        if m:
            data["duration_seconds"] = hhmmss_to_seconds(m.group(1))

    # Views
    m = re.search(r'\b"views(?:Count)?"\s*:\s*(\d{1,12})\b', html)
    if m:
        data["views"] = int(m.group(1))
    else:
        m2 = re.search(r"Просмотры[^\d]*(\d[\d\s\u202f\u00A0]*)", html)
        if m2:
            digits = re.sub(r"[\s\u202f\u00A0]", "", m2.group(1))
            try:
                data["views"] = int(digits)
            except Exception:
                pass

    # Upload date
    ld = soup.find("meta", {"itemprop": "datePublished"})
    if ld and ld.get("content"):
        data["upload_date"] = parse_upload_date(ld["content"])

    if data["upload_date"] is None:
        m = re.search(r'\b"date(?:Published)?"\s*:\s*"([^"]+)"', html)
        if m:
            data["upload_date"] = parse_upload_date(m.group(1))

    if data["upload_date"] is None:
        el = soup.select_one(".mv_info_date, .page_video_date, .vp-layer-info_date, .mv_info_author_date")
        if el and el.get_text(strip=True):
            data["upload_date"] = parse_upload_date(el.get_text(strip=True))

    # Channel URL & Name
    m = re.search(r'\b"authorHref"\s*:\s*"((?:https?:\\\/\\\/)?vk\.com[^"]+)"', html)
    if m:
        href = m.group(1).encode("utf-8").decode("unicode_escape").replace("\\/", "/")
        if href.startswith("http"):
            data["channel_url"] = href
        else:
            data["channel_url"] = "https://" + href

    if not data["channel_url"]:
        a = soup.select_one('a[href^="https://vk.com/"]')
        if a and a.get("href") and not a.get("href").endswith("/video"):
            data["channel_url"] = a["href"]

    m = re.search(r'\b"authorName"\s*:\s*"([^"]+)"', html)
    if m:
        data["channel_name"] = m.group(1)

    if not data["channel_name"]:
        by = soup.select_one(".mv_info_author, .post_author, .page_video_author")
        if by and by.get_text(strip=True):
            data["channel_name"] = by.get_text(strip=True)

    # Subscribers
    m = re.search(r'\b"authorFollowers"\s*:\s*(\d{1,12})\b', html)
    if m:
        data["subscribers"] = int(m.group(1))

    return data
