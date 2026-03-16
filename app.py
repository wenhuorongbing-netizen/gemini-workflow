from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
import logging
from bot import GeminiBot, JulesBot
import json
import uuid
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from github import Github
import dotenv

dotenv.load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")

gh_client = Github(GITHUB_TOKEN) if GITHUB_TOKEN else None

class AuthException(Exception):
    pass

def get_github_repo():
    if not gh_client or not GITHUB_REPO:
        raise AuthException("Please add a valid GITHUB_TOKEN to your .env file")
    from github.GithubException import GithubException
    try:
        return gh_client.get_repo(GITHUB_REPO)
    except GithubException as e:
        if e.status == 401:
            raise AuthException("Please add a valid GITHUB_TOKEN to your .env file")
        raise e

def create_feature_branch(base_branch="main", new_branch_name=None):
    if not new_branch_name:
        raise ValueError("new_branch_name is required")
    repo = get_github_repo()
    base_ref = repo.get_git_ref(f"heads/{base_branch}")
    repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=base_ref.object.sha)
    return new_branch_name

def get_branch_diff(base_branch="main", compare_branch=None):
    if not compare_branch:
         raise ValueError("compare_branch is required")
    repo = get_github_repo()
    comparison = repo.compare(base_branch, compare_branch)
    diff = []
    for file in comparison.files:
        filename = file.filename
        if (
            filename.endswith("package-lock.json") or
            filename.endswith("yarn.lock") or
            filename.endswith(".svg") or
            filename.endswith(".png") or
            ".next/" in filename or
            "node_modules/" in filename
        ):
            continue
        diff.append(f"File: {file.filename}\nStatus: {file.status}\nDiff:\n{file.patch}\n")
    return "\n".join(diff)

def merge_and_delete_branch(head_branch, base_branch="main"):
    repo = get_github_repo()

    # Check if there is a diff first
    comparison = repo.compare(base_branch, head_branch)
    if comparison.ahead_by == 0:
        return {"status": "success", "message": "Nothing to merge (branches are identical).", "merged": False}

    # Attempt to merge
    try:
        merge_msg = f"Auto-merge {head_branch} into {base_branch}"
        merge_result = repo.merge(base_branch, head_branch, merge_msg)

        # Delete the branch
        ref = repo.get_git_ref(f"heads/{head_branch}")
        ref.delete()
        return {"status": "success", "message": "Branch merged and deleted successfully.", "merged": True, "sha": merge_result.sha}
    except Exception as e:
         return {"status": "error", "message": f"Merge failed: {str(e)}", "merged": False}


app = FastAPI()


@app.post("/api/accounts/login")
async def login_account(profile_id: str):
    import bot
    try:
        # Stop global bot if it's running on this profile to release lock
        global bot_instance
        if bot_instance is not None and getattr(bot_instance, 'profile_path', '') == f"chrome_profile_{profile_id}":
            await bot_instance.quit()
            bot_instance = None

        b = bot.GeminiBot(profile_path=f"chrome_profile_{profile_id}")
        await b.initialize(headless=False)
        # We need to open gemini.google.com for login
        page = await b.create_new_page()
        await page.goto("https://gemini.google.com")
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = AsyncIOScheduler()

import datetime

EPICS_FILE = 'epics.json'
GLOBALS_FILE = 'globals.json'
TEMPLATES_FILE = 'templates.json'
HISTORY_FILE = 'history.json'
HEADLESS_MODE = True

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_history(data):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.get("/api/workspaces/{workspace_id}/history")
async def get_workspace_history(workspace_id: str):
    history_db = load_history()
    ws_history = history_db.get(workspace_id, [])
    return JSONResponse(ws_history)

def load_templates():
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_templates(data):
    with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.get("/api/templates")
async def get_templates():
    return JSONResponse(load_templates())

@app.post("/api/templates/{template_id}")
async def save_template_endpoint(template_id: str, request: Request):
    data = await request.json()
    templates_db = load_templates()
    templates_db[template_id] = {
        "name": data.get("name", "New Template"),
        "description": data.get("description", ""),
        "steps": data.get("steps", [])
    }
    save_templates(templates_db)
    return JSONResponse({"status": "success"})

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
@app.get("/api/epics")
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

@app.get("/api/devhouse/diff")
async def api_devhouse_diff(compare_branch: str, base_branch: str = "main"):
    try:
        diff = get_branch_diff(base_branch, compare_branch)
        return {"status": "success", "diff": diff}
    except AuthException as e:
        return JSONResponse({"error": str(e)}, status_code=401)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/devhouse/merge")
