from playwright.async_api import async_playwright

async def check_telegram_url(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=10000)
            html = await page.content()

            if "USERNAME_NOT_OCCUPIED" in html or "username not found" in html:
                return "Suspended"
            elif "message doesn't exist" in html or "was deleted" in html:
                return "Removed"
            elif "message_views" in html or "Join Channel" in html:
                return "Active"
            else:
                return "Unknown"
        except:
            return "Error"
        finally:
            await browser.close()
