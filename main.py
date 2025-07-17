from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import asyncio
from playwright_check import check_telegram_url

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

class URLItem(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.post("/api/check")
async def check_url(item: URLItem):
    status = await check_telegram_url(item.url)
    return {"status": status}
