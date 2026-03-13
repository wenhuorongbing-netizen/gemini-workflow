from playwright.sync_api import sync_playwright

def test_show_result_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:5000", wait_until="networkidle")

        # Verify show result checkbox exists and is checked by default
        checkbox_locator = page.locator("input#show-result-1")
        assert checkbox_locator.is_visible()
        assert checkbox_locator.is_checked()

        # Uncheck it
        checkbox_locator.uncheck()
        page.wait_for_timeout(200)
        assert not checkbox_locator.is_checked()

        # Take screenshot to prove it's rendered properly
        page.screenshot(path="showresult_ui_verification.png")
        print("Show Result UI Test Passed! Screenshot saved.")
        browser.close()

if __name__ == "__main__":
    test_show_result_ui()
