import time
import asyncio
from unittest.mock import MagicMock, patch
import os
from cryptography.fernet import Fernet
from fastapi import Response
from fastapi.security import OAuth2PasswordRequestForm

os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["GEMINI_API_KEY"] = "dummy_gemini_key"
os.environ["JWT_SECRET_KEY"] = "dummy_jwt_secret"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

import auth
import models

# To simulate the event loop behavior, we need to test how FastAPI runs it.
# Since FastAPI runs `def` in a threadpool, we use asyncio.to_thread for `def`,
# and await directly for `async def` (which is what we compare).

async def slow_db_query(*args, **kwargs):
    time.sleep(0.05) # simulate 50ms blocking DB query
    return models.User(id=1, email="test@test.com")

async def test_concurrent_login():
    mock_db = MagicMock()
    mock_form = MagicMock()
    mock_form.username = "test"
    mock_form.password = "pass"
    mock_response = Response()

    def slow_auth(db, username, password):
        time.sleep(0.05)
        return models.User(id=1, email="test@test.com")

    print("Running login benchmark...")

    with patch('auth.security.authenticate_user', side_effect=slow_auth):
        with patch('auth.security.create_access_token', return_value="token"):
            start = time.time()
            # If login were async, we'd do:
            # tasks = [auth.login(mock_response, mock_form, mock_db) for _ in range(20)]
            # await asyncio.gather(*tasks)
            # But since it's sync, FastAPI wraps it in run_in_threadpool.
            from fastapi.concurrency import run_in_threadpool
            tasks = [run_in_threadpool(auth.login, mock_response, mock_form, mock_db) for _ in range(20)]
            await asyncio.gather(*tasks)
            end = time.time()

    elapsed = end - start
    print(f"20 concurrent calls to optimized login took: {elapsed:.4f} seconds")
    print(f"Expected ideal time (if running in threadpool): ~0.05 seconds")
    print(f"Expected time if async blocking loop: ~1.0000 seconds")

if __name__ == "__main__":
    asyncio.run(test_concurrent_login())
