"""
question_selector.py — Assembles a 10-question test session.
5 easy AI MCQs + 3 random moderate coding + 2 circular hard coding.
"""

import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from pymongo.database import Database

from schema.question_schema import TestSessionOut
from skill_test.circular_tracker import get_hard_questions
from skill_test.ai_question_generator import generate_mcq_questions

# Resilient import of get_subtopics and get_canonical_skill
try:
    from extraction.skill_taxonomy import get_subtopics, get_canonical_skill
except ImportError:
    try:
        from skill_taxonomy import get_subtopics, get_canonical_skill
    except ImportError:
        try:
            from ..extraction.skill_taxonomy import get_subtopics, get_canonical_skill
        except Exception:
            def get_subtopics(skill_name: Optional[str]) -> list[str]:
                return []
            def get_canonical_skill(skill_name: Optional[str]) -> str:
                return ""


def _expand_skill(skill: str) -> list[str]:
    """Expand umbrella skill into candidate subtopics, preserving original skill."""
    if not skill:
        return []
    try:
        subtopics = get_subtopics(skill)
    except Exception:
        subtopics = []

    candidates = [skill]
    seen = {skill.strip().lower()}

    # Also resolve canonical skill name
    try:
        canonical = get_canonical_skill(skill)
        if canonical and canonical.strip().lower() not in seen:
            seen.add(canonical.strip().lower())
            candidates.append(canonical.strip())
    except Exception:
        pass

    # Ensure synonyms/variants are mirrored
    s_clean = skill.strip().lower()
    if "datascience" in s_clean or "data science" in s_clean or s_clean in ("machine learning", "ml", "ai/ml"):
        for extra in ["Data Science", "Datascience", "Machine Learning"]:
            if extra.lower() not in seen:
                seen.add(extra.lower())
                candidates.append(extra)
    elif "mix skill" in s_clean or "software engineering" in s_clean or s_clean in ("swe", "software engineer"):
        for extra in ["Software Engineering", "mix skill", "mix skills"]:
            if extra.lower() not in seen:
                seen.add(extra.lower())
                candidates.append(extra)
    elif "oop" in s_clean:
        for extra in ["OOP", "OOPS"]:
            if extra.lower() not in seen:
                seen.add(extra.lower())
                candidates.append(extra)
    elif "system design" in s_clean or s_clean in ("sys design", "system_design", "low level design", "high level design"):
        for extra in ["System Design", "Microservices", "Load Balancing", "Caching"]:
            if extra.lower() not in seen:
                seen.add(extra.lower())
                candidates.append(extra)

    for sub in subtopics:
        if isinstance(sub, str) and sub.strip():
            sub_key = sub.strip().lower()
            if sub_key not in seen:
                seen.add(sub_key)
                candidates.append(sub.strip())
    return candidates


def _build_skill_regex(skills: list[str]) -> str:
    """Build case-insensitive regex pattern matching any candidate skill."""
    if not skills:
        return "^$"
    return "^(" + "|".join(re.escape(s) for s in skills) + ")$"


def _distribute(skills: list[str], total: int) -> dict[str, int]:
    """Distribute `total` questions evenly across skills. Remainder goes to first skills."""
    if not skills:
        return {}
    base, rem = divmod(total, len(skills))
    return {s: base + (1 if i < rem else 0) for i, s in enumerate(skills)}


