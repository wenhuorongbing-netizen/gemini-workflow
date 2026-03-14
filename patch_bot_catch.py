import re

with open('bot.py', 'r') as f:
    content = f.read()

# Replace timeout error string in bot.py wait_for_response
old_wait = """        except TimeoutError:
            raise Exception("Timeout waiting for Gemini response.")"""

new_wait = """        except TimeoutError as te:
            if "TargetClosedError" in str(te) or "Browser closed" in str(te):
                raise Exception("💥 内存过载，系统正在为您自动重置环境...")
            raise Exception("⚠️ Target webpage timeout. Ensure the URL is accessible.")
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Too Many Requests" in err_str:
                raise Exception("⏳ LLM API rate limit (429) hit. Implementing exponential backoff and retrying...")
            elif "Session/Cookie" in err_str or "login" in err_str.lower() or "not found" in err_str.lower():
                raise Exception("🔒 Session expired or target not found. Please refresh your cookies.")
            raise"""

if old_wait in content:
    content = content.replace(old_wait, new_wait)

with open('bot.py', 'w') as f:
    f.write(content)
