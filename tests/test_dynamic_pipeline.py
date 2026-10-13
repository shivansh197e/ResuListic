"""
tests/test_dynamic_pipeline.py — Comprehensive Automated Verification Suite for
R1, R2, and R3 Dynamic Integration Remediation.

Covers:
1. R1: Pydantic Schema Alignment & Interoperability (camelCase vs snake_case).
2. R2: Frontend Dynamic Domain-to-Salary Pipeline Chaining & Parameter Standardization.
3. R3: Assessment Submission Score & Competency Synthesis in POST /api/submit-test.
4. R4: End-to-End Live Flow without Client Mock Fallbacks.
"""

import os
import sys
import uuid
import unittest
from datetime import datetime, timezone, timedelta
from starlette.testclient import TestClient

# Ensure repo root and ml-services are in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
ML_SERVICES_DIR = os.path.join(REPO_ROOT, "ml-services")
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

from main import app, test_sessions_collection, test_submissions_collection
from schema.question_schema import (
    PredictDomainRequest,
    PredictSalaryRequest,
    AnswerSubmission,
    TestSubmissionRequest,
    StartTestRequest,
    EvaluateRequest,
    TestSubmissionResponse,
)


class TestDynamicPipelineRemediation(unittest.TestCase):
    """Test suite verifying R1, R2, R3 dynamic integration remediation."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.created_sessions = []
        cls.created_submissions = []

    @classmethod
    def tearDownClass(cls):
        if cls.created_sessions:
            test_sessions_collection.delete_many({
                "$or": [
                    {"frontend_payload.session_id": {"$in": cls.created_sessions}},
                    {"session_id": {"$in": cls.created_sessions}},
                ]
            })
        if cls.created_submissions:
            test_submissions_collection.delete_many({
                "session_id": {"$in": cls.created_submissions}
            })

    def _create_session(self, session_id: str, skills: list, answers_key: dict):
        now_utc = datetime.now(timezone.utc)
        started_str = now_utc.isoformat()
        expires_str = (now_utc + timedelta(minutes=90)).isoformat()

        doc = {
            "session_id": session_id,
            "user_id": f"user_{session_id}",
            "time_limit_minutes": 90,
            "started_at": started_str,
            "expires_at": expires_str,
            "skills_tested": skills,
            "frontend_payload": {
                "session_id": session_id,
                "user_id": f"user_{session_id}",
                "skills_tested": skills,
                "total_questions": len(answers_key),
                "questions": [
                    {"q_index": int(k), "skill": v.get("skill", skills[0]), "question_type": "mcq"}
                    for k, v in answers_key.items()
                ],
                "created_at": started_str,
                "time_limit_minutes": 90,
                "started_at": started_str,
                "expires_at": expires_str,
            },
            "evaluation_key": answers_key,
        }
        test_sessions_collection.insert_one(doc)
        self.created_sessions.append(session_id)
        return doc

    # ── R1: Pydantic Schema Alignment Tests ─────────────────────────────────

    def test_r1_01_predict_domain_camelcase_and_snakecase(self):
        """R1: PredictDomainRequest parses camelCase and snake_case without nullifying scores."""
        # camelCase
        req_camel = PredictDomainRequest.model_validate({
            "userId": "usr_c1",
            "skills": ["React", "TypeScript"],
            "resumeText": "Experienced frontend engineer",
            "mcqScore": 92.5,
            "codingScore": 88.0,
        })
        self.assertEqual(req_camel.user_id, "usr_c1")
        self.assertEqual(req_camel.resume_text, "Experienced frontend engineer")
        self.assertEqual(req_camel.mcq_score, 92.5)
        self.assertEqual(req_camel.coding_score, 88.0)

        # snake_case
        req_snake = PredictDomainRequest.model_validate({
            "user_id": "usr_s1",
            "skills": ["React", "TypeScript"],
            "resume_text": "Experienced frontend engineer",
            "mcq_score": 92.5,
            "coding_score": 88.0,
        })
        self.assertEqual(req_snake.user_id, "usr_s1")
        self.assertEqual(req_snake.mcq_score, 92.5)
        self.assertEqual(req_snake.coding_score, 88.0)

    def test_r1_02_predict_salary_camelcase_and_snakecase(self):
        """R1: PredictSalaryRequest parses camelCase and snake_case correctly."""
        # camelCase
        sal_camel = PredictSalaryRequest.model_validate({
            "userId": "usr_sal_c",
            "skills": ["Docker", "Kubernetes"],
            "domain": "Cloud & DevOps",
            "mcqScore": 86.0,
            "codingScore": 91.0,
            "experienceTier": "mid",
        })
        self.assertEqual(sal_camel.user_id, "usr_sal_c")
        self.assertEqual(sal_camel.mcq_score, 86.0)
        self.assertEqual(sal_camel.coding_score, 91.0)
        self.assertEqual(sal_camel.experience_tier, "mid")

        # snake_case
        sal_snake = PredictSalaryRequest.model_validate({
            "user_id": "usr_sal_s",
            "skills": ["Docker", "Kubernetes"],
            "domain": "Cloud & DevOps",
            "mcq_score": 86.0,
            "coding_score": 91.0,
            "experience_tier": "mid",
        })
        self.assertEqual(sal_snake.user_id, "usr_sal_s")
        self.assertEqual(sal_snake.mcq_score, 86.0)
        self.assertEqual(sal_snake.coding_score, 91.0)

    def test_r1_03_submission_and_eval_schema_aliases(self):
        """R1: AnswerSubmission, StartTestRequest, and EvaluateRequest support camelCase."""
        # AnswerSubmission
        sub = AnswerSubmission.model_validate({
            "sessionId": "sess_123",
            "userId": "usr_456",
            "answers": [{"q_index": 0, "user_answer": "B"}],
        })
        self.assertEqual(sub.session_id, "sess_123")
        self.assertEqual(sub.user_id, "usr_456")

        # TestSubmissionRequest alias
        self.assertIs(TestSubmissionRequest, AnswerSubmission)

        # StartTestRequest
        start = StartTestRequest.model_validate({
            "userId": "usr_789",
            "selectedSkills": ["Python", "FastAPI"],
        })
        self.assertEqual(start.user_id, "usr_789")
        self.assertEqual(start.selected_skills, ["Python", "FastAPI"])

        # EvaluateRequest
        ev = EvaluateRequest.model_validate({
            "userId": "usr_ev",
            "questionId": "q_01",
            "code": "print('hello')",
            "problemDescription": "Print hello",
            "referenceSolution": "print('hello')",
        })
        self.assertEqual(ev.user_id, "usr_ev")
        self.assertEqual(ev.question_id, "q_01")
        self.assertEqual(ev.problem_description, "Print hello")
        self.assertEqual(ev.reference_solution, "print('hello')")

    def test_r1_04_api_predict_endpoints_with_camelcase(self):
        """R1: Live API endpoints accurately parse camelCase and do not fall back to 70.0 prior."""
        camel_payload = {
            "userId": "test_camel_user",
            "skills": ["React", "JavaScript"],
            "mcqScore": 94.0,
            "codingScore": 96.0,
        }
        res_domain = self.client.post("/api/predict-domain", json=camel_payload)
        self.assertEqual(res_domain.status_code, 200)
        dom_data = res_domain.json()
        self.assertEqual(dom_data["user_id"], "test_camel_user")
        # Overall test score is 0.4 * 94.0 + 0.6 * 96.0 = 95.2, NOT default 70.0!
        self.assertEqual(dom_data["overall_test_score"], 95.2)

        # Salary endpoint with camelCase
        camel_salary_payload = {
            "userId": "test_camel_user",
            "skills": ["React", "JavaScript"],
            "domain": "Frontend Web Development",
            "mcqScore": 94.0,
            "codingScore": 96.0,
            "experienceTier": "fresher",
        }
        res_salary = self.client.post("/api/predict-salary", json=camel_salary_payload)
        self.assertEqual(res_salary.status_code, 200)
        sal_data = res_salary.json()
        self.assertEqual(sal_data["overall_test_score"], 95.2)

    # ── R2: Frontend Dynamic Chaining & Standardization Tests ───────────────

    def test_r2_01_static_index_dynamic_chaining(self):
        """R2: static/index.html does not hardcode Frontend Web Development in predictSalary call."""
        html_path = os.path.join(REPO_ROOT, "static", "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Check ResultDashboard section
        self.assertIn("api.predictDomain", html)
        self.assertIn("api.predictSalary", html)

        # Ensure Promise.all concurrent dispatch with hardcoded domain is eliminated
        self.assertNotIn(
            "Promise.all([\n            api.predictDomain",
            html,
            "Promise.all with hardcoded parallel dispatch must be replaced by sequential chaining"
        )
        # Ensure predictSalary receives primaryDomain
        self.assertIn("domain: primaryDomain", html)
        self.assertIn("const primaryDomain = domainRes?.primary_domain", html)

    def test_r2_02_frontend_components_parity(self):
        """R2: frontend/src/components/ResultDashboard.jsx has dynamic chaining parity."""
        jsx_path = os.path.join(REPO_ROOT, "frontend", "src", "components", "ResultDashboard.jsx")
        with open(jsx_path, "r", encoding="utf-8") as f:
            jsx = f.read()

        self.assertIn("domain: primaryDomain", jsx)
        self.assertIn("const primaryDomain = domainRes?.primary_domain", jsx)

    # ── R3: Submit-Test Competency & Score Synthesis Tests ───────────────────

    def test_r3_01_submit_test_returns_all_required_fields(self):
        """R3: POST /api/submit-test returns score_percentage, correct_answers, total_questions, grade, skill_breakdown."""
        session_id = f"sess_r3_synth_{uuid.uuid4().hex[:6]}"
        self._create_session(
            session_id,
            skills=["Python", "DSA"],
            answers_key={
                "0": {"question_type": "mcq", "correct_answer": "B", "skill": "Python"},
                "1": {"question_type": "mcq", "correct_answer": "C", "skill": "DSA"},
            }
        )
        self.created_submissions.append(session_id)

        # Submit 2 correct answers (100%)
        sub_resp = self.client.post("/api/submit-test", json={
            "session_id": session_id,
            "user_id": f"user_{session_id}",
            "answers": [
                {"q_index": 0, "user_answer": "B"},
                {"q_index": 1, "user_answer": "C"},
            ]
        })
        self.assertEqual(sub_resp.status_code, 200)
        body = sub_resp.json()

        # Assert all R3 fields are present and authentic
        self.assertEqual(body["status"], "submitted")
        self.assertEqual(body["score"], 100.0)
        self.assertEqual(body["score_percentage"], 100.0)
        self.assertEqual(body["correct_answers"], 2)
        self.assertEqual(body["total_questions"], 2)
        self.assertEqual(body["grade"], "S+")
        self.assertIsInstance(body["skill_breakdown"], list)
        self.assertGreaterEqual(len(body["skill_breakdown"]), 2)

        # Check skill breakdown items
        skills_in_breakdown = [item["skill"] for item in body["skill_breakdown"]]
        self.assertIn("Python", skills_in_breakdown)
        self.assertIn("DSA", skills_in_breakdown)
        for item in body["skill_breakdown"]:
            self.assertIn("skill", item)
            self.assertIn("score", item)
            self.assertGreaterEqual(item["score"], 0.0)
            self.assertLessEqual(item["score"], 100.0)

        # Assert MongoDB document persistence
        db_doc = test_submissions_collection.find_one({"session_id": session_id})
        self.assertIsNotNone(db_doc)
        self.assertEqual(db_doc["correct_answers"], 2)
        self.assertEqual(db_doc["total_questions"], 2)
        self.assertEqual(db_doc["grade"], "S+")
        self.assertIsInstance(db_doc["skill_breakdown"], list)

    def test_r3_02_grade_boundaries(self):
        """R3: Grading thresholds are computed correctly (S+, A, B, C, D)."""
        test_cases = [
            (10, 10, "S+"),  # 100% >= 90
            (9, 10, "S+"),   # 90% >= 90
            (8, 10, "A"),    # 80% >= 80
            (7, 10, "B"),    # 70% >= 70
            (6, 10, "C"),    # 60% >= 60
            (5, 10, "D"),    # 50% < 60
            (0, 10, "D"),    # 0% < 60
        ]

        for correct_count, total_count, expected_grade in test_cases:
            sess_id = f"sess_grade_{correct_count}_{uuid.uuid4().hex[:6]}"
            answers_key = {
                str(i): {"question_type": "mcq", "correct_answer": "A", "skill": "Core"}
                for i in range(total_count)
            }
            self._create_session(sess_id, skills=["Core"], answers_key=answers_key)
            self.created_submissions.append(sess_id)

            answers = [
                {"q_index": i, "user_answer": "A" if i < correct_count else "B"}
                for i in range(total_count)
            ]
            resp = self.client.post("/api/submit-test", json={
                "session_id": sess_id,
                "user_id": f"user_{sess_id}",
                "answers": answers,
            })
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(
                resp.json()["grade"],
                expected_grade,
                f"Expected grade {expected_grade} for {correct_count}/{total_count}, got {resp.json()['grade']}"
            )

    def test_r3_03_zero_score_handling_in_frontend(self):
        """R3: Quiz handleSubmit does not convert 0 score to 94 due to falsy check."""
        html_path = os.path.join(REPO_ROOT, "static", "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Assert undefined check instead of falsy check
        self.assertIn("score_percentage: res.score !== undefined ? res.score : 94", html)
        self.assertNotIn("score_percentage: res.score || 94", html)

    # ── R4: End-to-End Live Workflow Integration ────────────────────────────

    def test_r4_01_full_live_dynamic_journey(self):
        """R4: Complete live pipeline execution: Submit -> Grade/Breakdown -> Predict Domain -> Predict Salary."""
        session_id = f"sess_e2e_{uuid.uuid4().hex[:6]}"
        user_id = f"user_e2e_{uuid.uuid4().hex[:6]}"

        # 1. Create session with Cloud & DevOps skills
        self._create_session(
            session_id,
            skills=["Docker", "Kubernetes", "AWS"],
            answers_key={
                "0": {"question_type": "mcq", "correct_answer": "A", "skill": "Docker"},
                "1": {"question_type": "mcq", "correct_answer": "A", "skill": "Kubernetes"},
            }
        )
        self.created_submissions.append(session_id)

        # 2. Submit test
        sub_resp = self.client.post("/api/submit-test", json={
            "session_id": session_id,
            "user_id": user_id,
            "answers": [
                {"q_index": 0, "user_answer": "A"},
                {"q_index": 1, "user_answer": "A"},
            ]
        })
        self.assertEqual(sub_resp.status_code, 200)
        sub_data = sub_resp.json()
        self.assertEqual(sub_data["score"], 100.0)
        self.assertEqual(sub_data["grade"], "S+")

        # 3. Dynamic Predict Domain using authentic score from submission
        domain_resp = self.client.post("/api/predict-domain", json={
            "user_id": user_id,
            "skills": ["Docker", "Kubernetes", "AWS"],
            "mcq_score": sub_data["score"],
            "coding_score": sub_data["score"],
        })
        self.assertEqual(domain_resp.status_code, 200)
        domain_data = domain_resp.json()
        primary_domain = domain_data["primary_domain"]
        self.assertEqual(primary_domain, "Cloud & DevOps")

        # 4. Dynamic Predict Salary chained directly with primary_domain
        salary_resp = self.client.post("/api/predict-salary", json={
            "user_id": user_id,
            "skills": ["Docker", "Kubernetes", "AWS"],
            "domain": primary_domain,
            "mcq_score": sub_data["score"],
            "coding_score": sub_data["score"],
            "experience_tier": "fresher",
        })
        self.assertEqual(salary_resp.status_code, 200)
        salary_data = salary_resp.json()

        # Verify salary benchmark evaluates Cloud & DevOps
        self.assertEqual(salary_data["domain"], "Cloud & DevOps")
        self.assertGreaterEqual(salary_data["predicted_lpa"], 4.0)
        factor_names = [f["factor"] for f in salary_data["factors"]]
        self.assertTrue(
            any("Cloud & DevOps" in name for name in factor_names),
            f"Expected Cloud & DevOps benchmark factor in {factor_names}"
        )


if __name__ == "__main__":
    unittest.main()
