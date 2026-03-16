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
        # Clean up any potential prompt-side formatting if necessary
        clean_instruction = instruction.strip()

        # Send to Jules
        await self.bot.send_task(self.page, clean_instruction)

        # We don't use stream_queue here because we assume DevHouseQueue
        # is handled by the orchestrator in app.py. But we need to wait for Jules.
        jules_response = await self.bot.poll_for_completion(self.page)

        return jules_response
