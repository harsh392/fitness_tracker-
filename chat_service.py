import json
import os
from datetime import datetime, timedelta

import httpx

import database

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-4-maverick:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

GURU_SYSTEM_PROMPT = """You are a friendly, knowledgeable fitness and nutrition guru. Your name is "Coach".

You have access to the user's complete meal tracking data which is provided below. Use this data to give personalized, specific advice.

When the user asks about their eating patterns, calorie intake, nutrition, or fitness goals:
- Reference their ACTUAL data with specific numbers, dates, and meals
- Be encouraging but honest
- Give actionable, practical advice
- If they mention being on a "cut" (caloric deficit), "bulk" (caloric surplus), or "maintenance", evaluate their data against that goal
- Calculate averages, trends, and totals when asked
- Point out nutritional gaps (low protein, missing vitamins, etc.)
- Keep responses concise but helpful — don't write essays

Current date: {current_date}

=== USER'S MEAL DATA (Last 30 days) ===
{meal_data}

=== DAILY SUMMARIES ===
{daily_summaries}
"""


def _build_meal_context() -> tuple[str, str]:
    """Build meal data context for the last 30 days."""
    today = datetime.now()
    start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    meals = database.get_meals_date_range(start, end)

    if not meals:
        return "No meals logged yet.", "No data available."

    # Build meal list
    meal_lines = []
    for m in meals:
        nutrition_str = ""
        if m.get("nutrition"):
            n = m["nutrition"]
            nutrition_str = f" | P:{n.get('protein',0)}g C:{n.get('carbs',0)}g F:{n.get('fat',0)}g"
        meal_lines.append(
            f"- {m['meal_date']} {m['meal_time']}: {m['food_description']} ({m['calories']} cal{nutrition_str})"
        )
    meal_data = "\n".join(meal_lines)

    # Build daily summaries
    daily = {}
    for m in meals:
        d = m["meal_date"]
        if d not in daily:
            daily[d] = {"calories": 0, "meals": 0, "protein": 0, "carbs": 0, "fat": 0}
        daily[d]["calories"] += m["calories"]
        daily[d]["meals"] += 1
        if m.get("nutrition"):
            n = m["nutrition"]
            daily[d]["protein"] += float(n.get("protein", 0))
            daily[d]["carbs"] += float(n.get("carbs", 0))
            daily[d]["fat"] += float(n.get("fat", 0))

    summary_lines = []
    for d in sorted(daily.keys()):
        s = daily[d]
        summary_lines.append(
            f"- {d}: {s['calories']} cal, {s['meals']} meals, P:{s['protein']:.0f}g C:{s['carbs']:.0f}g F:{s['fat']:.0f}g"
        )
    daily_summaries = "\n".join(summary_lines)

    return meal_data, daily_summaries


async def chat_with_guru(chat_id: int, user_message: str) -> str:
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY environment variable is not set.")

    # Save user message
    database.add_chat_message(chat_id, "user", user_message)

    # Build context
    meal_data, daily_summaries = _build_meal_context()
    current_date = datetime.now().strftime("%Y-%m-%d")

    system_msg = GURU_SYSTEM_PROMPT.format(
        current_date=current_date,
        meal_data=meal_data,
        daily_summaries=daily_summaries,
    )

    # Build message history (last 20 messages for context window)
    history = database.get_chat_messages(chat_id)
    messages = [{"role": "system", "content": system_msg}]
    for msg in history[-20:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.6,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Fitness Meal Tracker - Coach",
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        reply = data["choices"][0]["message"]["content"].strip()

    # Save assistant reply
    database.add_chat_message(chat_id, "assistant", reply)

    # Auto-title chat on first message
    chat = database.get_chat(chat_id)
    if chat and chat["title"] == "New Chat":
        # Use first ~40 chars of user message as title
        title = user_message[:40].strip()
        if len(user_message) > 40:
            title += "..."
        database.update_chat_title(chat_id, title)

    return reply
