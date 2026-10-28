"""AI helpers: Smart Notes and MCQs from Google Gemini, with a canned fallback.

If GEMINI_API_KEY is not set (or the call fails), we return sample content so
the demo always works.
"""
import json
import os
import re

import requests

# Try the chosen model first, then fall back to other Flash models if Google
# has renamed or retired it.
MODELS = [m for m in [os.environ.get("GEMINI_MODEL", "").strip(),
                      "gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash"] if m]
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
last_status = {"ok": None, "model": None, "error": None}


def _ask_gemini(prompt, want_json=True):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        last_status.update(ok=False, model=None, error="GEMINI_API_KEY not set")
        return None
    config = {"thinkingConfig": {"thinkingBudget": 0}}  # faster replies
    if want_json:
        config["responseMimeType"] = "application/json"
    for model in MODELS:
        for cfg in (config, {}):  # older models reject thinkingConfig
            try:
                # key goes in a header so it never shows up in logged URLs
                resp = requests.post(
                    GEMINI_URL.format(model=model),
                    headers={"x-goog-api-key": key},
                    json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg},
                    timeout=45,
                )
            except requests.RequestException as exc:
                last_status.update(ok=False, model=model, error=type(exc).__name__)
                print("Gemini call failed:", model, type(exc).__name__)
                return None
            if resp.ok:
                try:
                    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError, ValueError):
                    last_status.update(ok=False, model=model, error="empty reply")
                    return None
                last_status.update(ok=True, model=model, error=None)
                return text
            last_status.update(ok=False, model=model, error=f"HTTP {resp.status_code}")
            print("Gemini call failed:", model, resp.status_code, resp.text[:200])
            if resp.status_code == 400 and cfg:
                continue  # retry this model without the extra config
            break
        if resp.status_code != 404:
            return None  # bad key, quota, etc: another model won't help
    return None


