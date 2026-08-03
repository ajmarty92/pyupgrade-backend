import pytest
from unittest.mock import patch, MagicMock
import os
import importlib

import database
from database import get_db

def test_get_db_yields_session_and_closes():
    """
    Verify that get_db() correctly yields a database session and closes it.
    """
    with patch("database.SessionLocal") as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        db_generator = get_db()
        db = next(db_generator)

        # Verify the yielded database is the mock session
        assert db is mock_session

        # Verify close hasn't been called yet
        mock_session.close.assert_not_called()

        # Complete the generator
        try:
            next(db_generator)
        except StopIteration:
            pass

        # Verify close was called after iteration
        mock_session.close.assert_called_once()

def test_database_url_postgres_replacement():
    """
    Verify that if the URL starts with postgres://, it is replaced with postgresql+psycopg2://
    """
    with patch.dict(os.environ, {"DATABASE_URL": "postgres://user:pass@localhost/db"}):
        importlib.reload(database)
        assert database.SQLALCHEMY_DATABASE_URL == "postgresql+psycopg2://user:pass@localhost/db"

def test_database_url_sqlite_fallback():
    """
    Verify that for local SQLite testing, it keeps the original logic if no DATABASE_URL is provided.
    """
    with patch.dict(os.environ, clear=True):
        importlib.reload(database)
        assert database.SQLALCHEMY_DATABASE_URL == "sqlite:///./sql_app.db"

def test_database_url_existing_postgresql():
    """
    Verify that if DATABASE_URL is already set correctly (e.g., includes psycopg2), use it as is
    """
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db"}):
        importlib.reload(database)
        assert database.SQLALCHEMY_DATABASE_URL == "postgresql://user:pass@localhost/db"
