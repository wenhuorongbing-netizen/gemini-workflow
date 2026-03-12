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
        self.page: Optional[Page] = None
        self._initialized = False

    async def initialize(self):
        """Asynchronously initializes the browser context and opens Gemini."""
        if self._initialized:
            return

        try:
            self.playwright = await async_playwright().start()

            # Using persistent context to maintain login sessions
            # headless=False is recommended for first login, then it can be toggled
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.profile_path,
                headless=False, # Set to True after initial login for better performance
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
        Waits for the AI to finish generating the response.
        Instead of naive polling, it waits for the Send button to become enabled/visible again
        after the network activity settles down.
        """
        logging.info("Waiting for Gemini response...")
        try:
            # Wait a moment for generation to actually start
            await self.page.wait_for_timeout(3000)

            # Wait for the send button to become interactable again.
            # When generating, the send button is usually hidden or replaced by a 'Stop' button.
            send_button = self.page.locator("button[aria-label*='Send'], button:has-text('Send')").first

            # Playwright handles the polling efficiently internally
            await send_button.wait_for(state="visible", timeout=timeout)

            # Add a small buffer for DOM finalization
            await self.page.wait_for_timeout(2000)
            logging.info("Response generation appears complete.")
            return True

        except Exception as e:
            raise Exception(f"Timeout: Gemini did not finish responding within {timeout/1000} seconds. Error: {e}")

    async def get_last_response(self) -> str:
        """
        Extracts the generated response text from the DOM.
        """
        try:
            # Locate all response message containers
            response_containers = self.page.locator("message-content, div.message-content, div.model-response-text")
            count = await response_containers.count()

            if count > 0:
                last_response = response_containers.nth(count - 1)

                # Try to extract text from paragraphs for cleaner output
                paragraphs = last_response.locator("p")
                p_count = await paragraphs.count()

                if p_count > 0:
                    text_parts = []
                    for i in range(p_count):
                        text = await paragraphs.nth(i).inner_text()
                        if text.strip():
                            text_parts.append(text)
                    logging.info("Extracted response using heuristic paragraph parsing.")
                    return "\n\n".join(text_parts)
                else:
                    # Fallback to raw text
                    logging.info("Extracted response using raw text from response element.")
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
