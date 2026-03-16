import pytest
from fastapi.testclient import TestClient
import app
import sys
from unittest.mock import patch, MagicMock

# Mock github and google.generativeai modules directly so external APIs aren't called
sys.modules['github'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()

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

@patch('app.get_branch_diff')
def test_post_devhouse_review_no_changes(mock_get_branch_diff):
    mock_get_branch_diff.return_value = "   "

    payload = {
        "feature_branch": "devhouse-test-123"
    }

    response = client.post("/api/devhouse/review", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_changes"

@patch('app.get_github_repo')
def test_auth_exception_handling(mock_get_github_repo):
    mock_get_github_repo.side_effect = app.AuthException("Please add a valid GITHUB_TOKEN to your .env file")

    payload = {
        "prompt": "Test auth",
    }
    response = client.post("/api/devhouse/start", json=payload)

    assert response.status_code == 401
    data = response.json()
    assert "Please add a valid GITHUB_TOKEN" in data["error"]
