import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

os.environ["DB_PATH"] = ":memory:"
os.environ["OPENROUTER_API_KEY"] = "test-key"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from models import ParsedMeal
from app import app
import database


@pytest.fixture(autouse=True)
def setup_db():
    database.DB_PATH = ":memory:"
    database._shared_conn = None
    database.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def mock_parsed_meal(**overrides):
    defaults = {
        "food_description": "2 eggs and toast",
        "calories": 350,
        "meal_date": "2026-04-04",
        "meal_time": "08:00",
        "confidence": "high",
        "needs_clarification": False,
        "clarification_question": None,
        "calorie_breakdown": "2 large eggs (143 cal each = 286 cal) + 1 slice toast (64 cal) = 350 cal",
        "rationale": "Based on USDA FoodData Central values for large scrambled eggs and standard white toast.",
        "sources": ["USDA FoodData Central"],
        "raw_input": "I had 2 eggs and toast for breakfast",
    }
    defaults.update(overrides)
    return ParsedMeal(**defaults)


class TestParseEndpoint:
    @patch("app.parse_meal", new_callable=AsyncMock)
    def test_parse_meal_success(self, mock_parse, client):
        mock_parse.return_value = [mock_parsed_meal()]
        res = client.post("/api/meals/parse", json={"text": "I had 2 eggs and toast for breakfast"})
        assert res.status_code == 200
        data = res.json()
        assert len(data["meals"]) == 1
        assert data["meals"][0]["food_description"] == "2 eggs and toast"
        assert data["meals"][0]["calories"] == 350

    @patch("app.parse_meal", new_callable=AsyncMock)
    def test_parse_multiple_meals(self, mock_parse, client):
        mock_parse.return_value = [
            mock_parsed_meal(food_description="2 eggs and toast", calories=350, meal_time="08:00"),
            mock_parsed_meal(food_description="chicken sandwich", calories=450, meal_time="12:00"),
        ]
        res = client.post("/api/meals/parse", json={"text": "I had eggs for breakfast and a sandwich for lunch"})
        assert res.status_code == 200
        data = res.json()
        assert len(data["meals"]) == 2
        assert data["meals"][0]["food_description"] == "2 eggs and toast"
        assert data["meals"][1]["food_description"] == "chicken sandwich"

    @patch("app.parse_meal", new_callable=AsyncMock)
    def test_parse_meal_needs_clarification(self, mock_parse, client):
        mock_parse.return_value = [mock_parsed_meal(
            needs_clarification=True,
            clarification_question="What exactly did you eat?",
            confidence="low",
        )]
        res = client.post("/api/meals/parse", json={"text": "I ate something"})
        assert res.status_code == 200
        data = res.json()
        assert data["meals"][0]["needs_clarification"] is True
        assert "What exactly" in data["meals"][0]["clarification_question"]

    def test_parse_empty_text(self, client):
        res = client.post("/api/meals/parse", json={"text": ""})
        assert res.status_code == 400


class TestCreateMealEndpoint:
    def test_create_meal(self, client):
        res = client.post("/api/meals", json={
            "food_description": "2 eggs",
            "calories": 200,
            "meal_date": "2026-04-04",
            "meal_time": "08:00",
            "raw_input": "2 eggs",
        })
        assert res.status_code == 201
        assert res.json()["meal"]["food_description"] == "2 eggs"

    def test_create_meal_conflict(self, client):
        # First meal
        client.post("/api/meals", json={
            "food_description": "eggs",
            "calories": 200,
            "meal_date": "2026-04-04",
            "meal_time": "08:00",
            "raw_input": "eggs",
        })
        # Second meal at nearby time
        res = client.post("/api/meals", json={
            "food_description": "toast",
            "calories": 150,
            "meal_date": "2026-04-04",
            "meal_time": "08:10",
            "raw_input": "toast",
        })
        assert res.status_code == 409
        data = res.json()
        assert data["conflict"] is True

    def test_create_meal_force_replace(self, client):
        client.post("/api/meals", json={
            "food_description": "eggs",
            "calories": 200,
            "meal_date": "2026-04-04",
            "meal_time": "08:00",
            "raw_input": "eggs",
        })
        res = client.post("/api/meals", json={
            "food_description": "eggs and bacon",
            "calories": 400,
            "meal_date": "2026-04-04",
            "meal_time": "08:10",
            "raw_input": "eggs and bacon",
            "force": True,
        })
        assert res.status_code == 200
        assert res.json()["meal"]["food_description"] == "eggs and bacon"


class TestGetMeals:
    def test_get_meals_for_date(self, client):
        client.post("/api/meals", json={
            "food_description": "eggs",
            "calories": 200,
            "meal_date": "2026-04-04",
            "meal_time": "08:00",
        })
        res = client.get("/api/meals?date=2026-04-04")
        assert res.status_code == 200
        assert len(res.json()["meals"]) == 1

    def test_get_summary(self, client):
        client.post("/api/meals", json={
            "food_description": "eggs",
            "calories": 200,
            "meal_date": "2026-04-04",
            "meal_time": "08:00",
        })
        client.post("/api/meals", json={
            "food_description": "sandwich",
            "calories": 450,
            "meal_date": "2026-04-04",
            "meal_time": "12:00",
        })
        res = client.get("/api/meals/summary?date=2026-04-04")
        data = res.json()
        assert data["total_calories"] == 650
        assert data["meal_count"] == 2


class TestDeleteMeal:
    def test_delete_meal(self, client):
        create_res = client.post("/api/meals", json={
            "food_description": "eggs",
            "calories": 200,
            "meal_date": "2026-04-04",
            "meal_time": "08:00",
        })
        meal_id = create_res.json()["meal"]["id"]
        res = client.delete(f"/api/meals/{meal_id}")
        assert res.status_code == 200

    def test_delete_nonexistent(self, client):
        res = client.delete("/api/meals/999")
        assert res.status_code == 404
