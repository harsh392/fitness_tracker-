import os
import sys
import pytest

# Use in-memory database for tests
os.environ["DB_PATH"] = ":memory:"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import database


@pytest.fixture(autouse=True)
def setup_db():
    """Re-initialize the database before each test."""
    database.DB_PATH = ":memory:"
    database._shared_conn = None  # Reset shared connection for fresh DB
    database.init_db()
    yield


class TestInsertAndRetrieve:
    def test_insert_meal(self):
        meal = database.insert_meal("2 eggs and toast", 350, "2026-04-04", "08:00", "I had 2 eggs and toast for breakfast")
        assert meal["id"] is not None
        assert meal["food_description"] == "2 eggs and toast"
        assert meal["calories"] == 350
        assert meal["meal_date"] == "2026-04-04"
        assert meal["meal_time"] == "08:00"

    def test_get_meals_by_date(self):
        database.insert_meal("eggs", 200, "2026-04-04", "08:00")
        database.insert_meal("sandwich", 450, "2026-04-04", "12:00")
        database.insert_meal("pizza", 600, "2026-04-05", "19:00")

        meals = database.get_meals_by_date("2026-04-04")
        assert len(meals) == 2
        assert meals[0]["meal_time"] == "08:00"  # Sorted by time
        assert meals[1]["meal_time"] == "12:00"

    def test_get_meals_empty_date(self):
        meals = database.get_meals_by_date("2099-01-01")
        assert meals == []


class TestDailySummary:
    def test_summary_with_meals(self):
        database.insert_meal("eggs", 200, "2026-04-04", "08:00")
        database.insert_meal("sandwich", 450, "2026-04-04", "12:00")

        summary = database.get_daily_summary("2026-04-04")
        assert summary["meal_count"] == 2
        assert summary["total_calories"] == 650

    def test_summary_empty(self):
        summary = database.get_daily_summary("2099-01-01")
        assert summary["meal_count"] == 0
        assert summary["total_calories"] == 0


class TestConflictDetection:
    def test_find_conflict_exact_time(self):
        database.insert_meal("eggs", 200, "2026-04-04", "08:00")
        conflict = database.find_conflict("2026-04-04", "08:00")
        assert conflict is not None
        assert conflict["food_description"] == "eggs"

    def test_find_conflict_within_window(self):
        database.insert_meal("eggs", 200, "2026-04-04", "08:00")
        conflict = database.find_conflict("2026-04-04", "08:25")
        assert conflict is not None

    def test_no_conflict_outside_window(self):
        database.insert_meal("eggs", 200, "2026-04-04", "08:00")
        conflict = database.find_conflict("2026-04-04", "09:00")
        assert conflict is None

    def test_no_conflict_different_date(self):
        database.insert_meal("eggs", 200, "2026-04-04", "08:00")
        conflict = database.find_conflict("2026-04-05", "08:00")
        assert conflict is None


class TestDeleteAndUpdate:
    def test_delete_meal(self):
        meal = database.insert_meal("eggs", 200, "2026-04-04", "08:00")
        assert database.delete_meal(meal["id"]) is True
        assert database.get_meals_by_date("2026-04-04") == []

    def test_delete_nonexistent(self):
        assert database.delete_meal(999) is False

    def test_update_meal(self):
        meal = database.insert_meal("eggs", 200, "2026-04-04", "08:00")
        updated = database.update_meal(meal["id"], "3 eggs and bacon", 500, "2026-04-04", "08:00")
        assert updated["food_description"] == "3 eggs and bacon"
        assert updated["calories"] == 500

    def test_get_meal_by_id(self):
        meal = database.insert_meal("eggs", 200, "2026-04-04", "08:00")
        retrieved = database.get_meal_by_id(meal["id"])
        assert retrieved is not None
        assert retrieved["food_description"] == "eggs"

    def test_get_nonexistent_meal(self):
        assert database.get_meal_by_id(999) is None
