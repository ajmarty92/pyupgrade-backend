import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
import auth
import models
import schemas
from github import GithubException

@pytest.mark.asyncio
async def test_get_user_repositories_logging():
    mock_user = MagicMock(spec=models.User)
    mock_user.github_access_token = "encrypted_token"

    # We patch 'auth.logger' which we expect to exist after refactoring
    with patch('auth.security.decrypt_data', return_value="token"), \
         patch('auth.Github') as MockGithub, \
         patch('auth.logger') as mock_logger:

        mock_gh = MockGithub.return_value
        mock_gh.get_user.side_effect = Exception("Test Error")

        # The function catches generic Exception and raises HTTPException
        with pytest.raises(HTTPException):
             await auth.get_user_repositories(mock_user)

        # Verify logger.error was called
        mock_logger.error.assert_called()

@pytest.mark.asyncio
async def test_handle_create_pr_logging():
    pr_request = schemas.CreatePRRequest(
        repo_name="test/repo",
        file_path="test.py",
        old_code="old",
        new_code="new",
        issue_type="bug"
    )
    mock_user = MagicMock(spec=models.User)
    mock_user.github_access_token = "encrypted_token"

    with patch('auth.security.decrypt_data', return_value="token"), \
         patch('auth.Github') as MockGithub, \
         patch('auth.logger') as mock_logger:

        mock_gh = MockGithub.return_value
        # Mocking an exception that triggers the except block
        mock_gh.get_repo.side_effect = GithubException(400, {"message": "Error"})

        # The function catches GithubException and raises HTTPException
        with pytest.raises(HTTPException):
             await auth.handle_create_pr(pr_request, mock_user)

        mock_logger.error.assert_called()
