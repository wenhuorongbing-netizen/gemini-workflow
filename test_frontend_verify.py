import asyncio
from playwright.async_api import async_playwright
import time
import subprocess

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("http://localhost:5000", wait_until="networkidle")

        # Take initial screenshot
        await page.screenshot(path="initial_ui.png")

        # Click the add step button to add a second step
        await page.click(".btn-add")
        await page.wait_for_timeout(500)

        # Click the collapse button on the first step
        await page.click("#step-1 .collapse-btn")
        await page.wait_for_timeout(500)

        # Take screenshot of collapsed step
        await page.screenshot(path="collapsed_ui.png")

        # Open variable picker on second step
        await page.click("#toolbar-2 button")
        await page.wait_for_timeout(500)

        # Take screenshot of variable picker dropdown
        await page.screenshot(path="dropdown_ui.png")

        # Click on "Step 1 Output"
        await page.click("text='📄 Step 1 Output'")
        await page.wait_for_timeout(500)

        # Take screenshot of populated textarea
        await page.screenshot(path="populated_ui.png")

        await browser.close()

if __name__ == "__main__":
    server_process = subprocess.Popen(["python3", "app.py"])
    time.sleep(3)
    try:
        asyncio.run(main())
    finally:
        server_process.terminate()
        server_process.wait()
