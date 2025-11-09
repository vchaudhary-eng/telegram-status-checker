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

from parsers import parse_vk_page, seconds_to_hhmmss

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


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

TIMEOUT = httpx.Timeout(25.0, connect=25.0)


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
        resp = await client.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        text = resp.text
        soup = BeautifulSoup(text, "lxml")

        data = parse_vk_page(soup, text)

        # map safely
        def put(key, out_key=None):
            v = data.get(key)
            if out_key is None:
                out_key = key
            if v is not None and v != "":
                result[out_key] = v

        put("title")
        put("duration_seconds")
        if isinstance(result["duration_seconds"], int):
            result["duration_hhmmss"] = seconds_to_hhmmss(result["duration_seconds"])
        put("views")
        put("upload_date")
        put("channel_url")
        put("channel_name")
        put("subscribers")

        result["status"] = "Success"
    except Exception as e:
        result["error"] = str(e)

    return result


async def gather_limited(urls: List[str], limit: int = 5):
    sem = asyncio.Semaphore(limit)
    results = []

    async with httpx.AsyncClient() as client:
        async def runner(u):
            async with sem:
                return await fetch_one(client, u)

        tasks = [asyncio.create_task(runner(u)) for u in urls]
        for t in asyncio.as_completed(tasks):
            results.append(await t)
    return results


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
