from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import database
from models import ParseMealRequest, CreateMealRequest, UpdateMealRequest, CreateChatRequest, ChatMessageRequest
from calorie_service import parse_meal
from chat_service import chat_with_guru


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="Fitness Meal Tracker", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/meals/parse")
async def parse_meal_endpoint(req: ParseMealRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    try:
        meals = await parse_meal(req.text, current_date, current_time)
        return {"meals": [m.model_dump() for m in meals], "raw_input": req.text}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse meal: {str(e)}")


@app.post("/api/meals")
async def create_meal(req: CreateMealRequest):
    # Check for conflicts
    conflict = database.find_conflict(req.meal_date, req.meal_time)

    if conflict and not req.force:
        return JSONResponse(
            status_code=409,
            content={
                "conflict": True,
                "existing_meal": conflict,
                "message": f"A meal is already logged near {conflict['meal_time']} on {conflict['meal_date']}: \"{conflict['food_description']}\" ({conflict['calories']} cal). Replace it or ignore?",
            },
        )

    nutrition = req.nutrition.model_dump() if req.nutrition else None

    if conflict and req.force:
        updated = database.update_meal(
            conflict["id"],
            req.food_description,
            req.calories,
            req.meal_date,
            req.meal_time,
            req.raw_input,
            nutrition,
        )
        return {"message": "Meal replaced successfully", "meal": updated}

    # No conflict — insert new
    meal = database.insert_meal(
        req.food_description,
        req.calories,
        req.meal_date,
        req.meal_time,
        req.raw_input,
        nutrition,
    )
    return JSONResponse(status_code=201, content={"message": "Meal logged successfully", "meal": meal})


@app.get("/api/meals")
async def get_meals(date: str = None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    meals = database.get_meals_by_date(date)
    summary = database.get_daily_summary(date)
    return {"date": date, "meals": meals, **summary}


@app.get("/api/meals/summary")
async def get_summary(date: str = None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    summary = database.get_daily_summary(date)
    return {"date": date, **summary}


@app.delete("/api/meals/{meal_id}")
async def delete_meal_endpoint(meal_id: int):
    success = database.delete_meal(meal_id)
    if not success:
        raise HTTPException(status_code=404, detail="Meal not found")
    return {"message": "Meal deleted successfully"}


@app.put("/api/meals/{meal_id}")
async def update_meal_endpoint(meal_id: int, req: UpdateMealRequest):
    existing = database.get_meal_by_id(meal_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Meal not found")

    nutrition = req.nutrition.model_dump() if req.nutrition else None
    updated = database.update_meal(
        meal_id,
        req.food_description,
        req.calories,
        req.meal_date,
        req.meal_time,
        req.raw_input,
        nutrition,
    )
    return {"message": "Meal updated successfully", "meal": updated}


# ===== Chat endpoints =====

@app.post("/api/chats")
async def create_chat_endpoint(req: CreateChatRequest):
    chat = database.create_chat(req.title)
    return JSONResponse(status_code=201, content=chat)


@app.get("/api/chats")
async def list_chats_endpoint():
    return {"chats": database.list_chats()}


@app.get("/api/chats/{chat_id}/messages")
async def get_chat_messages_endpoint(chat_id: int):
    chat = database.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = database.get_chat_messages(chat_id)
    return {"chat": chat, "messages": messages}


@app.post("/api/chats/{chat_id}/messages")
async def send_chat_message_endpoint(chat_id: int, req: ChatMessageRequest):
    chat = database.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        reply = await chat_with_guru(chat_id, req.message)
        updated_chat = database.get_chat(chat_id)
        return {"reply": reply, "chat": updated_chat}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.delete("/api/chats/{chat_id}")
async def delete_chat_endpoint(chat_id: int):
    success = database.delete_chat(chat_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"message": "Chat deleted successfully"}