async def api_devhouse_merge(request: Request):
    data = await request.json()
    head_branch = data.get("head_branch")
    base_branch = data.get("base_branch", "main")
    if not head_branch:
        return JSONResponse({"status": "error", "message": "head_branch is required"}, status_code=400)
    try:
        result = merge_and_delete_branch(head_branch, base_branch)
        return result
    except AuthException as e:
        return JSONResponse({"error": str(e)}, status_code=401)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

import google.generativeai as genai

@app.post("/api/devhouse/review")
async def api_devhouse_review(request: Request):
    data = await request.json()
    base_branch = data.get("base_branch", "main")
    feature_branch = data.get("feature_branch")

    if not feature_branch:
        return JSONResponse({"status": "error", "message": "feature_branch is required"}, status_code=400)

    try:
        diff = get_branch_diff(base_branch, feature_branch)
        if not diff.strip():
            return {"status": "no_changes"}

        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            return JSONResponse({"status": "error", "message": "GEMINI_API_KEY is not set in .env"}, status_code=500)

        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-pro')

        prompt = f"You are the Lead Technical PM. Review this code diff. Ensure it meets the goal without introducing regressions. Diff: {diff}"
        response = model.generate_content(prompt)

        return {"status": "success", "review": response.text}

    except AuthException as e:
        return JSONResponse({"error": str(e)}, status_code=401)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

devhouse_lock = asyncio.Lock()
devhouse_queue = asyncio.Queue()

