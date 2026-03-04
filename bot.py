import asyncio
import logging
from playwright.async_api import async_playwright, Page, BrowserContext
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class GeminiBot:
    def __init__(self, profile_path="chrome_profile", headless=False):
        """
        Initializes the Playwright bot using an asynchronous architecture.
        Utilizes persistent context to keep the user logged into their Google account.
        """
        self.profile_path = profile_path
        self.headless = headless
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._initialized = False

    async def initialize(self):
        """Asynchronously initializes the browser context and opens Gemini."""
        if self._initialized:
            return

        try:
            self.playwright = await async_playwright().start()

            # Using persistent context to maintain login sessions
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.profile_path,
                headless=self.headless,
                args=[
                    "--disable-infobars",
                    "--disable-extensions",
                    "--no-sandbox",
                    "--disable-dev-shm-usage"
                ]
            )

            # Use the first open page or create a new one
            pages = self.context.pages
            self.page = pages[0] if pages else await self.context.new_page()

            # ⚡ Bolt Optimization: Network Interception
            # We don't need to load images, fonts, or media to read/write text.
            # Aborting these requests drastically reduces bandwidth, memory, and TTFB.
            async def abort_heavy_assets(route):
                if route.request.resource_type in ["image", "media", "font"]:
                    await route.abort()
                else:
                    await route.continue_()

            await self.page.route("**/*", abort_heavy_assets)
            logging.info("Network interception active: blocking images, media, and fonts.")

            await self.page.goto("https://gemini.google.com/")
            logging.info("Playwright initialized and Gemini loaded successfully.")
            self._initialized = True

        except Exception as e:
            logging.error(f"Failed to initialize Playwright bot: {e}")
            raise

    async def upload_file(self, file_path: str):
        """
        Uploads a file to Gemini by injecting the file path into the hidden file input.
        """
        try:
            # Locate the file input element
            file_input = self.page.locator('input[type="file"]').first

            # Ensure it exists before proceeding
            await file_input.wait_for(state="attached", timeout=10000)

            # Set the file path to the input
            await file_input.set_input_files(file_path)
            logging.info(f"Injected file path: {file_path}")

            # Wait for upload to complete (heuristic: wait for progress bar to disappear)
            # Find the file attachment chip container that appears during upload
            attachment_chip = self.page.locator('file-attachment-chip').first

            # We first wait for it to become visible (upload starts)
            try:
                await attachment_chip.wait_for(state="visible", timeout=5000)
                logging.info("File upload started.")

                # We need to wait for a specific element that shows "loading" or a "progress bar" to go away,
                # or just wait for the progress ring to stop spinning
                progress_indicator = attachment_chip.locator('mat-progress-spinner')
                if await progress_indicator.is_visible():
                    await progress_indicator.wait_for(state="hidden", timeout=30000)

            except Exception:
                # If it doesn't appear, or we timeout, wait a fixed brief duration
                # as small files might upload too fast to catch the state
                await self.page.wait_for_timeout(2000)

            logging.info("File uploaded successfully.")

        except Exception as e:
            error_msg = f"Error uploading file: {e}"
            logging.error(error_msg)
            raise Exception(error_msg)

    async def start_new_chat(self):
        """
        Attempts to click the 'New Chat' button using user-facing locators.
        """
        try:
            # More robust locator strategy using ARIA roles and labels
            new_chat_button = self.page.locator("button, a").filter(has_text="New chat").first
            # Fallback to aria-label if text isn't explicitly 'New chat'
            if not await new_chat_button.is_visible():
                new_chat_button = self.page.get_by_label("New chat")

            await new_chat_button.click()
            logging.info("Clicked 'New Chat' button.")
            # Wait for network idle to ensure UI resets
            await self.page.wait_for_load_state("networkidle", timeout=5000)

        except Exception as e:
            logging.error(f"Error starting new chat (it might not be visible): {e}")

    async def send_prompt(self, prompt_text: str):
        """
        Locates the chat input box, enters the prompt, and clicks the send button.
        """
        try:
            # Find the main input area using a robust locator
            input_box = self.page.locator("div[role='textbox'], div[contenteditable='true']").first
            await input_box.wait_for(state="visible", timeout=15000)

            await input_box.fill(prompt_text)
            logging.info("Entered prompt text.")

            # Wait a brief moment for the send button to become active after typing
            await self.page.wait_for_timeout(500)

            # Find and click the send button
            send_button = self.page.locator("button[aria-label*='Send'], button:has-text('Send')").first
            await send_button.click()
            logging.info("Clicked 'Send' button.")

        except Exception as e:
            error_msg = "Cannot find the chat input box. Please ensure you are logged into Google Gemini."
            logging.error(f"{error_msg} - Details: {e}")
            raise Exception(error_msg)

    async def wait_for_response(self, timeout=300000):
        """
        Waits for the AI to finish generating the response with dual-state checking.
        """
        logging.info("Waiting for Gemini response...")

        start_time = asyncio.get_event_loop().time()

        try:
            # Wait a moment for generation to actually start
            await self.page.wait_for_timeout(3000)

            # Locators for checking state
            send_button = self.page.locator("button[aria-label*='Send'], button:has-text('Send')").first
            stop_button = self.page.locator("button[aria-label*='Stop'], button:has-text('Stop generating')").first
            error_box = self.page.locator("div:has-text('Something went wrong'), div.error-message").first

            while (asyncio.get_event_loop().time() - start_time) < (timeout / 1000.0):
                # Check for errors first
                if await error_box.is_visible():
                    error_text = await error_box.inner_text()
                    raise Exception(f"Gemini returned an error: {error_text}")

                # If send button is visible and stop button is NOT visible, we are done
                if await send_button.is_visible() and not await stop_button.is_visible():
                    # Add a small buffer for DOM finalization
                    await self.page.wait_for_timeout(2000)
                    logging.info("Response generation appears complete.")
                    return True

                # Polling interval
                await self.page.wait_for_timeout(1000)

            raise Exception(f"Timeout: Gemini did not finish responding within {timeout/1000} seconds.")

        except Exception as e:
            raise Exception(f"Error waiting for response: {e}")

    async def get_last_response(self) -> str:
        """
        Extracts the generated response text from the DOM, specifically looking
        for the element that contains formatted text, code blocks, and tables.
        """
        try:
            # Locate all response message containers
            # Using specific data-testid as requested for optimal extraction of code blocks and tables
            response_containers = self.page.locator('[data-testid="model-response-content"], message-content, div.message-content, div.model-response-text')
            count = await response_containers.count()

            if count > 0:
                last_response = response_containers.nth(count - 1)

                # Use evaluate to extract innerText directly, which preserves basic formatting
                # like newlines for code blocks better than simple inner_text() in some cases
                text_content = await last_response.evaluate("el => el.innerText")

                if text_content and text_content.strip():
                    logging.info("Extracted response using optimized text extraction.")
                    return text_content.strip()
                else:
                    logging.info("Extracted response was empty, trying fallback.")
                    return await last_response.inner_text()
            else:
                 logging.warning("Could not find specific response elements. Falling back to page body extraction.")
                 body_text = await self.page.inner_text("body")
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
