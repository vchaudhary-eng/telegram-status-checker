from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel
from typing import List, Any
import asyncio

from parsers import extract_with_selectors, seconds_to_hhmmss

app = FastAPI(title="VK Video Scraper")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class ScrapeBody(BaseModel):
    urls: List[str]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
}
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

async def asyncio_gather_limited(client: httpx.AsyncClient, urls: List[str], limit: int = 5):
    sem = asyncio.Semaphore(limit)
    results: List[dict] = []

    async def run(u: str):
        async with sem:
            return await fetch(client, u)

    tasks = [asyncio.create_task(run(u)) for u in urls]
    for t in asyncio.as_completed(tasks):
        results.append(await t)
    return results

@app.post("/api/scrape")
async def api_scrape(body: ScrapeBody):
    urls = [u.strip() for u in body.urls if u and u.strip()]
    if not urls:
        return JSONResponse({"results": []})
    async with httpx.AsyncClient() as client:
        results = await asyncio_gather_limited(client, urls, limit=5)
    return JSONResponse({"results": results})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
