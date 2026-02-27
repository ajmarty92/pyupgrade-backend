import pytest
from unittest.mock import MagicMock, patch, ANY
from fastapi import HTTPException
import auth
from github import GithubException
import logging

@pytest.mark.asyncio
async def test_handle_create_pr_logging_security():
    # Setup
    mock_user = MagicMock()
    mock_user.github_access_token = "encrypted_token"

    mock_pr_request = MagicMock()
    mock_pr_request.repo_name = "user/repo"
    mock_pr_request.file_path = "file.py"
    mock_pr_request.old_code = "old"
    mock_pr_request.new_code = "new"
    mock_pr_request.issue_type = "bug"

    # Simulate a sensitive exception
    sensitive_headers = {"Authorization": "token SENSITIVE_TOKEN"}
    github_exception = GithubException(
        status=400,
        data={"message": "Error"},
        headers=sensitive_headers
    )

    with patch('auth.security.decrypt_data', return_value="token"), \
         patch('auth.Github') as MockGithub, \
         patch('builtins.print') as mock_print, \
         patch('traceback.print_exc') as mock_traceback, \
         patch('auth.logger', create=True) as mock_logger: # create=True allows mocking if it doesn't exist yet

        # Mock the Github client to raise the exception
        mock_gh_instance = MockGithub.return_value
        mock_gh_instance.get_repo.side_effect = github_exception

        # Expect HTTPException to be raised
        with pytest.raises(HTTPException):
            await auth.handle_create_pr(mock_pr_request, mock_user)

        # Assertions for Secure Behavior

        # 1. print should NOT be used
        if mock_print.called:
            # If called, ensure it doesn't leak sensitive info (though we prefer it not called at all)
            # But strictly, we want to replace print with logger.
            pytest.fail("builtins.print() was called. Should use logger instead.")

        # 2. traceback.print_exc should NOT be used
        if mock_traceback.called:
             pytest.fail("traceback.print_exc() was called. Should use logger instead.")

        # 3. logger.error SHOULD be called
        assert mock_logger.error.called, "logger.error() was not called."

        # 4. Verify logged message content
        # Get arguments of the call
        args, _ = mock_logger.error.call_args
        log_message = args[0]

        # Ensure sensitive token is not in the log message
        assert "SENSITIVE_TOKEN" not in log_message, "Log message contains sensitive token!"
        assert "Authorization" not in log_message, "Log message contains sensitive headers!"
