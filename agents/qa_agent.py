import re
import google.generativeai as genai

class QAAgent:
    def __init__(self, model: genai.GenerativeModel):
        self.model = model

    def generate_tests(self, latest_diff: str):
        """Generates TDD test cases based on a code diff."""
        qa_prompt = f"You are a strict QA Test Engineer. Review this code diff. Write a simple functional frontend or API test script using `pytest` or `vitest` that targets the new feature. Return ONLY the script inside a ```python or ```javascript markdown block.\n\nDiff:\n{latest_diff}"
        response = self.model.generate_content(qa_prompt)

        tokens_burned = 0
        if hasattr(response, 'usage_metadata'):
            tokens_burned = response.usage_metadata.total_token_count

        qa_text = response.text
        code_blocks = re.findall(r'```(?:python|javascript|js|typescript|ts)?\n(.*?)\n```', qa_text, re.DOTALL)

        test_script_content = None
        if code_blocks:
            test_script_content = code_blocks[0]

        return test_script_content, tokens_burned
