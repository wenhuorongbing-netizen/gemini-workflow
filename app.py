from fastapi import FastAPI, Request, BackgroundTasks, File, UploadFile, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse
import asyncio
import os
import logging
from bot import GeminiBot
import json

app = FastAPI()
templates = Jinja2Templates(directory="templates")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global bot instance to maintain session state asynchronously
bot = None
# A simple async lock to prevent concurrent executions messing up the browser
bot_lock = None

@app.on_event("startup")
async def startup_event():
    global bot_lock
    bot_lock = asyncio.Lock()

async def get_bot():
    global bot
    if bot is None:
        try:
            bot = GeminiBot()
            await bot.initialize()
        except Exception as e:
            logging.error(f"Failed to initialize Gemini Bot: {e}")
            raise Exception("Failed to initialize bot. Ensure Chrome profile path is valid.")
    return bot

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/execute")
async def execute_workflow(request: Request):
    async def error_stream(msg: str):
        yield f"data: {json.dumps({'error': msg})}\n\n"

    if bot_lock.locked():
        return StreamingResponse(error_stream("A workflow is currently running. Please wait for it to finish."), media_type="text/event-stream")

    content_type = request.headers.get("Content-Type", "")

    file_path = None
    steps = []
    continue_on_error = False

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            steps_str = form.get("steps")
            continue_on_error = form.get("continue_on_error") == "true"

            if not steps_str:
                return StreamingResponse(error_stream("No steps provided in workflow."), media_type="text/event-stream")
            steps = json.loads(steps_str)

            file_obj = form.get("file")
            if file_obj and hasattr(file_obj, "filename") and file_obj.filename:
                # Save uploaded file safely
                os.makedirs("uploads", exist_ok=True)
                safe_filename = os.path.basename(file_obj.filename)
                file_path = os.path.abspath(os.path.join("uploads", safe_filename))
                with open(file_path, "wb") as buffer:
                    buffer.write(await file_obj.read())
        else:
            data = await request.json()
            steps = data.get('steps', [])
            continue_on_error = data.get('continue_on_error', False)

    except Exception as e:
        return StreamingResponse(error_stream(f"Invalid payload: {str(e)}"), media_type="text/event-stream")

    if not steps:
        return StreamingResponse(error_stream("No steps provided in workflow."), media_type="text/event-stream")

    # Acquire the lock after payload parsing to prevent deadlocks on invalid requests
    try:
        await asyncio.wait_for(bot_lock.acquire(), timeout=0.1)
    except asyncio.TimeoutError:
        return StreamingResponse(error_stream("A workflow is currently running. Please wait for it to finish."), media_type="text/event-stream")

    async def event_generator():
        try:
            try:
                current_bot = await get_bot()
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

            results = {}

            # Reset context at the beginning of the workflow
            yield f"data: {json.dumps({'step': 0, 'status': 'Starting', 'message': 'Resetting Gemini chat context...'})}\n\n"
            await current_bot.start_new_chat()

            batch_items = []
            if steps and steps[0].get('type') == 'batch':
                batch_text = steps[0].get('prompt', '')
                batch_items = [item.strip() for item in batch_text.split('\n') if item.strip()]
                # Skip the batch definition step in execution
                steps_to_execute = steps[1:]
            else:
                steps_to_execute = steps

            if not batch_items:
                batch_items = [None] # Single run

            total_iterations = len(batch_items)
            total_steps = len(steps_to_execute)
            completed_tasks = 0

            # Map-Reduce Loop Inversion: Iterate over steps first
            for index, step in enumerate(steps_to_execute):
                step_id = index + 1 if not steps or steps[0].get('type') != 'batch' else index + 2
                prompt_template = step.get('prompt', '')
                new_chat = step.get('new_chat', False)
                is_batch_step = "{{CURRENT_ITEM}}" in prompt_template

                # Determine how many times this step will run
                step_iterations = batch_items if is_batch_step else [None]
                total_step_iterations = len(step_iterations)

                # Flag to break outer loop if non-resilient failure occurs
                fatal_error = False

                for iteration, current_item in enumerate(step_iterations):
                    iteration_id = iteration + 1

                    logging.info(f"Executing Step {step_id} (Iteration {iteration_id}/{total_step_iterations})")
                    progress_msg = f"Executing Step {step_id}"
                    if total_step_iterations > 1:
                        progress_msg += f" (Item {iteration_id}/{total_step_iterations})"

                    # Estimate total tasks by weighting steps.
                    # This is an approximation for the progress bar.
                    estimated_total_operations = 0
                    for s in steps_to_execute:
                         if "{{CURRENT_ITEM}}" in s.get('prompt', ''):
                             estimated_total_operations += total_iterations
                         else:
                             estimated_total_operations += 1

                    progress_percent = int((completed_tasks / max(1, estimated_total_operations)) * 100)

                    yield f"data: {json.dumps({'step': step_id, 'status': 'Starting', 'message': progress_msg, 'progress': progress_percent})}\n\n"

                    try:
                        if new_chat:
                            yield f"data: {json.dumps({'step': step_id, 'status': 'New Chat', 'message': 'Starting new chat...'})}\n\n"
                            await current_bot.start_new_chat()

                        # Smart Context Injection: Replace {{OUTPUT_X}} with actual results
                        final_prompt = prompt_template
                        if current_item is not None:
                            final_prompt = final_prompt.replace("{{CURRENT_ITEM}}", current_item)

                        # Look through all possible previous steps
                        for past_index in range(1, step_id):
                            tag = f"{{{{OUTPUT_{past_index}}}}}"
                            if tag in final_prompt:
                                # Try to get the output from the current iteration first (if previous step was a batch step)
                                iteration_key = f"{past_index}_{iteration_id}"
                                standard_key = str(past_index)

                                if iteration_key in results:
                                    final_prompt = final_prompt.replace(tag, results[iteration_key])
                                elif standard_key in results:
                                    final_prompt = final_prompt.replace(tag, results[standard_key])
                                else:
                                    # This implies the previous step was a batch step, but we are in a non-batch step.
                                    # We need to aggregate the results.
                                    aggregated_results = []
                                    for i in range(1, total_iterations + 1):
                                        key = f"{past_index}_{i}"
                                        if key in results:
                                            aggregated_results.append(f"--- Item {i} ---\n{results[key]}")

                                    if aggregated_results:
                                        final_prompt = final_prompt.replace(tag, "\n\n".join(aggregated_results))

                        yield f"data: {json.dumps({'step': step_id, 'status': 'Sending', 'message': 'Sending prompt to Gemini...'})}\n\n"

                        if file_path and index == 0 and iteration == 0:
                            yield f"data: {json.dumps({'step': step_id, 'status': 'Uploading', 'message': 'Uploading file...'})}\n\n"
                            await current_bot.upload_file(file_path)

                        # Send the final compiled prompt to the bot
                        await current_bot.send_prompt(final_prompt)

                        # Wait for the generation to finish
                        yield f"data: {json.dumps({'step': step_id, 'status': 'Waiting', 'message': 'Waiting for Gemini response...'})}\n\n"
                        await current_bot.wait_for_response()

                        # Extract the output
                        yield f"data: {json.dumps({'step': step_id, 'status': 'Extracting', 'message': 'Extracting response text...'})}\n\n"
                        response_text = await current_bot.get_last_response()

                        if total_step_iterations > 1:
                            results[f"{step_id}_{iteration_id}"] = response_text
                            yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': f'[Item {iteration_id}]: {response_text}'})}\n\n"
                        else:
                            results[str(step_id)] = response_text
                            yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': response_text})}\n\n"
                        logging.info(f"Step {step_id} completed successfully.")
                        completed_tasks += 1

                    except Exception as e:
                        error_msg = f"Error in Step {step_id}: {str(e)}"
                        logging.error(error_msg)
                        if total_step_iterations > 1:
                            results[f"{step_id}_{iteration_id}"] = f"[FAILED] {error_msg}"
                            yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'result': results[f'{step_id}_{iteration_id}']})}\n\n"
                        else:
                            results[str(step_id)] = f"[FAILED] {error_msg}"
                            yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'result': results[str(step_id)]})}\n\n"

                        completed_tasks += 1

                        if continue_on_error and is_batch_step:
                            logging.info(f"Continuing to next iteration despite error in step {step_id}.")
                            continue # Continue to next item in the batch
                        else:
                            # If not resilient batch mode, or a single non-batch step fails, break the entire execution
                            fatal_error = True
                            break

                if fatal_error:
                    yield f"data: {json.dumps({'status': 'Workflow Finished', 'results': results, 'progress': 100})}\n\n"
                    return

            yield f"data: {json.dumps({'status': 'Workflow Finished', 'results': results, 'progress': 100})}\n\n"
        finally:
            # Clean up uploaded files to prevent disk leak
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logging.info(f"Cleaned up uploaded file: {file_path}")
                except Exception as e:
                    logging.error(f"Failed to clean up file {file_path}: {e}")
            bot_lock.release()

    # We use StreamingResponse to send Server-Sent Events (SSE) back to the client
    # This prevents the long-running process from timing out the HTTP connection
    # and provides real-time feedback to the UI.
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)