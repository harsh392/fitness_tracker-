from pydantic import BaseModel


class ParseMealRequest(BaseModel):
    text: str


class NutritionData(BaseModel):
    protein: float = 0  # grams
    carbs: float = 0
    fat: float = 0
    fiber: float = 0
    sodium: float = 0  # mg
    iron: float = 0  # mg
    calcium: float = 0  # mg
    vitamin_a: float = 0  # mcg
    vitamin_c: float = 0  # mg
    vitamin_d: float = 0  # mcg
    potassium: float = 0  # mg


class ParsedMeal(BaseModel):
    food_description: str
    calories: int
    meal_date: str
    meal_time: str
    confidence: str  # "high" | "medium" | "low"
    needs_clarification: bool
    clarification_question: str | None = None
    calorie_breakdown: str | None = None
    rationale: str | None = None
    sources: list[str] | None = None
    nutrition: NutritionData | None = None
    raw_input: str


class CreateMealRequest(BaseModel):
    food_description: str
    calories: int
    meal_date: str
    meal_time: str
    raw_input: str = ""
    force: bool = False
    nutrition: NutritionData | None = None


class UpdateMealRequest(BaseModel):
    food_description: str
    calories: int
    meal_date: str
    meal_time: str
    raw_input: str = ""
    nutrition: NutritionData | None = None


class ParseMealResponse(BaseModel):
    meals: list[ParsedMeal]
    raw_input: str


class CreateChatRequest(BaseModel):
    title: str = "New Chat"


class ChatMessageRequest(BaseModel):
    message: str
