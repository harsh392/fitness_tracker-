const mealInput = document.getElementById('meal-input');
const micBtn = document.getElementById('mic-btn');
const micStatus = document.getElementById('mic-status');
const submitBtn = document.getElementById('submit-btn');
const confirmPanel = document.getElementById('confirm-panel');
const confirmContent = document.getElementById('confirm-content');
const confirmActions = document.getElementById('confirm-actions');
const errorPanel = document.getElementById('error-panel');
const errorMessage = document.getElementById('error-message');
const datePicker = document.getElementById('date-picker');
const mealsList = document.getElementById('meals-list');
const totalCalories = document.getElementById('total-calories');
const mealCount = document.getElementById('meal-count');

// State
let parsedMeals = [];       // Array of parsed meals from the API
let conflictMealIndex = -1;  // Index of the meal currently showing a conflict
let isProcessing = false;

// Initialize
const today = new Date().toISOString().split('T')[0];
datePicker.value = today;
loadMeals(today);

// Event listeners
submitBtn.addEventListener('click', handleSubmit);
mealInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleSubmit();
});
datePicker.addEventListener('change', () => loadMeals(datePicker.value));

// ---------- Speech Recognition ----------
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
        micBtn.classList.add('listening');
        micStatus.classList.remove('hidden');
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        mealInput.value = transcript;
    };

    recognition.onend = () => {
        micBtn.classList.remove('listening');
        micStatus.classList.add('hidden');
    };

    recognition.onerror = (event) => {
        micBtn.classList.remove('listening');
        micStatus.classList.add('hidden');
        if (event.error !== 'no-speech') {
            showError(`Microphone error: ${event.error}`);
        }
    };

    micBtn.addEventListener('click', () => {
        if (micBtn.classList.contains('listening')) {
            recognition.stop();
        } else {
            recognition.start();
        }
    });
} else {
    micBtn.style.display = 'none';
}

// ---------- Submit & Parse ----------
async function handleSubmit() {
    const text = mealInput.value.trim();
    if (!text || isProcessing) return;

    setProcessing(true);
    hideError();
    hideConfirm();

    try {
        const res = await fetch('/api/meals/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to parse meal');
        }

        const data = await res.json();
        parsedMeals = data.meals;

        // Check if any meal needs clarification
        const needsClarification = parsedMeals.find(m => m.needs_clarification);
        if (needsClarification) {
            showClarification(needsClarification, data.raw_input);
        } else {
            showConfirmation(parsedMeals);
        }
    } catch (err) {
        showError(err.message);
    } finally {
        setProcessing(false);
    }
}

// ---------- Confirmation Panel ----------
function renderMealCard(meal, index) {
    return `
        <div class="parsed-meal-card" style="padding:12px;background:#f9fafb;border-radius:8px;border:1px solid #f3f4f6;">
            <div class="row">
                <span class="label">Food</span>
                <span class="value">${escapeHtml(meal.food_description)}</span>
            </div>
            <div class="row">
                <span class="label">Calories</span>
                <span class="value calories-value">${meal.calories} cal</span>
            </div>
            <div class="row">
                <span class="label">When</span>
                <span class="value">${meal.meal_date} at ${meal.meal_time}</span>
            </div>
            <div class="row">
                <span class="label">Confidence</span>
                <span class="confidence-badge confidence-${meal.confidence}">${meal.confidence}</span>
            </div>
        </div>
    `;
}

function showConfirmation(meals) {
    const count = meals.length;
    const header = count > 1
        ? `<p style="font-weight:600;margin-bottom:12px;">Found ${count} meals to log:</p>`
        : '';

    confirmContent.innerHTML = `
        <div class="parsed-info">
            ${header}
            <div style="display:grid;gap:10px;">
                ${meals.map((m, i) => renderMealCard(m, i)).join('')}
            </div>
        </div>
    `;

    const btnLabel = count > 1 ? `Confirm All (${count})` : 'Confirm';
    confirmActions.innerHTML = `
        <button class="btn-confirm" onclick="confirmAllMeals(false)">${btnLabel}</button>
        <button class="btn-cancel" onclick="hideConfirm()">Cancel</button>
    `;

    confirmPanel.classList.remove('hidden');
}

