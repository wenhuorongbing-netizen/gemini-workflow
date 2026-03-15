from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:3000")
    page.wait_for_load_state("networkidle")

    page.once("dialog", lambda dialog: dialog.accept("My Test Emtpy Workspace"))
    page.get_by_text("+ New Workspace").click()
    page.wait_for_timeout(2000)

    # Dump the DOM so we can see what elements exist
    print(page.content())
    browser.close()
