
import json
import os

from flask import Flask, request, jsonify
from flask_cors import CORS
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

app = Flask(__name__)
CORS(app)


# CAREER SKILLS

CAREER_SKILLS = {
    "AI / ML Engineer": [
        "Python", "Mathematics", "Machine Learning", "SQL"
    ],
    "Software Developer": [
        "Programming", "Data Structures", "Git", "Problem Solving"
    ],
    "Data Scientist": [
        "Python", "Statistics", "SQL", "Data Visualization"
    ],
    "Web Developer": [
        "HTML", "CSS", "JavaScript", "React"
    ],
    "UI / UX Designer": [
        "Figma", "Wireframing", "Prototyping", "User Research"
    ]
}


# FILE PATHS

ASSESSMENT_FILE = os.path.join(app.root_path, "assessments.json")
ROADMAP_FILE = os.path.join(app.root_path, "roadmaps.json")
PROGRESS_FILE = os.path.join(app.root_path, "progress_data.json")


# JSON FILE HELPERS

def load_json_file(path, default):
    if os.path.exists(path):
        with open(path, "r") as file:
            return json.load(file)
    return default


def load_assessments():
    return load_json_file(ASSESSMENT_FILE, [])


def load_roadmaps():
    return load_json_file(ROADMAP_FILE, [])


def load_progress():
    return load_json_file(PROGRESS_FILE, {})


# HOME

@app.route("/")
def home():
    return "SkillBridge AI Backend is running!"


# HEALTH CHECK

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "success",
        "message": "SkillBridge AI backend connected"
    })


# ASSESSMENT

@app.route("/api/assessment", methods=["POST"])
def assessment():
    data = request.get_json()

    if not data:
        return jsonify({
            "status": "error",
            "message": "No assessment data received"
        }), 400

    assessments = load_assessments()
    assessments.append(data)

    with open(ASSESSMENT_FILE, "w") as file:
        json.dump(assessments, file, indent=4)

    return jsonify({
        "status": "success",
        "message": "Assessment saved successfully",
        "assessment": data
    })


# SKILL ANALYSIS

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json()

    if not data:
        return jsonify({
            "status": "error",
            "message": "No data received"
        }), 400

    career = data.get("career", "")
    skills = data.get("skills", "")

    if isinstance(skills, list):
        submitted_skills = [
            str(skill).strip().lower()
            for skill in skills
        ]
    else:
        submitted_skills = [
            skill.strip().lower()
            for skill in str(skills).replace("\n", ",").split(",")
            if skill.strip()
        ]

    required = CAREER_SKILLS.get(
        career,
        ["Programming", "Communication", "Problem Solving"]
    )

    known = [
        skill for skill in required
        if skill.lower() in submitted_skills
    ]

    missing = [
        skill for skill in required
        if skill.lower() not in submitted_skills
    ]

    return jsonify({
        "status": "success",
        "career": career,
        "current_skills": submitted_skills,
        "known_skills": known,
        "missing_skills": missing,
        "total_required": len(required),
        "matched_count": len(known)
    })


# AI ROADMAP

@app.route("/api/roadmap", methods=["POST"])
def roadmap():
    data = request.get_json()

    if not data:
        return jsonify({
            "status": "error",
            "message": "No data received"
        }), 400

    career = data.get("career", "")
    missing_skills = data.get("missing_skills", [])

    if not isinstance(missing_skills, list):
        return jsonify({
            "status": "error",
            "message": "Skills must be a list"
        }), 400

    missing_skills = [
        str(skill).strip()
        for skill in missing_skills
        if str(skill).strip()
    ]

    if not missing_skills:
        return jsonify({
            "status": "success",
            "career": career,
            "total_weeks": 0,
            "roadmap": [],
            "ai_generated": False,
            "ai_assisted": False
        })

    roadmap_plan = []
    generated_items = []
    ai_content_count = 0

    prompt = f"""
Create a beginner-friendly learning roadmap.

Target career: {career}

Missing skills:
{json.dumps(missing_skills)}

Rules:
- Create exactly {len(missing_skills)} items.
- Create one item for each skill.
- Follow the exact order of the supplied skills.
- Use only the supplied skills.
- Make the focus specific and useful.
- Give one practical beginner-friendly task per skill.
- Return valid JSON only.

Required format:
{{
    "roadmap": [
        {{
            "week": 1,
            "skill": "Skill name",
            "focus": "Specific learning topic",
            "task": "Practical exercise"
        }}
    ]
}}
"""

    # CONNECT TO OLLAMA

    try:
        payload = json.dumps({
            "model": "qwen2.5:1.5b",
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 700
            }
        }).encode("utf-8")

        req = Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={
                "Content-Type": "application/json"
            }
        )

        with urlopen(req, timeout=180) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

        ai_result = json.loads(result["response"])
        generated_items = ai_result.get("roadmap", [])

        if not isinstance(generated_items, list):
            generated_items = []

    except Exception as error:
        print("Ollama connection/generation error:", str(error))
        generated_items = []

    # NORMALIZE AI RESPONSE
    # Exactly one item for every missing skill.

    for index, skill in enumerate(missing_skills):

        item = {}

        if (
            index < len(generated_items)
            and isinstance(generated_items[index], dict)
        ):
            item = generated_items[index]

        focus = item.get("focus", "")
        task = item.get("task", "")

        valid_focus = (
            isinstance(focus, str) and bool(focus.strip())
        )

        valid_task = (
            isinstance(task, str) and bool(task.strip())
        )

        if valid_focus and valid_task:
            ai_content_count += 1

        if not valid_focus:
            focus = "Learn the fundamentals of " + skill

        if not valid_task:
            task = (
                "Study the basics of " + skill +
                " and complete one small practical exercise."
            )

        roadmap_plan.append({
            "week": index + 1,
            "skill": skill,
            "focus": focus,
            "task": task
        })

    # SAVE ROADMAP

    ai_generated = ai_content_count == len(missing_skills)
    ai_assisted = ai_content_count > 0

    roadmap_record = {
        "career": career,
        "total_weeks": len(roadmap_plan),
        "roadmap": roadmap_plan,
        "ai_generated": ai_generated,
        "ai_assisted": ai_assisted
    }

    roadmaps = load_roadmaps()
    roadmaps.append(roadmap_record)

    with open(ROADMAP_FILE, "w") as file:
        json.dump(roadmaps, file, indent=4)

    return jsonify({
        "status": "success",
        **roadmap_record
    })


# PROGRESS TRACKER - GET

@app.route("/api/progress", methods=["GET"])
def get_progress():
    career = request.args.get("career", "Not selected")
    all_progress = load_progress()

    return jsonify({
        "status": "success",
        "completed_skills": all_progress.get(career, [])
    })


# PROGRESS TRACKER - POST

@app.route("/api/progress", methods=["POST"])
def save_progress():
    data = request.get_json()

    if not data:
        return jsonify({
            "status": "error",
            "message": "No data received"
        }), 400

    career = data.get("career", "Not selected")
    completed_skills = data.get("completed_skills", [])

    if not isinstance(completed_skills, list):
        return jsonify({
            "status": "error",
            "message": "Completed skills must be a list"
        }), 400

    all_progress = load_progress()
    all_progress[career] = completed_skills

    with open(PROGRESS_FILE, "w") as file:
        json.dump(all_progress, file, indent=4)

    return jsonify({
        "status": "success",
        "message": "Progress saved successfully",
        "completed_skills": completed_skills
    })


# RUN SERVER

if __name__ == "__main__":
    app.run(debug=True)
