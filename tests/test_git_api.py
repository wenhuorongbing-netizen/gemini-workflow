import pytest
from fastapi.testclient import TestClient
import app
import sys
from unittest.mock import patch, MagicMock

# Mock github module directly so PyGithub isn't called during unit tests
sys.modules['github'] = MagicMock()

client = TestClient(app.app)

@patch('app.get_branch_diff')
def test_get_devhouse_diff(mock_get_branch_diff):
    mock_get_branch_diff.return_value = "File: main.py\nStatus: modified\nDiff:\n+print('hello')\n"

    response = client.get("/api/devhouse/diff?compare_branch=feature-branch")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "File: main.py" in data["diff"]
    mock_get_branch_diff.assert_called_once_with("main", "feature-branch")

@patch('app.create_feature_branch')
def test_post_devhouse_start(mock_create_feature_branch):
    mock_create_feature_branch.return_value = "devhouse-test-123"

    payload = {
        "prompt": "Build a new header component.",
        "kbLinks": "https://docs.github.com",
        "model": "Pro"
    }

    response = client.post("/api/devhouse/start", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["branch"] == "devhouse-test-123"
    assert mock_create_feature_branch.called

@patch('app.merge_and_delete_branch')
def test_post_devhouse_merge(mock_merge_and_delete_branch):
    mock_merge_and_delete_branch.return_value = {"status": "success", "message": "Branch merged.", "merged": True, "sha": "1234abc"}

    payload = {
        "head_branch": "devhouse-test-123"
    }

    response = client.post("/api/devhouse/merge", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["merged"] == True
    mock_merge_and_delete_branch.assert_called_once_with("devhouse-test-123", "main")