def _extract_json(text):
    """Pull the first JSON object or array out of a model reply."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
    return json.loads(match.group(1) if match else text)


# ---------- Smart Notes ----------

def make_notes(topic, source_text=""):
    prompt = (
        "You are Study Buddy, a friendly tutor for college students. "
        f"Write short, exam-ready study notes on the topic: '{topic}'.\n"
        + (f"Base them on this material:\n{source_text[:6000]}\n" if source_text else "")
        + "Reply ONLY with JSON in this shape: "
        '{"summary": "2-3 sentence overview", '
        '"key_points": ["5 to 7 short bullet points"], '
        '"keywords": [{"term": "...", "meaning": "..."}], '
        '"exam_tip": "one practical tip"}'
    )
    reply = _ask_gemini(prompt)
    if reply:
        try:
            data = _extract_json(reply)
            data["source"] = "gemini"
            return data
        except Exception as exc:
            print("Could not parse notes JSON:", exc)
    return _sample_notes(topic)


def _sample_notes(topic):
    return {
        "source": "sample",
        "summary": (
            f"{topic} is an important topic in your syllabus. These are sample notes "
            "shown because the AI key is not set up yet. Add a GEMINI_API_KEY to get "
            "real notes for any topic."
        ),
        "key_points": [
            f"Start with the definition of {topic} in your own words.",
            "List the main components or steps and how they connect.",
            "Learn one real-world example for each component.",
            "Draw a simple diagram; examiners reward clear diagrams.",
            "Note common mistakes students make on this topic.",
            "Revise with 5 quick MCQs right after reading.",
        ],
        "keywords": [
            {"term": "Definition", "meaning": f"A one-line meaning of {topic}."},
            {"term": "Example", "meaning": "A real case that shows the idea in action."},
            {"term": "Application", "meaning": "Where this is used in industry or daily life."},
        ],
        "exam_tip": "Write the definition first, then a diagram, then an example.",
    }


# ---------- MCQs ----------

def make_mcqs(topic, count=5):
    prompt = (
        f"Create {count} multiple-choice questions to test a college student on '{topic}'. "
        "Each question has exactly 4 options and one correct answer. "
        "Give each question a short 'subtopic' label (2-4 words) so we can find weak areas. "
        "Reply ONLY with a JSON array like: "
        '[{"question": "...", "options": ["A", "B", "C", "D"], "answer": 0, '
        '"subtopic": "...", "explanation": "one line"}] '
        "where answer is the index (0-3) of the correct option."
    )
    reply = _ask_gemini(prompt)
    if reply:
        try:
            qs = _extract_json(reply)
            clean = []
            for q in qs:
                if len(q.get("options", [])) == 4 and int(q.get("answer", -1)) in range(4):
                    q["answer"] = int(q["answer"])
                    q.setdefault("subtopic", topic)
                    q.setdefault("explanation", "")
                    clean.append(q)
            if clean:
                return clean[:count], "gemini"
        except Exception as exc:
            print("Could not parse MCQ JSON:", exc)
    return _sample_mcqs(topic)[:count], "sample"


SAMPLE_BANK = {
    "python": [
        {"question": "Which keyword defines a function in Python?", "options": ["func", "def", "function", "lambda"], "answer": 1, "subtopic": "Functions", "explanation": "Functions are defined with def."},
        {"question": "What is the output of len([1, 2, 3])?", "options": ["2", "3", "4", "Error"], "answer": 1, "subtopic": "Lists", "explanation": "The list has 3 items."},
        {"question": "Which type is immutable?", "options": ["list", "dict", "tuple", "set"], "answer": 2, "subtopic": "Data types", "explanation": "Tuples cannot be changed after creation."},
        {"question": "How do you start a for loop over 0..4?", "options": ["for i in range(5):", "for (i=0;i<5;i++)", "loop i to 5", "for i = 0 to 4"], "answer": 0, "subtopic": "Loops", "explanation": "range(5) gives 0 to 4."},
        {"question": "Which handles an error in Python?", "options": ["catch", "try/except", "error/handle", "if/else"], "answer": 1, "subtopic": "Exceptions", "explanation": "try/except catches exceptions."},
    ],
    "dbms": [
        {"question": "Which normal form removes partial dependency?", "options": ["1NF", "2NF", "3NF", "BCNF"], "answer": 1, "subtopic": "Normalization", "explanation": "2NF removes partial dependencies."},
        {"question": "Which SQL command removes a table entirely?", "options": ["DELETE", "REMOVE", "DROP", "TRUNCATE"], "answer": 2, "subtopic": "SQL commands", "explanation": "DROP deletes the table structure."},
        {"question": "A primary key must be...", "options": ["Unique and not null", "Nullable", "Duplicated", "A string"], "answer": 0, "subtopic": "Keys", "explanation": "Primary keys are unique and not null."},
        {"question": "ACID's 'I' stands for", "options": ["Integrity", "Isolation", "Index", "Insert"], "answer": 1, "subtopic": "Transactions", "explanation": "Isolation keeps transactions separate."},
        {"question": "Which join returns only matching rows?", "options": ["LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "FULL JOIN"], "answer": 2, "subtopic": "Joins", "explanation": "INNER JOIN keeps matches only."},
    ],
}


def _sample_mcqs(topic):
    key = topic.lower()
    for name, bank in SAMPLE_BANK.items():
        if name in key:
            return [dict(q) for q in bank]
    return [
        {"question": f"What is the best first step to learn {topic}?", "options": ["Memorise answers", "Understand the definition", "Skip theory", "Only read summaries"], "answer": 1, "subtopic": "Basics", "explanation": "Understanding the definition builds the base."},
        {"question": f"Which helps you remember {topic} for exams?", "options": ["Reading once", "Active recall with MCQs", "Highlighting everything", "Last-night cramming"], "answer": 1, "subtopic": "Revision", "explanation": "Active recall beats re-reading."},
        {"question": "A diagram in an answer usually...", "options": ["Wastes time", "Earns extra marks", "Is not allowed", "Replaces the answer"], "answer": 1, "subtopic": "Exam skills", "explanation": "Clear diagrams earn marks."},
        {"question": f"Real-world examples of {topic} help because they...", "options": ["Make answers longer", "Show you understand it", "Are required by law", "Replace definitions"], "answer": 1, "subtopic": "Applications", "explanation": "Examples prove understanding."},
        {"question": "Spaced revision means...", "options": ["Revising once", "Revising at growing gaps", "Revising all at once", "Never revising"], "answer": 1, "subtopic": "Revision", "explanation": "Spacing improves memory."},
    ]
