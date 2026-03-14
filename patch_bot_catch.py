import re

with open('bot.py', 'r') as f:
    content = f.read()

old_wait = """        except TimeoutError:
            raise Exception("Timeout waiting for Gemini response.")"""

new_wait = """        except TimeoutError as te:
            if "TargetClosedError" in str(te) or "Browser closed" in str(te):
                raise Exception("💥 内存过载，系统正在为您自动重置环境...")
            raise Exception("[ERROR] 网页响应超时，已跳过此节点或正在重试。")
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Too Many Requests" in err_str:
                raise Exception("[WARN] 大模型触发限流，正在等待 5 秒后重试...")
            elif "Session/Cookie" in err_str or "login" in err_str.lower() or "not found" in err_str.lower():
                raise Exception("[FATAL] Session/Cookie likely expired. Target not found.")
            raise"""

if old_wait in content:
    content = content.replace(old_wait, new_wait)
else:
    print("Could not find old_wait in bot.py")

with open('bot.py', 'w') as f:
    f.write(content)
