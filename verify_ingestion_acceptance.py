"""
verify_ingestion_acceptance.py — Programmatic verification script for ResuListic ETL ingestion.
Verifies:
1. Question counts across 4 dataset folders (OOPS=12, System Design=5, Data Science=142, Software Engineering=174 -> Total 333)
2. All 5 dataset domains present in questions_moderate, questions_hard, and solutions.
3. 100% matching reference solutions in solutions collection.
4. Document schema conformity with CodingQuestionDoc and SolutionDoc.
5. Test session generation (25 questions each) for OOPS, Datascience, System Design, and mix skill.
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_venv_site = os.path.join(_PROJECT_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(_venv_site) and _venv_site not in sys.path:
    sys.path.insert(0, _venv_site)

sys.path.append(os.path.join(_PROJECT_ROOT, "ml-services"))

from dotenv import load_dotenv
from pymongo import MongoClient
from schema.question_schema import CodingQuestionDoc, SolutionDoc
from skill_test.question_selector import generate_test_session

load_dotenv()


def main():
    uri = os.getenv("MONGODB_URI")
    assert uri, "MONGODB_URI environment variable must be set"
    client = MongoClient(uri)
    db = client["resulistic_db"]

    print("=" * 70)
    print("STEP 0: Verifying and Ensuring MongoDB Collection Indexes")
    print("=" * 70)
    db.questions_moderate.create_index([("skill", 1), ("index", 1)], unique=True)
    db.questions_moderate.create_index([("skill", 1)])
    db.questions_hard.create_index([("skill", 1), ("index", 1)], unique=True)
    db.questions_hard.create_index([("skill", 1)])
    db.solutions.create_index([("skill", 1), ("index", 1), ("difficulty", 1)], unique=True)
    db.solutions.create_index([("skill", 1)])
    print("[PASS] Collection indexes confirmed on questions_moderate, questions_hard, solutions.")

    print("\n" + "=" * 70)
    print("STEP 1: Verifying Question Counts across the 4 Ingested Datasets")
    print("=" * 70)

    expected_datasets = {
        "OOPS": {"mod": 8, "hard": 4, "total": 12},
        "System Design": {"mod": 3, "hard": 2, "total": 5},
        "Data Science": {"mod": 100, "hard": 42, "total": 142},
        "Software Engineering": {"mod": 98, "hard": 76, "total": 174},
    }

    ingested_sum = 0
    for skill, exp in expected_datasets.items():
        m_count = db.questions_moderate.count_documents({"skill": skill})
        h_count = db.questions_hard.count_documents({"skill": skill})
        total = m_count + h_count
        ingested_sum += total
        print(f"  Skill '{skill}': Moderate={m_count}/{exp['mod']}, Hard={h_count}/{exp['hard']}, Total={total}/{exp['total']}")
        assert m_count == exp["mod"], f"Moderate count mismatch for {skill}: got {m_count}, expected {exp['mod']}"
        assert h_count == exp["hard"], f"Hard count mismatch for {skill}: got {h_count}, expected {exp['hard']}"
        assert total == exp["total"], f"Total count mismatch for {skill}: got {total}, expected {exp['total']}"

    print(f"\n[PASS] Total questions ingested across the 4 target datasets: {ingested_sum} (Expected: 333)")
    assert ingested_sum == 333, f"Expected 333 total ingested questions, got {ingested_sum}"

    print("\n" + "=" * 70)
    print("STEP 2: Verifying Presence of All 5 Dataset Domains in All Collections")
    print("=" * 70)

    domains = ["Data Structures", "Data Science", "Software Engineering", "OOPS", "System Design"]
    for d in domains:
        m_c = db.questions_moderate.count_documents({"skill": d})
        h_c = db.questions_hard.count_documents({"skill": d})
        s_c = db.solutions.count_documents({"skill": d})
        print(f"  Domain '{d}': Moderate={m_c}, Hard={h_c}, Solutions={s_c}")
        assert m_c > 0, f"Domain {d} missing from questions_moderate"
        assert h_c > 0, f"Domain {d} missing from questions_hard"
        assert s_c > 0, f"Domain {d} missing from solutions"

    print("[PASS] All 5 domains confirmed in questions_moderate, questions_hard, and solutions.")

    print("\n" + "=" * 70)
    print("STEP 3: Verifying 100% Matching Reference Solutions")
    print("=" * 70)

    # Fetch all solutions in a single query for fast, deterministic in-memory validation
    sols_map = {(s["skill"], s["index"], s["difficulty"]): s for s in db.solutions.find()}
    print(f"  Loaded {len(sols_map)} solutions from MongoDB Atlas into verification map.")

    total_checked = 0
    missing_solutions = []

    for col_name, diff in [("questions_moderate", "moderate"), ("questions_hard", "hard")]:
        coll = db[col_name]
        for doc in coll.find():
            total_checked += 1
            sk, idx = doc.get("skill"), doc.get("index")
            sol = sols_map.get((sk, idx, diff))
            if not sol:
                missing_solutions.append({"skill": sk, "index": idx, "difficulty": diff, "title": doc.get("title")})
            else:
                assert sol.get("reference_solution"), f"Empty solution for {sk} idx {idx}"

    # Also spot-check indexed direct queries against MongoDB Atlas
    for skill in expected_datasets.keys():
        for diff in ("moderate", "hard"):
            spot = db.solutions.find_one({"skill": skill, "index": 0, "difficulty": diff})
            assert spot is not None, f"Direct indexed query failed for {skill} {diff}"
            assert spot.get("reference_solution"), f"Empty solution on spot check for {skill} {diff}"

    print(f"  Total questions checked across Atlas: {total_checked}")
    print(f"  Missing solutions count: {len(missing_solutions)}")
    assert len(missing_solutions) == 0, f"Found {len(missing_solutions)} missing solutions: {missing_solutions[:5]}"
    print("[PASS] 100% of inserted questions have matching valid reference solutions.")

    print("\n" + "=" * 70)
    print("STEP 4: Verifying Document Schema Adherence (CodingQuestionDoc & SolutionDoc)")
    print("=" * 70)

    schema_validated = 0
    for skill in expected_datasets.keys():
        for coll, diff in [(db.questions_moderate, "moderate"), (db.questions_hard, "hard")]:
            for doc in coll.find({"skill": skill}):
                # Validate question doc schema
                q_model = CodingQuestionDoc(
                    skill=doc["skill"],
                    index=doc["index"],
                    title=doc["title"],
                    description=doc["description"],
                    source=doc.get("source", "manual"),
                    source_url=doc.get("source_url", ""),
                    tags=doc.get("tags", []),
                )
                assert isinstance(q_model.title, str) and len(q_model.title) > 0
                assert isinstance(q_model.description, str) and len(q_model.description) > 0
                assert isinstance(q_model.index, int)
                assert isinstance(q_model.tags, list)

                # Validate solution doc schema
                sol_raw = sols_map.get((skill, doc["index"], diff))
                assert sol_raw is not None, f"Solution missing for {skill} {doc['index']} {diff}"
                s_model = SolutionDoc(
                    skill=sol_raw["skill"],
                    index=sol_raw["index"],
                    difficulty=sol_raw["difficulty"],
                    reference_solution=sol_raw["reference_solution"],
                    explanation=sol_raw.get("explanation", ""),
                )
                assert isinstance(s_model.reference_solution, str) and len(s_model.reference_solution) > 0
                schema_validated += 1

    print(f"[PASS] Successfully schema-validated all {schema_validated} documents for target skills.")

    print("\n" + "=" * 70)
    print("STEP 5: Verifying Test Session Generation for Target Skills")
    print("=" * 70)

    test_skills = ["OOPS", "Datascience", "System Design", "mix skill"]
    for skill in test_skills:
        print(f"  Generating 25-question session for skill '{skill}'...")
        session = generate_test_session(db, f"verify_{skill}_user", [skill])
        assert "frontend_payload" in session and "evaluation_key" in session
        questions = session["frontend_payload"]["questions"]
        assert len(questions) == 25, f"Expected 25 questions for {skill}, got {len(questions)}"

        mcqs = [q for q in questions if q.get("question_type") == "mcq"]
        coding = [q for q in questions if q.get("question_type") == "coding"]
        assert len(mcqs) == 20, f"Expected 20 MCQs for {skill}, got {len(mcqs)}"
        assert len(coding) == 5, f"Expected 5 coding questions for {skill}, got {len(coding)}"

        mods = [q for q in coding if q.get("difficulty") == "moderate"]
        hards = [q for q in coding if q.get("difficulty") == "hard"]
        assert len(mods) == 3, f"Expected 3 moderate coding questions for {skill}, got {len(mods)}"
        assert len(hards) == 2, f"Expected 2 hard coding questions for {skill}, got {len(hards)}"

        # Assert all coding questions have valid reference solutions in evaluation key
        eval_key = session["evaluation_key"]
        for cq in coding:
            q_idx = str(cq["q_index"])
            assert q_idx in eval_key, f"Missing evaluation key for q_index {q_idx}"
            ev = eval_key[q_idx]
            sol = db.solutions.find_one({
                "skill": ev["skill"],
                "index": ev["question_index"],
                "difficulty": ev["difficulty"],
            })
            assert sol is not None, f"Solution lookup failed for {ev}"

        print(f"    -> [SUCCESS] 25 questions (20 MCQs, 3 Moderate, 2 Hard) verified for '{skill}'.")

    print("\n" + "=" * 70)
    print("ALL ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
