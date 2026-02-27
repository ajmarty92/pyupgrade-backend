import pytest
from unittest.mock import MagicMock, patch
import logging
from fastapi.testclient import TestClient
from main import app
import models
import auth

client = TestClient(app)

@pytest.mark.asyncio
async def test_start_scan_logging(caplog):
    # Setup mock user and token
    mock_user = MagicMock(spec=models.User)
    mock_user.id = 1
    mock_user.github_access_token = "encrypted_token"

    # We need to override the dependency in the app, because TestClient uses the app's dependency overrides
    app.dependency_overrides[auth.get_current_active_user] = lambda: mock_user

    # Mock dependencies to trigger the generic Exception block
    # Note: We patch 'auth.verify_repo_permission' because main.py imports it from auth
    with patch('security.decrypt_data', return_value="token"), \
         patch('auth.verify_repo_permission', side_effect=Exception("Simulated API Failure")):

        repo_data = {"repo_name": "user/repo"}

        # Capture logs
        with caplog.at_level(logging.ERROR):
            response = client.post("/api/scan", json=repo_data)

            # Verify the response is 500 (as expected from the code)
            assert response.status_code == 500

            # Verify the log message is present in the captured logs
            assert "Error starting scan: Simulated API Failure" in caplog.text

    # Clean up overrides
    app.dependency_overrides = {}
