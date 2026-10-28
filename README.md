# Study Buddy

Study Buddy is an AI-powered learning platform that creates smart notes, practice MCQs, and personalized revision plans. It promotes collaborative learning through Class Arena quiz battles peer matching, and a Rescue Zone for doubt-solving. Teachers can track student progress through dashboardswhile colleges can share notices in one convenient app.

_Team 404 hackathon prototype._

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/kaushikkarthikayan/STUDY-BUDDY)

**Features:** Smart Notes (AI), AI MCQ quizzes, weak-topic detection, 7-day study plan,
Rescue Zone, Class Arena + peer matching, Teacher Dashboard, College Notices.

**Stack:** Python Flask, SQLite, HTML/CSS/JS with Bootstrap 5, Google Gemini API.

## How weak topics are measured
Every quiz question is tagged with a subtopic. The app stores each answer and works out the
percentage correct per subtopic across all quizzes. Any subtopic below **60%** is "weak" and
feeds the Study Plan and Rescue Zone.

## AI model
Google Gemini (`gemini-2.5-flash` by default, change with the `GEMINI_MODEL` env var).
Without a `GEMINI_API_KEY` the app runs in demo mode with sample notes and questions.

## Run on your computer
```
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000. To use real AI, set `GEMINI_API_KEY` first
(Windows: `set GEMINI_API_KEY=your_key`, Mac/Linux: `export GEMINI_API_KEY=your_key`).

## Deploy on Render (free)
1. Push this folder to a GitHub repo.
2. On render.com: **New > Blueprint**, pick the repo. Render reads `render.yaml`.
3. When asked, paste your Gemini key into `GEMINI_API_KEY` (get one free at https://aistudio.google.com/apikey).
4. Wait for the build, then open the `.onrender.com` link.

Note: on Render's free plan the SQLite file resets when the app restarts, so quiz history is demo data only.
