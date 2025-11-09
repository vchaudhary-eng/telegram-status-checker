import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import parser as dtparser

# --- helpers ---------------------------------------------------------

def _clean_spaces(s: str | None) -> str | None:
    if not s:
        return None
    return re.sub(r"\s+", " ", s).strip()

def _to_int_safe(v):
    try:
        return int(v)
    except Exception:
        return None

def _secs_to_hhmmss(secs: int | None):
    if not isinstance(secs, int):
        return None
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def _parse_views_from_text(html: str) -> int | None:
    # JSON keys most reliable
    for key in [r'"viewsCount"\s*:\s*(\d+)', r'"views"\s*:\s*(\d+)']:
        m = re.search(key, html)
        if m:
            return _to_int_safe(m.group(1))
    # fallbacks: Russian text with spaces/nbsp
    m = re.search(r"Просмотры[^0-9]*(\d[\d\s\u00A0\u202f]*)", html, re.I)
    if m:
        digits = re.sub(r"[\s\u00A0\u202f]", "", m.group(1))
        return _to_int_safe(digits)
    return None

def _parse_duration_seconds(html: str) -> int | None:
    # JSON keys first
    for key in [r'"duration"\s*:\s*(\d{1,7})', r'"video_duration"\s*:\s*(\d{1,7})']:
        m = re.search(key, html)
        if m:
            return _to_int_safe(m.group(1))
    # meta OG
    m = re.search(r'<meta[^>]+property="og:video:duration"[^>]+content="(\d+)"', html, re.I)
    if m:
        return _to_int_safe(m.group(1))
    # HH:MM:SS last resort
    m = re.search(r'(\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})', html)
    if m:
        parts = [int(p) for p in m.group(1).split(":")]
        if len(parts) == 3:
            return parts[0]*3600 + parts[1]*60 + parts[2]
        return parts[0]*60 + parts[1]
    return None

def _parse_upload_date(soup: BeautifulSoup, html: str) -> str | None:
    # JSON-LD/meta
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
    if m:
        try:
            dt = dtparser.parse(m.group(1))
            return dt.strftime("%d-%m-%Y %H:%M")
        except Exception:
            pass
    tag = soup.select_one(".mv_info_date, .page_video_date, .vp-layer-info_date, time")
    if tag:
        txt = tag.get_text(strip=True)
        # relative Russian words
        t = txt.lower()
        now = datetime.now()
        if t.startswith("сегодня"):
            m2 = re.search(r'(\d{1,2}:\d{2})', t)
            return now.strftime("%d-%m-%Y ") + (m2.group(1) if m2 else "00:00")
        if t.startswith("вчера"):
            m2 = re.search(r'(\d{1,2}:\d{2})', t)
            d = now - timedelta(days=1)
            return d.strftime("%d-%m-%Y ") + (m2.group(1) if m2 else "00:00")
        try:
            dt = dtparser.parse(txt, dayfirst=True, fuzzy=True)
            return dt.strftime("%d-%m-%Y %H:%M")
        except Exception:
            pass
    return None

def _parse_channel(html: str, soup: BeautifulSoup):
    url = name = subs = None
    # very often present in inline JSON
    m = re.search(r'"authorHref"\s*:\s*"([^"]+)"', html)
    if m:
        url = m.group(1).encode("utf-8").decode("unicode_escape").replace("\\/", "/")
    m = re.search(r'"authorName"\s*:\s*"([^"]+)"', html)
    if m:
        name = _clean_spaces(m.group(1))
    m = re.search(r'"authorFollowers"\s*:\s*(\d+)', html)
    if m:
        subs = _to_int_safe(m.group(1))

    if not url:
        a = soup.select_one('a[href^="https://vk.com/"], a[href^="https://vkvideo.ru/"]')
        if a and a.get("href") and not a["href"].endswith("/video"):
            url = a["href"]

    if not name:
        cand = soup.select_one(".mv_info_author, .page_video_author, .owner_link, .page_name")
        if cand:
            name = _clean_spaces(cand.get_text(" ", strip=True))

    return url, name, subs

def normalize_url(u: str) -> str:
    """
    Accepts:
      - https://vk.com/video-XXXX_YYYY
      - https://vkvideo.ru/video-XXXX_YYYY
      - mobile or query tail
    Returns original (we just strip query/fragment).
    """
    u = u.strip()
    u = re.sub(r"[#?].*$", "", u)
    return u

# --- main public -----------------------------------------------------

def parse_vk(html: str, url: str) -> dict:
    """Return dict with all fields, robust against both vk.com and vkvideo.ru players."""
    soup = BeautifulSoup(html, "lxml")

    # title
    title = None
    for sel in [
        ('meta', {"property": "og:title"}, "content"),
        ('meta', {"name": "twitter:title"}, "content"),
    ]:
        tag = soup.find(sel[0], sel[1])
        if tag and tag.get(sel[2]):
            title = _clean_spaces(tag.get(sel[2]))
            break
    if not title:
        h = soup.select_one("h1, .mv_title, .page_video_title")
        if h:
            title = _clean_spaces(h.get_text(" ", strip=True))

    dur_s = _parse_duration_seconds(html)
    views = _parse_views_from_text(html)
    upload = _parse_upload_date(soup, html)
    ch_url, ch_name, subs = _parse_channel(html, soup)

    return {
        "input_url": url,
        "title": title or "N/A",
        "duration_seconds": dur_s if isinstance(dur_s, int) else "N/A",
        "duration_hhmmss": _secs_to_hhmmss(dur_s) or "N/A",
        "views": views if isinstance(views, int) else "N/A",
        "upload_date": upload or "N/A",
        "channel_url": ch_url or "N/A",
        "channel_name": ch_name or "N/A",
        "subscribers": subs if isinstance(subs, int) else "N/A",
        "status": "Success",
        "error": None,
    }
