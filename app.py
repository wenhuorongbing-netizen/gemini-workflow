from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import logging
from bot import GeminiBot
import json
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

app = FastAPI()
scheduler = AsyncIOScheduler()

EPICS_FILE = 'epics.json'
GLOBALS_FILE = 'globals.json'
HEADLESS_MODE = False

def load_globals():
    if os.path.exists(GLOBALS_FILE):
        try:
            with open(GLOBALS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_globals(data):
    with open(GLOBALS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.get("/api/globals")
async def get_global_vars():
    return JSONResponse(load_globals())

@app.post("/api/globals")
async def save_global_vars(request: Request):
    data = await request.json()
    save_globals(data)
    return JSONResponse({"status": "success"})

@app.post("/api/settings/headless")
async def toggle_headless(request: Request):
    global HEADLESS_MODE
    global bot
    data = await request.json()
    HEADLESS_MODE = data.get('headless', False)

    if bot:
        # Re-initialize bot with new headless state
        await bot.quit()
        bot = None

    return JSONResponse({"status": "success", "headless": HEADLESS_MODE})

@app.get("/api/settings/headless")
async def get_headless():
    return JSONResponse({"headless": HEADLESS_MODE})

def load_epics():
    if os.path.exists(EPICS_FILE):
        try:
            with open(EPICS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_epics(data):
    with open(EPICS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
templates = Jinja2Templates(directory="templates")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler("gemini_workflow_error.log"),
        logging.StreamHandler()
    ]
)

# Global bot instance to maintain session state asynchronously
bot = None
current_profile_id = "1"
# A simple async semaphore to allow concurrent executions up to a limit
bot_semaphore = None
# Global event to signal emergency stop
cancel_event = None

# Global store for approval nodes
approval_events = {}

@app.post("/api/approve/{run_id}")
async def approve_step(run_id: str, request: Request):
    data = await request.json()
    if run_id in approval_events:
        approval_events[run_id]['text'] = data.get('text', '')
        approval_events[run_id]['action'] = data.get('action', 'approve')
        approval_events[run_id]['event'].set()
        return JSONResponse({"status": "success"})
    raise HTTPException(status_code=404, detail="Run ID not waiting for approval")

class WorkspaceFileHandler(FileSystemEventHandler):
    def __init__(self, workspace_id, steps, loop):
        self.workspace_id = workspace_id
        self.steps = steps
        self.loop = loop

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(('.txt', '.md')):
            logging.info(f"File {event.src_path} created. Triggering workflow for workspace {self.workspace_id}")
            asyncio.run_coroutine_threadsafe(self.trigger_workflow(event.src_path), self.loop)

    async def trigger_workflow(self, filepath):
        try:
            if bot_semaphore.locked():
                logging.warning(f"Skipping auto-trigger for {filepath} - server busy.")
                return

            await asyncio.wait_for(bot_semaphore.acquire(), timeout=0.1)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                if not content.strip():
                    return

                steps_copy = json.loads(json.dumps(self.steps))
                if steps_copy:
                    steps_copy[0]['prompt'] = f"{content}\n\n---\n\n" + steps_copy[0].get('prompt', '')

                # Run silently in background
                async for _ in run_workflow_engine(steps_copy, self.workspace_id, None):
                    pass
            finally:
                bot_semaphore.release()

        except Exception as e:
            logging.error(f"Auto-trigger failed for file {filepath}: {e}")

file_observer = None

async def execute_cron_job(workspace_id, steps):
    logging.info(f"Executing scheduled cron job for workspace {workspace_id}")
    try:
        if bot_semaphore.locked():
            logging.warning(f"Skipping cron job for {workspace_id} - server busy.")
            return

        await asyncio.wait_for(bot_semaphore.acquire(), timeout=0.1)
        try:
            steps_copy = json.loads(json.dumps(steps))
            async for _ in run_workflow_engine(steps_copy, workspace_id, None):
                pass
        finally:
            bot_semaphore.release()
    except Exception as e:
        logging.error(f"Cron execution failed for workspace {workspace_id}: {e}")

def setup_watchers(loop=None):
    global file_observer
    if not loop:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

    if file_observer:
        old_observer = file_observer
        old_observer.stop()
        # Don't block the event loop by calling join() synchronously
        import threading
        threading.Thread(target=lambda: old_observer.join()).start()

    file_observer = Observer()

    # Also update the scheduler
    scheduler.remove_all_jobs()

    epics = load_epics()

    for ws_id, data in epics.items():
        steps = data.get('steps', [])

        watch_folder = data.get('watch_folder')
        if watch_folder and os.path.isdir(watch_folder) and steps:
            handler = WorkspaceFileHandler(ws_id, steps, loop)
            file_observer.schedule(handler, watch_folder, recursive=False)
            logging.info(f"Watching folder {watch_folder} for workspace {ws_id}")

        cron_schedule = data.get('cron_schedule')
        if cron_schedule and steps:
            try:
                trigger = CronTrigger.from_crontab(cron_schedule)
                scheduler.add_job(execute_cron_job, trigger, args=[ws_id, steps], id=f"cron_{ws_id}")
                logging.info(f"Scheduled cron {cron_schedule} for workspace {ws_id}")
            except ValueError as e:
                logging.error(f"Invalid cron string '{cron_schedule}' for workspace {ws_id}: {e}")

    if file_observer.emitters:
        file_observer.start()

@app.on_event("startup")
async def startup_event():
    global bot_semaphore
    global cancel_event
    bot_semaphore = asyncio.Semaphore(3)
    cancel_event = asyncio.Event()
    scheduler.start()
    setup_watchers(asyncio.get_running_loop())

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    if file_observer and file_observer.is_alive():
        file_observer.stop()
        file_observer.join()

@app.post("/stop")
async def stop_workflow():
    if cancel_event:
        cancel_event.set()
    return {"status": "stopping"}

async def get_bot(profile_id="1"):
    global bot
    global current_profile_id

    if bot is not None and current_profile_id != profile_id:
        logging.info(f"Switching chrome profile from {current_profile_id} to {profile_id}...")
        await bot.quit()
        bot = None

    if bot is None or bot._initialized is False:
        try:
            profile_path = f"chrome_profile_{profile_id}" if profile_id != "1" else "chrome_profile"
            new_bot = GeminiBot(profile_path=profile_path)
            await new_bot.initialize(headless=HEADLESS_MODE)
            bot = new_bot
            current_profile_id = profile_id
        except Exception as e:
            logging.error(f"Failed to initialize Gemini Bot for profile {profile_id}: {e}")
            raise Exception(f"Failed to initialize bot for profile {profile_id}. Ensure Chrome profile path is valid.")
    return bot

@app.get("/api/logs")
async def get_logs():
    try:
        if not os.path.exists("gemini_workflow_error.log"):
            return JSONResponse({"logs": "Log file not found."})

        with open("gemini_workflow_error.log", "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Return last 100 lines
        last_lines = lines[-100:]
        return JSONResponse({"logs": "".join(last_lines)})
    except Exception as e:
        return JSONResponse({"logs": f"Error reading logs: {str(e)}"})

@app.get("/api/workspaces")
async def get_workspaces():
    epics = load_epics()
    # Return minimal info for sidebar
    workspaces = []
    for ws_id, data in epics.items():
        workspaces.append({"id": ws_id, "name": data.get("name", "Unnamed Workspace")})
    return JSONResponse(workspaces)

@app.get("/api/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str):
    epics = load_epics()
    if workspace_id not in epics:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return JSONResponse(epics[workspace_id])

@app.post("/api/workspaces/{workspace_id}")
async def save_workspace(workspace_id: str, request: Request):
    data = await request.json()
    epics = load_epics()

    if workspace_id not in epics:
        epics[workspace_id] = {"name": data.get("name", "New Workspace"), "steps": [], "results": {}}

    if "name" in data:
        epics[workspace_id]["name"] = data["name"]
    if "steps" in data:
        epics[workspace_id]["steps"] = data["steps"]
    if "results" in data:
        epics[workspace_id]["results"] = data["results"]
    if "watch_folder" in data:
        epics[workspace_id]["watch_folder"] = data["watch_folder"]
    if "webhook_url" in data:
        epics[workspace_id]["webhook_url"] = data["webhook_url"]
    if "cron_schedule" in data:
        epics[workspace_id]["cron_schedule"] = data["cron_schedule"]

    save_epics(epics)
    setup_watchers() # Refresh watchers and schedulers on save
    return JSONResponse({"status": "success"})

@app.delete("/api/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str):
    epics = load_epics()
    if workspace_id in epics:
        del epics[workspace_id]
        save_epics(epics)
    return JSONResponse({"status": "deleted"})

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

import uuid

async def run_workflow_engine(steps, workspace_id, stream_queue=None, profile_id="1"):
    run_id = str(uuid.uuid4())
    page = None
    try:
        try:
            current_bot = await get_bot(profile_id)
            page = await current_bot.create_new_page()
        except Exception as e:
            if stream_queue: yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        results = {}
        correction_counts = {}

        index = 0
        while index < len(steps):
            step = steps[index]
            if cancel_event and cancel_event.is_set():
                if stream_queue: yield f"data: {json.dumps({'step': index + 1, 'status': 'Canceled', 'message': 'Workflow stopped by user.'})}\n\n"
                break

            step_id = index + 1
            prompt_template = step.get('prompt', '')
            new_chat = step.get('new_chat', False)
            step_type = step.get('type', 'standard')
            chat_url = step.get('chat_url', '').strip()
            show_result = step.get('show_result', True)

            # Global variable injection
            global_vars = load_globals()
            for g_key, g_val in global_vars.items():
                g_tag = f"{{{{GLOBAL_{g_key}}}}}"
                if g_tag in prompt_template:
                    prompt_template = prompt_template.replace(g_tag, g_val)

            logging.info(f"Executing Step {step_id} (Type: {step_type})")
            if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Starting', 'message': f'Executing Step {step_id}...'})}\n\n"

            if step_type == 'approval':
                prev_result = results.get(str(step_id - 1), "")

                approval_events[run_id] = {
                    'event': asyncio.Event(),
                    'text': None,
                    'action': None
                }

                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Awaiting_Approval', 'run_id': run_id, 'result': prev_result, 'message': 'Waiting for user approval...'})}\n\n"

                # Wait for user input or cancel event
                while not approval_events[run_id]['event'].is_set():
                    if cancel_event and cancel_event.is_set():
                        break
                    try:
                        await asyncio.wait_for(asyncio.sleep(0.5), timeout=0.5)
                    except asyncio.TimeoutError:
                        pass

                if cancel_event and cancel_event.is_set():
                    del approval_events[run_id]
                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Canceled', 'message': 'Workflow stopped by user.'})}\n\n"
                    break

                action = approval_events[run_id]['action']
                edited_text = approval_events[run_id]['text']
                del approval_events[run_id]

                if action == 'reject':
                    results[str(step_id)] = "[REJECTED] Workflow stopped by user at Approval Node."
                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'result': results[str(step_id)]})}\n\n"
                    break
                else:
                    results[str(step_id)] = edited_text
                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': edited_text, 'show_result': show_result})}\n\n"
                    index += 1
                    continue

            # Auto-chunking for huge inputs
            is_chunked = False
            chunks = []
            CHUNK_LIMIT = 10000

            # We only auto-chunk standard/aggregator steps that are huge. We skip batch mode or iterators here.
            # Actually, let's pre-process the final_prompt to see if it exceeds 10,000 chars.
            # But we do that down in the "Standard or Aggregator Step" block.

            if step_type == 'batch':
                # Batch Input Step
                results[str(step_id)] = prompt_template
                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': prompt_template, 'show_result': show_result})}\n\n"
                index += 1
                continue

            elif step_type == 'scraper':
                # Web Scraper Node
                url_to_scrape = prompt_template.strip()
                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Scraping', 'message': f'Scraping URL: {url_to_scrape}'})}\n\n"
                try:
                    scraped_text = await current_bot.scrape_url(page, url_to_scrape)
                    results[str(step_id)] = scraped_text
                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': scraped_text, 'show_result': show_result})}\n\n"
                except Exception as e:
                    results[str(step_id)] = f"[SCRAPE FAILED] {str(e)}"
                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'result': results[str(step_id)]})}\n\n"
                index += 1
                continue

            elif step_type == 'correction':
                import re
                try:
                    # e.g. IF {{OUTPUT_1}} NOT CONTAINS "Keyword" THEN PROMPT: "Please rewrite and include Keyword"
                    match = re.search(r'IF\s+(.*?)\s+(CONTAINS|EQUALS|NOT CONTAINS)\s+"(.*?)"\s+THEN\s+PROMPT:\s+"(.*?)"', prompt_template, re.IGNORECASE)
                    if match:
                        var_raw, op, val, correction_prompt = match.groups()

                        var_val = var_raw
                        for past_id, past_output in results.items():
                            tag = f"{{{{OUTPUT_{past_id}}}}}"
                            if tag in var_val:
                                var_val = var_val.replace(tag, past_output)

                        condition_met = False
                        op = op.upper()
                        if op == 'CONTAINS':
                            condition_met = val in var_val
                        elif op == 'NOT CONTAINS':
                            condition_met = val not in var_val
                        elif op == 'EQUALS':
                            condition_met = val == var_val

                        if condition_met:
                            loop_count = correction_counts.get(step_id, 0)
                            if loop_count < 3:
                                correction_counts[step_id] = loop_count + 1
                                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Self-Correcting', 'message': f'Quality check failed. Looping back (Attempt {loop_count + 1}/3)...'})}\n\n"

                                # Go back to previous step
                                index -= 1
                                # Modify the previous step's prompt to include the correction
                                prev_step = steps[index]
                                prev_step['prompt'] += f"\n\n--- CORRECTION REQUIRED ---\n{correction_prompt}"
                                continue
                            else:
                                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'message': 'Max correction loops (3) exceeded. Proceeding anyway.'})}\n\n"
                                results[str(step_id)] = "[CORRECTION FAILED] Max loops exceeded."
                        else:
                            if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Correction Evaluated', 'message': 'Quality check passed. Continuing...'})}\n\n"
                            results[str(step_id)] = "Quality check passed."
                    else:
                        results[str(step_id)] = "[FAILED] Invalid Correction syntax"
                        if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'message': 'Invalid Correction syntax'})}\n\n"
                except Exception as e:
                    results[str(step_id)] = f"[FAILED] {e}"
                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'message': str(e)})}\n\n"

                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': results[str(step_id)], 'show_result': show_result})}\n\n"
                index += 1
                continue

            elif step_type == 'logic':
                # Evaluate logic gate
                import re
                try:
                    # Very simple parsing: IF {{OUTPUT_X}} CONTAINS "str" THEN GOTO STEP Y
                    match = re.search(r'IF\s+(.*?)\s+(CONTAINS|EQUALS|NOT CONTAINS)\s+"(.*?)"\s+THEN\s+GOTO\s+STEP\s+(\d+)', prompt_template, re.IGNORECASE)
                    if match:
                        var_raw, op, val, target_step_str = match.groups()

                        # Resolve variable
                        var_val = var_raw
                        for past_id, past_output in results.items():
                            tag = f"{{{{OUTPUT_{past_id}}}}}"
                            if tag in var_val:
                                var_val = var_val.replace(tag, past_output)

                        condition_met = False
                        op = op.upper()
                        if op == 'CONTAINS':
                            condition_met = val in var_val
                        elif op == 'NOT CONTAINS':
                            condition_met = val not in var_val
                        elif op == 'EQUALS':
                            condition_met = val == var_val

                        target_step = int(target_step_str)
                        if condition_met:
                            if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Logic Evaluated', 'message': f'Condition met. Jumping to Step {target_step}.'})}\n\n"
                            results[str(step_id)] = f"Logic Gate evaluated to True. Jumped to Step {target_step}."
                            index = target_step - 1
                            continue
                        else:
                            if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Logic Evaluated', 'message': 'Condition not met. Continuing...'})}\n\n"
                            results[str(step_id)] = "Logic Gate evaluated to False. Continued."
                    else:
                        if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'message': 'Invalid Logic Gate syntax'})}\n\n"
                        results[str(step_id)] = "[FAILED] Invalid Logic Gate syntax"
                except Exception as e:
                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'message': str(e)})}\n\n"
                    results[str(step_id)] = f"[FAILED] {e}"

                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': results[str(step_id)], 'show_result': show_result})}\n\n"
                index += 1
                continue

            elif step_type == 'python':
                # Execute Python Script
                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Executing Python', 'message': 'Running custom Python logic...'})}\n\n"

                # Resolve variables first
                final_script = prompt_template
                for past_id, past_output in results.items():
                    tag = f"{{{{OUTPUT_{past_id}}}}}"
                    if tag in final_script:
                        final_script = final_script.replace(tag, past_output)

                prev_input = results.get(str(step_id - 1), "")

                local_vars = {'input': prev_input, 'output': ''}
                try:
                    # Caution: Exec is dangerous in generic web apps, but for local-first assistant tools it provides extreme power.
                    exec(final_script, {}, local_vars)
                    py_output = local_vars.get('output', '')
                    results[str(step_id)] = str(py_output)
                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': results[str(step_id)], 'show_result': show_result})}\n\n"
                except Exception as e:
                    results[str(step_id)] = f"[PYTHON ERROR] {str(e)}"
                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'result': results[str(step_id)]})}\n\n"

                index += 1
                continue

            elif '{{CURRENT_ITEM}}' in prompt_template:
                # Iterator Step
                # Find nearest previous batch input
                batch_text = ""
                for i in range(index - 1, -1, -1):
                    if steps[i].get('type') == 'batch':
                        batch_text = results.get(str(i + 1), "")
                        break

                items = [item.strip() for item in batch_text.split('\n') if item.strip()]

                if not items:
                    results[str(step_id)] = "[FAILED] No batch items found to iterate over."
                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'result': results[str(step_id)]})}\n\n"
                    break

                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Processing Batch', 'message': f'Processing {len(items)} items concurrently...'})}\n\n"

                concurrent_semaphore = asyncio.Semaphore(3)

                async def process_item(item, item_index):
                    item_page = None
                    try:
                        await concurrent_semaphore.acquire()
                        if cancel_event and cancel_event.is_set():
                            return f"[Item {item_index + 1} CANCELED]"

                        item_page = await current_bot.create_new_page()

                        MAX_RETRIES = 3
                        for attempt in range(MAX_RETRIES):
                            try:
                                if chat_url and chat_url.startswith('https://gemini.google.com/'):
                                    # Instead of yield, we push to queue since this is an async function not generator
                                    if stream_queue: await stream_queue.put(f"__STATUS__:Navigating item {item_index + 1} to specific chat URL...")
                                    await current_bot.goto_specific_chat(item_page, chat_url)
                                elif new_chat:
                                    await current_bot.start_new_chat(item_page)

                                final_prompt = prompt_template.replace('{{CURRENT_ITEM}}', item)
                                # Use a safe lambda replacement as per memory instructions
                                import re
                                for past_id, past_output in results.items():
                                    tag = f"{{{{OUTPUT_{past_id}}}}}"
                                    if tag in final_prompt:
                                        # Avoid re module for simple string replacements unless necessary, string.replace is safer for arbitrary texts
                                        final_prompt = final_prompt.replace(tag, past_output)

                                await current_bot.send_prompt(item_page, final_prompt)

                                if cancel_event and cancel_event.is_set():
                                    return f"[Item {item_index + 1} CANCELED]"

                                # Stream to queue for pseudo-streaming if needed
                                async def item_poll_callback(partial_text):
                                    if cancel_event and cancel_event.is_set():
                                        raise asyncio.CancelledError("Workflow stopped by user.")
                                    if stream_queue: await stream_queue.put(partial_text)

                                wait_task = asyncio.create_task(current_bot.wait_for_response(item_page, poll_callback=item_poll_callback if stream_queue else None))

                                while not wait_task.done():
                                    try:
                                        # Wait in loop but we don't consume queue from here, the pump_queue will do it.
                                        await asyncio.wait_for(asyncio.sleep(0.5), timeout=0.5)
                                    except asyncio.TimeoutError:
                                        if cancel_event and cancel_event.is_set():
                                            wait_task.cancel()
                                            return f"[Item {item_index + 1} CANCELED]"
                                        continue

                                wait_task.result()

                                if cancel_event and cancel_event.is_set():
                                    return f"[Item {item_index + 1} CANCELED]"

                                response_text = await current_bot.get_last_response(item_page)
                                return response_text

                            except asyncio.CancelledError:
                                return f"[Item {item_index + 1} CANCELED]"
                            except Exception as e:
                                if attempt < MAX_RETRIES - 1:
                                    logging.warning(f"Batch item {item_index + 1} failed, retrying {attempt + 1}: {str(e)}")
                                    if cancel_event and cancel_event.is_set():
                                        return f"[Item {item_index + 1} CANCELED]"
                                    await item_page.reload()
                                else:
                                    logging.error(f"Error in Batch item {item_index + 1}: {str(e)}")
                                    return f"[FAILED - Item {item_index + 1}] {str(e)}"
                    finally:
                        if item_page:
                            await item_page.close()
                        concurrent_semaphore.release()

                tasks = [process_item(item, i) for i, item in enumerate(items)]

                pump_task = None
                if stream_queue:
                    # We need a way to pump the stream_queue while gather is running
                    async def pump_queue():
                        while True:
                            try:
                                partial_text = await asyncio.wait_for(stream_queue.get(), timeout=0.5)
                            except asyncio.TimeoutError:
                                pass
                            except Exception:
                                break
                    pump_task = asyncio.create_task(pump_queue())

                batch_results = await asyncio.gather(*tasks)
                if pump_task: pump_task.cancel()

                final_result_text = "\n\n--- \n\n".join(batch_results)
                results[str(step_id)] = final_result_text
                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': final_result_text, 'show_result': show_result})}\n\n"
                continue
            else:
                    # Standard or Aggregator Step
                    MAX_RETRIES = 3
                    step_success = False

                    for attempt in range(MAX_RETRIES):
                        try:
                            if chat_url and chat_url.startswith('https://gemini.google.com/'):
                                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Navigating', 'message': 'Navigating to specific chat URL...'})}\n\n"
                                await current_bot.goto_specific_chat(page, chat_url)
                            elif new_chat:
                                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'New Chat', 'message': 'Starting new chat...'})}\n\n"
                                await current_bot.start_new_chat(page)

                            # Smart Context Injection: Replace {{OUTPUT_X}} with actual results
                            final_prompt = prompt_template
                            for past_id, past_output in results.items():
                                tag = f"{{{{OUTPUT_{past_id}}}}}"
                                if tag in final_prompt:
                                    final_prompt = final_prompt.replace(tag, past_output)

                            if len(final_prompt) > CHUNK_LIMIT:
                                is_chunked = True
                                # Split by words or just naive length to keep it simple, but chunk roughly cleanly
                                # A simple chunking by character limit
                                chunks = [final_prompt[i:i + CHUNK_LIMIT] for i in range(0, len(final_prompt), CHUNK_LIMIT)]
                                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Chunking', 'message': f'Input exceeds 10k chars. Auto-split into {len(chunks)} chunks for parallel processing...'})}\n\n"
                                break # Break the retry loop and handle below via chunk logic
                            else:
                                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Sending', 'message': 'Sending prompt to Gemini...'})}\n\n"
                                # Send the final compiled prompt to the bot
                                await current_bot.send_prompt(page, final_prompt)

                            if cancel_event and cancel_event.is_set():
                                raise asyncio.CancelledError("Workflow stopped by user.")

                            # Wait for the generation to finish
                            if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Waiting', 'message': 'Waiting for Gemini response...'})}\n\n"

                            # Define a callback to put partial results into the queue
                            async def poll_callback(partial_text):
                                if cancel_event and cancel_event.is_set():
                                    raise asyncio.CancelledError("Workflow stopped by user.")
                                if stream_queue: await stream_queue.put(partial_text)

                            # Run wait_for_response in a background task so we can stream from the queue
                            wait_task = asyncio.create_task(current_bot.wait_for_response(page, poll_callback=poll_callback if stream_queue else None))

                            while not wait_task.done():
                                try:
                                    if stream_queue:
                                        # Poll the queue for partial updates
                                        partial_text = await asyncio.wait_for(stream_queue.get(), timeout=0.5)
                                        yield f"data: {json.dumps({'step': step_id, 'status': 'Typing', 'partial_result': partial_text, 'show_result': show_result})}\n\n"
                                    else:
                                        await asyncio.wait_for(asyncio.sleep(0.5), timeout=0.5)
                                except asyncio.TimeoutError:
                                    # Yield heartbeats or check cancel event
                                    if cancel_event and cancel_event.is_set():
                                        wait_task.cancel()
                                        raise asyncio.CancelledError("Workflow stopped by user.")
                                    continue

                            # Check if wait_task raised an exception
                            wait_task.result()

                            if cancel_event and cancel_event.is_set():
                                raise asyncio.CancelledError("Workflow stopped by user.")

                            # Extract the output
                            if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Extracting', 'message': 'Extracting response text...'})}\n\n"
                            response_text = await current_bot.get_last_response(page)

                            results[str(step_id)] = response_text

                            if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': response_text, 'show_result': show_result})}\n\n"
                            logging.info(f"Step {step_id} completed successfully.")
                            step_success = True
                            break

                        except asyncio.CancelledError as e:
                            if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Canceled', 'message': str(e)})}\n\n"
                            step_success = False
                            break # Break retry loop immediately on cancel
                        except Exception as e:
                            if attempt < MAX_RETRIES - 1:
                                error_msg = f"Step {step_id} failed, preparing retry {attempt + 1}, error: {str(e)}"
                                logging.warning(error_msg)
                                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Retrying', 'message': f'Response timeout, retrying {attempt + 1}...'})}\n\n"

                                # Break wait loop if canceled during sleep
                                try:
                                    await asyncio.wait_for(cancel_event.wait(), timeout=5)
                                    # If we didn't timeout, event was set
                                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Canceled', 'message': 'Workflow stopped by user.'})}\n\n"
                                    step_success = False
                                    break
                                except asyncio.TimeoutError:
                                    pass # Continue retrying

                                # Reload the page before retrying to clear stuck state but preserve session/history
                                await page.reload()
                            else:
                                error_msg = f"Error in Step {step_id}: {str(e)}"
                                logging.error(error_msg)
                                results[str(step_id)] = f"[FAILED] {error_msg}"
                                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'result': results[str(step_id)]})}\n\n"
                                # We break the retry loop, then we will break the workflow below
                                break

                    if is_chunked:
                        # Process chunks concurrently using the same pattern as batch map-reduce
                        concurrent_semaphore = asyncio.Semaphore(3)

                        async def process_chunk(chunk_text, chunk_index):
                            chunk_page = None
                            try:
                                await concurrent_semaphore.acquire()
                                if cancel_event and cancel_event.is_set():
                                    return f"[Chunk {chunk_index + 1} CANCELED]"

                                chunk_page = await current_bot.create_new_page()

                                chunk_retries = 3
                                for c_attempt in range(chunk_retries):
                                    try:
                                        if chat_url and chat_url.startswith('https://gemini.google.com/'):
                                            if stream_queue: await stream_queue.put(f"__STATUS__:Navigating chunk {chunk_index + 1} to chat URL...")
                                            await current_bot.goto_specific_chat(chunk_page, chat_url)
                                        elif new_chat:
                                            await current_bot.start_new_chat(chunk_page)

                                        # To provide context to the bot, we prepend instructions to chunks
                                        chunk_wrapper = f"Please process this chunk of a larger document:\n\n{chunk_text}"

                                        await current_bot.send_prompt(chunk_page, chunk_wrapper)

                                        if cancel_event and cancel_event.is_set():
                                            return f"[Chunk {chunk_index + 1} CANCELED]"

                                        async def chunk_poll(partial_text):
                                            if cancel_event and cancel_event.is_set():
                                                raise asyncio.CancelledError("Canceled")
                                            if stream_queue: await stream_queue.put(partial_text)

                                        wait_task = asyncio.create_task(current_bot.wait_for_response(chunk_page, poll_callback=chunk_poll if stream_queue else None))

                                        while not wait_task.done():
                                            try:
                                                await asyncio.wait_for(asyncio.sleep(0.5), timeout=0.5)
                                            except asyncio.TimeoutError:
                                                if cancel_event and cancel_event.is_set():
                                                    wait_task.cancel()
                                                    return f"[Chunk {chunk_index + 1} CANCELED]"
                                                continue

                                        wait_task.result()
                                        if cancel_event and cancel_event.is_set():
                                            return f"[Chunk {chunk_index + 1} CANCELED]"

                                        return await current_bot.get_last_response(chunk_page)

                                    except asyncio.CancelledError:
                                        return f"[Chunk {chunk_index + 1} CANCELED]"
                                    except Exception as ce:
                                        if c_attempt < chunk_retries - 1:
                                            if cancel_event and cancel_event.is_set():
                                                return f"[Chunk {chunk_index + 1} CANCELED]"
                                            await chunk_page.reload()
                                        else:
                                            return f"[FAILED Chunk {chunk_index + 1}] {str(ce)}"
                            finally:
                                if chunk_page:
                                    await chunk_page.close()
                                concurrent_semaphore.release()

                        chunk_tasks = [process_chunk(ch, i) for i, ch in enumerate(chunks)]

                        pump_task = None
                        if stream_queue:
                            async def pump_queue():
                                while True:
                                    try:
                                        partial_text = await asyncio.wait_for(stream_queue.get(), timeout=0.5)
                                    except asyncio.TimeoutError:
                                        pass
                                    except Exception:
                                        break
                            pump_task = asyncio.create_task(pump_queue())

                        chunk_results = await asyncio.gather(*chunk_tasks)
                        if pump_task: pump_task.cancel()

                        final_result_text = "\n\n--- [Auto-Chunk Break] ---\n\n".join(chunk_results)
                        results[str(step_id)] = final_result_text
                        if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': final_result_text, 'show_result': show_result})}\n\n"
                        step_success = True

            if not step_success:
                # If a critical error occurs and all retries fail, break the workflow to avoid cascaded failures
                break

            index += 1


        # Save results to the workspace if provided
        if workspace_id:
            epics = load_epics()
            if workspace_id in epics:
                epics[workspace_id]["results"] = results
                save_epics(epics)

            # If webhook exists, we could export it here
            webhook_url = epics.get(workspace_id, {}).get("webhook_url")
            if webhook_url:
                import httpx
                try:
                    # Execute in background so we don't block
                    asyncio.create_task(httpx.AsyncClient().post(webhook_url, json=results, timeout=10))
                except Exception as e:
                    logging.error(f"Webhook execution failed: {e}")

        if stream_queue: yield f"data: {json.dumps({'status': 'Workflow Finished', 'results': results})}\n\n"
    finally:
        if page:
            await page.close()


