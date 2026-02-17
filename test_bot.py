# test_bot.py
import pytest
from unittest.mock import AsyncMock, patch
import bot
from bot import extract_text_from_comment, check_mr_target_branch

@pytest.mark.asyncio
async def test_extract_text_from_comment():
    """Проверка извлечения текста из ADF-комментария."""
    adf_comment = {
        "content": [
            {
                "content": [
                    {"text": "Hello "},
                    {"text": "world"}
                ]
            }
        ]
    }
    result = extract_text_from_comment(adf_comment)
    assert result == "Hello world"

    result = extract_text_from_comment("plain text")
    assert result == "plain text"

@pytest.mark.asyncio
async def test_check_mr_target_branch():
    """Проверка определения целевой ветки MR через GitLab API."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json.return_value = {"target_branch": "main"}
        mock_get.return_value.__aenter__.return_value = mock_resp

        result = await check_mr_target_branch("https://gitlab.com/group/project/-/merge_requests/123")
        assert result is True

        mock_resp.json.return_value = {"target_branch": "develop"}
        result = await check_mr_target_branch("https://gitlab.com/group/project/-/merge_requests/123")
        assert result is False

@pytest.mark.asyncio
async def test_get_services_from_issue_simple(monkeypatch):
    """Проверка определения сервиса по простому ключевому слову."""
    test_patterns = [
        {"pattern": "fundist", "service": "Fundist"}
    ]
    monkeypatch.setattr(bot, 'SERVICE_PATTERNS', test_patterns)

    issue = {
        "fields": {
            "comment": {
                "comments": [
                    {"body": "Need to deploy fundist service"}
                ]
            }
        }
    }
    services = await bot.get_services_from_issue(issue)
    assert "Fundist" in services

@pytest.mark.asyncio
async def test_get_services_from_issue_branch_based(monkeypatch):
    """Проверка определения сервиса, зависящего от ветки MR."""
    # Устанавливаем TARGET_BRANCH в модуле bot
    monkeypatch.setattr(bot, 'TARGET_BRANCH', 'main')

    # Подменяем конфигурацию сервисов
    test_patterns = [
        {
            "pattern": "gitlab.com/group/backend",
            "branch_based": True,
            "branch_map": {"main": "Cote"},
            "default_service": "Django",
        }
    ]
    monkeypatch.setattr(bot, 'SERVICE_PATTERNS', test_patterns)

    issue = {
        "fields": {
            "comment": {
                "comments": [
                    {"body": "MR: https://gitlab.com/group/backend/-/merge_requests/1"}
                ]
            }
        }
    }

    # Мокаем check_mr_target_branch на True
    async def mock_check_true(*args, **kwargs):
        return True
    monkeypatch.setattr(bot, 'check_mr_target_branch', mock_check_true)

    services = await bot.get_services_from_issue(issue)
    assert "Cote" in services
    assert "Django" not in services

    # Мокаем на False
    async def mock_check_false(*args, **kwargs):
        return False
    monkeypatch.setattr(bot, 'check_mr_target_branch', mock_check_false)

    services = await bot.get_services_from_issue(issue)
    assert "Django" in services
    assert "Cote" not in services