function showClarification(meal, rawInput) {
    confirmContent.innerHTML = `
        <div class="parsed-info">
            <div class="row">
                <span class="label">Understood so far</span>
                <span class="value">${escapeHtml(meal.food_description)}</span>
            </div>
        </div>
        <div class="clarification-question">${escapeHtml(meal.clarification_question || 'Could you provide more details about what you ate?')}</div>
        <input type="text" class="clarification-input" id="clarification-input" placeholder="Add more details..." autofocus>
    `;

    confirmActions.innerHTML = `
        <button class="btn-confirm" onclick="submitClarification()">Submit</button>
        <button class="btn-cancel" onclick="hideConfirm()">Cancel</button>
    `;

    confirmPanel.classList.remove('hidden');

    setTimeout(() => {
        const clarInput = document.getElementById('clarification-input');
        if (clarInput) {
            clarInput.focus();
            clarInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') submitClarification();
            });
        }
    }, 50);
}

function showConflict(conflictData, pendingMeal, mealIndex) {
    const existing = conflictData.existing_meal;
    conflictMealIndex = mealIndex;

    confirmContent.innerHTML = `
        <div class="parsed-info">
            <p style="font-weight:600; margin-bottom:8px;">Duplicate detected!</p>
            <div class="row">
                <span class="label">Existing meal</span>
                <span class="value">${escapeHtml(existing.food_description)} (${existing.calories} cal)</span>
            </div>
            <div class="row">
                <span class="label">Time</span>
                <span class="value">${existing.meal_time}</span>
            </div>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:8px 0;">
            <div class="row">
                <span class="label">New meal</span>
                <span class="value">${escapeHtml(pendingMeal.food_description)} (${pendingMeal.calories} cal)</span>
            </div>
        </div>
    `;

    confirmActions.innerHTML = `
        <button class="btn-replace" onclick="resolveConflict(true)">Replace</button>
        <button class="btn-ignore" onclick="resolveConflict(false)">Skip</button>
    `;

    confirmPanel.classList.remove('hidden');
}

// ---------- Confirm / Save All Meals ----------
async function confirmAllMeals(force) {
    if (!parsedMeals.length || isProcessing) return;

    setProcessing(true);

    try {
        for (let i = 0; i < parsedMeals.length; i++) {
            const meal = parsedMeals[i];
            const res = await fetch('/api/meals', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    food_description: meal.food_description,
                    calories: meal.calories,
                    meal_date: meal.meal_date,
                    meal_time: meal.meal_time,
                    raw_input: meal.raw_input,
                    force: force,
                }),
            });

            const data = await res.json();

            if (res.status === 409) {
                // Conflict — pause and show conflict resolution for this meal
                setProcessing(false);
                showConflict(data, meal, i);
                return;
            }

            if (!res.ok) {
                throw new Error(data.detail || `Failed to save meal: ${meal.food_description}`);
            }
        }

        // All saved successfully
        hideConfirm();
        mealInput.value = '';
        parsedMeals = [];
        loadMeals(datePicker.value);
    } catch (err) {
        showError(err.message);
    } finally {
        setProcessing(false);
    }
}