@app.post("/execute")
async def execute_workflow(request: Request):
    async def error_stream(msg: str):
        yield f"data: {json.dumps({'error': msg})}\n\n"

    if bot_semaphore.locked():
        # Reject new requests if a workflow is already running to protect the browser instance
        return StreamingResponse(error_stream("Server is busy. Please try again later."), media_type="text/event-stream")

    try:
        data = await request.json()
    except Exception as e:
        return StreamingResponse(error_stream(f"Invalid JSON payload: {str(e)}"), media_type="text/event-stream")

    steps = data.get('steps', [])
    workspace_id = data.get('workspace_id')
    profile_id = data.get('profile_id', '1')

    if not steps:
        return StreamingResponse(error_stream("No steps provided in workflow."), media_type="text/event-stream")

    # Acquire the semaphore after payload parsing to prevent deadlocks on invalid requests
    try:
        await asyncio.wait_for(bot_semaphore.acquire(), timeout=0.1)
    except asyncio.TimeoutError:
        return StreamingResponse(error_stream("Server is busy. Please try again later."), media_type="text/event-stream")

    if cancel_event:
        cancel_event.clear()

    # Shared queue to receive pseudo-streaming updates from the bot callback
    stream_queue = asyncio.Queue()

    async def sse_wrapper():
        try:
            async for event in run_workflow_engine(steps, workspace_id, stream_queue, profile_id):
                yield event
        finally:
            bot_semaphore.release()

    return StreamingResponse(sse_wrapper(), media_type="text/event-stream")

    # We use StreamingResponse to send Server-Sent Events (SSE) back to the client
    # This prevents the long-running process from timing out the HTTP connection
    # and provides real-time feedback to the UI.
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)