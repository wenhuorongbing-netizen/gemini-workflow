import asyncio
import logging
import playwright
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

    async def send_prompt(self, page: Page, prompt_text: str, attachments=None, model=None):
        """
        Locates the chat input box, enters the prompt, and clicks the send button.
        """
        try:
            if model and model != "Auto":
                try:
                    # Attempt to click the top-left model selector
                    # This relies on standard UI structures, which may be fragile
                    model_btn = page.locator("button[aria-label*='model']").first
                    if await model_btn.is_visible():
                        await model_btn.click()
                        await page.wait_for_timeout(500)
                        await page.get_by_text(model, exact=False).first.click()
                        logging.info(f"Selected model: {model}")
                        await page.wait_for_timeout(500)
                except Exception as e:
                    logging.warning(f"Could not select model '{model}'. Defaulting. Error: {e}")

            if attachments:
                try:
                    # Click the '+' icon to reveal upload
                    plus_icon = page.locator("button[aria-label*='Upload image']").first
                    if await plus_icon.is_visible():
                        # Use set_input_files on the actual input element, often hidden
                        file_input = page.locator("input[type='file']").first
                        await file_input.set_input_files(attachments)
                        logging.info(f"Uploaded attachments: {attachments}")

                        # Wait for Google Gemini's file attachment thumbnail chip to appear before proceeding
                        # This prevents the 'race condition' of clicking send before the file finishes uploading
                        file_chip = page.locator("file-attachment-chip, div[data-test-id='uploaded-file']").first
                        try:
                            # Wait for at least one thumbnail indicating a successful upload
                            await page.wait_for_selector("file-attachment-chip, div[data-test-id='uploaded-file']", timeout=30000)
                            logging.info("Attachment thumbnail appeared, upload complete.")
                        except Exception as chip_e:
                            logging.warning("File chip didn't appear conventionally, falling back to progress bar wait.")
                            await page.wait_for_timeout(2000)
                            progress_bar = page.locator("progress, [role='progressbar']")
                            if await progress_bar.count() > 0:
                                await progress_bar.first.wait_for(state='hidden', timeout=30000)
                        await page.wait_for_timeout(1000) # Final safety buffer
                except Exception as e:
                    logging.error(f"Failed to upload attachment: {e}")

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

        except playwright.async_api.TimeoutError as te:
            if "TargetClosedError" in str(te) or "Browser closed" in str(te):
                raise Exception("💥 内存过载，系统正在为您自动重置环境...")
            raise Exception("[ERROR] 网页响应超时，已跳过此节点或正在重试。")
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Too Many Requests" in err_str:
                raise Exception("[WARN] 大模型触发限流，正在等待 5 秒后重试...")
            elif "Session/Cookie" in err_str or "login" in err_str.lower() or "not found" in err_str.lower():
                raise Exception("[FATAL] Session/Cookie likely expired. Target not found.")
            raise Exception(f"Timeout: Gemini did not finish responding within {timeout/1000} seconds. Error: {e}")

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
        try:
            if self.context:
                await self.context.close()
        finally:
            if self.playwright:
                await self.playwright.stop()
        logging.info("Browser closed.")


