"""
question_selector.py
────────────────────
The Master Orchestrator for the Skill Test Module.

This file coordinates everything:
1. Validates the requested skills against the resume's extracted skills
2. Calculates how to distribute 10 questions across N skills
3. Calls ai_question_generator for 5 easy MCQs
4. Queries MongoDB for 3 moderate coding questions (random selection)
5. Calls circular_tracker for 2 hard coding questions
6. Packages it all into a TestSessionOut for the frontend

DESIGN DECISION: Dynamic Distribution
───────────────────────────────────
What if the user has 3 skills ("Python", "React", "MongoDB")?
We can't divide 5 questions equally by 3 (5 ÷ 3 = 1.66).
So we use `divmod()` to distribute the remainder evenly.
Example:
    Base = 5 // 3 = 1 (everyone gets 1)
    Remainder = 5 % 3 = 2 (the first two skills get an extra 1)
Result: Python=2, React=2, MongoDB=1.
"""

import uuid
import random
from typing import List, Dict, Any
from datetime import datetime, timezone
from pymongo.database import Database

# Import our internal modules
from schema.question_schema import TestSessionOut
from skill_test.circular_tracker import get_hard_questions
from skill_test.ai_question_generator import generate_mcq_questions


def calculate_distribution(skills: List[str], total_questions: int) -> Dict[str, int]:
    """
    Distributes a total number of questions across a list of skills.
    Example: 5 questions across ["A", "B", "C"] -> {"A": 2, "B": 2, "C": 1}
    """
    count = len(skills)
    base_amount, remainder = divmod(total_questions, count)
    
    distribution = {}
    for i, skill in enumerate(skills):
        distribution[skill] = base_amount + (1 if i < remainder else 0)
        
    return distribution


def generate_test_session(db: Database, user_id: str, selected_skills: List[str]) -> dict:
    """
    Builds the final 10-question test session.
    
    Returns a dict containing:
      - "frontend_payload": The TestSessionOut model (no answers included)
      - "evaluation_key": Internal dict mapping q_index -> correct answers (saved to DB)
    """
    
    if not selected_skills:
        raise ValueError("At least one skill must be provided.")
        
    # We will aggregate all 10 questions here
    # Format: {"public_data": dict, "evaluation_data": dict}
    all_questions_raw = []
    
    # ── Phase 1: 5 Easy AI MCQs ──────────────────────────────────────────────
    # We call Gemini once, asking for 5 questions covering the skills.
    try:
        ai_questions = generate_mcq_questions(selected_skills, count=5)
        all_questions_raw.extend(ai_questions)
    except Exception as e:
        # If Gemini fails, we could fallback here. For now, we propagate.
        print(f"Failed to generate AI questions: {e}")
        raise

    # ── Phase 2: 3 Moderate DB Questions (Random Selection) ──────────────────
    mod_dist = calculate_distribution(selected_skills, total_questions=3)
    
    for skill, count in mod_dist.items():
        if count == 0: continue
        
        # MongoDB Aggregation Pipeline using $sample for randomness
        # Why $sample? It's much faster than fetching all and shuffling in Python.
        pipeline = [
            {"$match": {"skill": skill}},
            {"$sample": {"size": count}}
        ]
        
        cursor = db.questions_moderate.aggregate(pipeline)
        for doc in cursor:
            # We don't have reference solutions here, the future AI evaluator handles it
            all_questions_raw.append({
                "public_data": {
                    "skill": doc["skill"],
                    "difficulty": "moderate",
                    "source": "database",
                    "question_type": "coding",
                    "title": doc["title"],
                    "description": doc["description"]
                },
                "evaluation_data": {
                    "question_index": doc["index"],  # Needed to look up SolutionDoc later
                    "difficulty": "moderate"
                }
            })

    # ── Phase 3: 2 Hard DB Questions (Circular Logic) ────────────────────────
    hard_dist = calculate_distribution(selected_skills, total_questions=2)
    
    for skill, count in hard_dist.items():
        if count == 0: continue
        
        # Call the logic we built in File 2!
        hard_docs = get_hard_questions(db, user_id, skill, count=count)
        for doc in hard_docs:
            all_questions_raw.append({
                "public_data": {
                    "skill": doc["skill"],
                    "difficulty": "hard",
                    "source": "database",
                    "question_type": "coding",
                    "title": doc["title"],
                    "description": doc["description"]
                },
                "evaluation_data": {
                    "question_index": doc["index"],
                    "difficulty": "hard"
                }
            })

    # ── Final Assembly ───────────────────────────────────────────────────────
    # Now we have all 10 questions. We need to assign them 0-9 indices,
    # separate the public data from the secret evaluation data, and build the session.
    
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    public_questions = []
    evaluation_key = {}
    
    for idx, q_raw in enumerate(all_questions_raw):
        # Inject the final global test index (0 to 9)
        pub_data = q_raw["public_data"]
        pub_data["q_index"] = idx
        public_questions.append(pub_data)
        
        # Save the secret stuff indexed by the q_index
        eval_data = q_raw["evaluation_data"]
        eval_data["skill"] = pub_data["skill"]
        eval_data["question_type"] = pub_data["question_type"]
        evaluation_key[str(idx)] = eval_data
        
    # Build the final payload using our Pydantic schema
    session_out = TestSessionOut(
        session_id=session_id,
        user_id=user_id,
        skills_tested=selected_skills,
        total_questions=len(public_questions),
        questions=public_questions,
        created_at=datetime.now(timezone.utc).isoformat()
    )
    
    return {
        "frontend_payload": session_out.model_dump(),
        "evaluation_key": evaluation_key
    }
