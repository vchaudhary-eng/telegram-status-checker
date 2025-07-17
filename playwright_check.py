from playwright.async_api import async_playwright

async def check_telegram_urls(urls):
    results = []

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()

        for url in urls:
            status = "Unknown"
            try:
                response = await page.goto(url, timeout=15000)
                content = await page.content()

                if "username not found" in content.lower() or "page not found" in content.lower():
                    status = "Suspended"
                elif "this channel can't be displayed" in content.lower():
                    status = "Suspended"
                elif "message not found" in content.lower() or "message does not exist" in content.lower():
                    status = "Removed"
                elif 'view-count' in content.lower():
                    status = "Active"
                elif response.status == 404:
                    status = "Removed"
                else:
                    status = "Active"
            except Exception as e:
                status = "Error"

            results.append({"url": url, "status": status})

        await browser.close()

    return results
