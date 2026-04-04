from pydantic import BaseModel


class ParseMealRequest(BaseModel):
    text: str


class ParsedMeal(BaseModel):
    food_description: str
    calories: int
    meal_date: str
    meal_time: str
    confidence: str  # "high" | "medium" | "low"
    needs_clarification: bool
    clarification_question: str | None = None
    raw_input: str


class CreateMealRequest(BaseModel):
    food_description: str
    calories: int
    meal_date: str
    meal_time: str
    raw_input: str = ""
    force: bool = False  # If True, replace existing duplicate


class UpdateMealRequest(BaseModel):
    food_description: str
    calories: int
    meal_date: str
    meal_time: str
    raw_input: str = ""


class ParseMealResponse(BaseModel):
    meals: list[ParsedMeal]
    raw_input: str
