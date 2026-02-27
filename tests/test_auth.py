import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException
import auth
import models
import schemas
import time

@pytest.mark.asyncio
async def test_get_user_repositories_success():
    mock_user = MagicMock(spec=models.User)
    mock_user.github_access_token = "encrypted_token"

    with patch('auth.security.decrypt_data', return_value="token"), \
         patch('auth.Github') as MockGithub:

        mock_gh_instance = MockGithub.return_value
        mock_gh_user = mock_gh_instance.get_user.return_value
        mock_repo = MagicMock()
        mock_repo.name = "repo1"
        mock_repo.full_name = "user/repo1"
        mock_repo.html_url = "http://github.com/user/repo1"
        mock_repo.description = "desc"
        mock_repo.language = "Python"
        mock_repo.updated_at.isoformat.return_value = "2023-01-01"
        mock_gh_user.get_repos.return_value = [mock_repo]

        repos = await auth.get_user_repositories(mock_user)

        assert len(repos) == 1
        assert repos[0]['name'] == "repo1"

@pytest.mark.asyncio
async def test_verify_repo_permission_success():
    with patch('auth.Github') as MockGithub:
        mock_gh_instance = MockGithub.return_value
        mock_repo = mock_gh_instance.get_repo.return_value
        mock_repo.permissions.push = True

        # Should not raise exception
        await auth.verify_repo_permission("repo", "token")

@pytest.mark.asyncio
async def test_verify_repo_permission_failure():
    with patch('auth.Github') as MockGithub:
        mock_gh_instance = MockGithub.return_value
        mock_repo = mock_gh_instance.get_repo.return_value
        mock_repo.permissions.push = False

        with pytest.raises(HTTPException) as excinfo:
            await auth.verify_repo_permission("repo", "token")
        assert excinfo.value.status_code == 403

@pytest.mark.asyncio
async def test_generate_ai_fix():
    fix_request = schemas.GenerateFixRequest(
        code_snippet="code", issue_type="bug", file_path="file.py", line=1
    )
    with patch('auth.ai_service.generate_code_fix', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "fixed"
        result = await auth.generate_ai_fix(fix_request)
        assert result["fixed_code"] == "fixed"

@pytest.mark.asyncio
async def test_modernize_public_snippet():
    snippet_request = schemas.ModernizeSnippetRequest(code_snippet="code")
    with patch('auth.ai_service.modernize_code_snippet', new_callable=AsyncMock) as mock_mod:
        mock_mod.return_value = "modernized"
        result = await auth.modernize_public_snippet(snippet_request)
        assert result["modernized_code"] == "modernized"

@pytest.mark.asyncio
async def test_get_current_active_user_cache():
    """Test that caching prevents multiple DB calls."""
    # Clear cache
    auth.user_cache.clear()

    mock_db = MagicMock()
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value

    mock_user = models.User(id=999, email="cache@test.com")
    mock_user.__dict__ = {"id": 999, "email": "cache@test.com", "provider": "email"}
    mock_filter.first.return_value = mock_user

    # Mock db.merge to return the passed-in instance to satisfy tests
    mock_db.merge.side_effect = lambda instance, load: instance

    with patch('auth.security.decode_access_token') as mock_decode:
        mock_decode.return_value = {"sub": "999"}
        token = "token"

        # First call: Should hit DB
        user1 = await auth.get_current_active_user(token, mock_db)
        assert user1.id == 999
        assert isinstance(user1, models.User) # Verify it returns models.User
        assert mock_filter.first.call_count == 1

        # Second call: Should hit Cache (DB call count remains 1)
        user2 = await auth.get_current_active_user(token, mock_db)
        assert user2.id == 999
        assert isinstance(user2, models.User)
        assert mock_db.merge.call_count == 1 # Verify merge was called on hit
        assert mock_filter.first.call_count == 1 # Still 1!

        # Manually expire/clear cache and test again
        auth.user_cache.clear()
        user3 = await auth.get_current_active_user(token, mock_db)
        assert mock_filter.first.call_count == 2 # Now 2
