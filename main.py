from fastapi import FastAPI, Request
TIMEOUT = httpx.Timeout(20.0, connect=20.0)




@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
return templates.TemplateResponse("index.html", {"request": request})




async def fetch(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
result = {
"input_url": url,
"title": "N/A",
"duration_seconds": "N/A",
"duration_hhmmss": "N/A",
"views": "N/A",
"upload_date": "N/A",
"channel_url": "N/A",
"channel_name": "N/A",
"subscribers": "N/A",
"status": "Error",
"error": None,
}
try:
resp = await client.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
text = resp.text
soup = BeautifulSoup(text, "lxml")
data = extract_with_selectors(soup, text)


title = data.get("title")
dur = data.get("duration_seconds")
views = data.get("views")
up = data.get("upload_date")
ch_url = data.get("channel_url")
ch_name = data.get("channel_name")
subs = data.get("subscribers")


if title:
result["title"] = title
if isinstance(dur, int):
result["duration_seconds"] = dur
result["duration_hhmmss"] = seconds_to_hhmmss(dur)
if isinstance(views, int):
result["views"] = views
if up:
result["upload_date"] = up
if ch_url:
result["channel_url"] = ch_url
if ch_name:
result["channel_name"] = ch_name
if isinstance(subs, int):
result["subscribers"] = subs


result["status"] = "Success"
except Exception as e:
result["error"] = str(e)
return result




@app.post("/api/scrape")
async def api_scrape(body: ScrapeBody):
urls = [u.strip() for u in body.urls if u and u.strip()]
if not urls:
