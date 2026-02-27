import os
import shutil
import tempfile
import ast
import httpx
from git import Repo
from packaging.requirements import Requirement
import tomli
import ai_service 
import asyncio
from sqlalchemy.orm import Session
import models
import logging

# --- Configure Logging ---
logger = logging.getLogger(__name__)

# --- FIX: Restored Helper Functions ---

def detect_python_version(repo_path: str) -> str:
    """Detects the Python version specified in common project files."""
    # Check runtime.txt (Heroku)
    runtime_path = os.path.join(repo_path, 'runtime.txt')
    if os.path.exists(runtime_path):
        try:
            with open(runtime_path, 'r') as f:
                version_str = f.read().strip()
                # Handles formats like "python-3.9.10"
                if version_str.startswith('python-'):
                    return version_str.split('-')[1]
                return version_str # Assumes just the version number
        except Exception as e:
            logger.warning(f"Error reading runtime.txt: {e}")
            
    # Check .python-version (pyenv)
    pyenv_path = os.path.join(repo_path, '.python-version')
    if os.path.exists(pyenv_path):
        try:
            with open(pyenv_path, 'r') as f: 
                return f.read().strip()
        except Exception as e:
            logger.warning(f"Error reading .python-version: {e}")

    # Check pyproject.toml (PEP 621, Poetry, etc.)
    pyproject_path = os.path.join(repo_path, 'pyproject.toml')
    if os.path.exists(pyproject_path):
        try:
            with open(pyproject_path, 'rb') as f: 
                config = tomli.load(f)
            # Standard PEP 621 location
            if 'project' in config and 'requires-python' in config['project']: 
                return config['project']['requires-python']
            # Poetry specific location
            if 'tool' in config and 'poetry' in config['tool'] and 'dependencies' in config['tool']['poetry'] and 'python' in config['tool']['poetry']['dependencies']: 
                return config['tool']['poetry']['dependencies']['python']
        except tomli.TOMLDecodeError as e:
            logger.warning(f"Error decoding pyproject.toml: {e}")
        except Exception as e:
             logger.warning(f"Error reading pyproject.toml: {e}")

    # Could add checks for Pipfile, setup.py, etc. here later
    
    return "Undetermined" # Default if nothing found

def parse_pinned_requirements(filepath: str) -> list[dict]:
    """Parses a requirements.txt file for pinned dependencies (package==version)."""
    dependencies = []
    if not os.path.exists(filepath): 
        logger.warning(f"Warning: requirements.txt not found at {filepath}")
        return dependencies
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                # Skip empty lines, comments, and editable installs
                if not line or line.startswith('#') or line.startswith('-e'): 
                    continue
                try:
                    # Use packaging.requirements to handle complex lines
                    req = Requirement(line)
                    # We are only interested in *exactly* pinned versions for OSV check
                    if len(req.specifier) == 1 and str(req.specifier).startswith('=='):
                        version = str(req.specifier).replace('==', '').strip()
                        dependencies.append({'name': req.name.lower(), 'version': version})
                    # Optional: Could add logic here to warn about unpinned dependencies
                except Exception as parse_error:
                    logger.warning(f"Warning: Could not parse line {line_num} in {filepath}: {line} - Error: {parse_error}")
                    continue # Skip lines that can't be parsed
    except Exception as e:
         logger.error(f"Error reading requirements file {filepath}: {e}")
         
    return dependencies

