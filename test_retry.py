import asyncio
import json
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import app
import bot

class TestAutoRetry(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Reset locks and bot global
        app.bot = None
        app.bot_lock = asyncio.Lock()

    @patch('app.GeminiBot', autospec=True)
    async def test_auto_retry_success_on_third_try(self, MockGeminiBot):
        # Setup mock bot behavior
        mock_bot_instance = MockGeminiBot.return_value
        mock_bot_instance.initialize = AsyncMock()
        mock_bot_instance.start_new_chat = AsyncMock()
        mock_bot_instance.send_prompt = AsyncMock()

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
            response = await app.execute_workflow(mock_request)

            # The response is a StreamingResponse, so we need to iterate its body
            generator = response.body_iterator

            events = []
            async for event in generator:
                events.append(event)

            # Check that we received "Retrying" events
            retrying_events = [e for e in events if "Retrying" in e]
            self.assertEqual(len(retrying_events), 2)

            # Verify the output says 1st retry and 2nd retry (account for json.dumps unicode escaping)
            # "第 1 次重试" in json is "\\u7b2c 1 \\u6b21\\u91cd\\u8bd5"
            parsed_event_0 = json.loads(retrying_events[0].replace('data: ', '').strip())
            parsed_event_1 = json.loads(retrying_events[1].replace('data: ', '').strip())

            self.assertIn("第 1 次重试", parsed_event_0['message'])
            self.assertIn("第 2 次重试", parsed_event_1['message'])

            # Check that the final status was 'Complete' and 'Workflow Finished'
            complete_events = [e for e in events if '"status": "Complete"' in e]
            self.assertEqual(len(complete_events), 1)

            workflow_finished_events = [e for e in events if '"status": "Workflow Finished"' in e]
            self.assertEqual(len(workflow_finished_events), 1)

            # Verify start_new_chat was called to clear state during retries
            self.assertEqual(mock_bot_instance.start_new_chat.call_count, 2)

            # Verify wait_for_response was called 3 times
            self.assertEqual(mock_bot_instance.wait_for_response.call_count, 3)

if __name__ == '__main__':
    unittest.main()
