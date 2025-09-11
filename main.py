from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/scrape")
async def scrape(url: str = Form(...)):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            soup = BeautifulSoup(resp.text, "html.parser")
            meta_desc = soup.find("meta", attrs={"name": "description"}) or \
                        soup.find("meta", attrs={"property": "og:description"})
            description = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else "No description found"
            return JSONResponse({"url": url, "description": description})
    except Exception as e:
        return JSONResponse({"url": url, "description": f"Error: {str(e)}"})
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000)
