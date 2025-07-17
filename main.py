from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import asyncio
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
import httpx

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


# Install browser if not present
async def ensure_browser_installed():
    if not Path("/usr/bin/google-chrome").exists():
        subprocess.run(["playwright", "install", "chromium", "--with-deps"], check=True)

asyncio.run(ensure_browser_installed())


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


async def check_telegram_status(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url)
            html = response.text.lower()
            if "username not found" in html or "this channel can't be displayed" in html:
                return "Suspended ❌"
            elif "message not found" in html or "message doesn't exist" in html:
                return "Removed ⚠️"
            elif "views" in html or "reactions" in html:
                return "Active ✅"
            else:
                return "Unknown ❓"
    except Exception as e:
        return f"Error ⛔"


@app.post("/check", response_class=HTMLResponse)
async def check(request: Request, urls: str = Form(...)):
    url_list = [u.strip() for u in urls.strip().splitlines() if u.strip()]
    results = []

    for url in url_list:
        status = await check_telegram_status(url)
        results.append((url, status))

    return templates.TemplateResponse("index.html", {"request": request, "results": results, "urls": urls})
