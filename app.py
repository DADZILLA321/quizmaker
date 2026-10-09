"""
Notes -> Quiz  (Flask + Gemini + SQLite)

Flow:
  1. User notes paste karta hai            -> route "/"
  2. Gemini se MCQ banwate hain            -> route "/generate"
  3. User quiz solve karta hai             -> route "/quiz/<id>"
  4. Hum score nikalte hain, DB mein save  -> route "/quiz/<id>/submit"
  5. Result + explanation dikhate hain     -> route "/result/<id>"
  6. Galat sawalon ki practice             -> route "/result/<id>/practice"
  7. Purane results                        -> route "/history"
"""

import json
import os
import re
import sqlite3
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for, abort

load_dotenv()  # .env file se GEMINI_API_KEY padhta hai

# ---------------------------------------------------------------- settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "quizmaker.db")

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
# Pehla model try hota hai, na chale to agle.
MODELS = [m for m in [os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                      "gemini-2.5-flash", "gemini-2.0-flash"] if m]

MIN_CHARS, MAX_CHARS = 50, 12000

app = Flask(__name__)


# ---------------------------------------------------------------- database
def db():
    """Har request ke liye database se naya connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row      # row["column"] se value milti hai
    return conn


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            answers_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)


init_db()


def now():
    return datetime.now().strftime("%d %b %Y, %I:%M %p")


# ---------------------------------------------------------------- Gemini
def ask_gemini(prompt):
    """Prompt bhejo, text jawab wapas lo."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=API_KEY)
    last_error = None
    for model in MODELS:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",  # sirf JSON do
                    temperature=0.4,
                ),
            )
            if resp.text:
                return resp.text
        except Exception as e:                # model nahi mila / busy / etc.
            last_error = e
            print(f"[gemini] {model} failed: {str(e)[:150]}")
    raise RuntimeError(f"Gemini se jawab nahi mila: {last_error}")


def build_prompt(notes, n, difficulty):
    return f"""You are a quiz maker for students.
From the NOTES below, create exactly {n} multiple-choice questions.
Difficulty: {difficulty}.

Rules:
- Use ONLY information from the notes.
- Each question has exactly 4 options and exactly 1 correct option.
- "answer" is the index (0, 1, 2 or 3) of the correct option.
- "explanation" is 1-2 short sentences saying why the answer is correct.
- Write in the same language as the notes.
- Return ONLY a JSON array. Each item has the keys:
  "question", "options", "answer", "explanation".

NOTES:
\"\"\"
{notes}
\"\"\"
"""


