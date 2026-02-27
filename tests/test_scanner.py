import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock environment variable for ai_service import
os.environ["GEMINI_API_KEY"] = "dummy_key"

import scanner
import httpx
import tomli

class TestScanner(unittest.TestCase):

    @patch("scanner.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="python-3.9.10")
    def test_detect_python_version_runtime_txt_success(self, mock_file, mock_exists):
        mock_exists.side_effect = lambda p: p.endswith("runtime.txt")
        version = scanner.detect_python_version("/fake/path")
        self.assertEqual(version, "3.9.10")

    @patch("scanner.os.path.exists")
    @patch("builtins.open", side_effect=IOError("Permission denied"))
    def test_detect_python_version_runtime_txt_error(self, mock_file, mock_exists):
        mock_exists.side_effect = lambda p: p.endswith("runtime.txt")
        # This triggers the print statement at line 29
        version = scanner.detect_python_version("/fake/path")
        self.assertEqual(version, "Undetermined")

    @patch("scanner.os.path.exists")
    @patch("builtins.open", side_effect=IOError("Read error"))
    def test_detect_python_version_pyenv_error(self, mock_file, mock_exists):
        mock_exists.side_effect = lambda p: p.endswith(".python-version")
        version = scanner.detect_python_version("/fake/path")
        self.assertEqual(version, "Undetermined")

    @patch("scanner.os.path.exists")
    @patch("builtins.open", side_effect=tomli.TOMLDecodeError("Invalid TOML"))
    def test_detect_python_version_pyproject_toml_decode_error(self, mock_file, mock_exists):
        mock_exists.side_effect = lambda p: p.endswith("pyproject.toml")
        version = scanner.detect_python_version("/fake/path")
        self.assertEqual(version, "Undetermined")

    @patch("scanner.os.path.exists")
    @patch("builtins.open", side_effect=IOError("Read error"))
    def test_detect_python_version_pyproject_toml_read_error(self, mock_file, mock_exists):
        mock_exists.side_effect = lambda p: p.endswith("pyproject.toml")
        version = scanner.detect_python_version("/fake/path")
        self.assertEqual(version, "Undetermined")

    @patch("scanner.os.path.exists", return_value=False)
    def test_parse_pinned_requirements_not_found(self, mock_exists):
        deps = scanner.parse_pinned_requirements("/fake/requirements.txt")
        self.assertEqual(deps, [])

    @patch("scanner.os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="invalid-req-line\nflask==2.0.1")
    def test_parse_pinned_requirements_parsing_error(self, mock_file, mock_exists):
        deps = scanner.parse_pinned_requirements("/fake/requirements.txt")
        # Should parse valid line, skip invalid one and print warning
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0]['name'], 'flask')

    @patch("scanner.os.path.exists", return_value=True)
    @patch("builtins.open", side_effect=IOError("Read error"))
    def test_parse_pinned_requirements_read_error(self, mock_file, mock_exists):
        deps = scanner.parse_pinned_requirements("/fake/requirements.txt")
        self.assertEqual(deps, [])

    @patch("httpx.Client")
    def test_check_osv_for_vulnerabilities_http_error(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.__enter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("500 Error", request=MagicMock(), response=MagicMock(status_code=500, text="Server Error"))
        mock_client.post.return_value = mock_response

        deps = [{"name": "flask", "version": "1.0"}]
        report = scanner.check_osv_for_vulnerabilities(deps)

        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]['status'], 'warning')
        self.assertIn("API error", report[0]['reason'])

    @patch("httpx.Client")
    def test_check_osv_for_vulnerabilities_network_error(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.__enter__.return_value = mock_client

        mock_client.post.side_effect = httpx.RequestError("Connection refused")

        deps = [{"name": "flask", "version": "1.0"}]
        report = scanner.check_osv_for_vulnerabilities(deps)

        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]['status'], 'warning')
        self.assertIn("network error", report[0]['reason'])

    @patch("builtins.open", side_effect=SyntaxError("Bad syntax", ("file.py", 1, 1, "bad code")))
    def test_analyze_python_file_syntax_error(self, mock_file):
        issues = scanner.analyze_python_file("/fake/file.py")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]['type'], "Syntax Error")

    @patch("builtins.open", side_effect=Exception("Generic error"))
    def test_analyze_python_file_generic_error(self, mock_file):
        issues = scanner.analyze_python_file("/fake/file.py")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]['type'], "Analysis Error")
