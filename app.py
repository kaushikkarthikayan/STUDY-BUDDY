"""Study Buddy - AI study platform (hackathon prototype)."""
import json
import os
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import Flask, abort, g, redirect, render_template, request, url_for

import ai

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "study-buddy-dev-key")
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "study_buddy.db"))
WEAK_THRESHOLD = 60  # a subtopic below 60% correct counts as weak


# ---------- database ----------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            questions TEXT NOT NULL,
            source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER,
            topic TEXT,
            subtopic TEXT,
            correct INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER,
            student TEXT,
            topic TEXT,
            score INTEGER,
            total INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            category TEXT,
            posted_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    if db.execute("SELECT COUNT(*) FROM notices").fetchone()[0] == 0:
        today = date.today()
        db.executemany(
            "INSERT INTO notices (title, body, category, posted_by, created_at) VALUES (?,?,?,?,?)",
            [
                ("Internal assessment 2 timetable", "IA-2 starts next Monday. Check the department board for room numbers.", "Exam", "Exam Cell", str(today)),
                ("Hackathon results", "Round 2 shortlisted teams will be announced on the college website.", "Event", "Innovation Club", str(today - timedelta(days=1))),
                ("Library hours extended", "The central library stays open till 9 pm during exam weeks.", "General", "Librarian", str(today - timedelta(days=3))),
                ("DBMS assignment due", "Submit the normalization assignment on the portal before Friday.", "Assignment", "Prof. Kavitha", str(today - timedelta(days=4))),
            ],
        )
    db.commit()
    db.close()


init_db()


# ---------- sample data for demo pages ----------

ARENA_TEAMS = [
    {"name": "CSE-A Coders", "points": 1240, "wins": 9},
    {"name": "ECE Sparks", "points": 1105, "wins": 8},
    {"name": "IT Ninjas", "points": 980, "wins": 7},
    {"name": "MECH Titans", "points": 860, "wins": 5},
    {"name": "AIDS Bots", "points": 790, "wins": 4},
]

SAMPLE_STUDENTS = [
    {"name": "Arun", "score": 88, "weak": "Joins"},
    {"name": "Divya", "score": 92, "weak": "-"},
    {"name": "Karthik", "score": 54, "weak": "Normalization"},
    {"name": "Meena", "score": 71, "weak": "Transactions"},
    {"name": "Rahul", "score": 47, "weak": "Keys, Joins"},
    {"name": "Sneha", "score": 79, "weak": "SQL commands"},
]

PEERS = [
    {"name": "Divya", "strong": "DBMS", "needs": "Python", "time": "Evenings"},
    {"name": "Arun", "strong": "Python", "needs": "Networks", "time": "Weekends"},
    {"name": "Meena", "strong": "Maths", "needs": "DBMS", "time": "Mornings"},
    {"name": "Sneha", "strong": "Networks", "needs": "Maths", "time": "Evenings"},
]


# ---------- helpers ----------

def subtopic_stats():
    rows = get_db().execute(
        "SELECT topic, subtopic, SUM(correct) AS right, COUNT(*) AS total "
        "FROM answers GROUP BY topic, subtopic ORDER BY topic, subtopic"
    ).fetchall()
    stats = []
    for r in rows:
        pct = round(100 * r["right"] / r["total"]) if r["total"] else 0
        stats.append({"topic": r["topic"], "subtopic": r["subtopic"], "right": r["right"],
                      "total": r["total"], "pct": pct, "weak": pct < WEAK_THRESHOLD})
    return stats


