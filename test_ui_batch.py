from playwright.sync_api import sync_playwright

def test_batch_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:5000", wait_until="networkidle")

        # Select Batch Data List in Step 1
        page.select_option("select#steptype-1", "batch")
        page.wait_for_timeout(500)

        # Verify textarea placeholder changed
        textarea = page.locator("textarea#prompt-1")
        assert "Enter a list of items" in textarea.get_attribute("placeholder")

        # Add Step 2
        page.click("button:has-text('+ Add Step')")
        page.wait_for_timeout(500)

        # Verify {{CURRENT_ITEM}} button exists in Step 2 toolbar
        toolbar = page.locator("#toolbar-2")
        assert "+ {{CURRENT_ITEM}}" in toolbar.inner_text()

        # Click the {{CURRENT_ITEM}} button
        page.click("button:has-text('+ {{CURRENT_ITEM}}')")
        page.wait_for_timeout(200)

        # Verify it was inserted into step 2 textarea
        textarea2 = page.locator("textarea#prompt-2")
        assert "{{CURRENT_ITEM}}" in textarea2.input_value()

        # Take screenshot
        page.screenshot(path="batch_ui_verification.png")
        print("Batch UI Test Passed! Screenshot saved.")
        browser.close()

if __name__ == "__main__":
    test_batch_ui()
