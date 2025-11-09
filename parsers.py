import re
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from datetime import datetime, timedelta

# ------- helpers -------

ISO_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", re.I)

def iso8601_to_seconds(val: str) -> int | None:
    if not val:
        return None
    m = ISO_DURATION_RE.fullmatch(val.strip())
    if not m:
        return None
    h = int(m.group(1) or 0)
    m_ = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h * 3600 + m_ * 60 + s

def seconds_to_hhmmss(sec: int | None) -> str | None:
    if sec is None:
        return None
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def parse_upload_date(text: str | None) -> str | None:
    if not text:
        return None
    t = text.strip().lower()

    # relative russian: сегодня / вчера
    rel = {"сегодня": 0, "вчера": -1}
    for key, off in rel.items():
        if t.startswith(key):
            hhmm = re.search(r"(\d{1,2}:\d{2})", t)
            d = datetime.now() + timedelta(days=off)
            return d.strftime("%d-%m-%Y ") + (hhmm.group(1) if hhmm else "00:00")

    # DD.MM.YYYY HH:MM (or DD.MM HH:MM)
    m = re.search(r"(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\s*(\d{1,2}:\d{2})?", t)
    if m:
        day = int(m.group(1)); month = int(m.group(2))
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

# ------- main extractor -------

def extract_with_selectors(soup: BeautifulSoup, html: str) -> dict:
    data = {
        "title": None,
        "duration_seconds": None,
        "views": None,
        "upload_date": None,
        "channel_url": None,
        "channel_name": None,
        "subscribers": None,
    }

    # --- Title ---
    for sel in [
        ("meta", {"property": "og:title"}, "content"),
        ("meta", {"name": "twitter:title"}, "content"),
    ]:
        tag = soup.find(sel[0], sel[1])
        if tag and tag.get(sel[2]):
            data["title"] = tag[sel[2]].strip(); break
    if not data["title"]:
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            data["title"] = h1.get_text(strip=True)

    # --- Duration (prefer true numeric/ISO, avoid generic HH:MM noise) ---
    # 1) meta itemprop=duration (ISO 8601)
    tag = soup.find("meta", {"itemprop": "duration"})
    if tag and tag.get("content"):
        data["duration_seconds"] = iso8601_to_seconds(tag["content"])

    # 2) og:video:duration
    if data["duration_seconds"] is None:
        tag = soup.find("meta", {"property": "og:video:duration"})
        if tag and tag.get("content"):
            try:
                data["duration_seconds"] = int(tag["content"])
            except Exception:
                pass

    # 3) common JSON keys embedded in page
    if data["duration_seconds"] is None:
        for key in [
            r'"videoDurationSeconds"\s*:\s*(\d+)',
            r'"lengthSeconds"\s*:\s*"(\d+)"',
            r'"duration"\s*:\s*(\d+)',      # accept only pure number here
            r'data-duration="(\d+)"',
        ]:
            m = re.search(key, html)
            if m:
                data["duration_seconds"] = int(m.group(1)); break

    # (No blind HH:MM fallback now—to stop the constant 11:10 bug)

    # --- Views ---
    for pat in [
        r'"viewsCount"\s*:\s*(\d+)',
        r'"views"\s*:\s*(\d+)',
        r'Просмотры[^0-9]*(\d[\d\u00A0\u202f\s]*)',  # russian label
        r'"viewCount"\s*:\s*"(\d+)"',
    ]:
        m = re.search(pat, html)
        if m:
            try:
                digits = re.sub(r"[\s\u00A0\u202f]", "", m.group(1))
                data["views"] = int(digits)
                break
            except Exception:
                pass

    # --- Upload date ---
    tag = soup.find("meta", {"itemprop": "datePublished"})
    if tag and tag.get("content"):
        data["upload_date"] = parse_upload_date(tag["content"])
    if data["upload_date"] is None:
        m = re.search(r'"date(?:Published)?"\s*:\s*"([^"]+)"', html)
        if m:
            data["upload_date"] = parse_upload_date(m.group(1))
    if data["upload_date"] is None:
        el = soup.select_one(".mv_info_date, .page_video_date, .vp-layer-info_date, time")
        if el and el.get_text(strip=True):
            data["upload_date"] = parse_upload_date(el.get_text(strip=True))

    # --- Channel URL & Name (author) ---
    m = re.search(r'"authorHref"\s*:\s*"(https?:\\?/\\?/vk\.com\\?/[^"]+)"', html)
    if m:
        href = m.group(1).replace("\\/", "/")
        data["channel_url"] = bytes(href, "utf-8").decode("unicode_escape")
    if not data["channel_url"]:
        a = soup.select_one('a[href^="https://vk.com/"][rel="author"], a[href^="https://vk.com/"].mv_info_author, a[href^="https://vk.com/"].page_video_author')
        if a and a.get("href") and not a["href"].endswith("/video"):
            data["channel_url"] = a["href"]

    m = re.search(r'"authorName"\s*:\s*"([^"]+)"', html)
    if m:
        data["channel_name"] = m.group(1)
    if not data["channel_name"]:
        by = soup.select_one(".mv_info_author, .page_video_author, [rel='author']")
        if by and by.get_text(strip=True):
            data["channel_name"] = by.get_text(strip=True)

    # --- Subscribers (best effort) ---
    for pat in [r'"authorFollowers"\s*:\s*(\d+)', r'подписчик(?:ов|а)?[^0-9]*(\d[\d\s\u00A0\u202f]*)']:
        m = re.search(pat, html, flags=re.I)
        if m:
            try:
                digits = re.sub(r"[\s\u00A0\u202f]", "", m.group(1))
                data["subscribers"] = int(digits)
                break
            except Exception:
                pass

    return data
