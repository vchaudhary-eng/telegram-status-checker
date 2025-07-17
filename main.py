from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from playwright.async_api import async_playwright

app = FastAPI()

# CORS allow all
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class URLList(BaseModel):
    urls: List[str]

@app.post("/api/verify")
async def verify_urls(data: URLList):
    results = []

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        for url in data.urls:
            try:
                response = await page.goto(url, timeout=15000)
                content = await page.content()

                if 'If you have <strong>Telegram</strong>' in content:
                    status = "Suspended"
                elif 'message cannot be displayed' in content:
                    status = "Removed"
                elif 'This channel can’t be displayed' in content:
                    status = "Suspended"
                elif 'views' in content:
                    status = "Active"
                else:
                    status = "Dead"
            except:
                status = "Error"
            results.append({"url": url, "status": status})

        await browser.close()
    return {"results": results}
