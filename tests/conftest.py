import os
import pytest
from cryptography.fernet import Fernet

# --- FIX: Set environment variables for tests ---
# This must happen before other modules are imported during test collection
if "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = "dummy_key_for_testing"

if "FERNET_KEY" not in os.environ:
    # Use a valid Fernet key
    os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Any other test setup that requires dependencies or fixtures."""
    pass
