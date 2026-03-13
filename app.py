from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse
import asyncio
import logging
from bot import GeminiBot
import json

app = FastAPI()
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
# A simple async semaphore to allow concurrent executions up to a limit
bot_semaphore = None
# Global event to signal emergency stop
cancel_event = None

@app.on_event("startup")
async def startup_event():
    global bot_semaphore
    global cancel_event
    bot_semaphore = asyncio.Semaphore(3)
    cancel_event = asyncio.Event()

@app.post("/stop")
async def stop_workflow():
    if cancel_event:
        cancel_event.set()
    return {"status": "stopping"}

async def get_bot():
    global bot
    if bot is None:
        try:
            new_bot = GeminiBot()
            await new_bot.initialize()
            bot = new_bot
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

    if bot_semaphore.locked():
        # Reject new requests if a workflow is already running to protect the browser instance
        return StreamingResponse(error_stream("Server is busy. Please try again later."), media_type="text/event-stream")

    try:
        data = await request.json()
    except Exception as e:
        return StreamingResponse(error_stream(f"Invalid JSON payload: {str(e)}"), media_type="text/event-stream")

    steps = data.get('steps', [])

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

    async def event_generator():
        page = None
        try:
            try:
                current_bot = await get_bot()
                page = await current_bot.create_new_page()
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

            results = {}

            for index, step in enumerate(steps):
                if cancel_event and cancel_event.is_set():
                    yield f"data: {json.dumps({'step': index + 1, 'status': 'Canceled', 'message': 'Workflow stopped by user.'})}\n\n"
                    break

                step_id = index + 1
                prompt_template = step.get('prompt', '')
                new_chat = step.get('new_chat', False)
                step_type = step.get('type', 'standard')
                chat_url = step.get('chat_url', '').strip()

                logging.info(f"Executing Step {step_id}")
                yield f"data: {json.dumps({'step': step_id, 'status': 'Starting', 'message': f'Executing Step {step_id}...'})}\n\n"

                if step_type == 'batch':
                    # Batch Input Step
                    results[str(step_id)] = prompt_template
                    yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': prompt_template})}\n\n"
                    continue

                if '{{CURRENT_ITEM}}' in prompt_template:
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
                        yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'result': results[str(step_id)]})}\n\n"
                        break

                    yield f"data: {json.dumps({'step': step_id, 'status': 'Processing Batch', 'message': f'Processing {len(items)} items concurrently...'})}\n\n"

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
                                        await stream_queue.put(f"__STATUS__:Navigating item {item_index + 1} to specific chat URL...")
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
                                        await stream_queue.put(partial_text)

                                    wait_task = asyncio.create_task(current_bot.wait_for_response(item_page, poll_callback=item_poll_callback))

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

                    # We need a way to pump the stream_queue while gather is running
                    async def pump_queue():
                        while True:
                            try:
                                partial_text = await asyncio.wait_for(stream_queue.get(), timeout=0.5)
                                # To stream typing back, we would need to yield from the parent.
                                # Since we can't yield from a background task back to the client,
                                # we just discard it for batch mode to avoid complicating the gather loop.
                            except asyncio.TimeoutError:
                                pass
                            except Exception:
                                break

                    pump_task = asyncio.create_task(pump_queue())
                    batch_results = await asyncio.gather(*tasks)
                    pump_task.cancel()

                    final_result_text = "\n\n--- \n\n".join(batch_results)
                    results[str(step_id)] = final_result_text
                    yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': final_result_text})}\n\n"
                    continue
                else:
                    # Standard or Aggregator Step
                    MAX_RETRIES = 3
                    step_success = False

                    for attempt in range(MAX_RETRIES):
                        try:
                            if chat_url and chat_url.startswith('https://gemini.google.com/'):
                                yield f"data: {json.dumps({'step': step_id, 'status': 'Navigating', 'message': 'Navigating to specific chat URL...'})}\n\n"
                                await current_bot.goto_specific_chat(page, chat_url)
                            elif new_chat:
                                yield f"data: {json.dumps({'step': step_id, 'status': 'New Chat', 'message': 'Starting new chat...'})}\n\n"
                                await current_bot.start_new_chat(page)

                            # Smart Context Injection: Replace {{OUTPUT_X}} with actual results
                            final_prompt = prompt_template
                            for past_id, past_output in results.items():
                                tag = f"{{{{OUTPUT_{past_id}}}}}"
                                if tag in final_prompt:
                                    final_prompt = final_prompt.replace(tag, past_output)

                            yield f"data: {json.dumps({'step': step_id, 'status': 'Sending', 'message': 'Sending prompt to Gemini...'})}\n\n"
                            # Send the final compiled prompt to the bot
                            await current_bot.send_prompt(page, final_prompt)

                            if cancel_event and cancel_event.is_set():
                                raise asyncio.CancelledError("Workflow stopped by user.")

                            # Wait for the generation to finish
                            yield f"data: {json.dumps({'step': step_id, 'status': 'Waiting', 'message': 'Waiting for Gemini response...'})}\n\n"

                            # Define a callback to put partial results into the queue
                            async def poll_callback(partial_text):
                                if cancel_event and cancel_event.is_set():
                                    raise asyncio.CancelledError("Workflow stopped by user.")
                                await stream_queue.put(partial_text)

                            # Run wait_for_response in a background task so we can stream from the queue
                            wait_task = asyncio.create_task(current_bot.wait_for_response(page, poll_callback=poll_callback))

                            while not wait_task.done():
                                try:
                                    # Poll the queue for partial updates
                                    partial_text = await asyncio.wait_for(stream_queue.get(), timeout=0.5)
                                    yield f"data: {json.dumps({'step': step_id, 'status': 'Typing', 'partial_result': partial_text})}\n\n"
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
                            yield f"data: {json.dumps({'step': step_id, 'status': 'Extracting', 'message': 'Extracting response text...'})}\n\n"
                            response_text = await current_bot.get_last_response(page)

                            results[str(step_id)] = response_text

                            yield f"data: {json.dumps({'step': step_id, 'status': 'Complete', 'result': response_text})}\n\n"
                            logging.info(f"Step {step_id} completed successfully.")
                            step_success = True
                            break

                        except asyncio.CancelledError as e:
                            yield f"data: {json.dumps({'step': step_id, 'status': 'Canceled', 'message': str(e)})}\n\n"
                            step_success = False
                            break # Break retry loop immediately on cancel
                        except Exception as e:
                            if attempt < MAX_RETRIES - 1:
                                error_msg = f"Step {step_id} failed, preparing retry {attempt + 1}, error: {str(e)}"
                                logging.warning(error_msg)
                                yield f"data: {json.dumps({'step': step_id, 'status': 'Retrying', 'message': f'Response timeout, retrying {attempt + 1}...'})}\n\n"

                                # Break wait loop if canceled during sleep
                                try:
                                    await asyncio.wait_for(cancel_event.wait(), timeout=5)
                                    # If we didn't timeout, event was set
                                    yield f"data: {json.dumps({'step': step_id, 'status': 'Canceled', 'message': 'Workflow stopped by user.'})}\n\n"
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
                                yield f"data: {json.dumps({'step': step_id, 'status': 'Error', 'result': results[str(step_id)]})}\n\n"
                                # We break the retry loop, then we will break the workflow below
                                break

                    if not step_success:
                        # If a critical error occurs and all retries fail, break the workflow to avoid cascaded failures
                        break

            yield f"data: {json.dumps({'status': 'Workflow Finished', 'results': results})}\n\n"
        finally:
            if page:
                await page.close()
            bot_semaphore.release()

    # We use StreamingResponse to send Server-Sent Events (SSE) back to the client
    # This prevents the long-running process from timing out the HTTP connection
    # and provides real-time feedback to the UI.
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)