class JulesBot:
    """
    A class to interact with the Jules developer interface via Playwright.
    """
    def __init__(self, profile_id="1"):
        self.profile_id = profile_id
        self.playwright = None
        self.browser = None
        self.context = None
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return

        self.playwright = await async_playwright().start()

        # User data directory for persistence, separate from Gemini's profile
        user_data_dir = f"/tmp/jules_profile_{self.profile_id}"

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1280,800"
            ],
            viewport={"width": 1280, "height": 800}
        )

        self._initialized = True
        logging.info(f"JulesBot context initialized for profile {self.profile_id}")

    async def create_new_page(self) -> Page:
        if not self._initialized:
            await self.initialize()
        return await self.context.new_page()

    async def send_task(self, page: Page, url: str, prompt: str, stream_queue=None, step_id=None):
        """
        Navigates to the target URL and submits the prompt to Jules.
        """
        import json
        import asyncio
        from playwright.async_api import expect, TimeoutError as PlaywrightTimeoutError

        async def emit(msg):
            if stream_queue and step_id:
                await stream_queue.put(f"data: {json.dumps({'step': step_id, 'status': 'Jules Working', 'message': f'[TELEMETRY] {msg}', 'screen': 'right'})}\n\n")

        try:
            await emit(f"Navigating to Jules target URL: {url}...")
            logging.info(f"Navigating to Jules target URL: {url}")

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await emit("Page loaded successfully.")
            except PlaywrightTimeoutError:
                await emit("Network seems slow, checking status... Retrying navigation.")
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            await emit("Locating input field...")
            input_box = page.locator("textarea").first

            try:
                await input_box.wait_for(state="visible", timeout=20000)
            except PlaywrightTimeoutError:
                await emit("Timeout waiting for element, retrying...")
                await asyncio.sleep(2)
                await input_box.wait_for(state="visible", timeout=20000)

            await input_box.fill(prompt)
            await emit("Prompt entered into Jules interface.")
            logging.info("Entered prompt into Jules.")

            # Submission Check
            await emit("Pressing Enter to submit task...")
            await page.keyboard.press("Enter")

            # Verify submission by checking if input box clears or becomes disabled
            try:
                await expect(input_box).to_be_empty(timeout=5000)
                await emit("Input box cleared, submission successful.")
            except:
                await emit("Input box didn't clear immediately, assuming submission via DOM change...")

            await emit("Prompt submitted, waiting for generation...")
            logging.info("Submitted prompt to Jules.")

        except Exception as e:
            if "Target closed" in str(e):
                error_msg = "[FATAL] Browser crashed due to memory. Attempting recovery..."
                await emit(error_msg)
                logging.error(error_msg)
                # Let the caller handle the restart
                raise Exception("BROWSER_CRASH")
            else:
                error_msg = f"Error sending task to Jules: {e}"
                await emit(f"[ERROR] {error_msg}")
                logging.error(error_msg)
                raise Exception(error_msg)

    async def poll_for_completion(self, page: Page, stream_queue=None, step_id=None, interval_seconds=5) -> str:
        """
        Checks the DOM dynamically for completion and extracts result.
        Now supports a configurable interval for the autopilot loop.
        """
        import json
        import asyncio
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        async def emit(msg):
            if hasattr(stream_queue, 'put'): # Handle different queue types
                if hasattr(stream_queue, 'qsize'): # asyncio queue
                    if step_id == "autopilot":
                        await stream_queue.put({"type": "info", "message": msg})
                    else:
                        await stream_queue.put(f"data: {json.dumps({'step': step_id, 'status': 'Jules Working', 'message': f'[TELEMETRY] {msg}', 'screen': 'right'})}\n\n")

        try:
            # Check for Ready for review indicator within the given interval
            try:
                await page.locator("text='Ready for review'").wait_for(state="visible", timeout=interval_seconds * 1000)

                await emit("Detected 'Ready for review' text.")
                logging.info("Jules reported 'Ready for review'.")

                # Verify network is idle to ensure no lingering requests (Multi-Factor)
                await emit("Waiting for network to become idle...")
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except PlaywrightTimeoutError:
                    await emit("Network idle timeout, proceeding with DOM extraction anyway...")

                body_text = await page.inner_text("body")
                # Extract branch link using regex
                import re
                match = re.search(r'(https://github\.com/\S+/tree/\S+)', body_text)
                if match:
                    link = match.group(1)
                    await emit(f"Extracted branch link: {link}")
                    return f"Jules finished. Branch link: {link}"
                return "Jules finished successfully. Status: Ready for review."
            except PlaywrightTimeoutError:
                 return "Still working..."

        except Exception as e:
            if "Target closed" in str(e):
                error_msg = "[FATAL] Browser crashed due to memory. Attempting recovery..."
                await emit(error_msg)
                logging.error(error_msg)
                raise Exception("BROWSER_CRASH")
            else:
                logging.debug(f"Error during Jules polling check: {e}")
                return f"Error: {str(e)}"

    async def quit(self):
        """Closes the browser."""
        try:
            if self.context:
                await self.context.close()
        finally:
            if self.playwright:
                await self.playwright.stop()
        logging.info("JulesBot Browser closed.")
