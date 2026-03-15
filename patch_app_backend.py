import re

with open('app.py', 'r') as f:
    content = f.read()

# Add endpoints for upload and account login
login_endpoint = """
from fastapi import UploadFile, File
import os

@app.post("/api/accounts/login")
async def login_account(profile_id: str):
    import bot
    try:
        b = bot.GeminiBot(profile_path=f"chrome_profile_{profile_id}")
        await b.initialize(headless=False)
        return {"status": "success", "message": f"Browser opened for profile {profile_id}. Please log in manually and close the browser."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    import shutil
    try:
        os.makedirs("/tmp/uploads", exist_ok=True)
        file_path = f"/tmp/uploads/{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"status": "success", "path": file_path}
    except Exception as e:
        return {"status": "error", "message": str(e)}
"""

if "@app.post(\"/api/accounts/login\")" not in content:
    content = content.replace("from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse", "from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse\n" + login_endpoint)

# Fix send_prompt calls in app.py to include attachments and model
# For agentic_loop
old_agentic = """await current_bot.send_prompt(page, current_gemini_prompt)"""
new_agentic = """attachments = step.get('attachments', [])
                    model_type = step.get('model', 'Auto')
                    await current_bot.send_prompt(page, current_gemini_prompt, attachments=attachments, model=model_type)"""
content = content.replace(old_agentic, new_agentic)

# For gemini (iterator inner)
old_iterator = """await current_bot.send_prompt(item_page, final_prompt)"""
new_iterator = """attachments = step.get('attachments', [])
                                model_type = step.get('model', 'Auto')
                                await current_bot.send_prompt(item_page, final_prompt, attachments=attachments, model=model_type)"""
content = content.replace(old_iterator, new_iterator)

# For gemini (standard)
old_standard = """await current_bot.send_prompt(page, final_prompt)"""
new_standard = """attachments = step.get('attachments', [])
                                model_type = step.get('model', 'Auto')
                                await current_bot.send_prompt(page, final_prompt, attachments=attachments, model=model_type)"""
content = content.replace(old_standard, new_standard)

# For gemini (chunk fallback)
old_chunk = """await current_bot.send_prompt(chunk_page, chunk_wrapper)"""
new_chunk = """await current_bot.send_prompt(chunk_page, chunk_wrapper, attachments=step.get('attachments', []), model=step.get('model', 'Auto'))"""
content = content.replace(old_chunk, new_chunk)

with open('app.py', 'w') as f:
    f.write(content)
