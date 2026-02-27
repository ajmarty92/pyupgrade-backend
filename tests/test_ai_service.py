import pytest
from unittest.mock import AsyncMock, patch
import ai_service

@pytest.mark.asyncio
async def test_generate_code_fix():
    with patch('ai_service.code_generation_model.generate_content_async', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value.text = "fixed_code"

        result = await ai_service.generate_code_fix("old_code", "issue", "file.py", 10)

        assert result == "fixed_code"
        mock_generate.assert_called_once()

@pytest.mark.asyncio
async def test_generate_report_summary_and_steps():
    with patch('ai_service.report_generation_model.generate_content_async', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value.text = '{"summary": "test", "effort": "Low", "steps": []}'

        result = await ai_service.generate_report_summary_and_steps({})

        assert result["summary"] == "test"
        assert result["effort"] == "Low"
        mock_generate.assert_called_once()

@pytest.mark.asyncio
async def test_modernize_code_snippet():
    with patch('ai_service.code_generation_model.generate_content_async', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value.text = "modernized_code"

        result = await ai_service.modernize_code_snippet("old_code")

        assert result == "modernized_code"
        mock_generate.assert_called_once()
