import os
import pytest
from cryptography.fernet import Fernet

# Set up dummy environment variables before any modules are imported
# This prevents ValueErrors in module-level code (like in security.py or ai_service.py)
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["GEMINI_API_KEY"] = "dummy_gemini_key"
os.environ["JWT_SECRET_KEY"] = "dummy_jwt_secret"
