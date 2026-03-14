import asyncio
from playwright.async_api import async_playwright
import json

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("http://localhost:3000")
        await asyncio.sleep(2)

        # Add a node
        await page.click("button:has-text('Standard Node')")
        await asyncio.sleep(1)

        # Select node and set prompt
        nodes = await page.locator(".react-flow__node").all()
        await nodes[-1].click()
        await asyncio.sleep(1)

        prompt_textarea = page.locator("textarea[placeholder='Enter prompt for this step...']")
        await prompt_textarea.fill("output = 'Hello async queue'")

        type_select = page.locator("select").nth(0) # First select should be node type in properties
        await type_select.select_option("python")
        await asyncio.sleep(1)

        # Run workflow
        await page.click("button:has-text('Run')")

        # Wait for completion
        await page.wait_for_selector("text=Workflow Finished", timeout=15000)

        # Verify result in node
        node_text = await nodes[-1].inner_text()
        print("Final Node Text:")
        print(node_text)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
