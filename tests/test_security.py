import pytest
from cryptography.fernet import Fernet
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
