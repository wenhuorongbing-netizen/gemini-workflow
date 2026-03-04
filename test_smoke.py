import pytest
import os
import asyncio
from bot import GeminiBot

def test_imports_and_environment():
    """Ensure all critical files exist and dependencies can be imported."""
    assert os.path.exists("app.py"), "app.py is missing"
    assert os.path.exists("bot.py"), "bot.py is missing"
    assert os.path.exists("templates/index.html"), "Frontend template is missing"
    assert os.path.exists("requirements.txt"), "requirements.txt is missing"

@pytest.mark.asyncio
async def test_bot_initialization(monkeypatch):
    """
    Test that the GeminiBot class can be imported and instantiated as an async task.
    We mock the initialize method to avoid actually opening a browser in CI.
    """
    async def mock_initialize(self):
        self._initialized = True
        pass

    monkeypatch.setattr(GeminiBot, "initialize", mock_initialize)

    bot = GeminiBot(profile_path="test_profile")
    await bot.initialize()

    assert bot.profile_path == "test_profile"
    assert bot._initialized is True
