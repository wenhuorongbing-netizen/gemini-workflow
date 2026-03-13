from playwright.sync_api import sync_playwright

def test_scraper_and_globals():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:5000", wait_until="networkidle")

        # Add a new workspace
        page.on("dialog", lambda dialog: dialog.accept("Data Ingestion Workspace"))
        page.click("button[title='New Workspace']")
        page.wait_for_timeout(500)

        # Set Step 1 to Scraper
        page.select_option("select#steptype-1", "scraper")
        page.wait_for_timeout(200)
        assert "URL to scrape" in page.locator("textarea#prompt-1").get_attribute("placeholder")

        # Click Global Vault button
        page.click("button:has-text('Global Vault')")
        page.wait_for_timeout(200)
        assert page.locator("#globals-modal").is_visible()

        # Add a global field
        page.click("button:has-text('+ Add Variable')")
        page.wait_for_timeout(200)

        # Fill fields
        keys = page.locator(".global-key")
        vals = page.locator(".global-val")

        # In case there were existing ones from previous tests, just grab the last one
        keys.nth(keys.count() - 1).fill("COMPANY_INFO")
        vals.nth(vals.count() - 1).fill("We are a SaaS startup")

        # Save
        page.click("button:has-text('Save Vault')")
        page.wait_for_timeout(200)
        assert not page.locator("#globals-modal").is_visible()

        # Check API persistence
        import urllib.request
        res = urllib.request.urlopen("http://localhost:5000/api/globals")
        import json
        data = json.loads(res.read().decode('utf-8'))
        assert data['COMPANY_INFO'] == "We are a SaaS startup"

        page.screenshot(path="scraper_globals_ui_verification.png")
        print("Scraper and Globals UI Test Passed! Screenshot saved.")
        browser.close()

if __name__ == "__main__":
    test_scraper_and_globals()
