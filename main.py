from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from playwright.async_api import async_playwright

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/check", response_class=HTMLResponse)
async def check(request: Request, urls: str = Form(...)):
    url_list = [u.strip() for u in urls.splitlines() if u.strip()]
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        for url in url_list:
            try:
                await page.goto(url, timeout=15000)
                content = await page.content()

                if "this channel can’t be displayed" in content.lower():
                    status = "Suspended"
                elif "message not found" in content.lower() or "message doesn't exist" in content.lower():
                    status = "Removed"
                elif "views" in content.lower():
                    status = "Active"
                else:
                    status = "Unknown"
            except:
                status = "Error"
            results.append((url, status))
        await browser.close()

    return templates.TemplateResponse("index.html", {"request": request, "results": results})
