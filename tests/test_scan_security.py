import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException
import main
import models
import schemas

@pytest.mark.asyncio
async def test_get_scan_status_success():
    """Test access to own scan status."""
    task_id = "task-123"
    current_user = MagicMock(spec=models.User)
    current_user.id = 1

    # Mock DB returning a report owned by current_user
    mock_report = MagicMock(spec=models.ScanReport)
    mock_report.user_id = 1
    mock_report.task_id = task_id

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_report

    # Mock Celery AsyncResult
    with patch("main.AsyncResult") as MockAsyncResult:
        mock_result = MockAsyncResult.return_value
        mock_result.failed.return_value = False
        mock_result.ready.return_value = True
        mock_result.get.return_value = {"status": "done"}

        response = await main.get_scan_status(task_id, current_user=current_user, db=mock_db)
        assert response["status"] == "SUCCESS"
        assert response["result"] == {"status": "done"}

@pytest.mark.asyncio
async def test_get_scan_status_forbidden():
    """Test access denied for another user's scan."""
    task_id = "task-123"
    current_user = MagicMock(spec=models.User)
    current_user.id = 1

    # Mock DB returning a report owned by OTHER user
    mock_report = MagicMock(spec=models.ScanReport)
    mock_report.user_id = 2 # Different ID
    mock_report.task_id = task_id

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_report

    with pytest.raises(HTTPException) as exc:
        await main.get_scan_status(task_id, current_user=current_user, db=mock_db)
    assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_get_scan_status_not_found():
    """Test 404 for non-existent scan."""
    task_id = "task-123"
    current_user = MagicMock(spec=models.User)
    current_user.id = 1

    mock_db = MagicMock()
    # Return None
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        await main.get_scan_status(task_id, current_user=current_user, db=mock_db)
    assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_start_scan_creates_db_record():
    """Test that starting a scan creates a DB record with task_id."""
    repo_data = schemas.RepoScanRequest(repo_name="test/repo")
    current_user = MagicMock(spec=models.User)
    current_user.id = 1
    current_user.github_access_token = "encrypted_token"

    mock_db = MagicMock()

    with patch("main.security.decrypt_data", return_value="token"), \
         patch("main.auth.verify_repo_permission", new_callable=AsyncMock), \
         patch("main.run_repository_scan.delay") as mock_delay:

        mock_delay.return_value.id = "task-123"

        await main.start_scan(repo_data, current_user=current_user, db=mock_db)

        # Verify DB add was called
        mock_db.add.assert_called_once()
        args = mock_db.add.call_args[0]
        report = args[0]
        assert isinstance(report, models.ScanReport)
        assert report.task_id == "task-123"
        assert report.repo_name == "test/repo"
        assert report.user_id == 1
        assert report.report_data == {"status": "pending"}
