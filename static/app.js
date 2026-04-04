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
const calorieRing = document.getElementById('calorie-ring');
const caloriesRemaining = document.getElementById('calories-remaining');
const caloriesConsumed = document.getElementById('calories-consumed');
const calorieGoalDisplay = document.getElementById('calorie-goal-display');
const mealCountNum = document.getElementById('meal-count-num');

// State
let parsedMeals = [];
let conflictMealIndex = -1;
let isProcessing = false;
let calorieGoal = parseInt(localStorage.getItem('calorieGoal') || '2000');

// Ring constants
const RING_CIRCUMFERENCE = 2 * Math.PI * 70; // r=70

// Initialize
const today = new Date().toISOString().split('T')[0];
datePicker.value = today;
calorieGoalDisplay.textContent = calorieGoal;
caloriesRemaining.textContent = calorieGoal;
loadMeals(today);

// Make goal display clickable
document.querySelector('.card-calories').addEventListener('click', (e) => {
    if (e.target.closest('.meta-item:last-child') || e.target.closest('.meta-label')) {
        openGoalModal();
    }
});

// Event listeners
submitBtn.addEventListener('click', handleSubmit);
mealInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleSubmit();
});
datePicker.addEventListener('change', () => {
    document.querySelector('.section-title').textContent =
        datePicker.value === today ? "Today's Meals" : `Meals on ${datePicker.value}`;
    loadMeals(datePicker.value);
});

// ---------- Calorie Ring ----------
function updateRing(consumed) {
    const remaining = Math.max(0, calorieGoal - consumed);
    const progress = Math.min(consumed / calorieGoal, 1);
    const offset = RING_CIRCUMFERENCE * (1 - progress);

    calorieRing.style.strokeDasharray = RING_CIRCUMFERENCE;
    calorieRing.style.strokeDashoffset = offset;

    caloriesRemaining.textContent = remaining;
    caloriesConsumed.textContent = consumed;
    calorieGoalDisplay.textContent = calorieGoal;

    // Change ring color based on progress
    if (progress >= 1) {
        calorieRing.style.stroke = '#f87171'; // red — over goal
    } else if (progress >= 0.8) {
        calorieRing.style.stroke = '#fbbf24'; // yellow — getting close
    } else {
        calorieRing.style.stroke = '#7c5cfc'; // accent — normal
    }
}

// ---------- Goal Modal ----------
function openGoalModal() {
    document.getElementById('goal-modal').classList.remove('hidden');
    const goalInput = document.getElementById('goal-input');
    goalInput.value = calorieGoal;
    goalInput.focus();
    goalInput.select();
}

function closeGoalModal() {
    document.getElementById('goal-modal').classList.add('hidden');
}

function saveGoal() {
    const goalInput = document.getElementById('goal-input');
    const val = parseInt(goalInput.value);
    if (val && val >= 500 && val <= 10000) {
        calorieGoal = val;
        localStorage.setItem('calorieGoal', val);
        closeGoalModal();
        loadMeals(datePicker.value); // Refresh ring
    }
}

// Close modal on Escape or clicking overlay
document.getElementById('goal-modal').addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) closeGoalModal();
});
document.getElementById('goal-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') saveGoal();
    if (e.key === 'Escape') closeGoalModal();
});

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
        mealInput.value = event.results[0][0].transcript;
    };

    recognition.onend = () => {
        micBtn.classList.remove('listening');
        micStatus.classList.add('hidden');
    };

    recognition.onerror = (event) => {
        micBtn.classList.remove('listening');
        micStatus.classList.add('hidden');
        if (event.error !== 'no-speech') showError(`Mic error: ${event.error}`);
    };

    micBtn.addEventListener('click', () => {
        micBtn.classList.contains('listening') ? recognition.stop() : recognition.start();
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
function renderMealCard(meal) {
    let sourcesHtml = '';
    if (meal.sources && meal.sources.length > 0) {
        const sourceItems = meal.sources.map(s => {
            if (s.startsWith('http')) {
                const domain = s.replace(/^https?:\/\//, '').split('/')[0];
                return `<a href="${escapeHtml(s)}" target="_blank" rel="noopener">${escapeHtml(domain)}</a>`;
            }
            return escapeHtml(s);
        }).join(', ');
        sourcesHtml = `<div class="rationale-sources"><span class="label">Sources:</span> ${sourceItems}</div>`;
    }

    let rationaleHtml = '';
    if (meal.calorie_breakdown || meal.rationale) {
        rationaleHtml = `
            <div class="rationale-section">
                ${meal.calorie_breakdown ? `<div class="calorie-breakdown">${escapeHtml(meal.calorie_breakdown)}</div>` : ''}
                ${meal.rationale ? `<div class="rationale-text">${escapeHtml(meal.rationale)}</div>` : ''}
                ${sourcesHtml}
            </div>
        `;
    }

    return `
        <div class="parsed-meal-card">
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
            ${rationaleHtml}
        </div>
    `;
}

function showConfirmation(meals) {
    const count = meals.length;
    const header = count > 1
        ? `<p class="header-text">Found ${count} meals to log</p>`
        : `<p class="header-text">Ready to log</p>`;

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
            <p class="header-text">Need more details</p>
            <div class="row">
                <span class="label">Understood</span>
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
            <p class="header-text">Duplicate detected</p>
            <div class="row">
                <span class="label">Existing</span>
                <span class="value">${escapeHtml(existing.food_description)} (${existing.calories} cal)</span>
            </div>
            <div class="row">
                <span class="label">Time</span>
                <span class="value">${existing.meal_time}</span>
            </div>
            <hr class="conflict-divider">
            <div class="row">
                <span class="label">New</span>
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
                setProcessing(false);
                showConflict(data, meal, i);
                return;
            }

            if (!res.ok) throw new Error(data.detail || `Failed to save: ${meal.food_description}`);
        }

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
            if (!res.ok) throw new Error(data.detail || `Failed to save: ${meal.food_description}`);
        }

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
    mealInput.value = `${originalText} — clarification: ${clarification}`;
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

        // Update ring and stats
        updateRing(summaryData.total_calories);
        mealCountNum.textContent = summaryData.meal_count;

        if (mealsData.meals.length === 0) {
            mealsList.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">
                        <svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path d="M18 8h1a4 4 0 0 1 0 8h-1"/>
                            <path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/>
                            <line x1="6" y1="1" x2="6" y2="4"/>
                            <line x1="10" y1="1" x2="10" y2="4"/>
                            <line x1="14" y1="1" x2="14" y2="4"/>
                        </svg>
                    </div>
                    <p>No meals logged yet</p>
                    <p class="empty-hint">Type or speak what you ate above</p>
                </div>
            `;
            return;
        }

        mealsList.innerHTML = mealsData.meals.map(meal => `
            <div class="meal-card">
                <div class="meal-time-badge">${meal.meal_time}</div>
                <div class="meal-info">
                    <div class="meal-desc">${escapeHtml(meal.food_description)}</div>
                </div>
                <div class="meal-cal">${meal.calories}</div>
                <button class="delete-btn" onclick="deleteMeal(${meal.id})" title="Delete">&times;</button>
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
        if (res.ok) loadMeals(datePicker.value);
    } catch (err) {
        showError('Failed to delete meal');
    }
}

// ---------- Helpers ----------
function setProcessing(state) {
    isProcessing = state;
    submitBtn.disabled = state;
    if (state) {
        submitBtn.innerHTML = '<span class="spinner"></span>';
    } else {
        submitBtn.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>`;
    }
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
