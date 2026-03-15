import pytest
import sys
import json
import asyncio
from unittest.mock import MagicMock, patch

# Mock fastapi dependencies before importing app
sys.modules['fastapi'] = MagicMock()
sys.modules['fastapi.templating'] = MagicMock()
sys.modules['fastapi.responses'] = MagicMock()
sys.modules['fastapi.middleware.cors'] = MagicMock()
sys.modules['watchdog.observers'] = MagicMock()
sys.modules['watchdog.events'] = MagicMock()
sys.modules['apscheduler.schedulers.asyncio'] = MagicMock()
sys.modules['apscheduler.triggers.cron'] = MagicMock()

import app

@pytest.mark.asyncio
async def test_compile_nodes_and_variable_resolution():
    # Phase 1: Engine Integration Test - DAG Resolution

    # We will test `run_workflow_engine` with a predefined set of steps
    # Note: run_workflow_engine is a generator

    steps = [
        {"id": "A", "type": "standard", "prompt": "Output Hello"},
        {"id": "B", "type": "standard", "prompt": "Prepend 'User says: ' to {{OUTPUT_A}}"}
    ]

    # We must mock get_bot and the bot's responses
    bot_mock = MagicMock()
    bot_mock.profile_path = "chrome_profile_1"

    async def mock_create_new_page():
        page_mock = MagicMock()
        async def mock_close():
            pass
        page_mock.close = mock_close
        return page_mock

    bot_mock.all_prompts = []
    async def mock_send_prompt(page, prompt, attachments=None, model=None):
        bot_mock.last_prompt = prompt
        bot_mock.all_prompts.append(prompt)

    async def mock_wait_for_response(page, timeout=300000, poll_callback=None):
        pass

    async def mock_get_last_response(page):
        # Return different mock outputs based on the prompt
        if "Output Hello" in bot_mock.last_prompt:
            return "Hello"
        elif "User says" in bot_mock.last_prompt:
            return f"User says: Hello"
        return "Unknown"

    bot_mock.create_new_page = mock_create_new_page
    bot_mock.send_prompt = mock_send_prompt
    bot_mock.wait_for_response = mock_wait_for_response
    bot_mock.get_last_response = mock_get_last_response

    with patch('app.get_bot', return_value=bot_mock):
        stream_queue = asyncio.Queue()
        generator = app.run_workflow_engine(steps, "ws_1", stream_queue=stream_queue)

        events = []
        async for event in generator:
            events.append(event)

        # Verify the last event has the correct results
        last_event_str = events[-1]
        assert "Workflow Finished" in last_event_str

        # Extract json part from "data: {...}\n\n"
        data_str = last_event_str.replace("data: ", "").strip()
        result_data = json.loads(data_str)

        results = result_data["results"]
        assert results["A"] == "Hello"
        assert results["B"] == "User says: Hello"

        # Verify bot received the resolved prompt for step B
        # "Prepend 'User says: ' to Hello"

@pytest.mark.asyncio
async def test_multimodal_payload_validation():
    # Phase 1: Engine Integration Test - Multimodal

    steps = [
        {
            "id": "A",
            "type": "standard",
            "prompt": "Describe this image",
            "attachments": ["/tmp/test.png"]
        }
    ]

    bot_mock = MagicMock()
    bot_mock.profile_path = "chrome_profile_1"

    async def mock_create_new_page():
        page_mock = MagicMock()
        async def mock_close():
            pass
        page_mock.close = mock_close
        return page_mock

    bot_mock.all_prompts = []
    async def mock_send_prompt(page, prompt, attachments=None, model=None):
        bot_mock.received_attachments = attachments
        bot_mock.last_prompt = prompt
        bot_mock.all_prompts.append(prompt)

    async def mock_wait_for_response(page, timeout=300000, poll_callback=None):
        pass

    async def mock_get_last_response(page):
        return "It's a test image"

    bot_mock.create_new_page = mock_create_new_page
    bot_mock.send_prompt = mock_send_prompt
    bot_mock.wait_for_response = mock_wait_for_response
    bot_mock.get_last_response = mock_get_last_response

    with patch('app.get_bot', return_value=bot_mock):
        stream_queue = asyncio.Queue()
        generator = app.run_workflow_engine(steps, "ws_1", stream_queue=stream_queue)

        async for _ in generator:
            pass

        assert bot_mock.received_attachments == ["/tmp/test.png"]

@pytest.mark.asyncio
async def test_oom_crash_recovery():
    # Phase 1: Engine Integration Test - Crash Recovery in Agentic Loop

    steps = [
        {
            "id": "A",
            "type": "agentic_loop",
            "prompt": "Fix this code",
            "system_prompt": "You are a senior dev",
            "chat_url": "https://github.com/test",
            "max_iterations": 2
        }
    ]

    bot_mock = MagicMock()
    bot_mock.profile_path = "chrome_profile_1"

    async def mock_create_new_page():
        page_mock = MagicMock()
        async def mock_close():
            pass
        page_mock.close = mock_close
        return page_mock

    bot_mock.all_prompts = []
    async def mock_send_prompt(page, prompt, attachments=None, model=None):
        bot_mock.last_prompt = prompt
        bot_mock.all_prompts.append(prompt)

    async def mock_wait_for_response(page, timeout=300000, poll_callback=None):
        pass

    async def mock_get_last_response(page):
        return "Here is my code review"

    bot_mock.create_new_page = mock_create_new_page
    bot_mock.send_prompt = mock_send_prompt
    bot_mock.wait_for_response = mock_wait_for_response
    bot_mock.get_last_response = mock_get_last_response

    jules_bot_mock = MagicMock()

    async def mock_jules_create_new_page():
        page_mock = MagicMock()
        async def mock_close():
            pass
        page_mock.close = mock_close
        return page_mock

    jules_calls = {"send": 0}
    async def mock_jules_send_task(page, url, prompt, stream_queue=None, step_id=None):
        jules_calls["send"] += 1
        if jules_calls["send"] == 1:
            raise Exception("BROWSER_CRASH")

    async def mock_jules_poll(page, stream_queue=None, step_id=None):
        return "Jules failed"

    async def mock_jules_quit():
        pass

    jules_bot_mock.create_new_page = mock_jules_create_new_page
    jules_bot_mock.send_task = mock_jules_send_task
    jules_bot_mock.poll_for_completion = mock_jules_poll
    jules_bot_mock.quit = mock_jules_quit

    with patch('app.get_bot', return_value=bot_mock), \
         patch('app.JulesBot', return_value=jules_bot_mock):
        stream_queue = asyncio.Queue()
        generator = app.run_workflow_engine(steps, "ws_1", stream_queue=stream_queue)

        events = []
        async for event in generator:
            events.append(event)

        # Verify crash recovery message
        crash_recovered = False
        for event in events:
            if "u5185\\u5b58\\u8fc7\\u8f7d" in event:
                crash_recovered = True

        assert crash_recovered

        # Verify system prompt was injected in the recovery prompt
        recovery_prompt_found = False
        for p in bot_mock.all_prompts:
             if "System Instructions / Persona" in p and "We are continuing a task after a crash" in p:
                  recovery_prompt_found = True

        assert recovery_prompt_found, f"System instructions were not injected into recovery prompt. Prompts: {bot_mock.all_prompts}"
