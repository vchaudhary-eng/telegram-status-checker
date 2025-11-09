import re
if m:
data["duration_seconds"] = int(m.group(1))
if data["duration_seconds"] is None:
m = re.search(r"\b\"duration\"\s*:\s*(\d{1,7})\b", html)
if m:
data["duration_seconds"] = int(m.group(1))
if data["duration_seconds"] is None:
# last resort: HH:MM:SS in markup
m = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)", html)
if m:
data["duration_seconds"] = hhmmss_to_seconds(m.group(1))


# --- Views ---
# Try JSON keys commonly seen: views, viewsCount
m = re.search(r"\b\"views(?:Count)?\"\s*:\s*(\d{1,12})\b", html)
if m:
data["views"] = int(m.group(1))
else:
# textual like "Просмотры: 12 345" (with nbsp/thin spaces)
m2 = re.search(r"Просмотры[^\d]*(\d[\d\s\u202f\u00A0]*)", html)
if m2:
digits = re.sub(r"[\s\u202f\u00A0]", "", m2.group(1))
try:
data["views"] = int(digits)
except Exception:
pass


# --- Upload Date ---
# JSON-LD datePublished
ld = soup.find("meta", {"itemprop": "datePublished"})
if ld and ld.get("content"):
data["upload_date"] = parse_upload_date(ld["content"]) or None
if data["upload_date"] is None:
# inline: "date":"2025-10-20T14:20:00+03:00" or similar
m = re.search(r"\b\"date(?:Published)?\"\s*:\s*\"([^\"]+)\"", html)
if m:
data["upload_date"] = parse_upload_date(m.group(1))
if data["upload_date"] is None:
# visible label container with class names occasionally used
el = soup.select_one(".mv_info_date, .page_video_date, .vp-layer-info_date, .mv_info_author_date")
if el and el.get_text(strip=True):
data["upload_date"] = parse_upload_date(el.get_text(strip=True))


# --- Channel URL & Name ---
# Look for JSON keys like authorHref / authorName
m = re.search(r"\b\"authorHref\"\s*:\s*\"(https?:\\/\\/vk\.com\\/[^\"]+)\"", html)
if m:
data["channel_url"] = m.group(1).encode("utf-8").decode("unicode_escape").replace("\\/", "/")
if not data["channel_url"]:
# anchor with data-from-author or byline
a = soup.select_one('a[href^="https://vk.com/"]')
if a and a.get("href") and not a.get("href").endswith("/video"):
data["channel_url"] = a["href"]


m = re.search(r"\b\"authorName\"\s*:\s*\"([^\"]+)\"", html)
if m:
data["channel_name"] = m.group(1)
if not data["channel_name"]:
# fall back to the link text near author
by = soup.select_one(".mv_info_author, .post_author, .page_video_author")
if by and by.get_text(strip=True):
data["channel_name"] = by.get_text(strip=True)


# --- Subscribers ---
m = re.search(r"\b\"authorFollowers\"\s*:\s*(\d{1,12})\b", html)
if m:
data["subscribers"] = int(m.group(1))


return data