// ---------- Conflict Resolution ----------
async function resolveConflict(replace) {
    if (conflictMealIndex < 0 || isProcessing) return;

    setProcessing(true);

    try {
        if (replace) {
            // Re-send with force=true for the conflicting meal
            const meal = parsedMeals[conflictMealIndex];
            const res = await fetch('/api/meals', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    food_description: meal.food_description,
                    calories: meal.calories,
                    meal_date: meal.meal_date,
                    meal_time: meal.meal_time,
                    raw_input: meal.raw_input,
                    force: true,
                }),
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || 'Failed to replace meal');
            }
        }

        // Continue saving remaining meals after the conflict
        const remaining = parsedMeals.slice(conflictMealIndex + 1);
        conflictMealIndex = -1;

        for (let i = 0; i < remaining.length; i++) {
            const meal = remaining[i];
            const res = await fetch('/api/meals', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    food_description: meal.food_description,
                    calories: meal.calories,
                    meal_date: meal.meal_date,
                    meal_time: meal.meal_time,
                    raw_input: meal.raw_input,
                    force: false,
                }),
            });

            const data = await res.json();

            if (res.status === 409) {
                const globalIndex = parsedMeals.indexOf(meal);
                setProcessing(false);
                showConflict(data, meal, globalIndex);
                return;
            }

            if (!res.ok) {
                throw new Error(data.detail || `Failed to save meal: ${meal.food_description}`);
            }
        }

        // All done
        hideConfirm();
        mealInput.value = '';
        parsedMeals = [];
        loadMeals(datePicker.value);
    } catch (err) {
        showError(err.message);
    } finally {
        setProcessing(false);
    }
}

// ---------- Clarification ----------
async function submitClarification() {
    const clarInput = document.getElementById('clarification-input');
    const clarification = clarInput ? clarInput.value.trim() : '';
    if (!clarification) return;

    const originalText = parsedMeals.length > 0 ? parsedMeals[0].raw_input : mealInput.value;
    const combinedText = `${originalText} — clarification: ${clarification}`;

    mealInput.value = combinedText;
    hideConfirm();
    handleSubmit();
}

// ---------- Load Meals ----------
async function loadMeals(date) {
    try {
        const [mealsRes, summaryRes] = await Promise.all([
            fetch(`/api/meals?date=${date}`),
            fetch(`/api/meals/summary?date=${date}`),
        ]);

        const mealsData = await mealsRes.json();
        const summaryData = await summaryRes.json();

        totalCalories.textContent = `${summaryData.total_calories} cal`;
        mealCount.textContent = `${summaryData.meal_count} meal${summaryData.meal_count !== 1 ? 's' : ''}`;

        if (mealsData.meals.length === 0) {
            mealsList.innerHTML = '<p class="empty-state">No meals logged yet for this day.</p>';
            return;
        }

        mealsList.innerHTML = mealsData.meals.map(meal => `
            <div class="meal-card">
                <div class="meal-info">
                    <div class="meal-time">${meal.meal_time}</div>
                    <div class="meal-desc">${escapeHtml(meal.food_description)}</div>
                </div>
                <div class="meal-cal">${meal.calories} cal</div>
                <button class="delete-btn" onclick="deleteMeal(${meal.id})" title="Delete meal">&times;</button>
            </div>
        `).join('');
    } catch (err) {
        console.error('Failed to load meals:', err);
    }
}

// ---------- Delete Meal ----------
async function deleteMeal(id) {
    try {
        const res = await fetch(`/api/meals/${id}`, { method: 'DELETE' });
        if (res.ok) {
            loadMeals(datePicker.value);
        }
    } catch (err) {
        showError('Failed to delete meal');
    }
}

// ---------- Helpers ----------
function setProcessing(state) {
    isProcessing = state;
    submitBtn.disabled = state;
    submitBtn.innerHTML = state ? '<span class="spinner"></span>Processing...' : 'Log Meal';
}

function showError(msg) {
    errorMessage.textContent = msg;
    errorPanel.classList.remove('hidden');
    setTimeout(() => hideError(), 8000);
}

function hideError() {
    errorPanel.classList.add('hidden');
}

function hideConfirm() {
    confirmPanel.classList.add('hidden');
    confirmContent.innerHTML = '';
    confirmActions.innerHTML = '';
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
