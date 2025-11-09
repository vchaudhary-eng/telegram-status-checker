from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Any, Dict
import httpx
import asyncio

from parsers import parse_vk_page, pack_response_fields

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
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    # Russian first, then English improves chances to get Russian dates/labels
    "Accept-Language": "ru,en;q=0.9,en-US;q=0.8",
}
TIMEOUT = httpx.Timeout(25.0, connect=25.0)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


async def fetch_one(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
    base = {
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
        html = r.text
        parsed = parse_vk_page(html)
        packed = pack_response_fields(parsed)
        base.update(packed)
        base["status"] = "Success"
    except Exception as e:
        base["error"] = str(e)
    return base


async def gather_limited(urls: List[str], limit: int = 5) -> List[Dict[str, Any]]:
    sem = asyncio.Semaphore(limit)
    out: List[Dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        async def run(u):
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
    results = await gather_limited(urls, limit=5)
    return JSONResponse({"results": results})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
