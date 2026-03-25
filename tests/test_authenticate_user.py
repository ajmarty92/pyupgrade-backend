import pytest
from unittest.mock import MagicMock, patch
import security
import models

def test_authenticate_user_success():
    """Test that authenticate_user returns the user object when email and password are correct."""
    mock_db = MagicMock()
    mock_user = MagicMock(spec=models.User)
    mock_user.hashed_password = "correct_hashed_password"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user

    # Mock verify_password to return True
    with patch("security.verify_password", return_value=True) as mock_verify:
        result = security.authenticate_user(mock_db, "user@example.com", "correct_password")

        assert result == mock_user
        mock_verify.assert_called_once_with("correct_password", "correct_hashed_password")

def test_authenticate_user_wrong_password():
    """Test that authenticate_user returns None when the password verification fails."""
    mock_db = MagicMock()
    mock_user = MagicMock(spec=models.User)
    mock_user.hashed_password = "hashed_password"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user

    # Mock verify_password to return False
    with patch("security.verify_password", return_value=False) as mock_verify:
        result = security.authenticate_user(mock_db, "user@example.com", "wrong_password")

        assert result is None
        mock_verify.assert_called_once_with("wrong_password", "hashed_password")

def test_authenticate_user_not_found():
    """Test that authenticate_user returns None when user is not found in the database."""
    mock_db = MagicMock()
    # Mock db.query(models.User).filter(models.User.email == email).first()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    result = security.authenticate_user(mock_db, "nonexistent@example.com", "password123")

    assert result is None
    # Verify that the query was made for models.User
    mock_db.query.assert_called_with(models.User)
