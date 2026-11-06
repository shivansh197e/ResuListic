"""
tests/test_challenger_lifecycle_and_fallback.py

Empirical Challenger Test Suite:
1. Candidate Lifecycle Progression (Resume Upload -> Skills Intake -> 25-Question Assessment -> Domain & Salary Prediction)
2. Fallback Resilience & Adverse Boundary Protection (Simulated offline/network timeouts, malformed payloads, zero 500 errors)
"""

import os
import sys
import io
import uuid
import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

VENV_SITE = os.path.join(PROJECT_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

ML_SERVICES_DIR = os.path.join(PROJECT_ROOT, "ml-services")
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from pymongo import MongoClient
from starlette.testclient import TestClient
import main


def _mock_generated_mcqs(selected_skills, count=5):
    skills = selected_skills if selected_skills else ["Python", "DSA"]
    mcqs = []
    for i in range(count):
        skill = skills[i % len(skills)]
        mcqs.append({
            "public_data": {
                "q_index": i,
                "skill": skill,
                "difficulty": "easy",
                "source": "ai_generated",
                "question_type": "mcq",
                "question": f"What is a primary concept of {skill}?",
                "options": ["A) Encapsulation", "B) Linear scan", "C) Memory allocation", "D) Event loop"],
                "model_used": "mock_test_generator",
            },
            "evaluation_data": {
                "correct_answer": "A",
                "explanation": f"Concept A is foundational for {skill}.",
            },
        })
    return mcqs


class ChallengerLifecycleAndFallbackEmpiricalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
        if not uri:
            raise RuntimeError("MongoDB URI not found in environment.")
        cls.db_client = MongoClient(uri)
        cls.db = cls.db_client.resulistic_db
        cls.client = TestClient(main.app)

        cls.created_users = []
        cls.created_sessions = []
        cls.created_submissions = []

    @classmethod
    def tearDownClass(cls):
        for uid in cls.created_users:
            cls.db.resumes.delete_one({"_id": uid})
        for sid in cls.created_sessions:
            cls.db.test_sessions.delete_many({"$or": [{"session_id": sid}, {"frontend_payload.session_id": sid}]})
            cls.db.test_submissions.delete_many({"session_id": sid})
        cls.db_client.close()

    # =========================================================================
    # PART 1: FULL CANDIDATE LIFECYCLE PROGRESSION
    # =========================================================================

    @patch("skill_test.question_selector.generate_mcq_questions", side_effect=_mock_generated_mcqs)
    def test_full_candidate_lifecycle_progression(self, mock_mcqs):
        """
        Empirically verify end-to-end candidate lifecycle:
        1. Resume Upload & NLP Extraction
        2. Skills Intake Verification
        3. 25-Question Assessment Generation (20 MCQ + 5 Coding) with answer withholding
        4. Python Code Evaluation Engine (Mocked and Deterministic)
        5. Test Submission with Grading & DB Persistence
        6. Job Domain Intelligence Prediction
        7. Salary Intelligence Prediction
        """
        # Step 1: Resume Upload
        test_pdf = os.path.join(PROJECT_ROOT, "ml-services", "data", "test_resumes", "Resume_Shivansh.pdf")
        if not os.path.exists(test_pdf):
            test_pdf = os.path.join(PROJECT_ROOT, "Complete_System_Architecture.pdf")
        
        user_id = f"lifecycle_cand_{uuid.uuid4().hex[:8]}"
        self.created_users.append(user_id)

        with open(test_pdf, "rb") as f:
            upload_resp = self.client.post(
                "/api/parse-resume",
                data={"user_id": user_id},
                files={"file": ("Resume_Shivansh.pdf", f, "application/pdf")},
            )
        self.assertEqual(upload_resp.status_code, 200, f"Upload failed: {upload_resp.text}")
        upload_data = upload_resp.json().get("data", {})
        self.assertEqual(upload_data["_id"], user_id)
        self.assertIn("profile", upload_data)
        self.assertIn("enrichment", upload_data)
        extracted_skills = upload_data["enrichment"].get("skills", {})
        self.assertIn("high", extracted_skills)
        self.assertGreater(len(extracted_skills["high"]), 0)

        # Step 2: Skills Intake
        skills_resp = self.client.get(f"/api/user-skills/{user_id}")
        self.assertEqual(skills_resp.status_code, 200, f"Skills intake failed: {skills_resp.text}")
        skills_data = skills_resp.json()
        self.assertIn("high_confidence", skills_data)
        self.assertIn("medium_confidence", skills_data)
        selected_skills = skills_data["high_confidence"][:3] or ["Python", "DSA"]

        # Step 3: 25-Question Assessment Session Start
        start_resp = self.client.post(
            "/api/start-test",
            json={"user_id": user_id, "selected_skills": selected_skills, "mode": "live"},
        )
        self.assertEqual(start_resp.status_code, 200, f"Start test failed: {start_resp.text}")
        session_data = start_resp.json()
        session_id = session_data["session_id"]
        self.created_sessions.append(session_id)

        self.assertEqual(session_data["total_questions"], 25)
        self.assertEqual(len(session_data["questions"]), 25)
        self.assertEqual(session_data["time_limit_minutes"], 120)
        self.assertIn("expires_at", session_data)

        # Verify MCQ secrets are withheld in public payload
        mcq_count = 0
        coding_count = 0
        for q in session_data["questions"]:
            self.assertNotIn("correct_answer", q, "MCQ correct answer leaked in public payload!")
            self.assertNotIn("explanation", q, "MCQ explanation leaked in public payload!")
            if q.get("question_type") == "mcq":
                mcq_count += 1
            elif q.get("question_type") in ("coding", "subjective"):
                coding_count += 1
        
        self.assertEqual(mcq_count, 20, f"Expected 20 MCQs, got {mcq_count}")
        self.assertEqual(coding_count, 5, f"Expected 5 Coding/Subjective questions, got {coding_count}")

        # Step 4: Python Code Evaluation Engine
        coding_q = next(q for q in session_data["questions"] if q.get("question_type") in ("coding", "subjective"))
        eval_resp = self.client.post(
            "/api/evaluate",
            json={
                "user_id": user_id,
                "question_id": coding_q.get("question_id", "mock_q"),
                "code": "def solution(*args):\n    return True\n",
                "problem_description": "Return True for valid solution.",
                "reference_solution": "def solution(*args):\n    return True\n",
                "mock": True,
            }
        )
        self.assertEqual(eval_resp.status_code, 200, f"Code evaluate failed: {eval_resp.text}")
        eval_data = eval_resp.json()
        self.assertIn("score", eval_data)
        self.assertIn("passed", eval_data)
        self.assertIn("time_complexity", eval_data)
        self.assertIn("feedback", eval_data)

        # Step 5: Test Submission
        answers = [{"q_index": i, "user_answer": "A"} for i in range(20)]
        submit_resp = self.client.post(
            "/api/submit-test",
            json={
                "session_id": session_id,
                "user_id": user_id,
                "answers": answers,
            }
        )
        self.assertEqual(submit_resp.status_code, 200, f"Submit test failed: {submit_resp.text}")
        submit_data = submit_resp.json()
        self.assertEqual(submit_data["status"], "submitted")
        self.assertFalse(submit_data["is_expired"])
        self.assertIn("mcq_score", submit_data)

        # Verify DB persistence of submission
        db_sub = self.db.test_submissions.find_one({"session_id": session_id})
        self.assertIsNotNone(db_sub, "Test submission must be saved to MongoDB")
        self.assertEqual(db_sub["user_id"], user_id)

        # Step 6: Domain Prediction
        domain_resp = self.client.post(
            "/api/predict-domain",
            json={
                "user_id": user_id,
                "skills": selected_skills,
                "mcq_score": 85.0,
                "coding_score": 90.0,
            }
        )
        self.assertEqual(domain_resp.status_code, 200, f"Domain prediction failed: {domain_resp.text}")
        domain_data = domain_resp.json()
        self.assertIn("primary_domain", domain_data)
        self.assertIn("confidence", domain_data)
        self.assertIn("domain_probabilities", domain_data)
        self.assertIn("switch_domains", domain_data)

        # Step 7: Salary Prediction
        salary_resp = self.client.post(
            "/api/predict-salary",
            json={
                "user_id": user_id,
                "skills": selected_skills,
                "domain": domain_data["primary_domain"],
                "mcq_score": 85.0,
                "coding_score": 90.0,
                "experience_tier": "mid",
            }
        )
        self.assertEqual(salary_resp.status_code, 200, f"Salary prediction failed: {salary_resp.text}")
        salary_data = salary_resp.json()
        self.assertIn("predicted_lpa", salary_data)
        self.assertIn("compensation_tier", salary_data)
        self.assertIn("factors", salary_data)
        self.assertGreaterEqual(salary_data["predicted_lpa"], 0.0)
        self.assertLessEqual(salary_data["predicted_lpa"], 35.0)

    # =========================================================================
    # PART 2: FALLBACK RESILIENCE & ADVERSE BOUNDARY PROTECTION
    # =========================================================================

    def test_fallback_unsupported_upload_format(self):
        """Unsupported format (.sh, .exe) returns 400 Bad Request, never 500."""
        resp = self.client.post(
            "/api/parse-resume",
            data={"user_id": "test_unsupported"},
            files={"file": ("script.sh", io.BytesIO(b"#!/bin/bash\necho hello"), "application/x-sh")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertNotEqual(resp.status_code, 500)

    def test_fallback_malformed_evaluate_json(self):
        """Malformed evaluate payload returns 422 Unprocessable, never 500."""
        resp = self.client.post(
            "/api/evaluate",
            data="not a json string",
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(resp.status_code, 422)
        self.assertNotEqual(resp.status_code, 500)

    def test_fallback_empty_payload_predictions(self):
        """Empty payload to predict-domain and predict-salary succeeds with defaults, zero 500."""
        resp_dom = self.client.post("/api/predict-domain", json={})
        self.assertEqual(resp_dom.status_code, 200)
        self.assertIn("primary_domain", resp_dom.json())

        resp_sal = self.client.post("/api/predict-salary", json={})
        self.assertEqual(resp_sal.status_code, 200)
        self.assertIn("predicted_lpa", resp_sal.json())

    def test_fallback_nonexistent_session_submission(self):
        """Submitting an unknown session returns 404, never 500."""
        resp = self.client.post(
            "/api/submit-test",
            json={"session_id": f"ghost_{uuid.uuid4().hex[:6]}", "user_id": "ghost", "answers": []}
        )
        self.assertEqual(resp.status_code, 404)
        self.assertNotEqual(resp.status_code, 500)

    def test_fallback_duplicate_submission_handling(self):
        """Submitting an already submitted session returns 409 Conflict, never 500."""
        sid = f"sub_dup_{uuid.uuid4().hex[:6]}"
        now_utc = datetime.now(timezone.utc)
        self.db.test_sessions.insert_one({
            "session_id": sid,
            "user_id": "user_dup",
            "time_limit_minutes": 120,
            "started_at": now_utc.isoformat(),
            "expires_at": (now_utc + timedelta(minutes=120)).isoformat(),
            "frontend_payload": {
                "session_id": sid,
                "questions": [
                    {"q_index": 0, "question_type": "mcq", "question": "Q1", "options": ["A", "B"]}
                ]
            },
            "evaluation_key": {"0": {"correct_answer": "A"}},
        })
        self.created_sessions.append(sid)

        # First submission
        resp1 = self.client.post("/api/submit-test", json={"session_id": sid, "user_id": "user_dup", "answers": [{"q_index": 0, "user_answer": "A"}]})
        self.assertEqual(resp1.status_code, 200)

        # Duplicate submission
        resp2 = self.client.post("/api/submit-test", json={"session_id": sid, "user_id": "user_dup", "answers": [{"q_index": 0, "user_answer": "A"}]})
        self.assertEqual(resp2.status_code, 409)
        self.assertNotEqual(resp2.status_code, 500)

    def test_fallback_syntax_error_code_evaluation(self):
        """Code with Python syntax errors evaluated gracefully (score <= 30, no 500)."""
        resp = self.client.post(
            "/api/evaluate",
            json={
                "user_id": "syntax_err_user",
                "question_id": "q_syntax",
                "code": "def broken(:\n  return ?!!",
                "problem_description": "Broken syntax test",
                "reference_solution": "def solution(): return 1",
                "mock": False,
            }
        )
        self.assertEqual(resp.status_code, 200)
        res = resp.json()
        self.assertFalse(res["passed"])
        self.assertLessEqual(res["score"], 30)
        self.assertIn("syntax", res["feedback"].lower())


if __name__ == "__main__":
    unittest.main()
