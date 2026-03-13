from playwright.sync_api import sync_playwright

def test_advanced_nodes_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:5000")
        page.wait_for_load_state('networkidle')

        # Add a new workspace to ensure clean state
        page.on("dialog", lambda dialog: dialog.accept("Advanced Node Test Workspace"))
        page.click("button[title='New Workspace']")
        page.wait_for_timeout(1000)

        # Add a step if not exists
        if not page.locator("select#steptype-1").is_visible():
            page.click("button:has-text('+ Add Step')")
            page.wait_for_timeout(500)

        # Verify Approval and Logic nodes in the dropdown
        page.select_option("select#steptype-1", "approval")
        page.wait_for_timeout(200)
        textarea = page.locator("textarea#prompt-1")
        assert "Approval notes" in textarea.get_attribute("placeholder")

        page.select_option("select#steptype-1", "logic")
        page.wait_for_timeout(200)
        ph = textarea.get_attribute("placeholder")
        assert "GOTO STEP 5" in ph

        page.select_option("select#steptype-1", "python")
        page.wait_for_timeout(200)
        assert "Write Python code here" in textarea.get_attribute("placeholder")

        # Verify 'Important' checkbox
        important_checkbox = page.locator("label:has-text('⭐ Important')")
        assert important_checkbox.is_visible()

        # Unhide the results container to check tabs
        page.evaluate("document.getElementById('results-container').style.display = 'block';")

        # Check tabs exist
        assert page.locator(".result-tab:has-text('Summary Dashboard')").is_visible()

        # Take screenshot to prove it's rendered properly
        page.screenshot(path="advanced_nodes_ui_verification.png")
        print("Advanced Nodes UI Test Passed! Screenshot saved.")
        browser.close()

if __name__ == "__main__":
    test_advanced_nodes_ui()
