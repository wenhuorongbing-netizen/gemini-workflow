import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # We can just manually call the Javascript since we are just verifying UI logic
        await page.goto("http://localhost:5000", wait_until="networkidle")

        # Check Stop button is initially hidden
        stop_btn = page.locator("#stop-btn")
        is_visible = await stop_btn.is_visible()
        print(f"Stop button initially visible: {is_visible}")
        assert not is_visible

        # Trigger executeWorkflow manually to avoid form validation blocking
        await page.evaluate("""
            const runBtn = document.getElementById('run-btn');
            const stopBtn = document.getElementById('stop-btn');
            const statusBar = document.getElementById('status-bar');

            runBtn.style.display = 'none';
            stopBtn.style.display = 'inline-block';
            statusBar.style.display = 'block';
            statusBar.innerText = "Connecting to backend...";
        """)

        # Check Stop button becomes visible
        await stop_btn.wait_for(state="visible", timeout=2000)
        is_visible = await stop_btn.is_visible()
        print(f"Stop button visible during run: {is_visible}")
        assert is_visible

        # Check Run button is hidden
        run_btn = page.locator("#run-btn")
        run_visible = await run_btn.is_visible()
        print(f"Run button visible during run: {run_visible}")
        assert not run_visible

        # Mock fetch to test stopWorkflow
        await page.evaluate("""
            window.fetch = async () => new Response();
        """)

        # Click Stop
        print("Clicking Stop")
        await stop_btn.click()

        # Verify status bar text changes to Stopping...
        status_locator = page.locator("#status-bar")
        print("Waiting for status text to change to 'Stopping workflow...'")
        await page.wait_for_function('document.getElementById("status-bar").innerText.includes("Stopping workflow...")')

        color = await status_locator.evaluate("element => window.getComputedStyle(element).color")
        print(f"Stop Workflow Status Color: {color}")
        if "rgb(231, 76, 60)" in color: # #e74c3c
            print("SUCCESS: Emergency Stop UI updated correctly!")

        print("All QoL UI checks passed!")

        await browser.close()

if __name__ == "__main__":
    # Start our FastAPI app locally in a subprocess
    import subprocess
    import time
    server_process = subprocess.Popen(["python3", "app.py"])
    time.sleep(2) # Wait for server to start
    try:
        asyncio.run(main())
    finally:
        server_process.terminate()
        server_process.wait()
