import re
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as dateparser

# --- helpers ---------------------------------------------------------------

def seconds_to_hhmmss(sec: int | None) -> str | None:
    if sec is None:
        return None
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def parse_epoch_to_local_string(epoch: int | None) -> str | None:
    if not epoch:
        return None
    try:
        dt = datetime.fromtimestamp(int(epoch))
        return dt.strftime("%d-%m-%Y %H:%M")
    except Exception:
        return None

def parse_upload_text(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip().lower()
    # dd.mm.yyyy hh:mm or dd.mm hh:mm
    m = re.search(r"(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\s*(\d{1,2}:\d{2})?", text)
    if m:
        d, mo, y, t = m.group(1), m.group(2), m.group(3), m.group(4)
        y = y if y else str(datetime.now().year)
        t = t if t else "00:00"
        return f"{int(d):02d}-{int(mo):02d}-{int(y):04d} {t}"
    try:
        dt = dateparser.parse(text, dayfirst=True, fuzzy=True)
        return dt.strftime("%d-%m-%Y %H:%M") if dt else None
    except Exception:
        return None

# --- main extractor --------------------------------------------------------

def extract_with_selectors(soup: BeautifulSoup, html: str) -> dict:
    """
    Strategy:
    1) Look for VK's in-page JSON 'mvData' (most reliable).
    2) Fall back to OG/LD metas.
    3) Final safe fallbacks, never using free-floating HH:MM.
    """
    out = {
        "title": None,
        "duration_seconds": None,
        "views": None,
        "upload_date": None,
        "channel_url": None,
        "channel_name": None,
        "subscribers": None,
    }

    # 1) Try to isolate the mvData object (window._mvData or "mvData":{...})
    mv_block = None
    m_mv = re.search(r'"mvData"\s*:\s*{(.*?)}\s*,\s*"', html, flags=re.S)
    if m_mv:
        mv_block = m_mv.group(1)

    # When mv_block is present, pull the important fields from within it
    if mv_block:
        # title
        m = re.search(r'"title"\s*:\s*"([^"]+)"', mv_block)
        if m: out["title"] = _unescape(m.group(1))

        # duration seconds
        m = re.search(r'"duration"\s*:\s*(\d{1,7})', mv_block)
        if m:
            out["duration_seconds"] = int(m.group(1))
        else:
            # sometimes durationString:"3:04"
            ms = re.search(r'"durationString"\s*:\s*"(\d{1,2}:\d{2}(?::\d{2})?)"', mv_block)
            if ms:
                out["duration_seconds"] = _hhmmss_to_seconds(ms.group(1))

        # views
        m = re.search(r'"viewsCount"\s*:\s*(\d{1,12})', mv_block)
        if not m:
            m = re.search(r'"views"\s*:\s*(\d{1,12})', mv_block)
        if m:
            out["views"] = int(m.group(1))

        # upload date — VK usually exposes unix "date"
        m = re.search(r'"date"\s*:\s*(\d{9,11})', mv_block)
        if m:
            out["upload_date"] = parse_epoch_to_local_string(int(m.group(1)))

        # channel url / name
        m = re.search(r'"authorHref"\s*:\s*"([^"]+)"', mv_block)
        if m:
            out["channel_url"] = _unescape(m.group(1)).replace("\\/", "/")
        m = re.search(r'"authorName"\s*:\s*"([^"]+)"', mv_block)
        if m:
            out["channel_name"] = _unescape(m.group(1))

        # subscribers/followers (best-effort)
        m = re.search(r'"authorFollowers"\s*:\s*(\d{1,12})', mv_block)
        if m:
            out["subscribers"] = int(m.group(1))

    # 2) OG/LD fallbacks
    if not out["title"]:
        mt = soup.find("meta", {"property": "og:title"})
        if mt and mt.get("content"):
            out["title"] = mt["content"].strip()

    if out["duration_seconds"] is None:
        md = soup.find("meta", {"property": "og:video:duration"})
        if md and md.get("content"):
            try:
                out["duration_seconds"] = int(md["content"])
            except Exception:
                pass
    if out["duration_seconds"] is None:
        # schema.org duration (ISO8601)
        md = soup.find("meta", {"itemprop": "duration"})
        if md and md.get("content"):
            sec = _iso8601_to_seconds(md["content"])
            if sec is not None:
                out["duration_seconds"] = sec

    if not out["upload_date"]:
        ld = soup.find("meta", {"itemprop": "datePublished"})
        if ld and ld.get("content"):
            out["upload_date"] = parse_upload_text(ld["content"])
    if not out["upload_date"]:
        el = soup.select_one(".mv_info_date, .vp-layer-info_date, .page_video_date")
        if el and el.get_text(strip=True):
            out["upload_date"] = parse_upload_text(el.get_text(strip=True))

    if not out["channel_url"]:
        a = soup.select_one('a[href^="https://vk.com/"], a[href^="http://vk.com/"]')
        if a and a.get("href"):
            href = a["href"]
            if not href.endswith("/video"):
                out["channel_url"] = href
    if not out["channel_name"]:
        el = soup.select_one(".mv_info_author, .page_video_author")
        if el:
            nm = el.get_text(strip=True)
            if nm:
                out["channel_name"] = nm

    return out

# --- tiny utils ------------------------------------------------------------

def _unescape(s: str) -> str:
    return s.encode("utf-8").decode("unicode_escape")

def _iso8601_to_seconds(val: str | None) -> int | None:
    if not val:
        return None
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", val.strip(), flags=re.I)
    if not m:
        return None
    h = int(m.group(1) or 0)
    mi = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h * 3600 + mi * 60 + s

def _hhmmss_to_seconds(s: str) -> int:
    parts = [int(p) for p in s.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return parts[0] * 60 + parts[1]
