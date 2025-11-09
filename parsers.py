import re
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

# ---------------------------
# Helpers
# ---------------------------
RUS_REL = {"сегодня": 0, "вчера": -1}
ISO_DUR = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", re.I)


def _clean_space(s: Optional[str]) -> Optional[str]:
    if not s:
        return s
    return " ".join(s.split()).strip()


def iso_to_seconds(s: str) -> Optional[int]:
    m = ISO_DUR.fullmatch(s.strip()) if s else None
    if not m:
        return None
    h = int(m.group(1) or 0)
    m_ = int(m.group(2) or 0)
    s_ = int(m.group(3) or 0)
    return h * 3600 + m_ * 60 + s_


def hhmmss_to_seconds(s: str) -> Optional[int]:
    if not s:
        return None
    parts = s.split(":")
    if not parts:
        return None
    try:
        parts = list(map(int, parts))
    except Exception:
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
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def epoch_to_local_ddmmyyyy_hhmm(epoch: int) -> str:
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone()
    return dt.strftime("%d-%m-%Y %H:%M")


def parse_russian_date(text: str) -> Optional[str]:
    t = text.strip().lower()
    for k, off in RUS_REL.items():
        if t.startswith(k):
            # try HH:MM
            m = re.search(r"(\d{1,2}:\d{2})", t)
            now = datetime.now()
            day = (now + timedelta(days=off)).strftime("%d-%m-%Y")
            clock = m.group(1) if m else "00:00"
            return f"{day} {clock}"

    # dd.mm.yyyy hh:mm or dd.mm hh:mm
    m = re.search(r"(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\s*(\d{1,2}:\d{2})?", t)
    if m:
        d = int(m.group(1))
        M = int(m.group(2))
        y = int(m.group(3)) if m.group(3) else datetime.now().year
        hhmm = m.group(4) or "00:00"
        return f"{d:02d}-{M:02d}-{y:04d} {hhmm}"
    return None


# ---------------------------
# JSON hunters (VK uses inlined JSON; we try several places)
# ---------------------------
def _json_block_candidates(html: str) -> list[dict]:
    cands: list[dict] = []
    # window.__INITIAL_STATE__ = {...};
    for m in re.finditer(r"__INITIAL_STATE__\s*=\s*({.*?});\s*</script>", html, re.DOTALL):
        try:
            cands.append(json.loads(m.group(1)))
        except Exception:
            pass

    # mvcur / mvData structures
    for m in re.finditer(r"(?s)(\{|,)\s*\"mv(?:cur|Data)\"\s*:\s*({.*?})\s*(?:,|\})", html):
        try:
            obj = json.loads("{" + f"\"mvcur\": {m.group(2)}" + "}")
            cands.append(obj)
        except Exception:
            pass

    # any object that looks like it has duration & views
    for m in re.finditer(r"\{[^{}]{0,800}\"duration\"[^{}]{0,800}\}", html):
        try:
            cands.append(json.loads(m.group(0)))
        except Exception:
            pass

    return cands


def _drill_for_video_info(obj: Any) -> Dict[str, Any]:
    """
    Walk the dict and pick the first mapping that looks like video data.
    Fields we care about: duration, views/ viewsCount, authorHref, authorName, date/ datePublished, subscribers
    """
    out: Dict[str, Any] = {}
    stack = [obj]
    seen = set()
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))

        if isinstance(cur, dict):
            # duration
            for key in ("duration", "videoDuration", "lengthSeconds"):
                if key in cur and isinstance(cur[key], (int, float, str)):
                    out.setdefault("duration_seconds",
                                   iso_to_seconds(cur[key]) if isinstance(cur[key], str) else int(cur[key]))

            # views
            for key in ("views", "viewsCount", "viewCount"):
                if key in cur and isinstance(cur[key], (int, float, str)):
                    try:
                        out.setdefault("views", int(str(cur[key]).replace(" ", "")))
                    except Exception:
                        pass

            # author/channel
            for key in ("authorHref", "author_url", "channelUrl", "ownerUrl"):
                if key in cur and isinstance(cur[key], str):
                    out.setdefault("channel_url", cur[key].replace("\\/", "/"))

            for key in ("authorName", "author", "channelName", "ownerName", "titleOwnerName"):
                if key in cur and isinstance(cur[key], str):
                    out.setdefault("channel_name", _clean_space(cur[key]))

            # subscribers
            for key in ("authorFollowers", "subscribers", "followers"):
                if key in cur and isinstance(cur[key], (int, float, str)):
                    try:
                        out.setdefault("subscribers", int(str(cur[key]).replace(" ", "")))
                    except Exception:
                        pass

            # date: epoch or iso
            for key in ("date", "datePublished", "uploadDate", "timeCreated"):
                if key in cur and isinstance(cur[key], (int, float, str)):
                    v = cur[key]
                    if isinstance(v, (int, float)) and v > 10_000_000:  # epoch sec
                        out.setdefault("upload_date", epoch_to_local_ddmmyyyy_hhmm(int(v)))
                    elif isinstance(v, str):
                        # ISO or russian
                        # 2024-10-31T12:05:00+03:00
                        m = re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", v)
                        if m:
                            try:
                                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
                                out.setdefault("upload_date",
                                               dt.astimezone().strftime("%d-%m-%Y %H:%M"))
                            except Exception:
                                pass
                        else:
                            parsed = parse_russian_date(v)
                            if parsed:
                                out.setdefault("upload_date", parsed)

            for v in cur.values():
                stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return out