async def run_devhouse_autopilot(initial_prompt, kb_links, model_type, max_iterations=5):
    import datetime
    import time
    import google.generativeai as genai
    import bot

    branch_name = f"devhouse-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    jules_bot = None
    jules_page = None

    try:
        await devhouse_queue.put({"type": "info", "message": f"[PM] Analyzing requirements for Auto-Dev loop..."})

        await devhouse_queue.put({"type": "action", "message": f"[DEV] Spawning Jules..."})

        jules_bot = bot.JulesBot(profile_id="1")
        jules_page = await jules_bot.create_new_page()

        # Prepare the first instruction for Jules
        jules_instruction = f"Task: {initial_prompt}\nKnowledge Base: {kb_links}\nBranch: {branch_name}"

        accumulated_context = jules_instruction
        import sqlite3
        import os

        def save_state(count, ctx, status):
            try:
                db_path = os.path.join(os.path.dirname(__file__), 'dev.db')
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS DevHouseState (
                        id TEXT PRIMARY KEY,
                        branch TEXT,
                        iteration INTEGER,
                        max_iterations INTEGER,
                        accumulated_context TEXT,
                        status TEXT,
                        updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    INSERT OR REPLACE INTO DevHouseState (id, branch, iteration, max_iterations, accumulated_context, status, updatedAt)
                    VALUES ('active', ?, ?, ?, ?, ?, datetime('now'))
                """, (branch_name, count, max_iterations, ctx, status))
                conn.commit()
                conn.close()
            except Exception as e:
                logging.error(f"Failed to save DevHouse state: {e}")

        # Check if we should resume
        try:
             db_path = os.path.join(os.path.dirname(__file__), 'dev.db')
             conn = sqlite3.connect(db_path)
             cursor = conn.cursor()
             # We just query, if table doesn't exist, we skip resume
             cursor.execute("SELECT branch, iteration, max_iterations, accumulated_context, status FROM DevHouseState WHERE id = 'active'")
             row = cursor.fetchone()
             if row and row[4] == 'running':
                 branch_name = row[0]
                 start_iteration = row[1]
                 max_iterations = row[2]
                 accumulated_context = row[3]
                 await devhouse_queue.put({"type": "info", "message": f"[PM] Resuming DevHouse run from DB state on iteration {start_iteration}..."})

                 # Restore jules_instruction from accumulated context (the last block of text is the latest instruction)
                 jules_instruction = f"Task: {initial_prompt}\nKnowledge Base: {kb_links}\nBranch: {branch_name}\n\nResuming previous instruction set from crashed state."
                 if "Review (Iter" in accumulated_context:
                      parts = accumulated_context.split("Review (Iter")
                      latest_review = parts[-1]
                      jules_instruction = f"Code Review Feedback:\n{latest_review}\n\nPlease fix these issues."
             else:
                 start_iteration = 1
                 create_feature_branch("main", branch_name)
                 save_state(1, accumulated_context, 'running')
             conn.close()
        except sqlite3.OperationalError:
             start_iteration = 1
             create_feature_branch("main", branch_name)
             save_state(1, accumulated_context, 'running')

        for iteration in range(start_iteration, max_iterations + 1):
            await devhouse_queue.put({"type": "info", "message": f"[DEV] Iteration {iteration}/{max_iterations}: Sending instructions to Jules..."})
            save_state(iteration, accumulated_context, 'running')

            # Step A: Send task to Jules
            await jules_bot.send_task(jules_page, "https://jules.dev", jules_instruction)

            # Step B: Wait for Jules to finish
            await devhouse_queue.put({"type": "info", "message": f"[DEV] Iteration {iteration}/{max_iterations}: Writing code... Waiting for 'Ready for Review'."})

            # 30-second monitoring loop
            jules_status = ""
            max_polls = 60 # 60 * 30s = 30 mins
            for poll in range(max_polls):
                status_res = await jules_bot.poll_for_completion(jules_page, stream_queue=devhouse_queue, step_id="autopilot", interval_seconds=30)
                if "Ready for review" in status_res or "Jules finished" in status_res:
                     jules_status = status_res
                     break
                await asyncio.sleep(30)

            if not jules_status:
                raise Exception("Timeout waiting for Jules to finish task.")

            await devhouse_queue.put({"type": "action", "message": f"[GIT] Code pushed by Jules. Fetching diff for branch '{branch_name}'..."})

            # Step C: Get Diff
            diff = get_branch_diff("main", branch_name)

            if not diff.strip():
                await devhouse_queue.put({"type": "info", "message": f"[PM] No changes detected in diff. Jules might have failed."})
                break

            # Step D: Gemini Code Review
            await devhouse_queue.put({"type": "action", "message": f"[PM] Reviewing Diff: Analyzing code changes..."})

            gemini_api_key = os.environ.get("GEMINI_API_KEY")
            if not gemini_api_key:
                raise Exception("GEMINI_API_KEY is not set.")

            genai.configure(api_key=gemini_api_key)
            model = genai.GenerativeModel('gemini-1.5-pro') if model_type == "Pro" else genai.GenerativeModel('gemini-1.5-flash')

            review_prompt = f"You are the Lead Technical PM. Review this code diff. If the code looks perfect and meets the goal without regressions, output exactly 'LGTM'. Otherwise, provide specific feedback to the developer on what to fix. Diff:\n{diff}\n\nAccumulated Context:\n{accumulated_context}"
            response = model.generate_content(review_prompt)
            review_text = response.text

            accumulated_context += f"\n\nReview (Iter {iteration}):\n{review_text}"

            if "LGTM" in review_text.strip():
                await devhouse_queue.put({"type": "review", "message": f"[PM] Review complete: LGTM. Proceeding to merge."})
                break

            await devhouse_queue.put({"type": "review", "message": f"[PM] Reviewing Diff: Found issues. Sending feedback back:\n{review_text}"})

            # Step E: Feed feedback back to Jules
            jules_instruction = f"Code Review Feedback:\n{review_text}\n\nPlease fix these issues."

        # End of Loop - Auto-Merge
        await devhouse_queue.put({"type": "action", "message": f"[GIT] DevHouse loop finished. Merging branch '{branch_name}' and cleaning up."})
        save_state(max_iterations, accumulated_context, 'merging')
        merge_and_delete_branch(branch_name, "main")
        save_state(max_iterations, accumulated_context, 'finished')

        await devhouse_queue.put({"type": "info", "message": f"[SYSTEM] Merge complete. DevHouse Autopilot cycle finished."})

    except Exception as e:
        save_state(1, str(e), 'failed')
        await devhouse_queue.put({"type": "error", "message": f"[ERROR] DevHouse Autopilot crashed: {str(e)}"})
    finally:
        if jules_bot:
            await jules_bot.quit()

@app.post("/api/devhouse/start")
async def api_devhouse_start(request: Request, background_tasks: BackgroundTasks):
    if devhouse_lock.locked():
         return JSONResponse({"status": "error", "message": "A DevHouse Autopilot loop is already running."}, status_code=409)

    data = await request.json()
    prompt = data.get("prompt")
    kb_links = data.get("kbLinks", "")
    model = data.get("model", "Pro")

    if not prompt:
        return JSONResponse({"status": "error", "message": "prompt is required"}, status_code=400)

    async def task_wrapper():
        async with devhouse_lock:
            # Clear old queue messages before starting
            while not devhouse_queue.empty():
                 try:
                     devhouse_queue.get_nowait()
                 except asyncio.QueueEmpty:
                     break
            await run_devhouse_autopilot(prompt, kb_links, model)
            await devhouse_queue.put("__DONE__")

    background_tasks.add_task(task_wrapper)
    return {"status": "success", "message": "Started Auto-Dev loop in the background."}

@app.get("/api/devhouse/logs")
async def stream_devhouse_logs():
    async def log_generator():
        try:
            while True:
                event = await devhouse_queue.get()
                if event == "__DONE__":
                    break
                yield f"data: {json.dumps(event)}\n\n"
        except Exception:
            pass

    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

import uuid
task_streams = {}

async def run_workflow_engine(steps, workspace_id, stream_queue=None, profile_id="1", run_variables=None, global_state=None, user_id="user1", start_index=0, initial_results=None):
    if run_variables is None:
        run_variables = {}
    if global_state is None:
        global_state = {}
    run_id = str(uuid.uuid4())
    page = None
    try:
        results = initial_results if initial_results is not None else {}
        correction_counts = {}
        page = None
        current_bot = None

        index = start_index
        while index < len(steps):
            step = steps[index]
            step_profile_id = step.get('profileId', profile_id)

            # Re-initialize bot if profile changes or not yet initialized
            if not current_bot or getattr(current_bot, 'profile_path', None) != (f"chrome_profile_{step_profile_id}" if step_profile_id != "1" else "chrome_profile"):
                if page: await page.close()
                current_bot = await get_bot(step_profile_id)
                page = await current_bot.create_new_page()
            if cancel_event and cancel_event.is_set():
                if stream_queue: yield f"data: {json.dumps({'step': index + 1, 'status': 'Canceled', 'message': 'Workflow stopped by user.'})}\n\n"
                break

            step_id = step.get('id', str(index + 1))
            prompt_template = step.get('prompt', '')
            new_chat = step.get('new_chat', False)
            step_type = step.get('type', 'standard')
            chat_url = step.get('chat_url', '').strip()
            show_result = step.get('show_result', True)
            system_prompt = step.get('system_prompt', '').strip()

            # Global Context State Injection (Blackboard)
            for g_key, g_val in global_state.items():
                g_tag = f"{{{{GLOBAL_{g_key}}}}}"
                if g_tag in prompt_template:
                    prompt_template = prompt_template.replace(g_tag, g_val)
                if system_prompt and g_tag in system_prompt:
                    system_prompt = system_prompt.replace(g_tag, g_val)

            # Global variable injection
            global_vars = load_globals()
            for g_key, g_val in global_vars.items():
                g_tag = f"{{{{GLOBAL_{g_key}}}}}"
                if g_tag in prompt_template:
                    prompt_template = prompt_template.replace(g_tag, g_val)

            # Runtime variable injection
            for rv_key, rv_val in run_variables.items():
                rv_tag = f"{{{{RUN_VAR_{rv_key}}}}}"
                if rv_tag in prompt_template:
                    prompt_template = prompt_template.replace(rv_tag, str(rv_val))

            logging.info(f"Executing Step {step_id} (Type: {step_type})")
            if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Starting', 'message': f'Executing Step {step_id}...'})}\n\n"

            if step_type == 'file':
                file_name = step.get('fileName', 'Unknown File')
                file_content = step.get('fileContent', '')
                results[str(step_id)] = file_content
                # Export as a global-like variable for immediate downstream use via {{FILE_CONTENT}}
                global_state['FILE_CONTENT'] = file_content
                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': f'Loaded file: {file_name}', 'show_result': show_result})}\n\n"
                index += 1
                continue

            elif step_type == 'approval':
                try:
                    prev_step_id = str(int(step_id) - 1)
                except ValueError:
                    prev_step_id = ""
                prev_result = results.get(prev_step_id, "")

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

            elif step_type == 'agentic_loop':
                # Meta-Agent Loop (Gemini <-> Jules)
                jules_url = step.get('chat_url', '')
                try:
                    max_iterations = int(step.get('max_iterations', 3))
                    max_iterations = max(1, min(10, max_iterations))
                except ValueError:
                    max_iterations = 3

                loop_result = ""
                current_gemini_prompt = prompt_template
                if system_prompt:
                    current_gemini_prompt = f"System Instructions / Persona:\n{system_prompt}\n\nTask:\n{current_gemini_prompt}"

                if stream_queue: yield f"data: {{json.dumps({{'step': step_id, 'status': 'Agent Loop Started', 'message': 'Initializing Dual-Bot Engine...'}})}}\n\n"

                jules_bot = JulesBot(profile_id=profile_id)
                jules_page = None

                # We need accumulated context to pass across reset boundaries
                # We need accumulated context to pass across reset boundaries
                from datetime import datetime
                accumulated_context = f"[{datetime.now().strftime('%H:%M:%S')}] Task: {current_gemini_prompt}"


                try:
                    reset_threshold = int(step.get('reset_threshold', 3))
                except ValueError:
                    reset_threshold = 3

                try:
                    stop_sequence = step.get('stop_sequence', 'FINAL_REVIEW_COMPLETE')
                except Exception:
                    stop_sequence = 'FINAL_REVIEW_COMPLETE'

                for i in range(max_iterations):
                    if cancel_event and cancel_event.is_set():
                        break

                    # --- Context Reset (Prevent DOM Bloat) ---
                    if i > 0 and i % reset_threshold == 0:
                        if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Agent Loop Checkpoint', 'message': '[TELEMETRY] Routine context reset to prevent DOM bloat. Initializing new chat context...', 'screen': 'left'})}\n\n"
                        # We don't just reload the current page, we explicitly start a new chat
                        # and pass the summarized context to re-ground Gemini without the 3-turn heavy DOM
                        await current_bot.start_new_chat(page)
                        current_gemini_prompt = f"We are continuing a task. Here is the context so far:\n{accumulated_context}\n\nResume the review and next steps."

                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Gemini Working', 'message': f'Iteration {i+1}: Gemini generating coding prompt...', 'screen': 'left'})}\n\n"

                    # 1. Prompt Gemini
                    if new_chat and i == 0:
                        await current_bot.start_new_chat(page)
                    elif i == 0 and chat_url and chat_url.startswith("https://gemini.google.com"):
                        await current_bot.goto_specific_chat(page, chat_url)

                    attachments = step.get('attachments', [])
                    model_type = step.get('model', 'Auto')
                    await current_bot.send_prompt(page, current_gemini_prompt, attachments=attachments, model=model_type)

                    # Poll for Gemini Output
                    gemini_output_captured = {"text": ""}
                    async def gemini_poll_cb(text):
                        if text and text != gemini_output_captured["text"]:
                            gemini_output_captured["text"] = text
                            if stream_queue: await stream_queue.put(f"data: {json.dumps({'step': step_id, 'status': 'Gemini Output', 'message': text, 'screen': 'left'})}\n\n")

                    await current_bot.wait_for_response(page, timeout=300000, poll_callback=gemini_poll_cb)
                    gemini_response = await current_bot.get_last_response(page)

                    accumulated_context += f"\n\nGemini: {gemini_response}"

                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Gemini Output', 'message': gemini_response, 'screen': 'left'})}\n\n"

                    # If Gemini outputs something indicating it's completely done, we break early
                    if stop_sequence in gemini_response:
                        loop_result = gemini_response
                        break

                    # 2. Prompt Jules
                    if not jules_url:
                        loop_result = f"Error: Jules/Repository URL not provided. Gemini generated: {gemini_response}"
                        break

                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Jules Working', 'message': f'Iteration {i+1}: Sent to Jules. Waiting for completion...', 'screen': 'right'})}\n\n"

                    jules_response = ""
                    try:
                        # Attempt to use existing page to save overhead, if not create one
                        if not jules_page or jules_page.is_closed():
                            jules_page = await jules_bot.create_new_page()

                        await jules_bot.send_task(jules_page, jules_url, gemini_response, stream_queue=stream_queue, step_id=step_id)

                        jules_response = await jules_bot.poll_for_completion(jules_page, stream_queue=stream_queue, step_id=step_id)

                        if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Jules Output', 'message': jules_response, 'screen': 'right'})}\n\n"
                    except Exception as e:
                        error_msg = str(e)
                        if "BROWSER_CRASH" in error_msg:
                            # Context Recovery Logic
                            if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Jules Error', 'message': '💥 内存过载，系统正在为您自动重置环境...', 'screen': 'right'})}\n\n"
                            await jules_bot.quit()

                            # Initialize fresh bot
                            jules_bot = JulesBot(profile_id=profile_id)
                            jules_page = await jules_bot.create_new_page()

                            # Re-inject system_role and accumulated_context
                            if system_prompt:
                                current_gemini_prompt = f"System Instructions / Persona:\n{system_prompt}\n\nWe are continuing a task after a crash. Here is the context so far:\n{accumulated_context}\n\nResume the review and next steps."
                            else:
                                current_gemini_prompt = f"We are continuing a task after a crash. Here is the context so far:\n{accumulated_context}\n\nResume the review and next steps."

                            jules_response = "Jules experienced a system crash and was rebooted. Please resend the instructions."
                        else:
                            jules_response = f"Jules Error: {error_msg}"
                            if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Jules Error', 'message': jules_response, 'screen': 'right'})}\n\n"

                    accumulated_context += f"\n\nJules: {jules_response}"

                    # 3. Next iteration prompt
                    if "system crash and was rebooted" in jules_response:
                        pass # current_gemini_prompt is already set to the recovery prompt
                    else:
                        current_gemini_prompt = f"Jules has finished with the following output/status: {jules_response}\n\nPlease review this. If everything is correct and no further coding is needed, reply with 'FINAL_REVIEW_COMPLETE'. Otherwise, provide the next set of coding instructions for Jules."
                    loop_result = f"Latest Jules Output: {jules_response}\nLatest Gemini Review: {gemini_response}"

                await jules_bot.quit()

                results[str(step_id)] = loop_result
                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': loop_result, 'show_result': show_result})}\n\n"
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

            elif step_type == 'router':
                target_variable = step.get('targetVariable', '')
                condition = step.get('condition', 'CONTAINS')
                condition_value = step.get('conditionValue', '')

                true_target = step.get('trueTarget')
                false_target = step.get('falseTarget')

                # Resolve variable
                var_val = target_variable
                for past_id, past_output in results.items():
                    tag = f"{{{{OUTPUT_{past_id}}}}}"
                    if tag in var_val:
                        var_val = var_val.replace(tag, str(past_output))

                for s in steps:
                    tag = f"{{{{{s.get('id', '')}}}}}"
                    if tag in var_val and s.get('id', '') in results:
                        var_val = var_val.replace(tag, str(results[s.get('id', '')]))

                condition_met = False
                op = condition.upper()
                if op == 'CONTAINS':
                    condition_met = condition_value in var_val
                elif op == 'NOT CONTAINS':
                    condition_met = condition_value not in var_val
                elif op == 'EQUALS':
                    condition_met = condition_value == var_val

                target_node_id = true_target if condition_met else false_target

                msg = f"Condition evaluated to {condition_met}."
                if target_node_id:
                    msg += f" Routing to {target_node_id}..."
                else:
                    msg += " No valid route found, ending branch."

                if stream_queue: yield f"data: {{json.dumps({{'step': step_id, 'status': 'Routing', 'message': msg}})}}\n\n"
                results[str(step_id)] = msg

                if target_node_id:
                    # Find index of target_node_id in steps
                    next_index = -1
                    for i, s in enumerate(steps):
                        if str(s['id']) == str(target_node_id):
                            next_index = i
                            break
                    if next_index != -1:
                        index = next_index
                        continue
                    else:
                        if stream_queue: yield f"data: {{json.dumps({{'step': step_id, 'status': 'Error', 'message': 'Target node not found in compilation order.'}})}}\n\n"
                        break
                else:
                    # No path defined for this condition outcome, workflow terminates gracefully.
                    break

            elif step_type == 'webhook':
                webhook_url = chat_url # Reuse chat_url field for webhook url
                if not webhook_url:
                    results[str(step_id)] = "[FAILED] No webhook URL provided."
                    if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'result': results[str(step_id)]})}\n\n"
                    index += 1
                    continue

                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Sending Webhook', 'message': f'POSTing to {webhook_url}'})}\n\n"

                final_payload_str = prompt_template
                for past_id, past_output in results.items():
                    tag = f"{{{{OUTPUT_{past_id}}}}}"
                    if tag in final_payload_str:
                        # Ensure proper escaping for JSON payloads if injecting directly
                        escaped_output = json.dumps(past_output)[1:-1] # Strip quotes but keep escapes
                        final_payload_str = final_payload_str.replace(tag, escaped_output)

                import httpx
                try:
                    payload = json.loads(final_payload_str)
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(webhook_url, json=payload)
                        resp.raise_for_status()
                        results[str(step_id)] = f"Webhook success: {resp.status_code}\n{resp.text}"
                        if stream_queue: yield f"data: {{json.dumps({{'step': step_id, 'status': 'Complete', 'result': results[str(step_id)], 'show_result': show_result}})}}\n\n"
                except httpx.TimeoutException:
                    logging.warning(f"[WARN] Webhook Timeout: {webhook_url}")
                    results[str(step_id)] = f"[WARN] Webhook Timeout: Request timed out after 10 seconds."
                    if stream_queue: yield f"data: {{json.dumps({{'step': step_id, 'status': 'Error', 'result': results[str(step_id)]}})}}\n\n"
                except Exception as e:
                    results[str(step_id)] = f"[WEBHOOK FAILED] {str(e)}"
                    if stream_queue: yield f"data: {{json.dumps({{'step': step_id, 'status': 'Error', 'result': results[str(step_id)]}})}}\n\n"

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

                try:
                    prev_step_id = str(int(step_id) - 1)
                except ValueError:
                    prev_step_id = ""
                prev_input = results.get(prev_step_id, "")

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

                # Enforce strict concurrent limits (max 3) for batch execution to avoid spawning 100 browsers at once
                concurrent_semaphore = asyncio.Semaphore(3)

                async def process_item(item, item_index):
                    item_page = None
                    # Wait outside the try/finally so we don't accidentally close an un-acquired lock/unspawned page
                    await concurrent_semaphore.acquire()
                    try:
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

                                attachments = step.get('attachments', [])
                                model_type = step.get('model', 'Auto')
                                await current_bot.send_prompt(item_page, final_prompt, attachments=attachments, model=model_type)

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

                # Explicitly wrap gather to ensure we run parallel safe.
                try:
                    batch_results = await asyncio.gather(*tasks)
                finally:
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

                            # Smart Context Injection: Replace {{OUTPUT_X}} and {{NODE_ID}} with actual results
                            final_prompt = prompt_template
                            if system_prompt:
                                final_prompt = f"System Instructions / Persona:\n{system_prompt}\n\nUser Request:\n{final_prompt}"

                            for past_id, past_output in results.items():
                                tag = f"{{{{OUTPUT_{past_id}}}}}"
                                if tag in final_prompt:
                                    final_prompt = final_prompt.replace(tag, past_output)

                                node_tag = f"{{{{{past_id}}}}}"
                                if node_tag in final_prompt:
                                    final_prompt = final_prompt.replace(node_tag, str(past_output))

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
                                attachments = step.get('attachments', [])
                                model_type = step.get('model', 'Auto')
                                await current_bot.send_prompt(page, final_prompt, attachments=attachments, model=model_type)

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
                        # Enforce strict concurrent limits for auto-chunking (max 3)
                        concurrent_semaphore = asyncio.Semaphore(3)

                        async def process_chunk(chunk_text, chunk_index):
                            chunk_page = None
                            # Acquire semaphore first, so we don't spam 100 page creations
                            await concurrent_semaphore.acquire()
                            try:
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

                                        await current_bot.send_prompt(chunk_page, chunk_wrapper, attachments=step.get('attachments', []), model=step.get('model', 'Auto'))

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

                        try:
                            chunk_results = await asyncio.gather(*chunk_tasks)
                        finally:
                            if pump_task: pump_task.cancel()

                        final_result_text = "\n\n--- [Auto-Chunk Break] ---\n\n".join(chunk_results)
                        results[str(step_id)] = final_result_text
                        if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': final_result_text, 'show_result': show_result})}\n\n"
                        step_success = True

            if not step_success:
                # If a critical error occurs and all retries fail, break the workflow to avoid cascaded failures
                break

            index += 1


        # History and persistence is now handled by the Next.js database frontend.
        # We operate purely statelessly here as an execution engine.
        if stream_queue: yield f"data: {json.dumps({'status': 'Workflow Finished', 'results': results, 'timestamp': str(datetime.datetime.now())})}\n\n"
    finally:
        if page:
            await page.close()




@app.post("/stop_task/{task_id}")
async def stop_specific_task(task_id: str):
    task = active_tasks.get(task_id)
    if task:
        task.cancel()
        del active_tasks[task_id]
        if task_id in task_streams:
            await task_streams[task_id].put({"status": "Error", "message": "🚫 Workflow execution manually cancelled by user."})
            # Give it a moment to send the message before removing the queue
            await asyncio.sleep(0.5)
            del task_streams[task_id]
        return {"status": "cancelled", "task_id": task_id}
    return {"status": "not_found", "task_id": task_id}

@app.get("/stop")
async def stop_workflow():
    if cancel_event:
        cancel_event.set()
        logging.warning("User initiated manual stop.")
        return JSONResponse({"status": "stopping"})
    return JSONResponse({"status": "no active workflow"})

async def execution_wrapper(task_id, steps, workspace_id, profile_id, run_variables, global_state):
    stream_queue = asyncio.Queue()
    try:
        await bot_semaphore.acquire()
        if cancel_event:
            cancel_event.clear()

        async for event in run_workflow_engine(steps, workspace_id, stream_queue, profile_id, run_variables, global_state):
            await task_streams[task_id].put(event)
    except Exception as e:
        await task_streams[task_id].put(f"data: {json.dumps({'error': str(e)})}\n\n")
    finally:
        bot_semaphore.release()
        await task_streams[task_id].put("__DONE__")

@app.post("/resume")
async def resume_workflow(request: Request):
    try:
        data = await request.json()
        run_id = data.get('run_id')
        action = data.get('action') # 'approve' or 'reject'
        edited_text = data.get('text', '')

        import sqlite3, os
        db_path = os.path.join(os.path.dirname(__file__), 'dev.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT logs, userId, workflowId FROM RunHistory WHERE id = ?", (run_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return JSONResponse({"error": "Run not found"}, status_code=404)

        state_str, user_id, workspace_id = row
        state = json.loads(state_str)

        if action == 'reject':
            cursor.execute("UPDATE RunHistory SET status = 'Canceled' WHERE id = ?", (run_id,))
            conn.commit()
            conn.close()
            return JSONResponse({"status": "rejected"})

        index = state['index']
        steps = state['steps']
        results = state['results']

        approval_step_id = steps[index-1]['id']
        results[str(approval_step_id)] = edited_text

        task_id = str(uuid.uuid4())
        task_streams[task_id] = asyncio.Queue()

        # Dispatch background task resuming from index
        asyncio.create_task(task_worker(
            task_id,
            steps,
            workspace_id,
            "1", # profile_id
            state['run_variables'],
            state['global_state'],
            user_id,
            start_index=index,
            initial_results=results
        ))

        cursor.execute("UPDATE RunHistory SET status = 'Resumed' WHERE id = ?", (run_id,))
        conn.commit()
        conn.close()

        return {"task_id": task_id, "status": "resumed"}

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/execute")
async def execute_workflow(request: Request):
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"Invalid JSON payload: {str(e)}"}, status_code=400)
    # Cycle detection
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    if nodes and edges:
        in_degree = {node['id']: 0 for node in nodes}
        for edge in edges:
            if edge['target'] in in_degree:
                in_degree[edge['target']] += 1
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        visited_count = 0
        while queue:
            curr = queue.pop(0)
            visited_count += 1
            for edge in edges:
                if edge['source'] == curr:
                    target = edge['target']
                    if target in in_degree:
                        in_degree[target] -= 1
                        if in_degree[target] == 0:
                            queue.append(target)
        if visited_count != len(nodes) and len(nodes) > 0:
            return JSONResponse({"error": "Circular dependency detected in workflow diagram."}, status_code=400)


    steps = data.get('steps', [])
    workspace_id = data.get('workspace_id')
    profile_id = data.get('profile_id', '1')
    run_variables = data.get('run_variables', {})
    global_state = data.get('global_state', {})

    user_id = data.get('user_id', 'user1')

    # --- SAAS QUOTA CHECK ---
    if user_id:
        import sqlite3
        import os
        try:
            db_path = os.path.join(os.path.dirname(__file__), 'dev.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Auto-create user for seamless mock-auth experience
            cursor.execute("INSERT OR IGNORE INTO User (id, email, tokens_balance, createdAt, updatedAt) VALUES (?, ?, 5, datetime('now'), datetime('now'))", (user_id, f"{user_id}@example.com"))
            conn.commit()

            cursor.execute("SELECT tokens_balance FROM User WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                quota = row[0]
                if quota <= 0:
                    conn.close()
                    return JSONResponse({"error": "[SYSTEM_ERROR] 免费额度已耗尽 (Quota Exceeded). 请充值获取更多额度。"}, status_code=403)
                else:
                    cursor.execute("UPDATE User SET tokens_balance = tokens_balance - 1 WHERE id = ?", (user_id,))
                    conn.commit()
            else:
                conn.close()
                return JSONResponse({"error": "[SYSTEM_ERROR] User not found."}, status_code=403)
            conn.close()
        except Exception as e:
            logging.error(f"Quota check failed: {e}")
            return JSONResponse({"error": "[SYSTEM_ERROR] 余额校验失败 (Quota validation failed). 请稍后再试。"}, status_code=500)
    # ------------------------

    if not steps:
        return JSONResponse({"error": "No steps provided in workflow."}, status_code=400)

    task_id = str(uuid.uuid4())
    task_streams[task_id] = asyncio.Queue()

    # Spawn background task instantly
    asyncio.create_task(execution_wrapper(task_id, steps, workspace_id, profile_id, run_variables, global_state))

    return JSONResponse({"task_id": task_id, "status": "queued"})

@app.get("/api/logs/{task_id}")
async def stream_logs(task_id: str):
    if task_id not in task_streams:
        return JSONResponse({"error": "Task not found"}, status_code=404)

    async def log_generator():
        queue = task_streams[task_id]
        try:
            while True:
                event = await queue.get()
                if event == "__DONE__":
                    break
                yield event
        finally:
            if task_id in task_streams:
                del task_streams[task_id]

    return StreamingResponse(log_generator(), media_type="text/event-stream")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)