def build_plan(weak, days=7):
    """Spread weak subtopics over the week: learn, practise, then revise."""
    plan = []
    start = date.today()
    if not weak:
        return plan
    for i in range(days):
        item = weak[i % len(weak)]
        cycle = (i // len(weak)) % 3
        task = [
            f"Read Smart Notes on {item['subtopic']} ({item['topic']}) for 25 min",
            f"Take a 5-question quiz on {item['subtopic']} and review mistakes",
            f"Teach {item['subtopic']} to a peer or explain it aloud in 5 min",
        ][cycle]
        plan.append({"day": (start + timedelta(days=i)).strftime("%a %d %b"),
                     "task": task, "subtopic": item["subtopic"], "pct": item["pct"]})
    return plan


# ---------- routes ----------

@app.route("/")
def home():
    db = get_db()
    attempts = db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    stats = subtopic_stats()
    weak = [s for s in stats if s["weak"]]
    notices = db.execute("SELECT * FROM notices ORDER BY created_at DESC, id DESC LIMIT 3").fetchall()
    return render_template("index.html", attempts=attempts, weak=weak[:3],
                           notices=notices, ai_on=bool(os.environ.get("GEMINI_API_KEY")))


@app.route("/notes", methods=["GET", "POST"])
def notes():
    result, topic, text = None, "", ""
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()[:120]
        text = request.form.get("text", "").strip()
        if topic:
            result = ai.make_notes(topic, text)
    return render_template("notes.html", result=result, topic=topic, text=text)


@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()[:120]
        if not topic:
            return redirect(url_for("quiz"))
        questions, source = ai.make_mcqs(topic, 5)
        db = get_db()
        cur = db.execute("INSERT INTO quizzes (topic, questions, source) VALUES (?,?,?)",
                         (topic, json.dumps(questions), source))
        db.commit()
        return redirect(url_for("take_quiz", quiz_id=cur.lastrowid))
    return render_template("quiz_start.html", topic=request.args.get("topic", ""))


@app.route("/quiz/<int:quiz_id>", methods=["GET", "POST"])
def take_quiz(quiz_id):
    db = get_db()
    row = db.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    if not row:
        abort(404)
    questions = json.loads(row["questions"])
    if request.method == "GET":
        return render_template("quiz.html", quiz=row, questions=questions)

    student = request.form.get("student", "").strip()[:40] or "You"
    results, score = [], 0
    for i, q in enumerate(questions):
        picked = request.form.get(f"q{i}")
        picked = int(picked) if picked is not None and picked.isdigit() else None
        ok = picked == q["answer"]
        score += ok
        results.append({**q, "picked": picked, "ok": ok})
        db.execute("INSERT INTO answers (quiz_id, topic, subtopic, correct) VALUES (?,?,?,?)",
                   (quiz_id, row["topic"], q.get("subtopic", row["topic"]), int(ok)))
    db.execute("INSERT INTO attempts (quiz_id, student, topic, score, total) VALUES (?,?,?,?,?)",
               (quiz_id, student, row["topic"], score, len(questions)))
    db.commit()

    by_sub = defaultdict(lambda: [0, 0])
    for r in results:
        by_sub[r["subtopic"]][0] += r["ok"]
        by_sub[r["subtopic"]][1] += 1
    weak_now = [s for s, (right, total) in by_sub.items() if 100 * right / total < WEAK_THRESHOLD]
    return render_template("result.html", quiz=row, results=results, score=score,
                           total=len(questions), weak_now=weak_now)


@app.route("/plan")
def plan():
    stats = subtopic_stats()
    weak = sorted([s for s in stats if s["weak"]], key=lambda s: s["pct"])
    return render_template("plan.html", stats=stats, weak=weak, plan=build_plan(weak))


@app.route("/arena")
def arena():
    db = get_db()
    recent = db.execute("SELECT * FROM attempts ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("arena.html", teams=ARENA_TEAMS, recent=recent, peers=PEERS)


@app.route("/teacher")
def teacher():
    db = get_db()
    real = db.execute(
        "SELECT student, topic, score, total, created_at FROM attempts ORDER BY id DESC LIMIT 20"
    ).fetchall()
    stats = subtopic_stats()
    class_weak = sorted([s for s in stats if s["weak"]], key=lambda s: s["pct"])
    avg = round(sum(s["score"] for s in SAMPLE_STUDENTS) / len(SAMPLE_STUDENTS))
    return render_template("teacher.html", students=SAMPLE_STUDENTS, real=real,
                           class_weak=class_weak, avg=avg)


@app.route("/notices", methods=["GET", "POST"])
def notices():
    db = get_db()
    if request.method == "POST":
        title = request.form.get("title", "").strip()[:120]
        body = request.form.get("body", "").strip()[:1000]
        if title and body:
            db.execute("INSERT INTO notices (title, body, category, posted_by, created_at) VALUES (?,?,?,?,?)",
                       (title, body, request.form.get("category", "General"),
                        request.form.get("posted_by", "").strip()[:60] or "Teacher",
                        datetime.now().strftime("%Y-%m-%d")))
            db.commit()
        return redirect(url_for("notices"))
    rows = db.execute("SELECT * FROM notices ORDER BY created_at DESC, id DESC").fetchall()
    return render_template("notices.html", notices=rows)


@app.route("/rescue")
def rescue():
    stats = subtopic_stats()
    weak = sorted([s for s in stats if s["weak"]], key=lambda s: s["pct"])
    return render_template("rescue.html", weak=weak)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
