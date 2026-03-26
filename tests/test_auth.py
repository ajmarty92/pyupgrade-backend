import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
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
        user1 = auth.get_current_active_user(token, mock_db)
        assert user1.id == 999
        assert isinstance(user1, models.User) # Verify it returns models.User
        assert mock_filter.first.call_count == 1

        # Second call: Should hit Cache (DB call count remains 1)
        user2 = auth.get_current_active_user(token, mock_db)
        assert user2.id == 999
        assert isinstance(user2, models.User)
        assert mock_db.merge.call_count == 1 # Verify merge was called on hit
        assert mock_filter.first.call_count == 1 # Still 1!

        # Manually expire/clear cache and test again
        auth.user_cache.clear()
        user3 = auth.get_current_active_user(token, mock_db)
        assert mock_filter.first.call_count == 2 # Now 2

def test_login_success_not_production():
    mock_db = MagicMock()
    mock_response = MagicMock(spec=Response)
    mock_form_data = MagicMock(spec=OAuth2PasswordRequestForm)
    mock_form_data.username = "test@example.com"
    mock_form_data.password = "password123"

    mock_user = models.User(id=1, email="test@example.com")

    with patch('auth.security.authenticate_user', return_value=mock_user) as mock_auth, \
         patch('auth.security.create_access_token', return_value="fake-token") as mock_create_token, \
         patch('auth.os.getenv', return_value="false"):

        result = auth.login(response=mock_response, form_data=mock_form_data, db=mock_db)

        mock_auth.assert_called_once_with(mock_db, "test@example.com", "password123")
        mock_create_token.assert_called_once_with(data={"sub": "1"})

        mock_response.set_cookie.assert_called_once_with(
            key="access_token",
            value="Bearer fake-token",
            httponly=True,
            samesite='lax',
            secure=False
        )
        assert result == {"message": "Login successful"}

def test_login_success_production():
    mock_db = MagicMock()
    mock_response = MagicMock(spec=Response)
    mock_form_data = MagicMock(spec=OAuth2PasswordRequestForm)
    mock_form_data.username = "test@example.com"
    mock_form_data.password = "password123"

    mock_user = models.User(id=1, email="test@example.com")

    with patch('auth.security.authenticate_user', return_value=mock_user) as mock_auth, \
         patch('auth.security.create_access_token', return_value="fake-token") as mock_create_token, \
         patch('auth.os.getenv', return_value="true"):

        result = auth.login(response=mock_response, form_data=mock_form_data, db=mock_db)

        mock_auth.assert_called_once_with(mock_db, "test@example.com", "password123")
        mock_create_token.assert_called_once_with(data={"sub": "1"})

        mock_response.set_cookie.assert_called_once_with(
            key="access_token",
            value="Bearer fake-token",
            httponly=True,
            samesite='lax',
            secure=True
        )
        assert result == {"message": "Login successful"}

def test_login_failure_incorrect_credentials():
    mock_db = MagicMock()
    mock_response = MagicMock(spec=Response)
    mock_form_data = MagicMock(spec=OAuth2PasswordRequestForm)
    mock_form_data.username = "test@example.com"
    mock_form_data.password = "wrongpassword"

    with patch('auth.security.authenticate_user', return_value=None) as mock_auth:
        with pytest.raises(HTTPException) as excinfo:
            auth.login(response=mock_response, form_data=mock_form_data, db=mock_db)

        assert excinfo.value.status_code == 401
        assert excinfo.value.detail == "Incorrect email or password"
        mock_auth.assert_called_once_with(mock_db, "test@example.com", "wrongpassword")
