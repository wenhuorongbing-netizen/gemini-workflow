import os

class SecretManager:
    @staticmethod
    def get_github_token() -> str:
        return os.environ.get("GITHUB_TOKEN", "")

    @staticmethod
    def mask_secrets(text: str) -> str:
        if not text:
            return text
        token = SecretManager.get_github_token()
        if token:
            text = text.replace(token, "[REDACTED_TOKEN]")
        return text
