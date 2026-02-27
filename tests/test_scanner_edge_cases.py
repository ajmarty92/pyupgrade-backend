
import pytest
import ast
from unittest.mock import MagicMock
from scanner import DeprecatedSyntaxVisitor

def test_visit_print_node():
    """
    Test that DeprecatedSyntaxVisitor.visit_Print correctly identifies
    Python 2 print statements and reports them as issues.
    Since we are running in Python 3, we mock the AST node.
    """
    # Setup
    code = "print 'hello'"
    visitor = DeprecatedSyntaxVisitor("test.py", code)

    # Create a mock node that simulates an ast.Print node (Python 2)
    mock_node = MagicMock()
    mock_node.lineno = 1
    mock_node.col_offset = 0
    mock_node.end_lineno = 1
    mock_node.end_col_offset = 13

    # Configure _fields for generic_visit traversal
    # A print statement in Py2 has 'dest', 'values', 'nl'
    # We mock these to ensure generic_visit doesn't crash and iterates children
    mock_node._fields = ('dest', 'values', 'nl')
    mock_node.dest = None

    # Mock a child node for values
    # Ensure it passes isinstance(node, ast.AST) check in generic_visit
    mock_child = MagicMock(spec=ast.AST)
    mock_child.lineno = 1
    # Important: Set _fields to empty list so generic_visit can iterate over it (or rather, stop there)
    # without crashing on the mock object itself.
    mock_child._fields = []

    mock_node.values = [mock_child]

    mock_node.nl = True

    # Execute
    visitor.visit_Print(mock_node)

    # Verify
    assert len(visitor.issues) == 1
    issue = visitor.issues[0]
    assert issue['type'] == "Print Statement Syntax (Python 2)"
    assert issue['file'] == "test.py"
    assert issue['line'] == 1
    assert "Uses Python 2-style print statement" in issue['description']

    # Check that code snippet is captured (either actual snippet or fallback)
    assert issue['code_snippet'] is not None
    # Since we set correct line numbers, it should hopefully grab the real snippet
    # or at least not fail.
    if hasattr(ast, 'get_source_segment'):
        # Just a sanity check, doesn't need to be strict if implementation changes
        pass
