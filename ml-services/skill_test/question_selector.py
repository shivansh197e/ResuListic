"""
question_selector.py — Assembles a 25-question test session.
20 AI MCQs + 3 random moderate coding + 2 circular hard coding.
"""

import re
import uuid
from datetime import datetime, timezone, timedelta
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


STACK_TO_DB_SKILLS: dict[str, list[str]] = {
    "React": ["Software Engineering", "System Design", "Data Structures", "Array", "Hash Table"],
    "React.js": ["Software Engineering", "System Design", "Data Structures", "Array", "Hash Table"],
    "FastAPI": ["Software Engineering", "System Design", "Hash Table", "String"],
    "Docker": ["System Design", "Software Engineering"],
    "PostgreSQL": ["SQL", "Database", "Hash Table", "Software Engineering"],
    "Postgres": ["SQL", "Database", "Hash Table", "Software Engineering"],
    "SQL": ["Database", "Hash Table", "Software Engineering"],
    "Git": ["Software Engineering", "Data Structures", "Tree", "Graph"],
    "Node.js": ["Software Engineering", "Data Structures", "Hash Table"],
    "Express": ["Software Engineering", "Data Structures", "Hash Table"],
    "Kubernetes": ["System Design", "Software Engineering"],
    "Redis": ["System Design", "Hash Table", "Data Structures"],
    "MongoDB": ["Database", "Hash Table", "Software Engineering"],
    "Django": ["Software Engineering", "System Design", "Database"],
    "Flask": ["Software Engineering", "System Design", "Hash Table"],
    "Spring Boot": ["Software Engineering", "OOPS", "System Design"],
    "Spring": ["Software Engineering", "OOPS", "System Design"],
    "Java": ["OOPS", "Data Structures", "Array", "Software Engineering"],
    "C++": ["Data Structures", "Array", "Algorithms", "OOPS"],
}


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

    # Check STACK_TO_DB_SKILLS for framework-to-DB algorithmic mapping
    for stack_key, db_targets in STACK_TO_DB_SKILLS.items():
        if stack_key.lower() == s_clean:
            for tgt in db_targets:
                if tgt.strip().lower() not in seen:
                    seen.add(tgt.strip().lower())
                    candidates.append(tgt.strip())

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


VALID_DESC_QUERY = {
    "description": {"$exists": True, "$ne": None, "$nin": ["", "Rewritten:", "Rewritten: "], "$regex": r"(?s).{100,}"}
}


def _clean_title(t: str) -> str:
    """Removes scraping prefixes like 'Mutated: ' or 'Rewritten: '."""
    if not t:
        return "Coding Challenge"
    return re.sub(r"^(mutated:\s*|rewritten:\s*)", "", t, flags=re.IGNORECASE).strip()


def _clean_and_enrich_description(desc: str, title: str) -> str:
    """Strips artifacts, ensures HTML formatting, and guarantees at least one example and constraints."""
    cleaned = (desc or "").strip()
    cleaned = re.sub(r"^rewritten:\s*", "", cleaned, flags=re.IGNORECASE).strip()
    clean_t = _clean_title(title)
    if not cleaned or len(cleaned) < 50:
        cleaned = f"<p>Design and implement an optimal, production-grade algorithm for <strong>{clean_t}</strong>.</p>"

    # Ensure the description has clear structured examples if missing
    if not re.search(r"\b(example\s*\d*|input\s*:|output\s*:)\b", cleaned, re.IGNORECASE):
        cleaned += (
            f"\n\n<p><strong class=\"example\">Example 1:</strong></p>\n"
            f"<pre>\n<strong>Input:</strong> Valid parameters for {clean_t}\n"
            f"<strong>Output:</strong> Computed result satisfying problem invariants\n"
            f"<strong>Explanation:</strong> Implement standard edge-case handling for boundary and extreme inputs.\n</pre>\n"
            f"<p><strong>Constraints:</strong></p>\n"
            f"<ul>\n<li>Execution must adhere to optimal time and space complexity standards.</li>\n"
            f"<li>Return results matching the exact data types and specifications.</li>\n</ul>"
        )
    return cleaned


def _is_subjective_doc(doc: dict) -> bool:
    """Detects whether a question is a conceptual/descriptive explanation rather than code."""
    if not isinstance(doc, dict):
        return False
    if doc.get("question_type") in ("subjective", "conceptual", "text"):
        return True
    title = (doc.get("title") or "").strip()
    desc = (doc.get("description") or "").strip()
    if re.search(r"^(explain|describe|define|why|what is|what are|discuss|compare|differentiate|how does)\b", title, re.IGNORECASE):
        if not re.search(r"\b(def |class Solution|public |Input:|Output:|Constraints:|Example 1:|nums)\b", desc):
            return True
    return False


