from playwright.sync_api import sync_playwright

def test_platform_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:5000", wait_until="networkidle")

        # Test Template Library Button
        page.click("button:has-text('Template Library')")
        page.wait_for_timeout(200)
        assert page.locator("#template-library-modal").is_visible()
        page.click("#template-library-modal button:has-text('Close')")

        # Test Save as Template Button
        assert page.locator("button:has-text('Save as Template')").is_visible()

        # Check Time Machine Dropdown
        page.click("button#btn-dashboard-view")
        page.wait_for_timeout(200)
        assert page.locator("select#history-selector").is_visible()

        # Test Webhook Step Placeholder
        page.click("button#btn-editor-view")
        page.wait_for_timeout(200)

        # Add a new workspace
        page.on("dialog", lambda dialog: dialog.accept("Webhook Test Workspace"))
        page.click("button[title='New Workspace']")
        page.wait_for_timeout(1000)

        if not page.locator("select#steptype-1").is_visible():
            page.click("button:has-text('+ Add Step')")
            page.wait_for_timeout(500)

        page.select_option("select#steptype-1", "webhook")
        page.wait_for_timeout(200)

        ph = page.locator("textarea#prompt-1").get_attribute("placeholder")
        assert '"text":' in ph

        page.screenshot(path="platform_ui_verification.png", full_page=True)
        print("Platform UI Test Passed! Screenshot saved.")
        browser.close()

if __name__ == "__main__":
    test_platform_ui()
