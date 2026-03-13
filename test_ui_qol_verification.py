from playwright.sync_api import sync_playwright
import time
import subprocess
import threading
import sys

def run_server():
    import uvicorn
    import app
    uvicorn.run(app.app, host="127.0.0.1", port=8000, log_level="error")

def test_ui():
    print("Starting server...")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(3)  # Wait for server to start

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Navigating to app...")
        page.goto("http://127.0.0.1:8000")

        # Add a couple steps
        print("Adding steps...")
        page.click("text=+ Add Step")
        page.click("text=+ Add Step")

        # Collapse step 1
        print("Testing step collapse...")
        page.click("#chevron-1")
        assert page.locator("#stepbody-1").is_hidden()

        # Test visual picker on step 2
        print("Testing variable picker...")
        page.locator("#toolbar-2").locator("button:has-text('[ { } Insert Variable ]')").click()
        page.wait_for_selector("text={{OUTPUT_1}}", timeout=5000)
        assert page.locator("text={{OUTPUT_1}}").is_visible()

        page.click("text={{OUTPUT_1}}")
        prompt_val = page.locator("#prompt-2").input_value()
        assert "{{OUTPUT_1}}" in prompt_val

        print("Taking screenshot...")
        page.screenshot(path="ui_verification_qol.png")

        print("Test passed successfully!")
        browser.close()

if __name__ == "__main__":
    test_ui()
