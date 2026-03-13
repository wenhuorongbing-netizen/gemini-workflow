import asyncio
from playwright.async_api import async_playwright
import os

async def verify_react_flow_ui():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("http://localhost:3000")

        await page.wait_for_timeout(3000) # Wait for initial hydration

        # Verify elements are visible
        is_canvas_visible = await page.locator(".react-flow__pane").is_visible()
        print(f"React Flow Canvas visible: {is_canvas_visible}")

        # Verify node toolbar buttons exist
        gemini_btn_visible = await page.locator("button:has-text('Gemini AI')").is_visible()
        scraper_btn_visible = await page.locator("button:has-text('Web Scraper')").is_visible()
        agent_btn_visible = await page.locator("button:has-text('Agent Loop')").is_visible()

        print(f"Gemini AI Button visible: {gemini_btn_visible}")
        print(f"Web Scraper Button visible: {scraper_btn_visible}")
        print(f"Agent Loop Button visible: {agent_btn_visible}")

        # Take screenshot for verification
        os.makedirs("/home/jules/verification", exist_ok=True)
        await page.screenshot(path="/home/jules/verification/react_flow_canvas.png", full_page=True)
        print("Screenshot saved to /home/jules/verification/react_flow_canvas.png")

        await browser.close()

        if is_canvas_visible and gemini_btn_visible and scraper_btn_visible and agent_btn_visible:
            print("SUCCESS: React Flow UI elements are present and visible.")
        else:
            print("FAILURE: React Flow UI elements are missing.")

if __name__ == "__main__":
    asyncio.run(verify_react_flow_ui())
