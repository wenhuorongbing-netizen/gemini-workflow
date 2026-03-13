import asyncio
import logging
from playwright.async_api import async_playwright, Page, BrowserContext
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler("gemini_workflow_error.log"),
        logging.StreamHandler()
    ]
)

class GeminiBot:
    def __init__(self, profile_path="chrome_profile"):
        """
        Initializes the Playwright bot using an asynchronous architecture.
        Utilizes persistent context to keep the user logged into their Google account.
        """
        self.profile_path = profile_path
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self._initialized = False

    async def initialize(self, headless=False):
        """Asynchronously initializes the browser context and opens Gemini."""
        if self._initialized:
            return

        try:
            self.playwright = await async_playwright().start()

            # Using persistent context to maintain login sessions
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.profile_path,
                headless=headless,
                args=[
                    "--disable-infobars",
                    "--disable-extensions",
                    "--no-sandbox",
                    "--disable-dev-shm-usage"
                ]
            )

            logging.info(f"Playwright initialized (headless={headless}).")
            self._initialized = True

        except Exception as e:
            logging.error(f"Failed to initialize Playwright bot: {e}")
            raise

    async def create_new_page(self) -> Page:
        """Asynchronously creates a new page and navigates to Gemini."""
        page = await self.context.new_page()

        # ⚡ Bolt Optimization: Network Interception
        # We don't need to load images, fonts, or media to read/write text.
        # Aborting these requests drastically reduces bandwidth, memory, and TTFB.
        async def abort_heavy_assets(route):
            if route.request.resource_type in ["image", "media", "font"]:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", abort_heavy_assets)
        logging.info("Network interception active: blocking images, media, and fonts.")

        await page.goto("https://gemini.google.com/")
        logging.info("Gemini loaded successfully on new page.")
        return page

    async def start_new_chat(self, page: Page):
        """
        Attempts to click the 'New Chat' button using user-facing locators.
        """
        try:
            # More robust locator strategy using ARIA roles and labels
            new_chat_button = page.locator("button, a").filter(has_text="New chat").first
            # Fallback to aria-label if text isn't explicitly 'New chat'
            if not await new_chat_button.is_visible():
                new_chat_button = page.get_by_label("New chat")

            await new_chat_button.click()
            logging.info("Clicked 'New Chat' button.")
            # Wait for network idle to ensure UI resets
            await page.wait_for_load_state("networkidle", timeout=5000)

        except Exception as e:
            logging.error(f"Error starting new chat (it might not be visible): {e}")

    async def scrape_url(self, page: Page, url: str) -> str:
        """
        Navigates to a URL and extracts its main textual content.
        """
        try:
            logging.info(f"Scraping URL: {url}")
            await page.goto(url, wait_until="domcontentloaded")

            # Try to grab the main article first for cleaner text, fallback to body
            article = page.locator("article").first
            if await article.is_visible():
                return await article.inner_text()

            body = page.locator("body")
            if await body.is_visible():
                return await body.inner_text()

            return "No readable content found on this page."

        except Exception as e:
            error_msg = f"Failed to scrape URL {url}."
            logging.error(f"{error_msg} - Details: {e}")
            raise Exception(error_msg)

    async def goto_specific_chat(self, page: Page, url: str):
        """
        Navigates to a specific chat URL and waits for the input box to be visible.
        """
        try:
            logging.info(f"Navigating to specific chat URL: {url}")
            await page.goto(url)

            # Wait for the chat to load completely by checking the input box
            input_box = page.locator("div[role='textbox']").first
            await input_box.wait_for(state="visible", timeout=20000)
            logging.info("Specific chat loaded successfully.")

        except Exception as e:
            error_msg = f"Failed to load specific chat URL {url}. Ensure it is a valid Gemini chat."
            logging.error(f"{error_msg} - Details: {e}")
            raise Exception(error_msg)

    async def send_prompt(self, page: Page, prompt_text: str):
        """
        Locates the chat input box, enters the prompt, and clicks the send button.
        """
        try:
            # Find the main input area using a robust locator
            input_box = page.locator("div[role='textbox']").first
            await input_box.wait_for(state="visible", timeout=15000)

            await input_box.fill(prompt_text)
            logging.info("Entered prompt text.")

            # Wait a brief moment for the send button to become active after typing
            await page.wait_for_timeout(500)

            # Find and click the send button
            send_button = page.get_by_role("button", name="Send").first
            await send_button.click()
            logging.info("Clicked 'Send' button.")

        except Exception as e:
            error_msg = "Cannot find the chat input box. Please ensure you are logged into Google Gemini."
            logging.error(f"{error_msg} - Details: {e}")
            raise Exception(error_msg)

    async def wait_for_response(self, page: Page, timeout=300000, poll_callback=None):
        """
        Waits for the AI to finish generating the response.
        Polls the DOM for pseudo-streaming updates if poll_callback is provided.
        """
        logging.info("Waiting for Gemini response...")
        try:
            # Wait a moment for generation to actually start
            await page.wait_for_timeout(3000)

            # Wait for the send button to become interactable again.
            send_button = page.get_by_role("button", name="Send").first

            # If a callback is provided, we poll while waiting for the send button
            if poll_callback:
                import time
                start_time = time.time()
                while not await send_button.is_visible():
                    if time.time() - start_time > timeout / 1000:
                        raise Exception("Timeout exceeded during polling.")

                    try:
                        # Attempt to extract partial text
                        partial_text = await self.get_last_response(page)
                        if partial_text:
                            await poll_callback(partial_text)
                    except Exception as poll_e:
                        logging.debug(f"Polling partial text failed (normal if generation just started): {poll_e}")

                    # Wait 1 second before polling again, but check if send_button became visible during that second
                    try:
                        await send_button.wait_for(state="visible", timeout=1000)
                        break # Button appeared, we are done
                    except Exception:
                        pass # Not visible yet, loop again
            else:
                # Playwright handles the polling efficiently internally
                await send_button.wait_for(state="visible", timeout=timeout)

            # Add a small buffer for DOM finalization
            await page.wait_for_timeout(2000)
            logging.info("Response generation appears complete.")
            return True

        except Exception as e:
            raise Exception(f"Timeout: Gemini did not finish responding within {timeout/1000} seconds. Error: {e}")

    async def prompt_jules_and_poll(self, page: Page, target_url: str, prompt: str) -> str:
        """
        Navigates to the Jules interface, submits a prompt, and polls for completion.
        Returns the final extracted result/branch link.
        """
        try:
            logging.info(f"Navigating to Jules target URL: {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded")

            # Find Jules input box
            input_box = page.locator("textarea").first
            await input_box.wait_for(state="visible", timeout=20000)
            await input_box.fill(prompt)
            logging.info("Entered prompt into Jules.")

            # Press enter to submit
            await page.keyboard.press("Enter")
            logging.info("Submitted prompt to Jules.")

            # Polling loop
            logging.info("Polling Jules for 'Ready for review'...")
            max_polls = 60 # 10 minutes max (60 * 10s)
            poll_count = 0

            while poll_count < max_polls:
                await asyncio.sleep(10)
                poll_count += 1

                # Check for completion text
                if await page.locator("text='Ready for review'").is_visible():
                    logging.info("Jules reported 'Ready for review'.")

                    # Extract the latest response from Jules
                    # We assume it's in the DOM, potentially as a link or last text block
                    # A robust generic fallback:
                    body_text = await page.inner_text("body")
                    # Try to extract a branch link if present
                    import re
                    match = re.search(r'(https://github\.com/\S+/tree/\S+)', body_text)
                    if match:
                        return f"Jules finished. Branch link: {match.group(1)}"
                    return "Jules finished successfully. Status: Ready for review."

            raise Exception("Timeout waiting for Jules to complete task.")

        except Exception as e:
            error_msg = f"Error during Jules agent loop: {e}"
            logging.error(error_msg)
            raise Exception(error_msg)

    async def get_last_response(self, page: Page) -> str:
        """
        Extracts the generated response text from the DOM.
        """
        try:
            # Locate all response message containers
            response_containers = page.locator('[data-testid="model-response-content"]')
            count = await response_containers.count()

            if count > 0:
                last_response = response_containers.nth(count - 1)
                # Fallback to raw text
                logging.info("Extracted response using inner_text from response element.")
                return await last_response.inner_text()
            else:
                 logging.warning("Could not find specific response elements. Falling back to page body extraction.")
                 body_text = await page.inner_text("body")
                 return body_text[-2000:]

        except Exception as e:
             logging.error(f"Error extracting response: {e}")
             raise Exception(f"Failed to extract text from DOM: {e}")

    async def quit(self):
        """Closes the browser."""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        logging.info("Browser closed.")
