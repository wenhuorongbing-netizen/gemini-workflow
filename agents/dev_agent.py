import asyncio
import os
import logging
from typing import Optional, Any
from bot import GeminiBot, JulesBot
from playwright.async_api import Page, async_playwright

class DevAgent:
    """
    Route B: Native File-Editing Dev Agent
    Interacts directly with the file system within an isolated UUID sandbox.
    """
    def __init__(self, sandbox_path: str = None, sandbox_cwd: str = None, bot: Optional[GeminiBot] = None, page: Optional[Page] = None, *args, **kwargs):
        # Support both sandbox_path and sandbox_cwd naming for backwards compatibility
        self.sandbox_path = sandbox_path or sandbox_cwd or (args[0] if len(args) > 0 and isinstance(args[0], str) else None)

        if self.sandbox_path:
            os.makedirs(self.sandbox_path, exist_ok=True)

        # Legacy compatibility for app.py passing bot and page as positional arguments
        if not self.sandbox_path and len(args) >= 2:
             self.bot = args[0]
             self.page = args[1]
        else:
             self.bot = bot
             self.page = page

        # Fallback to bot and page if passed directly
        if not self.bot and bot:
             self.bot = bot
        if not self.page and page:
             self.page = page

        # For test_e2e_engine backwards compat where bot/page might be passed as kwargs or positional args 1 & 2
        if bot and not self.bot:
             self.bot = bot
        if page and not self.page:
             self.page = page

    def apply_code_changes(self, relative_path: str, code_content: str) -> bool:
        """
        Uses standard Python file operations to overwrite/create the file securely within the sandbox.
        """
        if not self.sandbox_path:
            raise Exception("Cannot apply code changes: sandbox_path is not set.")

        # Resolve path safely inside the sandbox
        safe_path = os.path.abspath(os.path.join(self.sandbox_path, relative_path.lstrip("/")))
        if not safe_path.startswith(os.path.abspath(self.sandbox_path)):
            raise Exception(f"Security Violation: Attempted to write outside sandbox ({safe_path})")

        # Ensure directory exists
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)

        with open(safe_path, "w") as f:
            f.write(code_content)

        logging.info(f"[DEV AGENT] Successfully wrote file: {safe_path}")
        return True

    async def run_compilation(self) -> dict:
        """
        Runs `npm run build` within the sandbox_path to verify compilation.
        Returns the result as {"success": bool, "log": str}
        """
        if not self.sandbox_path:
            return {"success": False, "log": "Sandbox path not set."}

        logging.info(f"[DEV AGENT] Running compilation in {self.sandbox_path}")
        try:
            process = await asyncio.create_subprocess_exec(
                "npm", "run", "build",
                cwd=self.sandbox_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                log_out = stdout.decode('utf-8') if stdout else ""
                return {"success": True, "log": log_out}
            else:
                error_log = stderr.decode('utf-8') or stdout.decode('utf-8')
                return {"success": False, "log": error_log}
        except Exception as e:
            return {"success": False, "log": str(e)}

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

if __name__ == "__main__":
    # Test block for Micro-Sprint verification
    import tempfile
    import os

    # Create a temporary sandbox directory
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Testing DevAgent in sandbox: {temp_dir}")
        agent = DevAgent(sandbox_path=temp_dir)

        # Test file creation
        test_file = "src/index.ts"
        test_code = "console.log('Hello, Native Dev Agent!');"

        agent.apply_code_changes(test_file, test_code)

        # Verify physical existence
        expected_path = os.path.join(temp_dir, "src/index.ts")
        if os.path.exists(expected_path):
            with open(expected_path, "r") as f:
                content = f.read()
                if content == test_code:
                    print("SUCCESS: File created and verified successfully.")
                else:
                    print(f"ERROR: File content mismatch. Expected {test_code}, got {content}")
        else:
            print(f"ERROR: File was not created at {expected_path}")