def check_osv_for_vulnerabilities(dependencies: list[dict]) -> list[dict]:
    """Queries the OSV API for vulnerabilities in the given list of dependencies."""
    if not dependencies: 
        return []
        
    # Prepare batch query for OSV
    queries = [{"version": d["version"], "package": {"name": d["name"], "ecosystem": "PyPI"}} for d in dependencies]
    report_entries = []
    
    try:
        # Use httpx for sync request within Celery task
        with httpx.Client() as client:
            response = client.post("https://api.osv.dev/v1/querybatch", json={"queries": queries}, timeout=30.0)
            response.raise_for_status() # Raise exception for bad status codes (4xx or 5xx)
            results = response.json().get("results", [])

        if len(results) != len(dependencies):
             logger.warning(f"Warning: OSV API returned {len(results)} results for {len(dependencies)} queries.")
             # Attempt to match based on name/version if lengths differ (simple matching)
             results_map = {(r['query']['package']['name'], r['query']['version']): r for r in results if r.get('query')}
             processed_indices = set()
             for i, dep in enumerate(dependencies):
                 result = results_map.get((dep['name'], dep['version']))
                 if result and "vulns" in result:
                    ids = [v.get("id", "N/A") for v in result["vulns"]]
                    reason = f"Vulnerable to: {', '.join(ids[:3])}"
                    if len(ids) > 3: reason += f", and {len(ids) - 3} more."
                    report_entries.append({"name": dep["name"], "version": dep["version"], "status": "incompatible", "reason": reason})
                    processed_indices.add(i)
             # Log unmatched results if necessary
             
        else:
             # Process results assuming order is maintained
            for i, res in enumerate(results):
                # Check if the result has vulnerabilities listed
                if res and "vulns" in res:
                    ids = [v.get("id", "N/A") for v in res["vulns"]]
                    reason = f"Vulnerable to: {', '.join(ids[:3])}" # Show first 3 IDs
                    if len(ids) > 3: 
                        reason += f", and {len(ids) - 3} more."
                    
                    original_dep = dependencies[i] # Get corresponding dependency
                    report_entries.append({
                        "name": original_dep["name"], 
                        "version": original_dep["version"], 
                        "status": "incompatible", # Mark as incompatible if vulnerable
                        "reason": reason
                    })

    except httpx.HTTPStatusError as e:
        logger.error(f"Error querying OSV API: HTTP {e.response.status_code} - {e.response.text}")
        # Optionally add an error marker to the report
        report_entries.append({"name": "OSV Check Failed", "version": "", "status": "warning", "reason": f"Could not check dependencies due to API error: {e.response.status_code}"})
    except httpx.RequestError as e:
        logger.error(f"Error querying OSV API: Network error - {e}")
        report_entries.append({"name": "OSV Check Failed", "version": "", "status": "warning", "reason": f"Could not check dependencies due to network error."})
    except Exception as e:
        logger.error(f"Unexpected error during OSV check: {e}")
        report_entries.append({"name": "OSV Check Failed", "version": "", "status": "warning", "reason": f"Unexpected error during check."})
        
    return report_entries

class DeprecatedSyntaxVisitor(ast.NodeVisitor):
    """AST visitor to find specific deprecated Python syntax patterns."""
    def __init__(self, file_path, source_code):
        self.file_path = file_path
        self.source_code = source_code # Store source for get_source_segment
        self.issues = []

    def _get_code_snippet(self, node):
        """Safely get the source code segment for a node."""
        try:
            # Requires Python 3.8+ for ast.get_source_segment
            return ast.get_source_segment(self.source_code, node) or ""
        except Exception:
            # Fallback for older versions or if source isn't available
             return f"# Code on line {node.lineno}"

    def visit_Raise(self, node):
        """Checks for Python 2 style 'raise Exception, value'."""
        # This checks for the old `raise E, V[, T]` syntax
        # In AST, this might appear as multiple args if not parsed correctly,
        # or specific attributes might be missing/different than modern `raise`.
        # A simple check: modern `raise` has `exc` and optionally `cause`.
        # Old `raise E, V` might parse `V` into `node.args` or similar.
        # This is tricky to catch reliably with AST across versions.
        # A simpler check might be needed, potentially involving line inspection.
        # Let's refine the check:
        if hasattr(node, 'type') and hasattr(node, 'inst'): # Common in Python 2 AST representation
             snippet = self._get_code_snippet(node)
             self.issues.append({
                 "type": "Old-style raise statement (Python 2)", 
                 "file": self.file_path, 
                 "line": node.lineno, 
                 "description": "Uses deprecated Python 2 'raise E, V' syntax.", 
                 "code_snippet": snippet
             })
        elif hasattr(node, 'exc') and node.exc and not hasattr(node, 'cause'): 
             # Check if there are multiple arguments being passed in a non-standard way
             # This is still heuristic and might need refinement
             pass # Let's avoid potentially noisy/incorrect detections for now

        self.generic_visit(node)

    def visit_Print(self, node):
        """Identifies the Python 2 style 'print' statement (which is a specific node type)."""
        snippet = self._get_code_snippet(node)
        self.issues.append({
            "type": "Print Statement Syntax (Python 2)", 
            "file": self.file_path, 
            "line": node.lineno, 
            "description": "Uses Python 2-style print statement.", 
            "code_snippet": snippet
        })
        self.generic_visit(node)
        
    # Add more visit_... methods here for other deprecated syntax
    # e.g., visit_ExceptHandler for old except syntax, visit_ImportFrom for relative imports