# ---------------------------
# Main parse entry
# ---------------------------
def parse_vk_page(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    data: Dict[str, Any] = {
        "title": None,
        "duration_seconds": None,
        "views": None,
        "upload_date": None,
        "channel_url": None,
        "channel_name": None,
        "subscribers": None,
    }

    # Title from metas first
    og = soup.find("meta", {"property": "og:title"})
    if og and og.get("content"):
        data["title"] = _clean_space(og["content"])
    if not data["title"]:
        tw = soup.find("meta", {"name": "twitter:title"})
        if tw and tw.get("content"):
            data["title"] = _clean_space(tw["content"])

    # Duration from known metas
    md = soup.find("meta", {"itemprop": "duration"})
    if md and md.get("content"):
        data["duration_seconds"] = iso_to_seconds(md["content"])
    if data["duration_seconds"] is None:
        ogd = soup.find("meta", {"property": "og:video:duration"})
        if ogd and ogd.get("content"):
            try:
                data["duration_seconds"] = int(ogd["content"])
            except Exception:
                pass

    # Fallbacks from HTML (HH:MM:SS fragments or data-duration)
    if data["duration_seconds"] is None:
        m = re.search(r'data-duration=["\'](\d+)["\']', html)
        if m:
            data["duration_seconds"] = int(m.group(1))
    if data["duration_seconds"] is None:
        m = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', html)
        if m:
            data["duration_seconds"] = hhmmss_to_seconds(m.group(1))

    # Upload date heuristics (visible russian text)
    if data["upload_date"] is None:
        el = soup.select_one(".mv_info_date, .page_video_date, .vp-layer-info_date, .mv_info_author_date")
        if el:
            parsed = parse_russian_date(el.get_text(" ", strip=True))
            if parsed:
                data["upload_date"] = parsed

    # Channel url/name rough heuristics in markup
    if data["channel_url"] is None:
        a = soup.select_one('a[href^="https://vk.com/"], a[href^="https://vkvideo.ru/"]')
        if a and a.get("href") and not a["href"].endswith("/video"):
            data["channel_url"] = a["href"]
    if data["channel_name"] is None:
        by = soup.select_one(".mv_info_author, .post_author, .page_video_author")
        if by:
            data["channel_name"] = _clean_space(by.get_text(" ", strip=True))

    # --- Deep JSON parsing (most reliable) ---
    for cand in _json_block_candidates(html):
        found = _drill_for_video_info(cand)
        # update only missing fields
        for k, v in found.items():
            if v and data.get(k) in (None, "", 0):
                data[k] = v

    # Clean channel_url (ensure absolute)
    if data["channel_url"]:
        if data["channel_url"].startswith("//"):
            data["channel_url"] = "https:" + data["channel_url"]
        if data["channel_url"].startswith("/"):
            # try to guess host from page — if not there, fall back to vk.com
            host = "https://vk.com"
            if "vkvideo.ru" in html:
                host = "https://vkvideo.ru"
            data["channel_url"] = host + data["channel_url"]

    # strip impossible values
    if isinstance(data["subscribers"], str):
        try:
            data["subscribers"] = int(data["subscribers"])
        except Exception:
            data["subscribers"] = None

    return data


def pack_response_fields(parsed: Dict[str, Any]) -> Dict[str, Any]:
    dur = parsed.get("duration_seconds")
    return {
        "title": parsed.get("title") or "N/A",
        "duration_seconds": dur if isinstance(dur, int) else "N/A",
        "duration_hhmmss": seconds_to_hhmmss(dur) if isinstance(dur, int) else "N/A",
        "views": parsed.get("views") if isinstance(parsed.get("views"), int) else "N/A",
        "upload_date": parsed.get("upload_date") or "N/A",
        "channel_url": parsed.get("channel_url") or "N/A",
        "channel_name": parsed.get("channel_name") or "N/A",
        "subscribers": parsed.get("subscribers") if isinstance(parsed.get("subscribers"), int) else "N/A",
    }
