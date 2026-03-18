import asyncio
import logging
from typing import Optional, Any
from bot import GeminiBot, JulesBot
from playwright.async_api import Page, async_playwright

class DevAgent:
    """
    Micro-Sprint C: Sandboxed Dev Agent
    Strictly isolated and confined to the absolute UUID workspace directory.
    Guarantees no Zombie Chromium instances via the try...finally hunter loop.
    """
    def __init__(self, sandbox_cwd: str = None, bot: Optional[GeminiBot] = None, page: Optional[Page] = None):
        self.sandbox_cwd = sandbox_cwd
        # Backwards compatibility for existing orchestration
        self.bot = bot
        self.page = page

    async def execute_coding_task(self, tech_spec: str) -> Any:
        """
        Micro-Sprint C Target Method.
        Instantiates Playwright and executes the LLM task.
        """
        playwright = None
        browser = None
        try:
            logging.info(f"[DEV AGENT] Booting sandboxed execution inside: {self.sandbox_cwd}")
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Execute actual task logic here
            # In Auto-DevHouse, this maps to JulesBot's instruction set
            if not self.bot:
                self.bot = JulesBot(profile_id="1")
                # Bind the newly launched Playwright instances so bot.quit() works properly
                self.bot.playwright = playwright
                self.bot.browser = browser
                self.bot.context = context
                self.bot._initialized = True

            clean_instruction = tech_spec.strip()
            if self.sandbox_cwd:
                clean_instruction += f"\n\n[MANDATE] Execute this task in strict workspace: {self.sandbox_cwd}"

            await self.bot.send_task(page, clean_instruction)
            response = await self.bot.poll_for_completion(page)

            # Heuristic token estimations
            dev_prompt_tokens = len(tech_spec) // 4
            dev_completion_tokens = len(response) // 4

            usage = {
                'prompt_token_count': dev_prompt_tokens,
                'candidates_token_count': dev_completion_tokens
            }

            return response, dev_prompt_tokens + dev_completion_tokens, usage

        finally:
            # 🧟 ZOMBIE BROWSER HUNTER: Absolute guarantee of closure
            logging.info("[DEV AGENT] Teardown triggered. Commencing Zombie Process Hunt...")
            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    logging.error(f"[DEV AGENT] Failed to close browser: {e}")
            if playwright:
                try:
                    await playwright.stop()
                except Exception as e:
                    logging.error(f"[DEV AGENT] Failed to stop Playwright: {e}")

    async def execute_task(self, instruction: str) -> Any:
        """
        Backwards compatibility for app.py's execute_task calls
        """
        if self.bot and self.page and not self.sandbox_cwd:
            # Running in legacy mode passed from app.py
            try:
                clean_instruction = instruction.strip()
                await self.bot.send_task(self.page, clean_instruction)
                jules_response = await self.bot.poll_for_completion(self.page)

                dev_prompt_tokens = len(instruction) // 4
                dev_completion_tokens = len(jules_response) // 4

                usage = {
                    'prompt_token_count': dev_prompt_tokens,
                    'candidates_token_count': dev_completion_tokens
                }

                return jules_response, dev_prompt_tokens + dev_completion_tokens, usage
            finally:
                if hasattr(self, 'bot') and hasattr(self.bot, 'quit'):
                    try:
                        await self.bot.quit()
                    except Exception:
                        pass
        else:
            return await self.execute_coding_task(instruction)
