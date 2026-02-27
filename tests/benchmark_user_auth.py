import os
import time
import asyncio
from unittest.mock import MagicMock, patch
from cryptography.fernet import Fernet

# Set up dummy environment variables BEFORE importing auth/security
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["GEMINI_API_KEY"] = "dummy_gemini_key"
os.environ["JWT_SECRET_KEY"] = "dummy_jwt_secret"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

# Now import the modules
import auth
import models
import security

async def run_benchmark():
    print("\n--- Benchmarking get_current_active_user (With Caching - Refactored) ---")

    # Clear cache before starting
    auth.user_cache.clear()

    # Mock database session
    mock_db = MagicMock()

    # Mock user object
    user = models.User(id=1, email="test@example.com", github_access_token="encrypted_token")

    # Configure the mock chain: db.query().filter().first()
    # We add a small sleep to simulate DB latency
    def side_effect_first():
        time.sleep(0.005) # Simulate 5ms DB latency
        return user

    mock_db.query.return_value.filter.return_value.first.side_effect = side_effect_first

    # Mock token decoding to isolate the DB/cache part
    with patch('auth.security.decode_access_token') as mock_decode:
        mock_decode.return_value = {"sub": "1"}

        token = "dummy_token"
        iterations = 100

        start_time = time.time()
        for _ in range(iterations):
            user_result = await auth.get_current_active_user(token, mock_db)
            # Basic validation
            assert user_result.id == 1
            assert user_result.email == "test@example.com"

        end_time = time.time()

        total_time = end_time - start_time
        avg_time = total_time / iterations

        print(f"Iterations: {iterations}")
        print(f"Total Time: {total_time:.4f}s")
        print(f"Avg Time per Call: {avg_time:.4f}s")
        print(f"Expected: First call ~0.005s, subsequent calls ~0.000s")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
