import re

with open('bot.py', 'r') as f:
    content = f.read()

# Update send_prompt signature
old_def = 'async def send_prompt(self, page: Page, prompt_text: str):'
new_def = 'async def send_prompt(self, page: Page, prompt_text: str, attachments=None, model=None):'
content = content.replace(old_def, new_def)

# Add attachment and model logic inside send_prompt
old_logic = """        try:
            # Find the main input area using a robust locator
            input_box = page.locator("div[role='textbox']").first
            await input_box.wait_for(state="visible", timeout=15000)

            await input_box.fill(prompt_text)
            logging.info("Entered prompt text.")"""

new_logic = """        try:
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
                        # Crucial: Wait for the progress bar to finish (it usually disappears)
                        await page.wait_for_timeout(2000) # give it a moment to appear
                        progress_bar = page.locator("progress, [role='progressbar']")
                        if await progress_bar.count() > 0:
                            await progress_bar.first.wait_for(state='hidden', timeout=30000)
                        await page.wait_for_timeout(1000) # buffer
                except Exception as e:
                    logging.error(f"Failed to upload attachment: {e}")

            # Find the main input area using a robust locator
            input_box = page.locator("div[role='textbox']").first
            await input_box.wait_for(state="visible", timeout=15000)

            await input_box.fill(prompt_text)
            logging.info("Entered prompt text.")"""

content = content.replace(old_logic, new_logic)

with open('bot.py', 'w') as f:
    f.write(content)