def _prioritize_skills(skills: list[str], collection, valid_query: dict) -> list[str]:
    """Order skills by availability of matching questions in the collection to prevent slot starvation."""
    scored = []
    for s in skills:
        candidates = _expand_skill(s)
        pat = _build_skill_regex(candidates)
        try:
            cnt = collection.count_documents({"skill": {"$regex": pat, "$options": "i"}, **valid_query})
        except Exception:
            cnt = 0
        scored.append((cnt, s))
    # Stable sort by question count descending; skills with available questions come first
    scored.sort(key=lambda x: x[0], reverse=True)
    avail = [s for cnt, s in scored if cnt > 0]
    return avail if avail else [s for _, s in scored]


def _distribute(skills: list[str], total: int) -> dict[str, int]:
    """Distribute `total` questions evenly across skills. Remainder goes to first skills."""
    if not skills:
        return {}
    base, rem = divmod(total, len(skills))
    return {s: base + (1 if i < rem else 0) for i, s in enumerate(skills)}


def generate_test_session(db: Database, user_id: str, selected_skills: list[str], time_limit_minutes: int = 120, mode: str = "live") -> dict:
    """
    Build 25-question test session: 20 MCQs (1 mark each = 20) + 3 Moderate (10 marks each = 30) + 2 Hard (25 marks each = 50) = 100 Marks.
    Supports mode='live' or mode='mock'.
    Returns:
      {"frontend_payload": dict (no answers), "evaluation_key": dict (secret answers)}
    """
    if not selected_skills:
        raise ValueError("At least one skill must be provided.")
    clean_skills = [str(s).strip() for s in selected_skills if s and str(s).strip()]
    if not clean_skills:
        raise ValueError("At least one valid non-empty skill must be provided.")
    selected_skills = clean_skills

    all_questions = []

    # Phase 1: Strictly 20 easy/fundamental AI MCQs (1 mark each)
    all_questions.extend(generate_mcq_questions(selected_skills, count=20))

    # Phase 2: 3 moderate coding (random via $sample, 10 marks each)
    moderate_docs = []
    seen_moderate_ids = set()
    prioritized_moderate = _prioritize_skills(selected_skills, db.questions_moderate, VALID_DESC_QUERY)
    for skill, count in _distribute(prioritized_moderate, 3).items():
        if count == 0:
            continue
        candidates = _expand_skill(skill)
        pattern = _build_skill_regex(candidates)
        match_query = {"skill": {"$regex": pattern, "$options": "i"}, **VALID_DESC_QUERY}
        if seen_moderate_ids:
            match_query["_id"] = {"$nin": list(seen_moderate_ids)}

        matched = list(db.questions_moderate.aggregate([
            {"$match": match_query},
            {"$sample": {"size": max(count * 3, 5)}}
        ]))
        matched = [d for d in matched if not _is_subjective_doc(d)][:count]
        moderate_docs.extend(matched)
        seen_moderate_ids.update(d["_id"] for d in matched)

    # Backfill moderate questions if skills didn't have enough
    if len(moderate_docs) < 3:
        needed = 3 - len(moderate_docs)
        seen_ids = list(seen_moderate_ids)
        backfill = list(db.questions_moderate.aggregate([
            {"$match": {"_id": {"$nin": seen_ids}, **VALID_DESC_QUERY}},
            {"$sample": {"size": max(needed * 3, 10)}}
        ]))
        backfill = [d for d in backfill if not _is_subjective_doc(d)][:needed]
        moderate_docs.extend(backfill)
        seen_moderate_ids.update(d["_id"] for d in backfill)

    for doc in moderate_docs:
        # The assessment contract reserves all moderate slots for coding tasks.
        q_type = "coding"
        clean_t = _clean_title(doc.get("title", "Moderate Coding Problem"))
        clean_d = _clean_and_enrich_description(doc.get("description", ""), clean_t)

        # Look up reference solution if present in db.solutions
        sol = db.solutions.find_one({"skill": doc.get("skill"), "index": doc.get("index"), "difficulty": "moderate"})
        ref_sol = sol.get("reference_solution", "") if sol else ""
        expl = sol.get("explanation", "") if sol else ""
        tc = sol.get("time_complexity", "O(N)") if sol else "O(N)"
        sc = sol.get("space_complexity", "O(1)") if sol else "O(1)"

        all_questions.append({
            "public_data": {
                "question_id": str(doc["_id"]),
                "skill": doc["skill"], "difficulty": "moderate", "source": "database",
                "question_type": q_type, "title": clean_t, "description": clean_d,
                "marks": 10,
            },
            "evaluation_data": {
                "question_id": str(doc["_id"]),
                "question_index": doc.get("index"),
                "difficulty": "moderate",
                "max_marks": 10.0,
                "reference_solution": ref_sol,
                "explanation": expl,
                "time_complexity": tc,
                "space_complexity": sc,
            },
        })

    # Phase 3: 2 hard coding (circular tracker with subtopic routing)
    hard_docs = []
    seen_hard_ids = set()
    prioritized_hard = _prioritize_skills(selected_skills, db.questions_hard, VALID_DESC_QUERY)
    for skill, count in _distribute(prioritized_hard, 2).items():
        if count == 0:
            continue
        candidates = _expand_skill(skill)
        pattern = _build_skill_regex(candidates)

        # Check if direct hard questions exist for skill with valid descriptions
        direct_query = {"skill": {"$regex": f"^{re.escape(skill)}$", "$options": "i"}, **VALID_DESC_QUERY}
        if db.questions_hard.count_documents(direct_query) > 0:
            direct_match = db.questions_hard.find_one(direct_query)
            canonical_skill = direct_match["skill"] if direct_match and "skill" in direct_match else skill
            fetched = get_hard_questions(db, user_id, canonical_skill, count=count * 2)
            fetched = [d for d in fetched if not _is_subjective_doc(d) and d["_id"] not in seen_hard_ids][:count]
            hard_docs.extend(fetched)
            seen_hard_ids.update(d["_id"] for d in fetched)
        else:
            # Route through available subtopics in questions_hard
            avail = db.questions_hard.distinct("skill", {"skill": {"$regex": pattern, "$options": "i"}, **VALID_DESC_QUERY})
            if avail:
                sub_counts = _distribute(avail, count)
                for sub_skill, sub_c in sub_counts.items():
                    if sub_c > 0:
                        fetched = get_hard_questions(db, user_id, sub_skill, count=sub_c * 2)
                        fetched = [d for d in fetched if not _is_subjective_doc(d) and d["_id"] not in seen_hard_ids][:sub_c]
                        hard_docs.extend(fetched)
                        seen_hard_ids.update(d["_id"] for d in fetched)
            else:
                matched = list(db.questions_hard.aggregate([
                    {"$match": {"skill": {"$regex": pattern, "$options": "i"}, **VALID_DESC_QUERY}},
                    {"$sample": {"size": max(count * 3, 5)}}
                ]))
                matched = [d for d in matched if not _is_subjective_doc(d) and d["_id"] not in seen_hard_ids][:count]
                hard_docs.extend(matched)
                seen_hard_ids.update(d["_id"] for d in matched)

    # Backfill hard questions if needed
    if len(hard_docs) < 2:
        needed = 2 - len(hard_docs)
        seen_ids = list(seen_hard_ids)
        backfill = list(db.questions_hard.aggregate([
            {"$match": {"_id": {"$nin": seen_ids}, **VALID_DESC_QUERY}},
            {"$sample": {"size": max(needed * 3, 10)}}
        ]))
        backfill = [d for d in backfill if not _is_subjective_doc(d)][:needed]
        hard_docs.extend(backfill)
        seen_hard_ids.update(d["_id"] for d in backfill)

    for doc in hard_docs:
        # The assessment contract reserves all hard slots for coding tasks.
        q_type = "coding"
        clean_t = _clean_title(doc.get("title", "Hard Algorithmic Challenge"))
        clean_d = _clean_and_enrich_description(doc.get("description", ""), clean_t)

        # Look up reference solution if present in db.solutions
        sol = db.solutions.find_one({"skill": doc.get("skill"), "index": doc.get("index"), "difficulty": "hard"})
        ref_sol = sol.get("reference_solution", "") if sol else ""
        expl = sol.get("explanation", "") if sol else ""
        tc = sol.get("time_complexity", "O(N²)") if sol else "O(N²)"
        sc = sol.get("space_complexity", "O(N)") if sol else "O(N)"

        all_questions.append({
            "public_data": {
                "question_id": str(doc["_id"]),
                "skill": doc["skill"], "difficulty": "hard", "source": "database",
                "question_type": q_type, "title": clean_t, "description": clean_d,
                "marks": 25,
            },
            "evaluation_data": {
                "question_id": str(doc["_id"]),
                "question_index": doc.get("index"),
                "difficulty": "hard",
                "max_marks": 25.0,
                "reference_solution": ref_sol,
                "explanation": expl,
                "time_complexity": tc,
                "space_complexity": sc,
            },
        })

    # Final assembly: assign q_index 0-24, split public vs secret
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

    started_dt = datetime.now(timezone.utc)
    expires_dt = started_dt + timedelta(minutes=time_limit_minutes)
    started_at = started_dt.isoformat()
    expires_at = expires_dt.isoformat()

    session_out = TestSessionOut(
        session_id=session_id,
        user_id=user_id,
        mode=mode,
        skills_tested=selected_skills,
        total_questions=len(public_questions),
        questions=public_questions,
        created_at=started_at,
        time_limit_minutes=time_limit_minutes,
        started_at=started_at,
        expires_at=expires_at,
    )

    return {
        "session_id": session_id,
        "user_id": user_id,
        "mode": mode,
        "frontend_payload": session_out.model_dump(),
        "evaluation_key": evaluation_key,
        "time_limit_minutes": time_limit_minutes,
        "started_at": started_at,
        "expires_at": expires_at,
    }
