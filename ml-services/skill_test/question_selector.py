"""
question_selector.py — Assembles a 10-question test session.
5 easy AI MCQs + 3 random moderate coding + 2 circular hard coding.
"""

import uuid
from datetime import datetime, timezone
from pymongo.database import Database

from schema.question_schema import TestSessionOut
from skill_test.circular_tracker import get_hard_questions
from skill_test.ai_question_generator import generate_mcq_questions


def _distribute(skills: list[str], total: int) -> dict[str, int]:
    """Distribute `total` questions evenly across skills. Remainder goes to first skills."""
    base, rem = divmod(total, len(skills))
    return {s: base + (1 if i < rem else 0) for i, s in enumerate(skills)}


def generate_test_session(db: Database, user_id: str, selected_skills: list[str]) -> dict:
    """
    Build 10-question test. Returns:
      {"frontend_payload": dict (no answers), "evaluation_key": dict (secret answers)}
    """
    if not selected_skills:
        raise ValueError("At least one skill must be provided.")

    all_questions = []

    # Phase 1: 5 easy AI MCQs
    all_questions.extend(generate_mcq_questions(selected_skills, count=5))

    # Phase 2: 3 moderate coding (random via $sample)
    for skill, count in _distribute(selected_skills, 3).items():
        if count == 0:
            continue
        for doc in db.questions_moderate.aggregate([{"$match": {"skill": skill}}, {"$sample": {"size": count}}]):
            all_questions.append({
                "public_data": {
                    "skill": doc["skill"], "difficulty": "moderate", "source": "database",
                    "question_type": "coding", "title": doc["title"], "description": doc["description"],
                },
                "evaluation_data": {"question_index": doc["index"], "difficulty": "moderate"},
            })

    # Phase 3: 2 hard coding (circular tracker)
    for skill, count in _distribute(selected_skills, 2).items():
        if count == 0:
            continue
        for doc in get_hard_questions(db, user_id, skill, count=count):
            all_questions.append({
                "public_data": {
                    "skill": doc["skill"], "difficulty": "hard", "source": "database",
                    "question_type": "coding", "title": doc["title"], "description": doc["description"],
                },
                "evaluation_data": {"question_index": doc["index"], "difficulty": "hard"},
            })

    # Final assembly: assign q_index 0-9, split public vs secret
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    public_questions = []
    evaluation_key = {}

    for idx, q in enumerate(all_questions):
        pub = q["public_data"]
        pub["q_index"] = idx
        public_questions.append(pub)

        ev = q["evaluation_data"]
        ev["skill"] = pub["skill"]
        ev["question_type"] = pub["question_type"]
        evaluation_key[str(idx)] = ev

    session_out = TestSessionOut(
        session_id=session_id, user_id=user_id, skills_tested=selected_skills,
        total_questions=len(public_questions), questions=public_questions,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    return {"frontend_payload": session_out.model_dump(), "evaluation_key": evaluation_key}
