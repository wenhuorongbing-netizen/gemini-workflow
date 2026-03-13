from playwright.sync_api import sync_playwright

def test_headless_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:5000", wait_until="networkidle")

        # Find Headless Toggle
        toggle = page.locator("#headless-toggle")
        assert toggle.is_visible()

        # Click it
        toggle.check()
        page.wait_for_timeout(500)

        # Check API persistence
        import urllib.request
        res = urllib.request.urlopen("http://localhost:5000/api/settings/headless")
        import json
        data = json.loads(res.read().decode('utf-8'))
        assert data['headless'] == True

        # Take screenshot to prove it's rendered properly
        page.screenshot(path="headless_ui_verification.png")
        print("Headless UI Test Passed! Screenshot saved.")
        browser.close()

if __name__ == "__main__":
    test_headless_ui()
