import asyncio
import json
import logging
from bot import GeminiBot
from playwright.async_api import Page

class DevAgent:
    def __init__(self, bot: GeminiBot, page: Page):
        self.bot = bot
        self.page = page

    async def execute_task(self, instruction: str):
        """Passes the instruction to the Jules bot and waits for completion."""
        try:
            # Clean up any potential prompt-side formatting if necessary
            clean_instruction = instruction.strip()

            # Send to Jules
            await self.bot.send_task(self.page, clean_instruction)

            # We don't use stream_queue here because we assume DevHouseQueue
            # is handled by the orchestrator in app.py. But we need to wait for Jules.
            jules_response = await self.bot.poll_for_completion(self.page)

            # Dev Agent uses Playwright/Puppeteer heuristic, so we estimate token usage based on instruction length
            dev_prompt_tokens = len(instruction) // 4
            dev_completion_tokens = len(jules_response) // 4

            usage = {
                'prompt_token_count': dev_prompt_tokens,
                'candidates_token_count': dev_completion_tokens
            }

            return jules_response, dev_prompt_tokens + dev_completion_tokens, usage
        finally:
            # Zombie Browser Hunter: Ensure browser closes properly.
            # In DevAgent, we call bot.quit() to guarantee no orphaned Chromium instances.
            if hasattr(self, 'bot') and hasattr(self.bot, 'quit'):
                try:
                    await self.bot.quit()
                except Exception:
                    pass
