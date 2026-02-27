import pytest
from cryptography.fernet import Fernet
from datetime import datetime, timedelta, timezone
import security

def test_encrypt_decrypt_lifecycle():
    """Test that data can be encrypted and then decrypted back to the original value."""
    original_data = "This is a secret message"
    encrypted_data = security.encrypt_data(original_data)
    decrypted_data = security.decrypt_data(encrypted_data)
    assert decrypted_data == original_data
    assert encrypted_data != original_data

def test_encryption_randomness():
    """Test that encrypting the same data twice results in different ciphertexts."""
    data = "Consistency check"
    encrypted_1 = security.encrypt_data(data)
    encrypted_2 = security.encrypt_data(data)
    assert encrypted_1 != encrypted_2
    # Ensure both can be decrypted
    assert security.decrypt_data(encrypted_1) == data
    assert security.decrypt_data(encrypted_2) == data

def test_decrypt_failure():
    """Test that decrypting invalid data raises an error."""
    invalid_data = "NotEncryptedData"
    # Fernet raises an error (InvalidToken usually, or binascii.Error if base64 is bad)
    # The exact error depends on the implementation details of Fernet, but it should fail.
    # In cryptography library, it typically raises cryptography.fernet.InvalidToken
    # However, since the function just calls fernet.decrypt, we expect that exception to propagate.
    # Let's catch Exception generally or the specific one if we import it.
    from cryptography.fernet import InvalidToken
    import binascii

    with pytest.raises((InvalidToken, binascii.Error)):
        security.decrypt_data(invalid_data)

def test_create_access_token_default_expiry():
    """Test creating an access token with default expiration."""
    data = {"sub": "testuser"}
    token = security.create_access_token(data)
    assert isinstance(token, str)

    payload = security.decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "testuser"
    assert "exp" in payload

    # Expected expiration is roughly now + 7 days (ACCESS_TOKEN_EXPIRE_MINUTES)
    # ACCESS_TOKEN_EXPIRE_MINUTES is 60 * 24 * 7
    expected_delta = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    expected_exp = datetime.now(timezone.utc) + expected_delta

    # Verify expiration is within a reasonable range (e.g., 10 seconds)
    # JWT exp is in seconds (int or float)
    assert abs(payload["exp"] - expected_exp.timestamp()) < 10

def test_create_access_token_custom_expiry():
    """Test creating an access token with custom expiration."""
    data = {"sub": "testuser_custom"}
    expires_delta = timedelta(minutes=15)
    token = security.create_access_token(data, expires_delta=expires_delta)

    payload = security.decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "testuser_custom"

    # Check expiration
    expected_exp = datetime.now(timezone.utc) + expires_delta
    assert abs(payload["exp"] - expected_exp.timestamp()) < 10

def test_decode_access_token_invalid():
    """Test decoding an invalid token returns None."""
    invalid_token = "invalid.token.string"
    payload = security.decode_access_token(invalid_token)
    assert payload is None

def test_decode_access_token_expired():
    """Test decoding an expired token returns None."""
    data = {"sub": "expired_user"}
    # Create a token that expired 1 minute ago
    expires_delta = timedelta(minutes=-1)
    token = security.create_access_token(data, expires_delta=expires_delta)

    payload = security.decode_access_token(token)
    assert payload is None
