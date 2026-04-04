import json
import os
import httpx
from models import ParsedMeal

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-4-maverick:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are a nutrition assistant. The user will describe one or more meals in natural language.
Your job is to extract structured information and estimate calories for EACH meal mentioned.

The user may describe multiple meals in a single message (e.g., "I had eggs for breakfast and a sandwich for lunch").
You must return a JSON object with a "meals" array containing one entry per distinct meal.

Each meal object must have:
1. food_description: A clean, normalized description of what was eaten
2. calories: Your best estimate of total calories (integer)
3. meal_date: The date of the meal in ISO format YYYY-MM-DD. The current date is {current_date}.
4. meal_time: The time of the meal in HH:MM 24-hour format. The current time is {current_time}.
5. confidence: "high" if quantities and foods are specific, "medium" if reasonable assumptions were made, "low" if very vague
6. needs_clarification: true if the input is too vague to give a reasonable estimate
7. clarification_question: If needs_clarification is true, ask a specific question to get the missing information. Otherwise null.

Rules:
- If no time is mentioned, use the current time.
- If no date is mentioned, use the current date.
- If "yesterday" is mentioned, subtract one day from the current date.
- "same day" or "that day" refers to the most recently mentioned date.
- If "lunch" or "afternoon" is mentioned without a time, use 12:00. "breakfast" or "morning" -> 08:00. "dinner" or "evening" -> 19:00. "snack" -> 15:00.
- For calorie estimation, use standard serving sizes when quantity is not specified (e.g., "toast" = 1 slice ≈ 80 cal). Set confidence to "medium" in this case.
- Only set needs_clarification to true when the input is genuinely too vague (e.g., "I ate something", "had a big meal", "ate food").
- Be generous with interpretation. "Had a burger" is fine — assume a standard burger (~450 cal). Only ask for clarification when you truly cannot determine what was eaten.
- Even if the user describes only one meal, still wrap it in the "meals" array.

Respond with ONLY valid JSON in this format: {{"meals": [...]}}
No markdown, no code fences, no explanation. Just the JSON object."""


async def parse_meal(text: str, current_date: str, current_time: str) -> list[ParsedMeal]:
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY environment variable is not set. Please set it in your .env file.")

    system_msg = SYSTEM_PROMPT.format(current_date=current_date, current_time=current_time)

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Fitness Meal Tracker",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # Strip any markdown code fences the model might add despite instructions
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # Retry once asking for valid JSON
            payload["messages"].append({"role": "assistant", "content": content})
            payload["messages"].append({"role": "user", "content": "Please respond with ONLY valid JSON, no other text."})

            response = await client.post(OPENROUTER_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            parsed = json.loads(content.strip())

        # Handle both formats: {"meals": [...]} or single object (backward compat)
        if "meals" in parsed and isinstance(parsed["meals"], list):
            meal_list = parsed["meals"]
        else:
            meal_list = [parsed]

        return [
            ParsedMeal(
                food_description=m.get("food_description", text),
                calories=int(m.get("calories", 0)),
                meal_date=m.get("meal_date", current_date),
                meal_time=m.get("meal_time", current_time),
                confidence=m.get("confidence", "low"),
                needs_clarification=m.get("needs_clarification", False),
                clarification_question=m.get("clarification_question"),
                raw_input=text,
            )
            for m in meal_list
        ]
