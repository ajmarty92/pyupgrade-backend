import os
import json
import re
import textwrap
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables.")
genai.configure(api_key=GEMINI_API_KEY)

code_generation_model = genai.GenerativeModel('gemini-1.5-flash')
report_generation_model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})

REPORT_SUMMARY_PROMPT = textwrap.dedent("""
    You are a senior software architect. Analyze the following Python project scan report:
    {report_data}

    Your task is to:
    1. Provide a concise executive summary of the project's technical debt and security posture.
    2. Estimate the effort required to modernize the project (Low, Medium, High).
    3. List step-by-step actions to address the identified issues (dependencies and syntax).

    Output the result as a JSON object with the following keys:
    - "summary": string
    - "effort": string
    - "steps": list of strings
    """)

async def generate_code_fix(code_snippet: str, issue_type: str, file_path: str, line: int) -> str:
    """Generates a fix for a specific code issue using Gemini."""
    prompt = f"""
    You are an expert Python developer. A code issue has been identified in the following file.
    File: {file_path}
    Line: {line}
    Issue: {issue_type}

    The problematic code snippet is:
    ```python
    {code_snippet}
    ```

    Your task is to provide a corrected version of this code snippet that fixes the issue while preserving the original logic.
    Output ONLY the corrected Python code, without any markdown formatting or explanations.
    """
    response = await code_generation_model.generate_content_async(prompt)
    return response.text.strip()

async def generate_report_summary_and_steps(report_data: dict) -> dict:
    """Generates a summary and modernization steps based on the scan report."""
    prompt = REPORT_SUMMARY_PROMPT.format(report_data=report_data)

    try:
        response = await report_generation_model.generate_content_async(prompt)
        response_text = response.text.strip()

        # Strip Markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = re.sub(r"^```json\s*", "", response_text)
            response_text = re.sub(r"\s*```$", "", response_text)
        elif response_text.startswith("```"):
            response_text = re.sub(r"^```\s*", "", response_text)
            response_text = re.sub(r"\s*```$", "", response_text)

        return json.loads(response_text)
    except Exception:
        # Fallback if API fails or JSON parsing fails
        return {
            "summary": "Analysis completed, but structured output failed.",
            "effort": "Unknown",
            "steps": ["Review report manually."]
        }

async def modernize_code_snippet(code_snippet: str) -> str:
    """Modernizes a Python code snippet to Python 3.11+ standards."""
    prompt = f"""
    You are an expert Python developer. Your task is to modernize the following Python code snippet to follow Python 3.11+ best practices and syntax.

    Original Code:
    ```python
    {code_snippet}
    ```

    Instructions:
    - Update deprecated syntax (e.g., print statements, old-style classes).
    - Use modern features like f-strings, type hinting, and new standard library modules where appropriate.
    - Preserve the original logic.
    - Output ONLY the modernized Python code, without any markdown formatting or explanations.
    """
    response = await code_generation_model.generate_content_async(prompt)
    return response.text.strip()

# --- NEW AI FUNCTIONS ---

async def generate_pr_description(old_code: str, new_code: str, issue_type: str, file_path: str) -> dict:
    """Generates a PR title and body for an automated code fix."""
    system_instruction = """
    You are a helpful engineering assistant. Based on the provided code diff, generate a concise, conventional commit-style PR title and a brief, professional markdown body.
    The output must be a JSON object with two keys: "title" and "body".
    Example title format: "refactor(scanner): Modernize deprecated syntax"
    """
    prompt = f"""
    A file was changed to fix a deprecated syntax issue.
    File: {file_path}
    Issue Type: {issue_type}
    --- OLD CODE ---
    {old_code}
    --- NEW CODE ---
    {new_code}
    """
    response = await report_generation_model.generate_content_async([system_instruction, prompt])
    return response.text

async def generate_unit_tests(old_code: str, new_code: str) -> str:
    """Generates pytest unit tests to verify the behavior of a code change."""
    prompt = f"""
    As a senior testing engineer, your task is to write unit tests using the `pytest` framework to validate a code refactoring.
    
    Here is the original, deprecated code snippet:
    ```python
    {old_code}
    ```

    Here is the new, modernized code snippet:
    ```python
    {new_code}
    ```

    Your instructions:
    1. Write one or more `pytest` functions to test the behavior of the code.
    2. Crucially, ensure your tests would pass for *both* the old and new code snippets to verify that the refactoring did not change the core logic.
    3. Provide only the Python code for the tests, with no explanations or markdown formatting.
    """
    response = await code_generation_model.generate_content_async(prompt)
    return response.text.strip()

async def generate_strategic_summary(scan_reports: list[dict]) -> str:
    """Generates a high-level strategic summary based on multiple scan reports."""
    prompt = f"""
    As a CTO, analyze the following list of Python project scan reports. Each report summarizes the technical debt and security risks for a repository.

    Scan data:
    {scan_reports}

    Your task is to synthesize this information into a single, concise executive summary (2-3 paragraphs).
    - Identify the most critical, recurring risks across the portfolio.
    - Highlight which projects or types of issues require the most urgent attention.
    - Frame the analysis in terms of business impact (e.g., security exposure, development slowdown).
    - The output should be a professional, well-formatted markdown string.
    """
    response = await code_generation_model.generate_content_async(prompt)
    return response.text.strip()
