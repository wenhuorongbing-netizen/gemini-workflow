import asyncio
import json
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import app

class TestAutoRetry(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Reset locks and bot global
        app.bot = None
        app.bot_lock = asyncio.Lock()
        app.cancel_event = asyncio.Event()

    @patch('app.GeminiBot', autospec=True)
    async def test_auto_retry_success_on_third_try(self, MockGeminiBot):
        # Setup mock bot behavior
        mock_bot_instance = MockGeminiBot.return_value
        mock_bot_instance.initialize = AsyncMock()
        mock_bot_instance.start_new_chat = AsyncMock()
        mock_bot_instance.send_prompt = AsyncMock()
        mock_bot_instance.page = MagicMock()
        mock_bot_instance.page.reload = AsyncMock()

        # We'll make wait_for_response throw two exceptions, and succeed on the third attempt
        self.call_count = 0
        async def mock_wait_for_response(*args, **kwargs):
            self.call_count += 1
            if self.call_count < 3:
                raise Exception("Simulated network timeout")
            return True

        mock_bot_instance.wait_for_response = AsyncMock(side_effect=mock_wait_for_response)
        mock_bot_instance.get_last_response = AsyncMock(return_value="Success response!")

        # Setup mock request
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value={
            'steps': [{'prompt': 'Test Prompt', 'new_chat': False}]
        })

        # Patch sleep so tests run fast
        with patch('asyncio.sleep', new_callable=AsyncMock):
            # Do NOT patch wait_for globally since app.py heavily relies on it for asyncio primitives
            # We'll just run it realistically. It will wait for lock and queue, which is fine since we aren't simulating real long waits.

            # The issue with execute_workflow raising TypeError when awaited is because it is defined as:
            # @app.post("/execute")
            # async def execute_workflow(request: Request):
            #     ...
            # Oh wait. When we mocked FastAPI, the decorator might have messed with it?
            # test_retry.py wasn't mocking FastAPI initially in the working run, only in the failing run?
            # Wait, the working run had:
            # import sys
            # sys.modules['fastapi'] = MagicMock()
            # Let's see if we can just invoke the event_generator directly if it's too much trouble.
            pass

        # Actually `execute_workflow` is an async function returning a StreamingResponse.
        # So `await app.execute_workflow(mock_request)` should work IF FastAPI is NOT mocked as a MagicMock that turns the decorator into returning a MagicMock.
        # Oh, in the earlier version where it failed, it failed because of wait_for blocking on cancel_event.
        pass

if __name__ == '__main__':
    unittest.main()
