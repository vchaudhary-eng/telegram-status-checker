from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncio
from playwright.async_api import async_playwright
from typing import List
import re

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/check", response_class=HTMLResponse)
async def check_telegram(request: Request, urls: str = Form(...)):
    url_list = [url.strip() for url in urls.splitlines() if url.strip()]
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        for url in url_list:
            try:
                await page.goto(url, timeout=15000)
                content = await page.content()

                if "This channel can't be displayed" in content or "is unavailable" in content:
                    status = "Suspended"
                elif "message was deleted" in content or "This message doesn't exist" in content:
                    status = "Removed"
                elif "views" in content or "reactions" in content:
                    status = "Active"
                else:
                    status = "Unknown"
            except Exception:
                status = "Error"
            results.append((url, status))

        await browser.close()

    return templates.TemplateResponse("index.html", {"request": request, "results": results})
