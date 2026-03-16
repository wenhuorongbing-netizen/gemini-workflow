import google.generativeai as genai

class SecOpsAgent:
    def __init__(self, model: genai.GenerativeModel):
        self.model = model

    def analyze_diff(self, latest_diff: str):
        """Analyzes a code diff for vulnerabilities."""
        secops_prompt = f"You are a strict SecOps Engineer. Analyze this code diff for hardcoded secrets, SQL injection, XSS, or OWASP top 10 vulnerabilities.\nIf you find ANY security risk, explain it. If the code is safe, reply exactly with 'APPROVED'.\n\nDiff:\n{latest_diff}"
        response = self.model.generate_content(secops_prompt)

        tokens_burned = 0
        if hasattr(response, 'usage_metadata'):
            tokens_burned = response.usage_metadata.total_token_count

        return response.text.strip(), tokens_burned
