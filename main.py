from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Any
import httpx
from bs4 import BeautifulSoup
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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
}
TIMEOUT = httpx.Timeout(25.0, connect=20.0)

class ScrapeBody(BaseModel):
    urls: List[str]

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

async def fetch_one(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
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
        r = await client.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        text = r.text
        soup = BeautifulSoup(text, "lxml")

        d = extract_with_selectors(soup, text)

        if d.get("title"):
            result["title"] = d["title"]
        if isinstance(d.get("duration_seconds"), int):
            result["duration_seconds"] = d["duration_seconds"]
            result["duration_hhmmss"] = seconds_to_hhmmss(d["duration_seconds"])
        if isinstance(d.get("views"), int):
            result["views"] = d["views"]
        if d.get("upload_date"):
            result["upload_date"] = d["upload_date"]
        if d.get("channel_url"):
            result["channel_url"] = d["channel_url"]
        if d.get("channel_name"):
            result["channel_name"] = d["channel_name"]
        if isinstance(d.get("subscribers"), int):
            result["subscribers"] = d["subscribers"]

        result["status"] = "Success"
    except Exception as e:
        result["error"] = str(e)
    return result

async def gather_limited(client: httpx.AsyncClient, urls: List[str], limit: int = 5):
    sem = asyncio.Semaphore(limit)
    out = []

    async def run(u: str):
        async with sem:
            return await fetch_one(client, u)

    tasks = [asyncio.create_task(run(u)) for u in urls]
    for t in asyncio.as_completed(tasks):
        out.append(await t)
    return out

@app.post("/api/scrape")
async def api_scrape(body: ScrapeBody):
    urls = [u.strip() for u in body.urls if u and u.strip()]
    if not urls:
        return JSONResponse({"results": []})

    async with httpx.AsyncClient() as client:
        results = await gather_limited(client, urls, limit=5)
    return JSONResponse({"results": results})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
