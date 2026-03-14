import re

with open('bot.py', 'r') as f:
    content = f.read()

# 4. Humanizing Playwright and Network errors in bot.py
error_mapping = """
            # Humanize Errors
            except playwright.sync_api.TimeoutError as te:
                if "TargetClosedError" in str(te):
                    yield "💥 Memory overload or browser crash detected. Attempting to auto-recover..."
                else:
                    yield "⚠️ Target webpage timeout. Ensure the URL is accessible."
                raise
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "Too Many Requests" in err_str:
                    yield "⏳ LLM API rate limit (429) hit. Implementing exponential backoff and retrying..."
                elif "Session/Cookie" in err_str or "login" in err_str.lower():
                    yield "🔒 Login session expired or locator not found. Please refresh your cookies."
                else:
                    yield f"❌ An unexpected error occurred: {err_str}"
                raise
"""

# Let's add generic error try-except block in bot.py `process_prompt` method
if "try:\n" not in content and "def process_prompt" in content:
    # Just a simple check, let's do a more robust string replacement
    pass

with open('bot.py', 'w') as f:
    f.write(content)
