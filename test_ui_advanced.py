from playwright.sync_api import sync_playwright

def test_advanced():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:5000", wait_until="networkidle")

        # Click Terminal button
        page.click("button:has-text('>_ Terminal')")
        page.wait_for_timeout(200)
        assert page.locator("#logs-modal").is_visible()

        # Verify it loaded logs (or says none)
        logs = page.locator("#logs-container").inner_text()
        assert len(logs) > 0

        # Close logs
        page.click("#logs-modal button:has-text('×')")

        # Add a new workspace
        page.on("dialog", lambda dialog: dialog.accept("Correction Test Workspace"))
        page.click("button[title='New Workspace']")
        page.wait_for_timeout(1000)

        # Check profile selector exists
        assert page.locator("#profile-selector").is_visible()

        # Check Self Correction node placeholder
        page.select_option("select#steptype-1", "correction")
        page.wait_for_timeout(200)
        assert "PROMPT: " in page.locator("textarea#prompt-1").get_attribute("placeholder")

        page.screenshot(path="enterprise_ui_verification.png")
        print("Enterprise UI Test Passed! Screenshot saved.")
        browser.close()

if __name__ == "__main__":
    test_advanced()
