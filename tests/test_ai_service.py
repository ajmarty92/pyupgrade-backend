import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import ai_service

@pytest.mark.asyncio
async def test_generate_code_fix():
    # Mock the client instance within ai_service
    with patch('ai_service.client.aio.models.generate_content', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value.text = "fixed_code"

        result = await ai_service.generate_code_fix("old_code", "issue", "file.py", 10)

        assert result == "fixed_code"
        mock_generate.assert_called_once()

@pytest.mark.asyncio
async def test_generate_report_summary_and_steps():
    with patch('ai_service.client.aio.models.generate_content', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value.text = '{"summary": "test", "effort": "Low", "steps": []}'

        result = await ai_service.generate_report_summary_and_steps({})

        assert result["summary"] == "test"
        assert result["effort"] == "Low"
        mock_generate.assert_called_once()

@pytest.mark.asyncio
async def test_modernize_code_snippet():
    with patch('ai_service.client.aio.models.generate_content', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value.text = "modernized_code"

        result = await ai_service.modernize_code_snippet("old_code")

        assert result == "modernized_code"
        mock_generate.assert_called_once()

@pytest.mark.asyncio
async def test_generate_pr_description():
    with patch('ai_service.client.aio.models.generate_content', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value.text = '{"title": "test_title", "body": "test_body"}'

        result = await ai_service.generate_pr_description("old", "new", "issue", "file.py")

        assert result["title"] == "test_title"
        assert result["body"] == "test_body"
        mock_generate.assert_called_once()

@pytest.mark.asyncio
async def test_generate_unit_tests():
    with patch('ai_service.client.aio.models.generate_content', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value.text = "def test_foo(): pass"

        result = await ai_service.generate_unit_tests("old", "new")

        assert result == "def test_foo(): pass"
        mock_generate.assert_called_once()

@pytest.mark.asyncio
async def test_generate_strategic_summary():
    with patch('ai_service.client.aio.models.generate_content', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value.text = "Strategic summary"

        result = await ai_service.generate_strategic_summary([])

        assert result == "Strategic summary"
        mock_generate.assert_called_once()
