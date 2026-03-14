import pytest
from playwright.sync_api import sync_playwright
import time

def test_happy_path_gemini():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:3000")
        page.wait_for_timeout(4000)

        # 1. Click New Workspace
        page.get_by_text("+ New Workspace").click()
        page.wait_for_timeout(1000)

        # 2. Add Gemini AI Node
        page.get_by_text("Gemini AI").click()
        page.wait_for_timeout(1000)

        # 3. Enter Prompt
        page.locator(".react-flow__node").first.click()
        page.wait_for_timeout(1000)
        page.locator("textarea[placeholder='Prompt instructions...']").fill("Say exactly 'HELLO WORLD'")

        # 4. Run Workflow
        page.get_by_text("▶ Run Workflow").click()

        # 5. Wait for success
        page.wait_for_timeout(15000)

        logs = page.locator(".flex-1.overflow-y-auto").text_content()
        assert "[Complete]" in logs or "[Workflow Finished]" in logs, "Workflow did not finish successfully."

        browser.close()

def test_circular_dependency():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:3000")
        page.wait_for_timeout(4000)

        page.get_by_text("+ New Workspace").click()
        page.wait_for_timeout(1000)

        page.get_by_text("Gemini AI").click()
        page.wait_for_timeout(1000)
        page.get_by_text("Gemini AI").click()
        page.wait_for_timeout(1000)

        # Drag connection A -> B
        nodes = page.locator(".react-flow__node").all()
        assert len(nodes) == 2

        # Source handle of node 1
        handle_source_1 = nodes[0].locator(".react-flow__handle-bottom")
        # Target handle of node 2
        handle_target_2 = nodes[1].locator(".react-flow__handle-top")

        handle_source_1.drag_to(handle_target_2)
        page.wait_for_timeout(500)

        # Drag connection B -> A
        handle_source_2 = nodes[1].locator(".react-flow__handle-bottom")
        handle_target_1 = nodes[0].locator(".react-flow__handle-top")

        handle_source_2.drag_to(handle_target_1)
        page.wait_for_timeout(500)

        # Try to Run
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_text("▶ Run Workflow").click()
        page.wait_for_timeout(1000)

        # The alert should have been handled, and workflow shouldn't run.
        # Check if "Executing..." is visible
        run_btn = page.get_by_text("Executing...")
        assert not run_btn.is_visible(), "Workflow should not start with circular dependency."

        browser.close()

def test_invalid_url():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:3000")
        page.wait_for_timeout(4000)

        page.get_by_text("+ New Workspace").click()
        page.wait_for_timeout(1000)

        page.get_by_text("Web Scraper").click()
        page.wait_for_timeout(1000)

        page.locator(".react-flow__node").first.click()
        page.wait_for_timeout(1000)

        # Type invalid URL
        page.locator("input[placeholder='https://example.com']").fill("github.com")

        # Check for warning text
        warning = page.get_by_text("⚠️ Must start with http:// or https://")
        assert warning.is_visible(), "URL validation warning not shown."

        browser.close()

def test_empty_canvas():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:3000")
        page.wait_for_timeout(4000)

        page.get_by_text("+ New Workspace").click()
        page.wait_for_timeout(1000)

        # Do not add any nodes

        # Click run
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_text("▶ Run Workflow").click()
        page.wait_for_timeout(1000)

        # Check if executing
        run_btn = page.get_by_text("Executing...")
        assert not run_btn.is_visible(), "Workflow should not run with empty canvas."

        browser.close()
