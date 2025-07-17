from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
import os

from playwright_check import check_telegram_urls

app = FastAPI()

# Enable CORS (for local frontend testing or deployment issues)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTML templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/verify")
async def verify_links(request: Request):
    data = await request.json()
    urls = data.get("urls", [])

    if not urls or not isinstance(urls, list):
        return JSONResponse(status_code=400, content={"error": "Invalid or missing 'urls' list."})

    results = await check_telegram_urls(urls)
    return {"results": results}