def generate_test_session(db: Database, user_id: str, selected_skills: list[str]) -> dict:
    """
    Build 10-question test. Returns:
      {"frontend_payload": dict (no answers), "evaluation_key": dict (secret answers)}
    """
    if not selected_skills:
        raise ValueError("At least one skill must be provided.")
    clean_skills = [str(s).strip() for s in selected_skills if s and str(s).strip()]
    if not clean_skills:
        raise ValueError("At least one valid non-empty skill must be provided.")
    selected_skills = clean_skills

    all_questions = []

    # Phase 1: 5 easy AI MCQs
    all_questions.extend(generate_mcq_questions(selected_skills, count=5))

    # Phase 2: 3 moderate coding (random via $sample)
    moderate_docs = []
    seen_moderate_ids = []
    for skill, count in _distribute(selected_skills, 3).items():
        if count == 0:
            continue
        candidates = _expand_skill(skill)
        pattern = _build_skill_regex(candidates)
        match_query = {"skill": {"$regex": pattern, "$options": "i"}}
        if seen_moderate_ids:
            match_query["_id"] = {"$nin": seen_moderate_ids}

        matched = list(db.questions_moderate.aggregate([
            {"$match": match_query},
            {"$sample": {"size": count}}
        ]))
        moderate_docs.extend(matched)
        seen_moderate_ids.extend([d["_id"] for d in matched])

    # Backfill moderate questions if skills didn't have enough
    if len(moderate_docs) < 3:
        needed = 3 - len(moderate_docs)
        seen_ids = [d["_id"] for d in moderate_docs]
        backfill = list(db.questions_moderate.aggregate([
            {"$match": {"_id": {"$nin": seen_ids}}},
            {"$sample": {"size": needed}}
        ]))
        moderate_docs.extend(backfill)

    for doc in moderate_docs:
        all_questions.append({
            "public_data": {
                "question_id": str(doc["_id"]),
                "skill": doc["skill"], "difficulty": "moderate", "source": "database",
                "question_type": "coding", "title": doc["title"], "description": doc["description"],
            },
            "evaluation_data": {
                "question_id": str(doc["_id"]),
                "question_index": doc.get("index"),
                "difficulty": "moderate",
            },
        })

    # Phase 3: 2 hard coding (circular tracker with subtopic routing)
    hard_docs = []
    for skill, count in _distribute(selected_skills, 2).items():
        if count == 0:
            continue
        candidates = _expand_skill(skill)
        pattern = _build_skill_regex(candidates)

        # Check if direct hard questions exist for skill
        if db.questions_hard.count_documents({"skill": {"$regex": f"^{re.escape(skill)}$", "$options": "i"}}) > 0:
            direct_match = db.questions_hard.find_one({"skill": {"$regex": f"^{re.escape(skill)}$", "$options": "i"}})
            canonical_skill = direct_match["skill"] if direct_match and "skill" in direct_match else skill
            hard_docs.extend(get_hard_questions(db, user_id, canonical_skill, count=count))
        else:
            # Route through available subtopics in questions_hard
            avail = db.questions_hard.distinct("skill", {"skill": {"$regex": pattern, "$options": "i"}})
            if avail:
                sub_counts = _distribute(avail, count)
                for sub_skill, sub_c in sub_counts.items():
                    if sub_c > 0:
                        hard_docs.extend(get_hard_questions(db, user_id, sub_skill, count=sub_c))
            else:
                matched = list(db.questions_hard.aggregate([
                    {"$match": {"skill": {"$regex": pattern, "$options": "i"}}},
                    {"$sample": {"size": count}}
                ]))
                hard_docs.extend(matched)

    # Backfill hard questions if needed
    if len(hard_docs) < 2:
        needed = 2 - len(hard_docs)
        seen_ids = [d["_id"] for d in hard_docs]
        backfill = list(db.questions_hard.aggregate([
            {"$match": {"_id": {"$nin": seen_ids}}},
            {"$sample": {"size": needed}}
        ]))
        hard_docs.extend(backfill)

    for doc in hard_docs:
        all_questions.append({
            "public_data": {
                "question_id": str(doc["_id"]),
                "skill": doc["skill"], "difficulty": "hard", "source": "database",
                "question_type": "coding", "title": doc["title"], "description": doc["description"],
            },
            "evaluation_data": {
                "question_id": str(doc["_id"]),
                "question_index": doc.get("index"),
                "difficulty": "hard",
            },
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