def parse_questions(text):
    """Gemini ka text -> saaf list of questions. Galat items hata deta hai."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()  # ```json hatao
    data = json.loads(text)
    if isinstance(data, dict):                 # kabhi {"questions": [...]} aa jata hai
        data = data.get("questions", [])

    clean = []
    for item in data:
        try:
            q = str(item["question"]).strip()
            options = [str(o).strip() for o in item["options"]]
            answer = int(item["answer"])
            explanation = str(item.get("explanation", "")).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if q and len(options) == 4 and all(options) and 0 <= answer <= 3:
            clean.append({"question": q, "options": options,
                          "answer": answer, "explanation": explanation})
    return clean


DEMO_QUESTIONS = [
    {"question": "Flask kis language mein likha gaya framework hai?",
     "options": ["Java", "Python", "C++", "PHP"], "answer": 1,
     "explanation": "Flask ek Python web framework hai."},
    {"question": "Database mein 'SELECT' ka kaam kya hai?",
     "options": ["Data delete karna", "Table banana", "Data padhna", "Data badalna"],
     "answer": 2, "explanation": "SELECT table se data nikaalta (padhta) hai."},
    {"question": "HTTP mein form submit ke liye aam taur par kaunsa method use hota hai?",
     "options": ["GET", "POST", "HEAD", "TRACE"], "answer": 1,
     "explanation": "Form ka data POST se bheja jata hai."},
    {"question": "JSON ka full form kya hai?",
     "options": ["JavaScript Object Notation", "Java Standard Output Name",
                 "Joint Source Object Network", "JavaScript Online Node"],
     "answer": 0, "explanation": "JSON = JavaScript Object Notation."},
    {"question": "Virtual environment (venv) kyun banate hain?",
     "options": ["Code tez chalane ke liye", "Project ki libraries alag rakhne ke liye",
                 "Internet chalane ke liye", "Database banane ke liye"],
     "answer": 1, "explanation": "venv har project ki libraries ko alag rakhta hai."},
]


def generate_questions(notes, n, difficulty):
    """Questions banao. Pehli baar fail ho to ek baar aur try karta hai."""
    if DEMO_MODE:
        return DEMO_QUESTIONS[:n]
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY nahi mili. .env file mein key daalo "
                           "(ya testing ke liye DEMO_MODE=1 karo).")
    last_error = None
    for _ in range(2):
        try:
            questions = parse_questions(ask_gemini(build_prompt(notes, n, difficulty)))
            if questions:
                return questions[:n]
            last_error = "Gemini ne sahi format mein sawal nahi diye."
        except json.JSONDecodeError:
            last_error = "Gemini ka jawab JSON nahi tha."
        except Exception as e:
            last_error = e
    raise RuntimeError(f"Quiz nahi ban paya. {last_error} Dobara try karo.")


# ---------------------------------------------------------------- helpers
def save_quiz(title, questions):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO quizzes (title, questions_json, created_at) VALUES (?, ?, ?)",
            (title, json.dumps(questions), now()))
        return cur.lastrowid


def get_quiz(quiz_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    if row is None:
        abort(404)
    return {"id": row["id"], "title": row["title"],
            "questions": json.loads(row["questions_json"])}


def get_attempt(attempt_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None:
        abort(404)
    return row


# ---------------------------------------------------------------- routes
@app.get("/")
def home():
    return render_template("index.html", error=None, form={}, demo=DEMO_MODE,
                           has_key=bool(API_KEY))


@app.post("/generate")
def generate():
    notes = request.form.get("notes", "").strip()
    difficulty = request.form.get("difficulty", "medium")
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    try:
        n = max(3, min(15, int(request.form.get("count", 5))))
    except ValueError:
        n = 5

    form = {"notes": notes, "difficulty": difficulty, "count": n}
    error = None
    if len(notes) < MIN_CHARS:
        error = f"Notes bahut chhote hain. Kam se kam {MIN_CHARS} characters daalo."
    elif len(notes) > MAX_CHARS:
        error = f"Notes bahut bade hain (max {MAX_CHARS} characters). Thode kam karo."
    else:
        try:
            questions = generate_questions(notes, n, difficulty)
            title = notes.splitlines()[0][:50]
            return redirect(url_for("quiz", quiz_id=save_quiz(title, questions)))
        except RuntimeError as e:
            error = str(e)

    return render_template("index.html", error=error, form=form, demo=DEMO_MODE,
                           has_key=bool(API_KEY)), 400


@app.get("/quiz/<int:quiz_id>")
def quiz(quiz_id):
    return render_template("quiz.html", quiz=get_quiz(quiz_id))


@app.post("/quiz/<int:quiz_id>/submit")
def submit(quiz_id):
    q = get_quiz(quiz_id)
    answers, score = [], 0
    for i, question in enumerate(q["questions"]):
        raw = request.form.get(f"q{i}")          # radio button ki value ("0".."3")
        chosen = int(raw) if raw in ("0", "1", "2", "3") else None
        answers.append(chosen)
        if chosen == question["answer"]:
            score += 1
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO attempts (quiz_id, score, total, answers_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (quiz_id, score, len(q["questions"]), json.dumps(answers), now()))
        attempt_id = cur.lastrowid
    return redirect(url_for("result", attempt_id=attempt_id))


@app.get("/result/<int:attempt_id>")
def result(attempt_id):
    attempt = get_attempt(attempt_id)
    q = get_quiz(attempt["quiz_id"])
    answers = json.loads(attempt["answers_json"])
    wrong = sum(1 for a, qu in zip(answers, q["questions"]) if a != qu["answer"])
    percent = round(attempt["score"] * 100 / attempt["total"])
    return render_template("result.html", attempt=attempt, quiz=q, answers=answers,
                           wrong=wrong, percent=percent)


@app.post("/result/<int:attempt_id>/practice")
def practice(attempt_id):
    """Sirf galat / chhoote hue sawalon ka naya quiz."""
    attempt = get_attempt(attempt_id)
    q = get_quiz(attempt["quiz_id"])
    answers = json.loads(attempt["answers_json"])
    wrong_qs = [qu for a, qu in zip(answers, q["questions"]) if a != qu["answer"]]
    if not wrong_qs:
        return redirect(url_for("result", attempt_id=attempt_id))
    new_id = save_quiz("Practice: " + q["title"], wrong_qs)
    return redirect(url_for("quiz", quiz_id=new_id))


@app.get("/history")
def history():
    with db() as conn:
        rows = conn.execute("""
            SELECT a.id, a.score, a.total, a.created_at, q.title
            FROM attempts a JOIN quizzes q ON q.id = a.quiz_id
            ORDER BY a.id DESC LIMIT 50""").fetchall()
    return render_template("history.html", rows=rows)


if __name__ == "__main__":
    app.run(debug=True)
