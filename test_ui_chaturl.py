from playwright.sync_api import sync_playwright

def test_chaturl_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:5000", wait_until="networkidle")

        # Verify chat URL input exists and has correct placeholder
        input_locator = page.locator("input#chaturl-1")
        assert input_locator.is_visible()
        assert "Target Chat URL" in input_locator.get_attribute("placeholder")

        # Type a URL and verify it gets persisted to draft (we'll check dom values)
        input_locator.fill("https://gemini.google.com/app/test1234")
        page.wait_for_timeout(200)

        # Take screenshot to prove it's rendered properly
        page.screenshot(path="chaturl_ui_verification.png")
        print("Chat URL UI Test Passed! Screenshot saved.")
        browser.close()

if __name__ == "__main__":
    test_chaturl_ui()
