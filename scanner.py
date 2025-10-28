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

# This function is now responsible for saving the report
def save_scan_report(db: Session, user_id: int, repo_name: str, report_data: dict):
    """Saves a completed scan report to the database."""
    new_report = models.ScanReport(
        user_id=user_id,
        repo_name=repo_name,
        report_data=report_data
    )
    db.add(new_report)
    db.commit()

# The core analysis logic is now fully synchronous
def analyze_repository(repo_name, github_token):
    temp_dir = tempfile.mkdtemp()
    clone_url = f"https://oauth2:{github_token}@github.com/{repo_name}.git"
    
    try:
        Repo.clone_from(clone_url, temp_dir, depth=1)
        
        detected_version = detect_python_version(temp_dir)
        dependencies = parse_pinned_requirements(os.path.join(temp_dir, 'requirements.txt'))
        dependency_report = check_osv_for_vulnerabilities(dependencies)
        
        syntax_issues = []
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, temp_dir)
                    issues = analyze_python_file(file_path)
                    for issue in issues:
                        issue['file'] = relative_path
                    syntax_issues.extend(issues)

        raw_report_data = { "repoName": repo_name, "pythonVersion": detected_version, "dependencies": dependency_report, "syntaxIssues": syntax_issues }
        
        # We must run the async AI function in a new event loop for Celery
        ai_generated_content = asyncio.run(ai_service.generate_report_summary_and_steps(raw_report_data))

        risk_score = min(len(dependency_report) * 25 + len(syntax_issues) * 10, 95)
        if not dependency_report and not syntax_issues: risk_score = 0
            
        return {
            "repoName": repo_name, "pythonVersion": detected_version, "riskScore": risk_score,
            "summary": ai_generated_content["summary"], "dependencies": dependency_report, "syntaxIssues": syntax_issues,
            "recommendations": { "targetVersion": "Python 3.11+", "estimatedEffort": ai_generated_content["effort"], "steps": ai_generated_content["steps"] }
        }
    finally:
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)

# ... (All other helper functions like detect_python_version, parse_pinned_requirements, etc. are unchanged)
def detect_python_version(repo_path: str) -> str: return "Undetermined" # Placeholder
def parse_pinned_requirements(filepath: str) -> list[dict]: return [] # Placeholder
def check_osv_for_vulnerabilities(dependencies: list[dict]) -> list[dict]: return [] # Placeholder
def analyze_python_file(filepath): return [] # Placeholder

