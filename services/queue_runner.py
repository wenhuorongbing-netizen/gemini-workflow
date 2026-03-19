import asyncio
import logging
import httpx
import os
import subprocess
import json
import datetime
from services.state import devhouse_lock, devhouse_queue, uat_approval_event, uat_decision
from services.db_service import DevHouseDB
from utils.secrets import SecretManager
from utils.git_helpers import index_repository, scan_repo_structure, get_branch_diff, create_feature_branch, merge_and_delete_branch

async def run_devhouse_autopilot(task_id, initial_prompt, attachments, target_repo, kb_links, model_type, max_iterations=5):
    import time
    import bot
    from agents import PMAgent, DevAgent, QAAgent, SecOpsAgent
    from app import log_telemetry

    pm_tokens_burned = 0
    dev_tokens_burned = 0
    iteration = 0

    branch_name = f"devhouse-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    jules_bot = None
    jules_page = None

    repo_name = target_repo.split('/')[-1].replace('.git', '')
    import uuid
    run_id = str(uuid.uuid4())
    workspace_dir = f"/tmp/devhouse_workspaces/{run_id}/"

    try:
        await devhouse_queue.put({"type": "info", "message": f"[PM] Analyzing requirements for Auto-Dev loop..."})
        await devhouse_queue.put({"type": "action", "message": f"[DEV] Cloning {target_repo} into Sandbox..."})

        os.makedirs("/tmp/devhouse_workspaces", exist_ok=True)
        if os.path.exists(workspace_dir):
            subprocess.run(["rm", "-rf", workspace_dir], check=True)

        git_token = SecretManager.get_github_token()
        clone_url = f"https://oauth2:{git_token}@github.com/{target_repo}.git" if git_token else f"https://github.com/{target_repo}.git"

        try:
            subprocess.run(["git", "clone", clone_url, workspace_dir], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            error_msg = SecretManager.mask_secrets(str(e))
            stderr_masked = SecretManager.mask_secrets(e.stderr) if e.stderr else ""
            raise Exception(f"Failed to clone repository: {error_msg}. Stderr: {stderr_masked}")

        await devhouse_queue.put({"type": "info", "message": f"[SYSTEM] Indexing repository for Codebase RAG..."})
        radar_report = index_repository(workspace_dir, initial_prompt)
        repo_structure = scan_repo_structure(workspace_dir)

        await devhouse_queue.put({"type": "radar", "message": f"Radar mapped {workspace_dir}"})
        await devhouse_queue.put({"type": "action", "message": f"[PM] Generating initial technical spec..."})
        pm_agent = PMAgent(workspace_dir, run_id, model_type)
        qa_agent = QAAgent(pm_agent.get_model())
        secops_agent = SecOpsAgent(pm_agent.get_model())

        corporate_memory_context = ""
        try:
            memories = DevHouseDB.get_recent_corporate_memories()
            if memories:
                memory_lines = []
                for idx, mem in enumerate(memories):
                    memory_lines.append(f"Memory {idx+1} ({mem[0]}):\nPattern to Avoid: {mem[1]}\nSolution: {mem[2]}\n")
                corporate_memory_context = "\n".join(memory_lines)
                await devhouse_queue.put({"type": "info", "message": f"[MEMORY] Loaded {len(memories)} recent Corporate Memories to avoid past mistakes."})
        except Exception as e:
            logging.warning(f"Failed to load corporate memory: {e}")

        initial_spec, spec_tokens, spec_usage = pm_agent.generate_initial_spec(initial_prompt, radar_report, kb_links, corporate_memory=corporate_memory_context, attachments=attachments)
        pm_tokens_burned += spec_tokens
        log_telemetry(task_id, "PM", spec_usage)

        await devhouse_queue.put({"type": "action", "message": f"[DEV] Spawning Jules..."})

        jules_bot = bot.JulesBot(profile_id="1")
        jules_page = await jules_bot.create_new_page()
        dev_agent = DevAgent(jules_bot, jules_page)

        jules_instruction = f"Technical Spec: {initial_spec}\nKnowledge Base: {kb_links}\nBranch: {branch_name}\n\n--- REPO STRUCTURE ---\n{repo_structure}\n\n{radar_report}\n\nIMPORTANT MANDATE: You are operating in a sandbox. The target codebase is located exclusively at: `{workspace_dir}`. All bash commands, file modifications, and git operations MUST be executed within `{workspace_dir}`. Do NOT edit the local engine files."

        accumulated_context = jules_instruction

        async def update_agent_state(state: str):
            try:
                DevHouseDB.update_task_agent_state(task_id, state)
                await devhouse_queue.put({"type": "state_change", "newState": state})
            except Exception as e:
                logging.error(f"Failed to update agent state: {e}")

        def save_state(count, ctx, status):
            try:
                DevHouseDB.save_loop_state(branch_name, count, max_iterations, ctx, status, task_id)
            except Exception as e:
                logging.error(f"Failed to save DevHouse state: {e}")

        start_iteration = 1

        try:
            row = DevHouseDB.get_task_state(task_id)
            if row and row[0]:
                db_state = row[0]
                if db_state not in ['PLANNING', 'DEPLOYED', 'FAILED'] and row[1]:
                    await devhouse_queue.put({"type": "info", "message": f"[SYSTEM] Resuming task from state: {db_state}"})
                    accumulated_context = row[1]
                    start_iteration = row[2] or 1
                    jules_instruction = accumulated_context

                    if not os.path.exists(workspace_dir):
                        subprocess.run(["git", "clone", clone_url, workspace_dir], check=True, capture_output=True, text=True)
                        subprocess.run(["git", "checkout", branch_name], cwd=workspace_dir, check=True)
        except Exception as e:
            logging.error(f"Failed to load resume state: {e}")

        if start_iteration == 1 and not os.path.exists(os.path.join(workspace_dir, ".git")):
             create_feature_branch("main", branch_name, target_repo)

        save_state(start_iteration, accumulated_context, 'running')
        await update_agent_state("CODING")

        empty_diff_count = 0
        iteration = start_iteration
        max_fix_iterations = 3
        fix_count = 0

        while iteration <= max_iterations:
            try:
                hash_proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace_dir, capture_output=True, text=True, check=True)
                safe_commit_hash = hash_proc.stdout.strip()
            except Exception as e:
                safe_commit_hash = None
                logging.warning(f"Failed to capture safe commit hash: {e}")

            await devhouse_queue.put({"type": "info", "message": f"[DEV] Iteration {iteration}/{max_iterations}: Sending instructions to Jules..."})
            save_state(iteration, accumulated_context, 'running')

            try:
                await devhouse_queue.put({"type": "info", "message": f"[DEV] Iteration {iteration}/{max_iterations}: Writing code... Waiting for 'Ready for Review'."})
                jules_status, dev_tokens, dev_usage = await asyncio.wait_for(dev_agent.execute_task(jules_instruction), timeout=900)
                dev_tokens_burned += dev_tokens
                log_telemetry(task_id, "DEV", dev_usage)

                if not jules_status:
                    raise Exception("Timeout waiting for Jules to finish task.")

            except asyncio.TimeoutError:
                await devhouse_queue.put({"type": "error", "message": f"[WATCHDOG] Process hung for 15 minutes, hard resetting Jules browser..."})
                logging.error("[WATCHDOG] Process hung, hard resetting...")
                await jules_bot.quit()
                jules_bot = bot.JulesBot(profile_id="1")
                jules_page = await jules_bot.create_new_page()
                dev_agent = DevAgent(jules_bot, jules_page)
                continue

            await devhouse_queue.put({"type": "action", "message": f"[GIT] Code pushed by Jules. Fetching diff for branch '{branch_name}'..."})
            diff = get_branch_diff("main", branch_name, target_repo)

            if not diff.strip():
                empty_diff_count += 1
                await devhouse_queue.put({"type": "info", "message": f"[SYSTEM WARNING] No code changes detected. Attempt {empty_diff_count}/2."})
                if empty_diff_count >= 2:
                    raise Exception("Jules failed to push code twice.")
                jules_instruction = "You failed to commit any code. You must implement the changes and push."
                continue

            empty_diff_count = 0

            await devhouse_queue.put({"type": "ci", "message": "[CI] Compiling project... (npm run build in Docker)"})
            container_name = f"ci_build_{uuid.uuid4().hex[:8]}"
            try:
                 ci_process = await asyncio.create_subprocess_exec(
                      "docker", "run", "--rm", "--name", container_name,
                      "-v", f"{os.path.abspath(workspace_dir)}:/app", "-w", "/app",
                      "node:18-alpine", "npm", "run", "build",
                      stdout=asyncio.subprocess.PIPE,
                      stderr=asyncio.subprocess.PIPE
                 )

                 try:
                      stdout_bytes, stderr_bytes = await asyncio.wait_for(ci_process.communicate(), timeout=120.0)
                 except asyncio.TimeoutError:
                      try:
                          kill_proc = await asyncio.create_subprocess_exec("docker", "rm", "-f", container_name, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                          await kill_proc.communicate()
                      except Exception:
                          pass
                      await devhouse_queue.put({"type": "ci_failed", "message": "[CI] ❌ Build Timeout (120s)! Sending failure back to Developer."})
                      jules_instruction = f"[SYSTEM CI ALERT] The code you just wrote caused a build timeout (exceeded 120 seconds). Fix any infinite loops or build hang issues."

                      fix_count += 1
                      if fix_count > max_fix_iterations:
                          raise Exception("Jules failed to fix CI errors after 3 attempts.")
                      continue

                 returncode = ci_process.returncode
                 if returncode != 0:
                      await devhouse_queue.put({"type": "ci_failed", "message": "[CI] ❌ Build Failed! Sending stack trace back to Developer."})

                      fix_count += 1

                      if fix_count >= 2 and safe_commit_hash:
                          await devhouse_queue.put({"type": "error", "message": f"[TIME-MACHINE] ⚠️ Jules entered an error spiral. Rolling back to previous stable commit..."})
                          try:
                              subprocess.run(["git", "reset", "--hard", safe_commit_hash], cwd=workspace_dir, check=True)
                          except Exception as e:
                              logging.error(f"Time-Machine Rollback failed: {e}")

                          fix_count = 0
                          jules_instruction = f"Your previous code caused a CI spiral and was rolled back. Re-attempt the feature from scratch, ensuring it compiles properly. Original Request:\n{initial_prompt}"
                          continue

                      stderr = stderr_bytes.decode() if stderr_bytes else ""
                      stdout_str = stdout_bytes.decode() if stdout_bytes else ""
                      stdout_lines = "\n".join(stdout_str.splitlines()[-50:]) if stdout_str else ""

                      jules_instruction = f"[SYSTEM CI ALERT] The code you just wrote caused a build failure. Do NOT write new features. Fix the compilation errors immediately based on this stack trace:\n\nSTDERR:\n{stderr}\n\nSTDOUT (Last 50 lines):\n{stdout_lines}"

                      if fix_count > max_fix_iterations:
                          raise Exception("Jules failed to fix CI errors after 3 attempts.")
                      continue
                 else:
                      fix_count = 0
                      await devhouse_queue.put({"type": "ci_success", "message": "[CI] ✅ Build Passed! Proceeding to Agent Swarm Validation."})
            except Exception as e:
                 await devhouse_queue.put({"type": "error", "message": f"[CI] ❌ Unknown Execution Error: {e}"})
                 raise e

            try:
                await update_agent_state("SECOPS_AUDIT")
                await devhouse_queue.put({"type": "info", "message": f"[SECOPS] 🛡️ SecOps Agent analyzing diff for vulnerabilities..."})

                secops_text, sec_tokens, sec_usage = secops_agent.analyze_diff(diff)
                pm_tokens_burned += sec_tokens
                log_telemetry(task_id, "SECOPS", sec_usage)

                if "APPROVED" not in secops_text.upper():
                    await devhouse_queue.put({"type": "error", "message": f"[SECOPS] 🛑 Security Violation Detected:\n{secops_text}"})
                    jules_instruction = f"[SECOPS REJECTION] Fix the following security vulnerabilities immediately:\n{secops_text}"

                    try:
                        DevHouseDB.add_corporate_memory(f"mem-{uuid.uuid4().hex[:8]}", "SECOPS", "Security Vulnerability detected in code diff", secops_text)
                    except Exception as e:
                        logging.warning(f"Failed to store SECOPS memory: {e}")

                    continue

                await devhouse_queue.put({"type": "ci_success", "message": "[SECOPS] ✅ Security check passed."})

                await update_agent_state("QA_AUDIT")
                await devhouse_queue.put({"type": "info", "message": f"[QA] 🧪 QA Agent generating TDD test cases..."})

                test_script_content, qa_tokens, qa_usage = qa_agent.generate_tests(diff)
                pm_tokens_burned += qa_tokens
                log_telemetry(task_id, "QA", qa_usage)

                if test_script_content:
                    test_file_path = os.path.join(workspace_dir, "devhouse_swarm_test.spec.js")
                    with open(test_file_path, "w") as f:
                        f.write(test_script_content)

                    await devhouse_queue.put({"type": "info", "message": f"[QA] ⚙️ Running generated TDD tests (in Docker)..."})

                    test_container_name = f"qa_test_{uuid.uuid4().hex[:8]}"
                    try:
                        test_proc = await asyncio.create_subprocess_exec(
                            "docker", "run", "--rm", "--network", "none", "--name", test_container_name,
                            "-v", f"{os.path.abspath(workspace_dir)}:/app", "-w", "/app",
                            "node:18-alpine", "npm", "run", "test",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        test_stdout, test_stderr = await asyncio.wait_for(test_proc.communicate(), timeout=60.0)
                    except asyncio.TimeoutError:
                        try:
                            kill_proc = await asyncio.create_subprocess_exec("docker", "rm", "-f", test_container_name, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                            await kill_proc.communicate()
                        except Exception:
                            pass
                        error_msg = "[SECURITY ALERT] QA test execution breached sandbox constraints (Timeout)."
                        logging.error(error_msg)
                        await devhouse_queue.put({"type": "error", "message": f"[QA] 🛑 {error_msg}"})
                        raise Exception(error_msg)
                    except PermissionError as e:
                        error_msg = f"[SECURITY ALERT] QA test execution breached sandbox constraints (PermissionError): {e}"
                        logging.error(error_msg)
                        await devhouse_queue.put({"type": "error", "message": f"[QA] 🛑 {error_msg}"})
                        raise Exception(error_msg)

                    if test_proc.returncode != 0:
                        test_error = (test_stderr.decode('utf-8') if test_stderr else "") or (test_stdout.decode('utf-8') if test_stdout else "")
                        await devhouse_queue.put({"type": "error", "message": f"[QA] 🛑 TDD Gate Failed:\n{test_error}"})
                        jules_instruction = f"[QA REJECTION] Fix the code so it passes the QA test. Here is the failing test error:\n{test_error}"

                        try:
                            DevHouseDB.add_corporate_memory(f"mem-{uuid.uuid4().hex[:8]}", "QA", "TDD Test Failure", test_error)
                        except Exception as e:
                            logging.warning(f"Failed to store QA memory: {e}")

                        continue

                    await devhouse_queue.put({"type": "ci_success", "message": "[QA] ✅ TDD tests passed!"})
                else:
                    await devhouse_queue.put({"type": "info", "message": "[QA] ⚠️ No test block generated. Proceeding to PM."})

            except Exception as e:
                 await devhouse_queue.put({"type": "error", "message": f"[SWARM] ❌ Swarm execution error: {e}"})
                 raise e

            await update_agent_state("UAT_GATE")
            await devhouse_queue.put({"type": "info", "message": "[SYSTEM] Spinning up Live Preview Engine (npm run dev)..."})
            preview_process = None

            try:
                kill_proc = await asyncio.create_subprocess_shell("kill $(lsof -t -i:3005) 2>/dev/null || true")
                await kill_proc.communicate()
            except Exception as e:
                logging.warning(f"Error attempting to kill port 3005: {e}")

            try:
                preview_process = await asyncio.create_subprocess_exec(
                    "npm", "run", "dev", "--", "-p", "3005",
                    cwd=workspace_dir,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )

                await asyncio.sleep(5)

                try:
                    from playwright.async_api import async_playwright
                    await devhouse_queue.put({"type": "info", "message": "[SYSTEM] Capturing automated UAT visual diff thumbnail..."})
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page()
                        await page.goto("http://localhost:3005", wait_until="networkidle", timeout=15000)
                        os.makedirs("public", exist_ok=True)
                        await page.screenshot(path="public/uat_preview.png")
                        await browser.close()
                except Exception as e:
                    logging.warning(f"Failed to capture UAT thumbnail: {e}")

                save_state(iteration, accumulated_context, 'AWAITING_UAT')
                DevHouseDB.update_task_status(task_id, 'AWAITING_UAT')

                await devhouse_queue.put({
                    "type": "preview",
                    "message": "Live Preview Ready. Awaiting UAT Approval...",
                    "url": "http://localhost:3005"
                })

                uat_approval_event.clear()
                await uat_approval_event.wait()

                save_state(iteration, accumulated_context, 'running')
                DevHouseDB.update_task_status(task_id, 'running')

                if not uat_decision.get("approved", False):
                     await devhouse_queue.put({"type": "error", "message": "[UAT] Human rejected changes. Resetting to Jules."})
                     user_feedback = uat_decision.get("feedback", "")
                     jules_instruction = f"[UAT ALERT] The human product manager REJECTED your latest changes in the UI preview. Fix the visual layout or feature based on the original request.\n\nSpecific Human Feedback:\n{user_feedback}"
                     continue

                await devhouse_queue.put({"type": "success", "message": "[UAT] Human approved changes. Proceeding to final Code Review."})
            finally:
                if preview_process:
                     try:
                         preview_process.kill()
                         await preview_process.communicate()
                     except Exception:
                         pass

            await update_agent_state("PM_REVIEW")
            await devhouse_queue.put({"type": "action", "message": f"[PM] Reviewing Diff: Analyzing code changes..."})

            review_text, review_tokens, review_usage = pm_agent.review_diff(diff, accumulated_context)
            pm_tokens_burned += review_tokens
            log_telemetry(task_id, "PM", review_usage)

            accumulated_context += f"\n\nReview (Iter {iteration}):\n{review_text}"

            if "LGTM" in review_text.strip():
                await devhouse_queue.put({"type": "review", "message": f"[PM] Review complete: LGTM. Proceeding to merge."})
                break

            await devhouse_queue.put({"type": "review", "message": f"[PM] Reviewing Diff: Found issues. Sending feedback back:\n{review_text}"})

            jules_instruction = f"Code Review Feedback:\n{review_text}\n\nPlease fix these issues."
            iteration += 1

        await update_agent_state("DEPLOYED")
        await devhouse_queue.put({"type": "action", "message": f"[GIT] DevHouse loop finished. Merging branch '{branch_name}' and cleaning up."})
        save_state(max_iterations, accumulated_context, 'merging')
        merge_and_delete_branch(branch_name, "main", target_repo)
        save_state(max_iterations, accumulated_context, 'finished')

        deploy_webhook_url = os.environ.get("DEPLOY_WEBHOOK_URL")
        if deploy_webhook_url:
            try:
                deploy_secret = os.environ.get("DEPLOY_SECRET", "")
                headers = {"Authorization": f"Bearer {deploy_secret}"} if deploy_secret else {}
                import httpx
                async with httpx.AsyncClient() as client:
                    await client.post(deploy_webhook_url, headers=headers)
                await devhouse_queue.put({"type": "info", "message": f"[CD] 🚀 Code merged to main. Deployment webhook triggered!"})
            except Exception as e:
                logging.error(f"Failed to trigger deploy webhook: {e}")

        await devhouse_queue.put({"type": "info", "message": f"[SYSTEM] Merge complete. DevHouse Autopilot cycle finished."})

    except Exception as e:
        await update_agent_state("FAILED")
        try:
             DevHouseDB.save_loop_state(branch_name, 1, max_iterations, str(e), 'failed', task_id)
        except Exception:
             pass
        await devhouse_queue.put({"type": "error", "message": f"[ERROR] DevHouse Autopilot crashed: {str(e)}"})
        raise e
    finally:
        if jules_bot:
            await jules_bot.quit()

queue_running = False

async def queue_runner_loop():
    global queue_running
    if queue_running:
        return
    queue_running = True

    while True:
        try:
            row = DevHouseDB.get_pending_task()
            if not row:
                completed_count, failed_count = DevHouseDB.get_task_counts()
                webhook_url = DevHouseDB.get_first_webhook_url()

                if webhook_url and (completed_count > 0 or failed_count > 0):
                    try:
                         details = DevHouseDB.get_all_tasks()
                         payload = {
                             "total_completed": completed_count,
                             "total_failed": failed_count,
                             "details": details
                         }
                         async with httpx.AsyncClient(timeout=10.0) as client:
                              await client.post(webhook_url, json=payload)

                         DevHouseDB.clear_webhooks()
                    except Exception as e:
                         logging.error(f"Failed to send Morning Report webhook: {e}")

                queue_running = False
                break

            task_id, prompt_data, target_repo, kb_links, model, webhook_url = row
            try:
                import json
                parsed_prompt = json.loads(prompt_data)
                if isinstance(parsed_prompt, dict):
                    actual_prompt = parsed_prompt.get('prompt', '')
                    attachments = parsed_prompt.get('attachments', [])
                else:
                    actual_prompt = prompt_data
                    attachments = []
            except Exception:
                actual_prompt = prompt_data
                attachments = []

            DevHouseDB.update_task_status(task_id, 'running')

            async with devhouse_lock:
                 while not devhouse_queue.empty():
                      try:
                          devhouse_queue.get_nowait()
                      except asyncio.QueueEmpty:
                          break
                 await devhouse_queue.put({"type": "info", "message": f"[QUEUE] Starting task {task_id}..."})

                 success = False
                 try:
                      await run_devhouse_autopilot(task_id, actual_prompt, attachments, target_repo, kb_links, model)
                      success = True
                 except Exception as e:
                      logging.error(f"Task {task_id} failed: {e}")

                 new_status = 'completed' if success else 'failed'
                 DevHouseDB.update_task_status(task_id, new_status)

        except Exception as e:
            logging.error(f"Queue runner error: {e}")
            await asyncio.sleep(5)
