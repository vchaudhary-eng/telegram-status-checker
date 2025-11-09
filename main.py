from typing import List, Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import httpx

from parsers import parse_vk, normalize_url

# --------------------------- app -----------------------------

app = FastAPI(title="VK Video Scraper")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    # VK often serves ru locale; adding Accept-Language improves hit rate
    "Accept-Language": "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
}
TIMEOUT = httpx.Timeout(25.0, connect=25.0)

class ScrapeBody(BaseModel):
    urls: List[str]

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

async def fetch_one(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    u = normalize_url(url)
    out = {
        "input_url": u, "title": "N/A",
        "duration_seconds": "N/A", "duration_hhmmss": "N/A",
        "views": "N/A", "upload_date": "N/A",
        "channel_url": "N/A", "channel_name": "N/A", "subscribers": "N/A",
        "status": "Error", "error": None
    }
    try:
        resp = await client.get(u, headers=HEADERS, follow_redirects=True, timeout=TIMEOUT)
        html = resp.text
        data = parse_vk(html, u)
        out.update(data)
    except Exception as e:
        out["error"] = str(e)
    return out

import asyncio

async def gather_limited(urls: List[str], limit: int = 5) -> List[dict]:
    sem = asyncio.Semaphore(limit)
    async with httpx.AsyncClient() as client:
        async def run(u):
            async with sem:
                return await fetch_one(client, u)
        tasks = [asyncio.create_task(run(u)) for u in urls]
        results: List[dict] = []
        for t in asyncio.as_completed(tasks):
            results.append(await t)
        return results

@app.post("/api/scrape")
async def api_scrape(body: ScrapeBody):
    urls = [u for u in (body.urls or []) if u and u.strip()]
    if not urls:
        return JSONResponse({"results": []})
    results = await gather_limited(urls, limit=5)
    return JSONResponse({"results": results})

# local dev
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
