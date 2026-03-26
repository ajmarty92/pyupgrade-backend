import pytest
import os
from unittest.mock import patch, mock_open
from scanner import parse_pinned_requirements

def test_parse_pinned_requirements_valid(tmp_path):
    """Test parsing of valid pinned requirements."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("flask==2.0.1\nrequests==2.25.1", encoding="utf-8")

    deps = parse_pinned_requirements(str(req_file))

    assert deps == [
        {"name": "flask", "version": "2.0.1"},
        {"name": "requests", "version": "2.25.1"}
    ]

def test_parse_pinned_requirements_case_normalization(tmp_path):
    """Test that package names are normalized to lowercase."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("Flask==2.0.1\nREQUESTS==2.25.1", encoding="utf-8")

    deps = parse_pinned_requirements(str(req_file))

    assert deps == [
        {"name": "flask", "version": "2.0.1"},
        {"name": "requests", "version": "2.25.1"}
    ]

def test_parse_pinned_requirements_ignore_comments_and_empty(tmp_path):
    """Test that comments and empty lines are ignored."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("\n# This is a comment\nflask==2.0.1\n  \n# Another comment", encoding="utf-8")

    deps = parse_pinned_requirements(str(req_file))

    assert deps == [{"name": "flask", "version": "2.0.1"}]

def test_parse_pinned_requirements_ignore_editable(tmp_path):
    """Test that editable installs are ignored."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("-e .\n-e git+https://github.com/requests/requests.git#egg=requests\nflask==2.0.1", encoding="utf-8")

    deps = parse_pinned_requirements(str(req_file))

    assert deps == [{"name": "flask", "version": "2.0.1"}]

def test_parse_pinned_requirements_ignore_loose_pinning(tmp_path):
    """Test that unpinned or loosely pinned requirements are ignored."""
    req_file = tmp_path / "requirements.txt"
    content = [
        "flask>=2.0.1",
        "requests<=2.25.1",
        "django~=3.2",
        "pytest!=6.0.0",
        "numpy",
        "valid==1.0.0"
    ]
    req_file.write_text("\n".join(content), encoding="utf-8")

    deps = parse_pinned_requirements(str(req_file))

    assert deps == [{"name": "valid", "version": "1.0.0"}]

def test_parse_pinned_requirements_multiple_specifiers(tmp_path):
    """Test that requirements with multiple specifiers are ignored."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("flask>=2.0.1,<=2.1.0\nvalid==1.0.0", encoding="utf-8")

    deps = parse_pinned_requirements(str(req_file))

    assert deps == [{"name": "valid", "version": "1.0.0"}]

def test_parse_pinned_requirements_with_extras(tmp_path):
    """Test parsing of requirements with extras."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests[security]==2.25.1", encoding="utf-8")

    deps = parse_pinned_requirements(str(req_file))

    assert deps == [{"name": "requests", "version": "2.25.1"}]

def test_parse_pinned_requirements_with_markers(tmp_path):
    """Test parsing of requirements with environment markers."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("package==1.2.3; python_version < '3.7'", encoding="utf-8")

    deps = parse_pinned_requirements(str(req_file))

    # Current implementation includes it regardless of markers
    assert deps == [{"name": "package", "version": "1.2.3"}]

def test_parse_pinned_requirements_malformed_line(tmp_path, capsys):
    """Test handling of malformed lines."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("this is not a requirement\nflask==2.0.1", encoding="utf-8")

    deps = parse_pinned_requirements(str(req_file))

    assert deps == [{"name": "flask", "version": "2.0.1"}]
    captured = capsys.readouterr()
    assert "Warning: Could not parse line 1" in captured.out

def test_parse_pinned_requirements_file_not_found(capsys):
    """Test behavior when requirements.txt does not exist."""
    deps = parse_pinned_requirements("non_existent_file.txt")

    assert deps == []
    captured = capsys.readouterr()
    assert "Warning: requirements.txt not found" in captured.out

def test_parse_pinned_requirements_read_error(tmp_path, capsys):
    """Test handling of file read errors."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("flask==2.0.1", encoding="utf-8")

    with patch("builtins.open", side_effect=IOError("Disk full")):
        deps = parse_pinned_requirements(str(req_file))

    assert deps == []
    captured = capsys.readouterr()
    assert "Error reading requirements file" in captured.out
    assert "Disk full" in captured.out
