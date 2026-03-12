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
# A simple async lock to prevent concurrent executions messing up the browser
bot_lock = None
# Global event to signal emergency stop
cancel_event = None

@app.on_event("startup")
async def startup_event():
    global bot_lock
    global cancel_event
    bot_lock = asyncio.Lock()
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

    if bot_lock.locked():
        # Reject new requests if a workflow is already running to protect the browser instance
        return StreamingResponse(error_stream("A workflow is currently running. Please wait for it to finish."), media_type="text/event-stream")

    try:
        data = await request.json()
    except Exception as e:
        return StreamingResponse(error_stream(f"Invalid JSON payload: {str(e)}"), media_type="text/event-stream")

    steps = data.get('steps', [])

    if not steps:
        return StreamingResponse(error_stream("No steps provided in workflow."), media_type="text/event-stream")

    # Acquire the lock after payload parsing to prevent deadlocks on invalid requests
    try:
        await asyncio.wait_for(bot_lock.acquire(), timeout=0.1)
    except asyncio.TimeoutError:
        return StreamingResponse(error_stream("A workflow is currently running. Please wait for it to finish."), media_type="text/event-stream")

    if cancel_event:
        cancel_event.clear()

    # Shared queue to receive pseudo-streaming updates from the bot callback
    stream_queue = asyncio.Queue()

    async def event_generator():
        try:
            try:
                current_bot = await get_bot()
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

                logging.info(f"Executing Step {step_id}")
                yield f"data: {json.dumps({'step': step_id, 'status': 'Starting', 'message': f'Executing Step {step_id}...'})}\n\n"

                MAX_RETRIES = 3
                step_success = False

                for attempt in range(MAX_RETRIES):
                    try:
                        if new_chat:
                            yield f"data: {json.dumps({'step': step_id, 'status': 'New Chat', 'message': 'Starting new chat...'})}\n\n"
                            await current_bot.start_new_chat()

                        # Smart Context Injection: Replace {{OUTPUT_X}} with actual results
                        final_prompt = prompt_template
                        for past_id, past_output in results.items():
                            tag = f"{{{{OUTPUT_{past_id}}}}}"
                            if tag in final_prompt:
                                final_prompt = final_prompt.replace(tag, past_output)

                        yield f"data: {json.dumps({'step': step_id, 'status': 'Sending', 'message': 'Sending prompt to Gemini...'})}\n\n"
                        # Send the final compiled prompt to the bot
                        await current_bot.send_prompt(final_prompt)

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
                        wait_task = asyncio.create_task(current_bot.wait_for_response(poll_callback=poll_callback))

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
                        response_text = await current_bot.get_last_response()

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
                            error_msg = f"Step {step_id} 失败，准备第 {attempt + 1} 次重试，错误原因：{str(e)}"
                            logging.warning(error_msg)
                            yield f"data: {json.dumps({'step': step_id, 'status': 'Retrying', 'message': f'响应超时，正在进行第 {attempt + 1} 次重试...'})}\n\n"

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
                            await current_bot.page.reload()
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
            bot_lock.release()

    # We use StreamingResponse to send Server-Sent Events (SSE) back to the client
    # This prevents the long-running process from timing out the HTTP connection
    # and provides real-time feedback to the UI.
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)