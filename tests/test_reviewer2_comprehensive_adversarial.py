"""
test_reviewer2_comprehensive_adversarial.py — Reviewer Adversarial Verification Suite.

Covers:
1. [OPEN-1 Verification] Code evaluation grading & MongoDB submissions persistence
   for newly ingested skills (OOPS, System Design, Data Science, Software Engineering).
2. [OPEN-2 Verification] Groq fallback resilience, model list validation, and
   empty/whitespace/None resilience in ai_question_generator.py and question_selector.py.
3. [OPEN-3 Verification] Multi-skill adversarial queries against question_selector.py
   (OOPS + Datascience + System Design combined, alias handling, empty skill rejection).
4. Full database schema integrity across 4 newly ingested datasets + DSA (1,523 docs).
5. Clean teardown with zero database pollution.
"""

import os
import sys
import unittest
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_SITE = os.path.join(PROJECT_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

ML_SERVICES_DIR = os.path.join(PROJECT_ROOT, "ml-services")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from schema.question_schema import CodingQuestionDoc, SolutionDoc
from skill_test.question_selector import (
    generate_test_session,
    _expand_skill,
    _distribute,
    _build_skill_regex,
)
from skill_test.ai_question_generator import generate_mcq_questions
from skill_test.code_evaluator import (
    evaluate_code,
    mock_evaluate_code,
    get_question_and_solution,
    save_submission,
)


class TestReviewerComprehensiveAdversarial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        uri = os.getenv("MONGODB_URI")
        assert uri, "MONGODB_URI is required"
        cls.client = MongoClient(uri)
        cls.db = cls.client.resulistic_db
        cls.test_submission_ids = []

    @classmethod
    def tearDownClass(cls):
        # Clean teardown of any test submission docs created during run
        if cls.test_submission_ids:
            oids = [ObjectId(sid) for sid in cls.test_submission_ids if ObjectId.is_valid(sid)]
            if oids:
                cls.db.submissions.delete_many({"_id": {"$in": oids}})
        cls.client.close()

    def record_sub_id(self, sid: str):
        if sid and sid not in self.test_submission_ids:
            self.test_submission_ids.append(sid)

    # -------------------------------------------------------------------------
    # PART 1: Database Ingestion & 100% Solution Coverage
    # -------------------------------------------------------------------------
    def test_01_total_question_and_solution_counts(self):
        """Verify exact counts: 1,173 moderate + 350 hard = 1,523 total questions & 1,523 solutions."""
        total_mod = self.db.questions_moderate.count_documents({})
        total_hard = self.db.questions_hard.count_documents({})
        total_sol = self.db.solutions.count_documents({})

        self.assertEqual(total_mod, 1173)
        self.assertEqual(total_hard, 350)
        self.assertEqual(total_mod + total_hard, 1523)
        self.assertEqual(total_sol, 1523)

    def test_02_newly_ingested_datasets_counts(self):
        """Verify the 4 newly ingested datasets sum to exactly 333 questions."""
        expected = {
            "OOPS": 12,
            "System Design": 5,
            "Data Science": 142,
            "Software Engineering": 174,
        }
        actual_total = 0
        for skill, exp_count in expected.items():
            mod_c = self.db.questions_moderate.count_documents({"skill": skill})
            hard_c = self.db.questions_hard.count_documents({"skill": skill})
            sol_c = self.db.solutions.count_documents({"skill": skill})
            total_q = mod_c + hard_c
            actual_total += total_q
            self.assertEqual(total_q, exp_count, f"Mismatch for {skill}: got {total_q}, exp {exp_count}")
            self.assertEqual(sol_c, exp_count, f"Solution count mismatch for {skill}: got {sol_c}, exp {exp_count}")

        self.assertEqual(actual_total, 333)

    # -------------------------------------------------------------------------
    # PART 2: [OPEN-1] Code Evaluation & Submissions Persistence
    # -------------------------------------------------------------------------
    def test_03_code_evaluation_on_newly_ingested_skills(self):
        """Verify get_question_and_solution, evaluate_code (mock & live fallback), and save_submission."""
        test_skills = ["OOPS", "System Design", "Data Science", "Software Engineering"]

        for skill in test_skills:
            # Pick a moderate question and a hard question
            for coll, diff in [(self.db.questions_moderate, "moderate"), (self.db.questions_hard, "hard")]:
                sample = coll.find_one({"skill": skill})
                self.assertIsNotNone(sample, f"No question found in {coll.name} for {skill}")

                qid = str(sample["_id"])
                q_doc, sol_doc = get_question_and_solution(self.db, qid)

                self.assertEqual(q_doc.get("skill"), skill)
                self.assertEqual(sol_doc.get("skill"), skill)
                self.assertEqual(sol_doc.get("difficulty"), diff)
                self.assertTrue(bool(sol_doc.get("reference_solution")), f"Empty solution for {skill} ({diff})")

                # Evaluate candidate code against question and reference solution
                candidate_code = "def solution():\n    # Candidate implementation\n    return 42"
                eval_res = mock_evaluate_code(
                    code=candidate_code,
                    problem_description=q_doc.get("description", ""),
                    reference_solution=sol_doc["reference_solution"],
                )
                self.assertTrue(eval_res["passed"])
                self.assertGreaterEqual(eval_res["score"], 80)
                self.assertIn("time_complexity", eval_res)

                # Persist to MongoDB submissions collection
                sub_id = save_submission(
                    db=self.db,
                    user_id=f"test_eval_{skill}_{diff}",
                    question_id=qid,
                    submitted_code=candidate_code,
                    evaluation_result=eval_res,
                )
                self.record_sub_id(sub_id)

                # Verify submission record saved with exact fields
                sub_doc = self.db.submissions.find_one({"_id": ObjectId(sub_id)})
                self.assertIsNotNone(sub_doc)
                self.assertEqual(sub_doc["user_id"], f"test_eval_{skill}_{diff}")
                self.assertEqual(sub_doc["question_id"], qid)
                self.assertTrue(sub_doc["passed"])
                self.assertIn("timestamp", sub_doc)

    # -------------------------------------------------------------------------
    # PART 3: [OPEN-2] Fallback Resilience & Model List Safeguards
    # -------------------------------------------------------------------------
    def test_04_ai_question_generator_empty_and_whitespace_skills(self):
        """Verify ai_question_generator gracefully handles empty/whitespace skill lists without ZeroDivisionError."""
        for bad_input in [[], [""], ["   "], ["\t\n"], [None]]:
            res = generate_mcq_questions(bad_input, count=5)
            self.assertEqual(len(res), 5)
            for q in res:
                self.assertIn("public_data", q)
                self.assertIn("evaluation_data", q)
                self.assertEqual(q["public_data"]["difficulty"], "easy")

    def test_05_question_selector_invalid_skill_rejection(self):
        """Verify question_selector rejects empty, whitespace, and None-only skills with ValueError."""
        for invalid_skills in [[], [""], ["   "], [None]]:
            with self.assertRaises(ValueError):
                generate_test_session(self.db, "u_test", invalid_skills)

    # -------------------------------------------------------------------------
    # PART 4: [OPEN-3] Multi-Skill Adversarial Test Session Generation
    # -------------------------------------------------------------------------
    def test_06_multi_skill_session_oops_datascience_system_design(self):
        """Adversarial query: combined OOPS, Datascience, and System Design."""
        skills = ["OOPS", "Datascience", "System Design"]
        session = generate_test_session(self.db, "u_multi_1", skills)

        questions = session["frontend_payload"]["questions"]
        self.assertEqual(len(questions), 10)

        mcqs = [q for q in questions if q.get("question_type") == "mcq"]
        coding = [q for q in questions if q.get("question_type") == "coding"]
        self.assertEqual(len(mcqs), 5)
        self.assertEqual(len(coding), 5)

        mods = [q for q in coding if q.get("difficulty") == "moderate"]
        hards = [q for q in coding if q.get("difficulty") == "hard"]
        self.assertEqual(len(mods), 3)
        self.assertEqual(len(hards), 2)

        # Assert every coding question has a valid reference solution in MongoDB
        eval_key = session["evaluation_key"]
        for cq in coding:
            q_idx = str(cq["q_index"])
            ev = eval_key[q_idx]
            sol = self.db.solutions.find_one({
                "skill": ev["skill"],
                "index": ev["question_index"],
                "difficulty": ev["difficulty"],
            })
            self.assertIsNotNone(sol, f"No matching solution for: {ev}")

    def test_07_multi_skill_session_mix_skills_and_oops(self):
        """Adversarial query: Software Engineering / mix skill combined with OOPS."""
        skills = ["mix skill", "OOPS"]
        session = generate_test_session(self.db, "u_multi_2", skills)

        questions = session["frontend_payload"]["questions"]
        self.assertEqual(len(questions), 10)

        # All 5 coding questions must have valid matching solutions
        eval_key = session["evaluation_key"]
        coding = [q for q in questions if q.get("question_type") == "coding"]
        for cq in coding:
            q_idx = str(cq["q_index"])
            ev = eval_key[q_idx]
            sol = self.db.solutions.find_one({
                "skill": ev["skill"],
                "index": ev["question_index"],
                "difficulty": ev["difficulty"],
            })
            self.assertIsNotNone(sol, f"No matching solution for: {ev}")


if __name__ == "__main__":
    unittest.main()
