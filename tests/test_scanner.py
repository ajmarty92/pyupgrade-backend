import pytest
import os
import ast
from unittest.mock import MagicMock
from scanner import analyze_python_file, DeprecatedSyntaxVisitor

# Fixture to create a temporary file with content
@pytest.fixture
def create_temp_file(tmp_path):
    def _create_temp_file(content):
        p = tmp_path / "test_file.py"
        p.write_text(content, encoding='utf-8')
        return str(p)
    return _create_temp_file

def test_analyze_python_file_valid_code(create_temp_file):
    """Test that valid Python code produces no issues."""
    content = "print('Hello, world!')"
    filepath = create_temp_file(content)

    issues = analyze_python_file(filepath)
    assert len(issues) == 0

def test_analyze_python_file_syntax_error(create_temp_file):
    """Test that a file with syntax error (like Python 2 print) is caught."""
    content = 'print "Hello, world!"'
    filepath = create_temp_file(content)

    issues = analyze_python_file(filepath)

    # Python 3 parsing will fail with SyntaxError for print "..."
    # The analyze_python_file function catches SyntaxError
    assert len(issues) == 1
    assert issues[0]['type'] == 'Syntax Error'

def test_analyze_python_file_file_not_found():
    """Test behavior when file does not exist."""
    filepath = "non_existent_file.py"

    issues = analyze_python_file(filepath)

    # The function catches exceptions and reports Analysis Error
    assert len(issues) == 1
    assert issues[0]['type'] == 'Analysis Error'
    assert "No such file or directory" in issues[0]['description']

def test_deprecated_syntax_visitor_print():
    """Test that DeprecatedSyntaxVisitor correctly flags Python 2 print statements."""
    # We manually create a visitor and call visit_Print with a mock node
    # because Python 3 ast.parse won't generate a Print node.
    visitor = DeprecatedSyntaxVisitor("test.py", "print 'hello'")

    # Mock a Print node (Python 2 AST node type)
    mock_node = MagicMock()
    mock_node.lineno = 1
    # ast.get_source_segment will fail or return None since node is mock,
    # but the visitor handles this gracefully.

    # Simulate visit_Print call
    visitor.visit_Print(mock_node)

    assert len(visitor.issues) == 1
    issue = visitor.issues[0]
    assert issue['type'] == 'Print Statement Syntax (Python 2)'
    assert issue['file'] == 'test.py'
    assert issue['line'] == 1

def test_deprecated_syntax_visitor_raise():
    """Test that DeprecatedSyntaxVisitor correctly flags Python 2 raise statements."""
    visitor = DeprecatedSyntaxVisitor("test.py", "raise Exception, 'value'")

    # Mock a Raise node with Python 2 attributes (type, inst)
    mock_node = MagicMock()
    mock_node.lineno = 2
    mock_node.type = "Exception"
    mock_node.inst = "value"

    # Simulate visit_Raise call
    visitor.visit_Raise(mock_node)

    assert len(visitor.issues) == 1
    issue = visitor.issues[0]
    assert issue['type'] == 'Old-style raise statement (Python 2)'
    assert issue['file'] == 'test.py'
    assert issue['line'] == 2