def analyze_python_file(filepath: str) -> list:
    """Parses a Python file and uses AST visitor to find deprecated syntax."""
    issues = []
    try:
        # Read the file content
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Parse the code into an Abstract Syntax Tree
        tree = ast.parse(content, filename=filepath)
        
        # Use the visitor to find issues
        visitor = DeprecatedSyntaxVisitor(filepath, content)
        visitor.visit(tree)
        issues = visitor.issues
        
    except SyntaxError as e:
        logger.warning(f"Warning: Skipping file due to syntax error: {filepath} - Line {e.lineno}, Offset {e.offset}: {e.msg}")
        # Optionally report this as a different kind of issue
        issues.append({
            "type": "Syntax Error", 
            "file": filepath, 
            "line": e.lineno, 
            "description": f"File could not be parsed: {e.msg}", 
            "code_snippet": f"# Error on line {e.lineno}"
        })
    except Exception as e:
        logger.error(f"Error analyzing file {filepath}: {e}")
        # Optionally report this failure
        issues.append({
            "type": "Analysis Error", 
            "file": filepath, 
            "line": 0, 
            "description": f"Could not analyze file: {e}", 
            "code_snippet": "# Analysis Failed"
        })
    return issues


# --- Main Analyzer Function (Unchanged - relies on restored helpers) ---

def analyze_repository(repo_name, github_token):
    temp_dir = tempfile.mkdtemp()
    clone_url = f"https://oauth2:{github_token}@github.com/{repo_name}.git"
    
    try:
        Repo.clone_from(clone_url, temp_dir, depth=1)
        
        detected_version = detect_python_version(temp_dir)
        req_path = os.path.join(temp_dir, 'requirements.txt')
        dependencies = parse_pinned_requirements(req_path)
        dependency_report = check_osv_for_vulnerabilities(dependencies)
        
        syntax_issues = []
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, temp_dir)
                    issues = analyze_python_file(file_path) # Use restored function
                    for issue in issues:
                        issue['file'] = relative_path # Update path to be relative
                    syntax_issues.extend(issues)

        raw_report_data = { 
            "repoName": repo_name, 
            "pythonVersion": detected_version, 
            "dependencies": dependency_report, 
            "syntaxIssues": syntax_issues 
        }
        
        ai_generated_content = asyncio.run(ai_service.generate_report_summary_and_steps(raw_report_data))

        risk_score = min(len(dependency_report) * 25 + len(syntax_issues) * 10, 95)
        if not dependency_report and not syntax_issues: 
            risk_score = 0
            
        final_report = {
            "repoName": repo_name, 
            "pythonVersion": detected_version, 
            "riskScore": risk_score,
            "summary": ai_generated_content.get("summary", "AI summary generation failed."), 
            "dependencies": dependency_report, 
            "syntaxIssues": syntax_issues,
            "recommendations": { 
                "targetVersion": "Python 3.11+", 
                "estimatedEffort": ai_generated_content.get("effort", "Medium"), 
                "steps": ai_generated_content.get("steps", ["Review findings and prioritize fixes."]) 
            }
        }
        return final_report

    finally:
        if os.path.exists(temp_dir): 
            shutil.rmtree(temp_dir)

# --- Save Report Function (Unchanged) ---
def save_scan_report(db: Session, user_id: int, repo_name: str, report_data: dict):
    """Saves a completed scan report to the database."""
    new_report = models.ScanReport(
        user_id=user_id,
        repo_name=repo_name,
        report_data=report_data
    )
    db.add(new_report)
    db.commit()

