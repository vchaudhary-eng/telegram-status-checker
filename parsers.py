import re
import json
from bs4 import BeautifulSoup
from datetime import datetime


def _int(v):
    try:
        return int(v)
    except Exception:
        return None


def seconds_to_hhmmss(sec: int | None) -> str | None:
    if sec is None:
        return None
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ---------- JSON helpers ----------
def _json_candidates_from_scripts(soup: BeautifulSoup):
    """Return list of JSON-like blobs found in <script> tags."""
    blobs = []
    for sc in soup.find_all("script"):
        txt = sc.string or sc.text or ""
        txt = txt.strip()
        if not txt:
            continue

        # plain JSON in script tag
        if ("{" in txt and "}" in txt) and any(k in txt for k in ["duration", "views", "author", "owner_id", "date"]):
            blobs.append(txt)
    return blobs


def _parse_any_json(text: str):
    """Attempt to extract JSON objects from JS text."""
    candidates = []

    # 1) find {...} blocks
    for m in re.finditer(r"{.*?}", text, flags=re.DOTALL):
        blob = m.group(0)
        # try load
        try:
            obj = json.loads(blob)
            candidates.append(obj)
        except Exception:
            # sometimes VK escapes quotes: try to relax
            pass

    # 2) find arrays of objects
    for m in re.finditer(r"\[.*?\]", text, flags=re.DOTALL):
        blob = m.group(0)
        try:
            obj = json.loads(blob)
            candidates.append(obj)
        except Exception:
            pass

    return candidates


def _first_int_from_patterns(text: str, patterns: list[str]):
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            val = _int(m.group(1))
            if val is not None:
                return val
    return None


def _first_str_from_patterns(text: str, patterns: list[str]):
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            return m.group(1).strip()
    return None


def parse_vk_page(soup: BeautifulSoup, html: str) -> dict:
    """
    Works for both https://vk.com/... and https://vkvideo.ru/...
    We try multiple sources:
      - meta tags (og:title, og:video:duration, itemprop)
      - inline JSON (var mvData / mv_init_data, or generic JSON blobs)
      - robust regex fallbacks
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

    # ----- Title -----
    ogt = soup.find("meta", {"property": "og:title"})
    if ogt and ogt.get("content"):
        out["title"] = ogt["content"].strip()
    if not out["title"]:
        ttag = soup.find("title")
        if ttag and ttag.text:
            out["title"] = ttag.text.strip()

    # ----- Duration from meta -----
    ogdur = soup.find("meta", {"property": "og:video:duration"})
    if ogdur and ogdur.get("content"):
        out["duration_seconds"] = _int(ogdur["content"])

    # itemprop duration as ISO 8601 (PT#H#M#S)
    if out["duration_seconds"] is None:
        iso = soup.find("meta", {"itemprop": "duration"})
        if iso and iso.get("content"):
            val = iso["content"]
            m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", val, flags=re.I)
            if m:
                h = int(m.group(1) or 0)
                mi = int(m.group(2) or 0)
                s = int(m.group(3) or 0)
                out["duration_seconds"] = h * 3600 + mi * 60 + s

    # ----- Try to read inline JSON -----
    # Common keys across VK players: duration (seconds), views/ viewsCount, date (unix), authorName/authorHref
    if any(v is None for v in [out["duration_seconds"], out["views"], out["channel_name"]]):
        for blob in _json_candidates_from_scripts(soup):
            for obj in _parse_any_json(blob):
                # hunt recursively
                stack = [obj]
                while stack:
                    cur = stack.pop()
                    if isinstance(cur, dict):
                        # duration
                        if out["duration_seconds"] is None:
                            for key in ("duration", "duration_sec", "videoDuration"):
                                v = cur.get(key)
                                iv = _int(v) if v is not None else None
                                if iv is not None:
                                    out["duration_seconds"] = iv
                                    break
                        # views
                        if out["views"] is None:
                            for key in ("views", "viewsCount", "view_counter", "play_count"):
                                v = cur.get(key)
                                iv = _int(v) if v is not None else None
                                if iv is not None:
                                    out["views"] = iv
                                    break
                        # upload date
                        if out["upload_date"] is None:
                            for key in ("date", "publish_date", "created", "upload_date"):
                                v = cur.get(key)
                                iv = _int(v) if v is not None else None
                                if iv:
                                    # assume unix
                                    try:
                                        out["upload_date"] = datetime.fromtimestamp(iv).strftime("%d-%m-%Y %H:%M")
                                    except Exception:
                                        pass
                        # channel
                        if out["channel_url"] is None:
                            for key in ("authorHref", "channel_url", "owner_href"):
                                v = cur.get(key)
                                if isinstance(v, str) and v.startswith("http"):
                                    out["channel_url"] = v
                                    break
                        if out["channel_name"] is None:
                            for key in ("authorName", "channel_name"):
                                v = cur.get(key)
                                if isinstance(v, str) and v.strip():
                                    out["channel_name"] = v.strip()
                                    break
                        # subscribers
                        if out["subscribers"] is None:
                            for key in ("authorFollowers", "subscribers", "followers"):
                                v = cur.get(key)
                                iv = _int(v) if v is not None else None
                                if iv is not None:
                                    out["subscribers"] = iv
                                    break

                        # push children
                        for k, v in cur.items():
                            if isinstance(v, (dict, list)):
                                stack.append(v)
                    elif isinstance(cur, list):
                        for v in cur:
                            if isinstance(v, (dict, list)):
                                stack.append(v)

            # if we already found enough, stop early
            if out["duration_seconds"] and (out["views"] is not None or out["channel_name"] or out["channel_url"]):
                break

    # ----- Regex fallbacks on raw HTML -----
    if out["duration_seconds"] is None:
        # e.g. "duration": 670, "video_duration": 670
        out["duration_seconds"] = _first_int_from_patterns(
            html,
            [r'"videoDuration"\s*:\s*(\d+)', r'"duration"\s*:\s*(\d+)', r'video_duration"\s*:\s*(\d+)']
        )

    if out["views"] is None:
        out["views"] = _first_int_from_patterns(
            html,
            [r'"viewsCount"\s*:\s*(\d+)', r'"views"\s*:\s*(\d+)']
        )

    if out["upload_date"] is None:
        # "date": 1691234567
        ts = _first_int_from_patterns(html, [r'"date"\s*:\s*(\d{9,11})'])
        if ts:
            try:
                out["upload_date"] = datetime.fromtimestamp(ts).strftime("%d-%m-%Y %H:%M")
            except Exception:
                pass

    if out["channel_url"] is None:
        href = _first_str_from_patterns(html, [r'"authorHref"\s*:\s*"([^"]+)"'])
        if href and href.startswith("http"):
            out["channel_url"] = href

    if out["channel_name"] is None:
        nm = _first_str_from_patterns(html, [r'"authorName"\s*:\s*"([^"]+)"'])
        if nm:
            out["channel_name"] = nm

    return out
