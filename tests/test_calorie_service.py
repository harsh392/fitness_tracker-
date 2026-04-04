import os
import sys
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

os.environ["OPENROUTER_API_KEY"] = "test-key"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calorie_service import parse_meal, SYSTEM_PROMPT


class TestPromptDesign:
    def test_system_prompt_includes_date_placeholder(self):
        assert "{current_date}" in SYSTEM_PROMPT
        assert "{current_time}" in SYSTEM_PROMPT

    def test_system_prompt_includes_key_instructions(self):
        assert "needs_clarification" in SYSTEM_PROMPT
        assert "calories" in SYSTEM_PROMPT
        assert "JSON" in SYSTEM_PROMPT


class TestParseMeal:
    @pytest.mark.asyncio
    @patch("calorie_service.httpx.AsyncClient")
    async def test_parse_specific_meal(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "food_description": "2 scrambled eggs and 1 slice of toast",
                        "calories": 350,
                        "meal_date": "2026-04-04",
                        "meal_time": "08:00",
                        "confidence": "high",
                        "needs_clarification": False,
                        "clarification_question": None,
                    })
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await parse_meal("I had 2 eggs and toast for breakfast", "2026-04-04", "10:00")

        assert result.food_description == "2 scrambled eggs and 1 slice of toast"
        assert result.calories == 350
        assert result.confidence == "high"
        assert result.needs_clarification is False

    @pytest.mark.asyncio
    @patch("calorie_service.httpx.AsyncClient")
    async def test_parse_vague_meal(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "food_description": "unknown food",
                        "calories": 0,
                        "meal_date": "2026-04-04",
                        "meal_time": "10:00",
                        "confidence": "low",
                        "needs_clarification": True,
                        "clarification_question": "Could you describe what you ate in more detail?",
                    })
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await parse_meal("I ate something", "2026-04-04", "10:00")

        assert result.needs_clarification is True
        assert result.clarification_question is not None
        assert result.confidence == "low"

    @pytest.mark.asyncio
    async def test_missing_api_key(self):
        import calorie_service
        original_key = calorie_service.OPENROUTER_API_KEY
        calorie_service.OPENROUTER_API_KEY = ""
        try:
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                await parse_meal("eggs", "2026-04-04", "10:00")
        finally:
            calorie_service.OPENROUTER_API_KEY = original_key
