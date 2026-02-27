import pytest
import os
from scanner import detect_python_version

def test_detect_python_version_runtime_txt_heroku_style(tmp_path):
    """Test detection from runtime.txt with Heroku style 'python-X.X.X'."""
    d = tmp_path / "repo"
    d.mkdir()
    p = d / "runtime.txt"
    p.write_text("python-3.9.10", encoding="utf-8")

    version = detect_python_version(str(d))
    assert version == "3.9.10"

def test_detect_python_version_runtime_txt_simple(tmp_path):
    """Test detection from runtime.txt with simple version string."""
    d = tmp_path / "repo"
    d.mkdir()
    p = d / "runtime.txt"
    p.write_text("3.8", encoding="utf-8")

    version = detect_python_version(str(d))
    assert version == "3.8"

def test_detect_python_version_pyenv(tmp_path):
    """Test detection from .python-version."""
    d = tmp_path / "repo"
    d.mkdir()
    p = d / ".python-version"
    p.write_text("3.11.0", encoding="utf-8")

    version = detect_python_version(str(d))
    assert version == "3.11.0"

def test_detect_python_version_pyproject_pep621(tmp_path):
    """Test detection from pyproject.toml using PEP 621 standard."""
    d = tmp_path / "repo"
    d.mkdir()
    p = d / "pyproject.toml"
    p.write_text("""
[project]
name = "test_project"
requires-python = ">=3.10"
""", encoding="utf-8")

    version = detect_python_version(str(d))
    assert version == ">=3.10"

def test_detect_python_version_pyproject_poetry(tmp_path):
    """Test detection from pyproject.toml using Poetry format."""
    d = tmp_path / "repo"
    d.mkdir()
    p = d / "pyproject.toml"
    p.write_text("""
[tool.poetry.dependencies]
python = "^3.9"
""", encoding="utf-8")

    version = detect_python_version(str(d))
    assert version == "^3.9"

def test_detect_python_version_priority(tmp_path):
    """Test that runtime.txt takes precedence over other files."""
    d = tmp_path / "repo"
    d.mkdir()

    # Create runtime.txt
    (d / "runtime.txt").write_text("3.9", encoding="utf-8")
    # Create .python-version
    (d / ".python-version").write_text("3.10", encoding="utf-8")
    # Create pyproject.toml
    (d / "pyproject.toml").write_text("""
[project]
requires-python = "3.11"
""", encoding="utf-8")

    version = detect_python_version(str(d))
    assert version == "3.9"

def test_detect_python_version_priority_pyenv_over_toml(tmp_path):
    """Test that .python-version takes precedence over pyproject.toml."""
    d = tmp_path / "repo"
    d.mkdir()

    # Create .python-version
    (d / ".python-version").write_text("3.10", encoding="utf-8")
    # Create pyproject.toml
    (d / "pyproject.toml").write_text("""
[project]
requires-python = "3.11"
""", encoding="utf-8")

    version = detect_python_version(str(d))
    assert version == "3.10"

def test_detect_python_version_undetermined(tmp_path):
    """Test that it returns 'Undetermined' when no version files exist."""
    d = tmp_path / "repo"
    d.mkdir()

    version = detect_python_version(str(d))
    assert version == "Undetermined"

def test_detect_python_version_malformed_toml(tmp_path):
    """Test behavior with malformed pyproject.toml."""
    d = tmp_path / "repo"
    d.mkdir()
    p = d / "pyproject.toml"
    p.write_text("this is not valid toml", encoding="utf-8")

    # Should handle the error gracefully and return Undetermined (if no other files)
    # The function prints the error but should not crash
    version = detect_python_version(str(d))
    assert version == "Undetermined"
