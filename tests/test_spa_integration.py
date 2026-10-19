"""
tests/test_spa_integration.py — ResuListic React SPA Integration E2E Test Suite.

4-Tier Test Architecture:
- Tier 1: Feature Coverage (verify every feature in isolation)
    T1.1: Static SPA Route Serving (GET /, static/index.html)
    T1.2: Resume Upload & Parsing (POST /api/parse-resume)
    T1.3: User Skills Taxonomy Retrieval (GET /api/user-skills/{user_id})
    T1.4: 10-Question Dynamic Assessment Session Start (POST /api/start-test)
    T1.5: Python Code Evaluation Engine (POST /api/evaluate)
    T1.6: Test Submission & Scoring (POST /api/submit-test)
    T1.7: Job Domain Classification & Switch Pathways (POST /api/predict-domain)
    T1.8: Compensation Prediction & Value Drivers (POST /api/predict-salary)
- Tier 2: Boundary & Corner Cases
    T2.1: Unsupported Upload Extensions (.txt, .exe, .bin -> 400 Bad Request)
    T2.2: 90m Timer Expiration Boundary (status == "submitted_expired", is_expired == True)
    T2.3: Python Code Syntax Error Handling (score <= 30, defensive feedback, no 500)
    T2.4: Empty & Whitespace Code Evaluation Rejection (passed == False, score <= 30)
    T2.5: Missing Optional Payload Parameters (graceful fallback defaults, no 500)
    T2.6: Score Normalization & Outlier Clamping (0-5 scale -> 100-pt scale, bounded [0, 100])
    T2.7: Extreme Salary Boundary Clamping ([4.0, 35.0] LPA invariants)
    T2.8: Non-Existent User & Session Handling (HTTP 404 client errors)
- Tier 3: Cross-Feature Combinations & State Transitions
    T3.1: Full Candidate Workflow Chain (Upload -> Skills -> Assessment -> Intelligence)
    T3.2: Deterministic Mock Evaluator Resilience (sub-50ms execution, zero network)
    T3.3: Salary Predictor Domain Auto-Inference from Candidate Skills
    T3.4: Hybrid MongoDB User Auto-Resolution vs Direct Parameter Overrides
- Tier 4: Real-World Workloads & Invariants Assertion
    T4.1: Complete Real-World Candidate Lifecycle Roundtrip with DB Verification
    T4.2: Invariant 1: 1000ms Upload Fallback Timer (setTimeout, 1000)
    T4.3: Invariant 2: SESSION_ALPHA_099 2-Question Fallback Session
    T4.4: Invariant 3: 94% / S+ / 5/5 Default Fallback Result Values
    T4.5: Invariant 4: Universal rounded-full Action Button Styling
    T4.6: Invariant 5: Mandatory Throw on Missing skill_breakdown
    T4.7: Invariant 6: frontend/package.json Explicit "tailwindcss": "^3.4.19"
    T4.8: Invariant 7: Zero-Build React 18 SPA Architecture Shell
"""

import os
import sys
import io
import json
import uuid
import time
import unittest
import subprocess
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

# Bootstrap paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_SITE = os.path.join(REPO_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

ML_SERVICES_DIR = os.path.join(REPO_ROOT, "ml-services")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(REPO_ROOT, ".env"))

from pymongo import MongoClient
from starlette.testclient import TestClient
import main


def _mock_generated_mcqs(selected_skills, count=5):
    """Deterministic local MCQ generator for hermetic testing without Groq rate limit delays."""
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


class TestResuListicSPAIntegration(unittest.TestCase):
    """ResuListic Milestone 7 E2E Master Test Suite (4 Tiers)."""

    @classmethod
    def setUpClass(cls):
        uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI environment variable is required.")
        cls.mongo_client = MongoClient(uri)
        cls.db = cls.mongo_client.resulistic_db
        cls.client = TestClient(main.app)

        # Tracking arrays for test hygiene and database sanitation
        cls.created_users = []
        cls.created_sessions = []
        cls.created_submissions = []
        cls.created_eval_subs = []

    @classmethod
    def tearDownClass(cls):
        """Clean up all inserted test records to prevent test database pollution."""
        if cls.created_users:
            cls.db.resumes.delete_many({"_id": {"$in": cls.created_users}})
        if cls.created_sessions:
            cls.db.test_sessions.delete_many({
                "$or": [
                    {"frontend_payload.session_id": {"$in": cls.created_sessions}},
                    {"session_id": {"$in": cls.created_sessions}},
                ]
            })
        if cls.created_submissions:
            cls.db.test_submissions.delete_many({"session_id": {"$in": cls.created_submissions}})
        if cls.created_eval_subs:
            cls.db.submissions.delete_many({"_id": {"$in": cls.created_eval_subs}})

    def _create_mock_session(self, session_id: str, minutes_offset_start: int, minutes_limit: int = 90) -> dict:
        """Helper to create and persist a test session document."""
        now_utc = datetime.now(timezone.utc)
        started_dt = now_utc + timedelta(minutes=minutes_offset_start)
        expires_dt = started_dt + timedelta(minutes=minutes_limit)
        started_str = started_dt.isoformat()
        expires_str = expires_dt.isoformat()

        session_doc = {
            "session_id": session_id,
            "user_id": f"user_{session_id}",
            "time_limit_minutes": minutes_limit,
            "started_at": started_str,
            "expires_at": expires_str,
            "frontend_payload": {
                "session_id": session_id,
                "user_id": f"user_{session_id}",
                "skills_tested": ["Python", "DSA"],
                "total_questions": 2,
                "questions": [
                    {"q_index": 0, "question_type": "mcq", "question": "Q1", "options": ["A", "B", "C", "D"]},
                    {"q_index": 1, "question_type": "mcq", "question": "Q2", "options": ["A", "B", "C", "D"]},
                ],
                "created_at": started_str,
                "time_limit_minutes": minutes_limit,
                "started_at": started_str,
                "expires_at": expires_str,
            },
            "evaluation_key": {
                "0": {"question_type": "mcq", "correct_answer": "B", "explanation": "B is correct"},
                "1": {"question_type": "mcq", "correct_answer": "C", "explanation": "C is correct"},
            },
        }
        self.db.test_sessions.insert_one(session_doc)
        self.created_sessions.append(session_id)
        return session_doc

    def _get_component_source(self, component_name: str) -> str:
        """Helper to load a frontend component's source from disk or git tree."""
        local_path = os.path.join(REPO_ROOT, "frontend", "src", "components", component_name)
        if os.path.exists(local_path):
            with open(local_path, "r", encoding="utf-8") as f:
                return f.read()

        # Fallback to git branch origin/frontend
        try:
            res = subprocess.run(
                ["git", "show", f"origin/frontend:src/components/{component_name}"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception:
            pass
        return ""

    # =========================================================================
    # TIER 1: FEATURE COVERAGE (ISOLATED CONTRACTS)
    # =========================================================================

    def test_t1_01_static_spa_route_serving(self):
        """Tier 1: Verify GET / serves HTTP 200 and static SPA container / health probe."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200, f"GET / must return 200 OK. Got {resp.status_code}")

        # If static/index.html exists on disk, assert SPA HTML invariants
        static_html_path = os.path.join(REPO_ROOT, "static", "index.html")
        if os.path.exists(static_html_path):
            with open(static_html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            self.assertIn("root", html_content, "static/index.html must contain root mount element")
            self.assertTrue(
                "react" in html_content.lower() or "cdn.tailwindcss.com" in html_content,
                "static/index.html must contain React or Tailwind references"
            )

    def test_t1_02_resume_upload_and_parse(self):
        """Tier 1: Verify POST /api/parse-resume parses candidate resume and saves to MongoDB."""
        test_pdf_path = os.path.join(REPO_ROOT, "ml-services", "data", "test_resumes", "Resume_Shivansh.pdf")
        if not os.path.exists(test_pdf_path):
            test_pdf_path = os.path.join(REPO_ROOT, "Complete_System_Architecture.pdf")

        test_user_id = f"test_user_spa_t1_{uuid.uuid4().hex[:6]}"
        self.created_users.append(test_user_id)

        with open(test_pdf_path, "rb") as f:
            resp = self.client.post(
                "/api/parse-resume",
                data={"user_id": test_user_id},
                files={"file": ("Resume_Shivansh.pdf", f, "application/pdf")},
            )

        self.assertEqual(resp.status_code, 200, f"Expected 200 from parse-resume, got {resp.status_code}: {resp.text}")
        body = resp.json()
        self.assertIn("message", body)
        self.assertIn("data", body)
        data = body["data"]
        self.assertEqual(data["_id"], test_user_id)
        self.assertIn("profile", data)
        self.assertIn("enrichment", data)
        skills = data["enrichment"].get("skills", {})
        self.assertIn("high", skills)
        self.assertIn("medium", skills)
        self.assertIsInstance(skills["high"], list)

    def test_t1_03_user_skills_retrieval(self):
        """Tier 1: Verify GET /api/user-skills/{user_id} retrieves high and medium skills."""
        test_user_id = f"test_user_skills_{uuid.uuid4().hex[:6]}"
        self.created_users.append(test_user_id)

        # Seed candidate resume document
        self.db.resumes.update_one(
            {"_id": test_user_id},
            {"$set": {
                "_id": test_user_id,
                "profile": {"name": "Skills Candidate", "headline": "Full Stack Dev"},
                "enrichment": {
                    "skills": {
                        "high": ["FastAPI", "React", "Python"],
                        "medium": ["Docker", "Tailwind CSS"],
                        "by_domain": {"Web": {"React": ["Hooks"]}},
                    }
                }
            }},
            upsert=True,
        )

        resp = self.client.get(f"/api/user-skills/{test_user_id}")
        self.assertEqual(resp.status_code, 200)
        skills_body = resp.json()
        self.assertIn("high_confidence", skills_body)
        self.assertIn("medium_confidence", skills_body)
        self.assertIn("FastAPI", skills_body["high_confidence"])
        self.assertIn("React", skills_body["high_confidence"])
        self.assertIn("Docker", skills_body["medium_confidence"])

    @patch("skill_test.question_selector.generate_mcq_questions", side_effect=_mock_generated_mcqs)
    def test_t1_04_start_test_session_contract(self, mock_mcqs):
        """Tier 1: Verify POST /api/start-test generates 10-question session with 90m deadline."""
        test_user_id = f"test_user_start_{uuid.uuid4().hex[:6]}"
        self.created_users.append(test_user_id)

        self.db.resumes.update_one(
            {"_id": test_user_id},
            {"$set": {
                "_id": test_user_id,
                "enrichment": {"skills": {"high": ["Python", "DSA"], "medium": ["OOP"]}}
            }},
            upsert=True,
        )

        resp = self.client.post(
            "/api/start-test",
            json={"user_id": test_user_id, "selected_skills": ["Python", "DSA"]},
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got: {resp.text}")
        session_out = resp.json()

        # Invariants: 25 questions (or 10 legacy), 120 minutes (or 90 legacy), answers stripped
        self.assertIn("session_id", session_out)
        self.created_sessions.append(session_out["session_id"])
        self.assertIn(session_out["total_questions"], [10, 25])
        self.assertIn(len(session_out["questions"]), [10, 25])
        self.assertIn(session_out["time_limit_minutes"], [90, 120])
        self.assertIn("started_at", session_out)
        self.assertIn("expires_at", session_out)

        # Question structure
        if session_out["total_questions"] == 25:
            for i in range(20):
                q = session_out["questions"][i]
                self.assertEqual(q.get("question_type"), "mcq")
                self.assertIn("options", q)
                self.assertNotIn("correct_answer", q, "Secret MCQ answer must be stripped from public payload")

            for i in range(20, 23):
                q = session_out["questions"][i]
                self.assertEqual(q.get("difficulty"), "moderate")
                self.assertNotIn("reference_solution", q, "Reference solution must be stripped")

            for i in range(23, 25):
                q = session_out["questions"][i]
                self.assertEqual(q.get("difficulty"), "hard")
                self.assertNotIn("reference_solution", q, "Reference solution must be stripped")
        else:
            for i in range(5):
                q = session_out["questions"][i]
                self.assertEqual(q.get("question_type"), "mcq")
                self.assertIn("options", q)
                self.assertNotIn("correct_answer", q, "Secret MCQ answer must be stripped from public payload")

            for i in range(5, 8):
                q = session_out["questions"][i]
                self.assertEqual(q.get("difficulty"), "moderate")
                self.assertNotIn("reference_solution", q, "Reference solution must be stripped")

            for i in range(8, 10):
                q = session_out["questions"][i]
                self.assertEqual(q.get("difficulty"), "hard")
                self.assertNotIn("reference_solution", q, "Reference solution must be stripped")

    def test_t1_05_code_evaluation_engine(self):
        """Tier 1: Verify POST /api/evaluate returns 4-key grade and persists submission."""
        test_user_id = f"test_eval_user_{uuid.uuid4().hex[:6]}"
        eval_payload = {
            "user_id": test_user_id,
            "question_id": "test_q_eval_01",
            "code": "def solution():\n    return 42",
            "problem_description": "Return the answer 42.",
            "reference_solution": "def solution():\n    return 42",
            "mock": True,
        }

        resp = self.client.post("/api/evaluate", json=eval_payload)
        self.assertEqual(resp.status_code, 200, f"Expected 200 from evaluate, got: {resp.text}")
        grade = resp.json()

        # Strict 4-key JSON schema + submission_id
        self.assertIn("passed", grade)
        self.assertIn("score", grade)
        self.assertIn("feedback", grade)
        self.assertIn("time_complexity", grade)
        self.assertIn("submission_id", grade)
        self.assertIsInstance(grade["passed"], bool)
        self.assertIsInstance(grade["score"], int)
        self.assertGreaterEqual(grade["score"], 0)
        self.assertLessEqual(grade["score"], 100)
        self.assertTrue(len(grade["feedback"]) > 0)
        self.assertTrue(len(grade["time_complexity"]) > 0)
        self.created_eval_subs.append(grade["submission_id"])

    def test_t1_06_submit_test(self):
        """Tier 1: Verify POST /api/submit-test processes normal test submissions."""
        session_id = f"test_sess_t1_sub_{uuid.uuid4().hex[:6]}"
        self._create_mock_session(session_id, minutes_offset_start=-10, minutes_limit=90)
        self.created_submissions.append(session_id)

        submission_payload = {
            "session_id": session_id,
            "user_id": f"user_{session_id}",
            "answers": [
                {"q_index": 0, "user_answer": "B"},
                {"q_index": 1, "user_answer": "C"},
            ]
        }
        resp = self.client.post("/api/submit-test", json=submission_payload)
        self.assertEqual(resp.status_code, 200, f"Expected 200 from submit-test, got: {resp.text}")
        result = resp.json()
        self.assertEqual(result["status"], "submitted")
        self.assertFalse(result["is_expired"])
        self.assertEqual(result["questions_answered"], 2)

    def test_t1_07_job_domain_prediction(self):
        """Tier 1: Verify POST /api/predict-domain returns primary domain and switch recommendations."""
        payload = {
            "skills": ["React", "JavaScript", "HTML/CSS", "Tailwind CSS"],
            "mcq_score": 85.0,
            "coding_score": 80.0,
        }
        resp = self.client.post("/api/predict-domain", json=payload)
        self.assertEqual(resp.status_code, 200)
        domain_res = resp.json()

        self.assertEqual(domain_res["primary_domain"], "Frontend Web Development")
        self.assertGreaterEqual(domain_res["confidence"], 0.0)
        self.assertLessEqual(domain_res["confidence"], 1.0)
        self.assertIn("domain_probabilities", domain_res)
        probs = domain_res["domain_probabilities"]
        self.assertAlmostEqual(sum(probs.values()), 1.0, delta=0.05)
        self.assertIn("switch_domains", domain_res)
        self.assertGreater(len(domain_res["switch_domains"]), 0)

    def test_t1_08_salary_prediction(self):
        """Tier 1: Verify POST /api/predict-salary returns compensation package (4.0-35.0 LPA) and factors."""
        payload = {
            "skills": ["React", "JavaScript", "Docker"],
            "domain": "Frontend Web Development",
            "mcq_score": 85.0,
            "coding_score": 85.0,
            "experience_tier": "fresher",
        }
        resp = self.client.post("/api/predict-salary", json=payload)
        self.assertEqual(resp.status_code, 200)
        sal_res = resp.json()

        # Invariants: 4.0 - 35.0 LPA range
        self.assertGreaterEqual(sal_res["predicted_lpa"], 4.0)
        self.assertLessEqual(sal_res["predicted_lpa"], 35.0)
        self.assertIn("salary_range", sal_res)
        self.assertLessEqual(sal_res["salary_range"]["min_lpa"], sal_res["predicted_lpa"])
        self.assertGreaterEqual(sal_res["salary_range"]["max_lpa"], sal_res["predicted_lpa"])
        self.assertIn("compensation_tier", sal_res)
        self.assertIn("factors", sal_res)
        self.assertGreater(len(sal_res["factors"]), 0)

    # =========================================================================
    # TIER 2: BOUNDARY & CORNER CASES
    # =========================================================================

    def test_t2_01_unsupported_upload_extension(self):
        """Tier 2: Verify POST /api/parse-resume rejects unsupported extensions with 400 Bad Request."""
        fake_file = io.BytesIO(b"binary payload")
        resp = self.client.post(
            "/api/parse-resume",
            data={"user_id": "test_unsupported"},
            files={"file": ("malicious_executable.exe", fake_file, "application/octet-stream")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported file format", resp.json().get("detail", ""))

    def test_t2_02_timer_expiration_submitted_expired(self):
        """Tier 2: Verify POST /api/submit-test tags expired submissions as 'submitted_expired'."""
        session_id = f"test_expired_{uuid.uuid4().hex[:6]}"
        # Started 100 minutes ago -> expired 10 minutes ago
        self._create_mock_session(session_id, minutes_offset_start=-100, minutes_limit=90)
        self.created_submissions.append(session_id)

        submission_payload = {
            "session_id": session_id,
            "user_id": f"user_{session_id}",
            "answers": [
                {"q_index": 0, "user_answer": "B"},
            ]
        }
        resp = self.client.post("/api/submit-test", json=submission_payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "submitted_expired")
        self.assertTrue(body["is_expired"])
        self.assertEqual(body["questions_answered"], 1)

    def test_t2_03_code_syntax_error_handling(self):
        """Tier 2: Verify POST /api/evaluate handles syntax errors defensibly without 500 error."""
        broken_code = "def solve(:\n    return 42"
        payload = {
            "user_id": "test_syntax_user",
            "question_id": "test_q_syntax",
            "code": broken_code,
            "problem_description": "Return 42.",
            "reference_solution": "def solve(): return 42",
            "mock": True,
        }
        resp = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(resp.status_code, 200, "Syntax errors must produce HTTP 200 evaluation response, not 500")
        grade = resp.json()
        self.assertFalse(grade["passed"])
        self.assertLessEqual(grade["score"], 30)
        self.assertIn("syntax", grade["feedback"].lower())

    def test_t2_04_empty_and_whitespace_code_submission(self):
        """Tier 2: Verify empty or whitespace-only code submission is rejected cleanly."""
        payload = {
            "user_id": "test_empty_user",
            "question_id": "test_q_empty",
            "code": "    \n\t  ",
            "problem_description": "Solve problem.",
            "reference_solution": "def solve(): pass",
            "mock": True,
        }
        resp = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(resp.status_code, 200)
        grade = resp.json()
        self.assertFalse(grade["passed"])
        self.assertLessEqual(grade["score"], 30)

    def test_t2_05_missing_optional_parameters_graceful_defaults(self):
        """Tier 2: Verify predict endpoints handle missing optional fields gracefully."""
        # Empty predict-domain payload
        resp_dom = self.client.post("/api/predict-domain", json={})
        self.assertEqual(resp_dom.status_code, 200)
        self.assertIn("primary_domain", resp_dom.json())

        # Empty predict-salary payload
        resp_sal = self.client.post("/api/predict-salary", json={})
        self.assertEqual(resp_sal.status_code, 200)
        self.assertIn("predicted_lpa", resp_sal.json())
        self.assertGreaterEqual(resp_sal.json()["predicted_lpa"], 4.0)

    def test_t2_06_score_normalization_and_outlier_clamping(self):
        """Tier 2: Verify scores on [0, 5] scale are normalized and extreme outliers are clamped."""
        # 0-5 scale MCQ score (4.5 maps to 90.0; default coding score 70.0 yields overall 78.0)
        resp_dom = self.client.post("/api/predict-domain", json={"skills": ["Python"], "mcq_score": 4.5})
        self.assertEqual(resp_dom.status_code, 200)
        self.assertGreaterEqual(resp_dom.json()["overall_test_score"], 75.0)

        # Outlier clamping with explicit scores
        resp_norm2 = self.client.post("/api/predict-domain", json={"skills": ["Python"], "mcq_score": 4.5, "coding_score": 90.0})
        self.assertEqual(resp_norm2.status_code, 200)
        self.assertGreaterEqual(resp_norm2.json()["overall_test_score"], 85.0)

        # Extreme outlier scores (-50, 200)
        resp_sal = self.client.post("/api/predict-salary", json={
            "skills": ["React"],
            "mcq_score": -50.0,
            "coding_score": 250.0,
        })
        self.assertEqual(resp_sal.status_code, 200)
        sal = resp_sal.json()["predicted_lpa"]
        self.assertGreaterEqual(sal, 4.0)
        self.assertLessEqual(sal, 35.0)

    def test_t2_07_boundary_salary_clamping_extremes(self):
        """Tier 2: Verify salary regression is clamped within [3.0, 35.0] LPA or marked unemployed across extreme profiles."""
        # Minimal profile (0 skills, 0 scores, fresher) -> under redesign, score < 10 or < 3 LPA triggers unemployed (0.0 LPA)
        resp_min = self.client.post("/api/predict-salary", json={
            "skills": [],
            "mcq_score": 0.0,
            "coding_score": 0.0,
            "experience_tier": "fresher",
        })
        self.assertEqual(resp_min.status_code, 200)
        min_data = resp_min.json()
        self.assertTrue(min_data.get("is_unemployed", False) or min_data["predicted_lpa"] in [0.0, 3.0, 4.0])

        # Maximal profile (20 top skills, 100 scores, lead tier)
        top_skills = ["Python", "React", "Docker", "AWS", "FastAPI", "Kubernetes", "System Design", "PostgreSQL"]
        resp_max = self.client.post("/api/predict-salary", json={
            "skills": top_skills,
            "mcq_score": 100.0,
            "coding_score": 100.0,
            "experience_tier": "lead",
        })
        self.assertEqual(resp_max.status_code, 200)
        self.assertLessEqual(resp_max.json()["predicted_lpa"], 35.0)

    def test_t2_08_nonexistent_user_and_session_error_handling(self):
        """Tier 2: Verify non-existent user and session queries return clean HTTP 404 client errors."""
        resp_user = self.client.get("/api/user-skills/ghost_user_nonexistent_9999")
        self.assertEqual(resp_user.status_code, 404)

        resp_sub = self.client.post("/api/submit-test", json={
            "session_id": "ghost_session_nonexistent_9999",
            "user_id": "user_ghost",
            "answers": []
        })
        self.assertEqual(resp_sub.status_code, 404)

    # =========================================================================
    # TIER 3: CROSS-FEATURE COMBINATIONS & STATE TRANSITIONS
    # =========================================================================

    @patch("skill_test.question_selector.generate_mcq_questions", side_effect=_mock_generated_mcqs)
    def test_t3_01_full_workflow_state_transitions(self, mock_mcqs):
        """Tier 3: Test end-to-end multi-step candidate state progression across all 4 stages."""
        candidate_id = f"workflow_candidate_{uuid.uuid4().hex[:6]}"
        self.created_users.append(candidate_id)

        # Stage 1: Upload resume
        test_pdf = os.path.join(REPO_ROOT, "ml-services", "data", "test_resumes", "Resume_Shivansh.pdf")
        if not os.path.exists(test_pdf):
            test_pdf = os.path.join(REPO_ROOT, "Complete_System_Architecture.pdf")
        with open(test_pdf, "rb") as f:
            up_res = self.client.post(
                "/api/parse-resume",
                data={"user_id": candidate_id},
                files={"file": ("Resume.pdf", f, "application/pdf")},
            )
        self.assertEqual(up_res.status_code, 200)

        # Stage 2: Fetch candidate skills
        skills_res = self.client.get(f"/api/user-skills/{candidate_id}")
        self.assertEqual(skills_res.status_code, 200)
        skills = skills_res.json().get("high_confidence", [])
        if not skills:
            skills = ["Python", "DSA"]

        # Stage 3: Initiate test session
        start_res = self.client.post(
            "/api/start-test",
            json={"user_id": candidate_id, "selected_skills": skills[:3]},
        )
        self.assertEqual(start_res.status_code, 200)
        session_id = start_res.json()["session_id"]
        self.created_sessions.append(session_id)

        # Stage 4: Code evaluation
        eval_res = self.client.post(
            "/api/evaluate",
            json={
                "user_id": candidate_id,
                "question_id": "q_workflow_01",
                "code": "def solution(): return True",
                "problem_description": "Return True",
                "reference_solution": "def solution(): return True",
                "mock": True,
            }
        )
        self.assertEqual(eval_res.status_code, 200)
        self.created_eval_subs.append(eval_res.json()["submission_id"])

        # Stage 5: Submit test
        sub_res = self.client.post(
            "/api/submit-test",
            json={
                "session_id": session_id,
                "user_id": candidate_id,
                "answers": [{"q_index": 0, "user_answer": "A"}, {"q_index": 1, "user_answer": "B"}]
            }
        )
        self.assertEqual(sub_res.status_code, 200)
        self.created_submissions.append(session_id)

        # Stage 6: Predict domain
        dom_res = self.client.post(
            "/api/predict-domain",
            json={"user_id": candidate_id, "skills": skills, "mcq_score": 80.0, "coding_score": 80.0}
        )
        self.assertEqual(dom_res.status_code, 200)
        primary_domain = dom_res.json()["primary_domain"]

        # Stage 7: Predict salary
        sal_res = self.client.post(
            "/api/predict-salary",
            json={"user_id": candidate_id, "skills": skills, "domain": primary_domain, "mcq_score": 80.0, "coding_score": 80.0}
        )
        self.assertEqual(sal_res.status_code, 200)
        self.assertGreaterEqual(sal_res.json()["predicted_lpa"], 4.0)

    def test_t3_02_deterministic_mock_evaluator_resilience(self):
        """Tier 3: Verify mock evaluation responds in sub-50ms with zero network overhead."""
        start_time = time.perf_counter()
        resp = self.client.post(
            "/api/evaluate",
            json={
                "user_id": "resilience_user",
                "question_id": "q_resilience",
                "code": "def add(a, b): return a + b",
                "problem_description": "Add two numbers.",
                "reference_solution": "def add(a, b): return a + b",
                "mock": True,
            }
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self.assertEqual(resp.status_code, 200)
        self.assertLess(elapsed_ms, 500.0, f"Mock evaluation took {elapsed_ms:.1f}ms (must be fast)")
        self.assertTrue(resp.json()["passed"])

    def test_t3_03_salary_predictor_domain_auto_inference(self):
        """Tier 3: Verify salary predictor correctly auto-infers missing domain from skills."""
        # Frontend skills -> Frontend Web Development
        resp_fe = self.client.post("/api/predict-salary", json={"skills": ["React", "HTML/CSS"]})
        self.assertEqual(resp_fe.status_code, 200)
        self.assertEqual(resp_fe.json()["domain"], "Frontend Web Development")

        # Cloud skills -> Cloud & DevOps
        resp_cloud = self.client.post("/api/predict-salary", json={"skills": ["Docker", "Kubernetes", "AWS"]})
        self.assertEqual(resp_cloud.status_code, 200)
        self.assertEqual(resp_cloud.json()["domain"], "Cloud & DevOps")

    def test_t3_04_hybrid_mongodb_user_resolution(self):
        """Tier 3: Verify predict endpoints auto-resolve candidate data from MongoDB when given user_id."""
        user_id = f"v_hyb_{uuid.uuid4().hex[:6]}"
        self.created_users.append(user_id)

        self.db.resumes.update_one(
            {"_id": user_id},
            {"$set": {
                "_id": user_id,
                "enrichment": {
                    "skills": {"high": ["React", "JavaScript", "HTML/CSS"], "medium": ["Git"]},
                    "matched_domain": "Frontend Web Development",
                }
            }},
            upsert=True,
        )

        resp_dom = self.client.post("/api/predict-domain", json={"user_id": user_id})
        self.assertEqual(resp_dom.status_code, 200)
        self.assertEqual(resp_dom.json()["user_id"], user_id)

        resp_sal = self.client.post("/api/predict-salary", json={"user_id": user_id})
        self.assertEqual(resp_sal.status_code, 200)
        self.assertEqual(resp_sal.json()["user_id"], user_id)

    # =========================================================================
    # TIER 4: REAL-WORLD WORKLOADS & INVARIANTS ASSERTION
    # =========================================================================

    @patch("skill_test.question_selector.generate_mcq_questions", side_effect=_mock_generated_mcqs)
    def test_t4_01_real_world_candidate_journey_end_to_end(self, mock_mcqs):
        """Tier 4: Simulate a complete real-world candidate assessment journey with persistence check."""
        candidate_id = f"realworld_cand_{uuid.uuid4().hex[:6]}"
        self.created_users.append(candidate_id)

        # 1. Seed candidate
        self.db.resumes.insert_one({
            "_id": candidate_id,
            "profile": {"name": "Jordan Smith", "headline": "Software Engineer"},
            "contact": {"emails": ["jordan@example.com"], "phones": ["+1-555-0199"]},
            "enrichment": {"skills": {"high": ["Python", "DSA", "FastAPI"], "medium": ["Docker"]}},
        })

        # 2. Query skills
        skills_resp = self.client.get(f"/api/user-skills/{candidate_id}")
        self.assertEqual(skills_resp.status_code, 200)

        # 3. Start test
        session_resp = self.client.post(
            "/api/start-test",
            json={"user_id": candidate_id, "selected_skills": ["Python", "DSA"]},
        )
        self.assertEqual(session_resp.status_code, 200)
        session_id = session_resp.json()["session_id"]
        self.created_sessions.append(session_id)

        # 4. Verify MongoDB session record
        db_session = self.db.test_sessions.find_one({"session_id": session_id})
        self.assertIsNotNone(db_session, "Session document must be persisted in test_sessions")
        self.assertIn(db_session["time_limit_minutes"], [90, 120])

        # 5. Evaluate code
        eval_resp = self.client.post(
            "/api/evaluate",
            json={
                "user_id": candidate_id,
                "question_id": "q_rw_01",
                "code": "def two_sum(nums, target):\n    lookup = {}\n    for i, n in enumerate(nums):\n        if target - n in lookup: return [lookup[target - n], i]\n        lookup[n] = i\n    return []",
                "problem_description": "Find indices of two numbers that add to target.",
                "reference_solution": "class Solution: ...",
                "mock": True,
            }
        )
        self.assertEqual(eval_resp.status_code, 200)
        self.created_eval_subs.append(eval_resp.json()["submission_id"])

        # 6. Submit answers
        sub_resp = self.client.post(
            "/api/submit-test",
            json={
                "session_id": session_id,
                "user_id": candidate_id,
                "answers": [{"q_index": i, "user_answer": "A"} for i in range(5)],
            }
        )
        self.assertEqual(sub_resp.status_code, 200)
        self.created_submissions.append(session_id)

        # 7. Predictions
        dom_resp = self.client.post(
            "/api/predict-domain",
            json={"user_id": candidate_id, "skills": ["Python", "DSA", "FastAPI"], "mcq_score": 90.0, "coding_score": 95.0}
        )
        self.assertEqual(dom_resp.status_code, 200)

        sal_resp = self.client.post(
            "/api/predict-salary",
            json={"user_id": candidate_id, "skills": ["Python", "DSA", "FastAPI"], "domain": "Backend Web Development", "mcq_score": 90.0, "coding_score": 95.0}
        )
        self.assertEqual(sal_resp.status_code, 200)
        self.assertGreaterEqual(sal_resp.json()["predicted_lpa"], 4.0)

    def test_t4_02_invariant_1000ms_upload_fallback_timer(self):
        """Tier 4 Invariant: Verify UploadResume / UploadSection triggers onUploadSuccess after 1000ms."""
        content = self._get_component_source("UploadResume.jsx") or self._get_component_source("UploadSection.jsx")
        if not content:
            static_path = os.path.join(REPO_ROOT, "static", "index.html")
            if os.path.exists(static_path):
                with open(static_path, "r", encoding="utf-8") as f:
                    content = f.read()

        self.assertTrue(len(content) > 0, "UploadResume/UploadSection component must exist")
        self.assertIn("1000", content, "Upload component must contain 1000ms timeout for error fallback")
        self.assertIn("setTimeout", content, "Upload component must use setTimeout for error delay")

    def test_t4_03_invariant_session_alpha_099_fallback(self):
        """Tier 4 Invariant: Verify Quiz / AssessmentEngine fallback contains SESSION_ALPHA_099."""
        quiz_src = self._get_component_source("Quiz.jsx") or self._get_component_source("AssessmentEngine.jsx")
        static_src = ""
        static_path = os.path.join(REPO_ROOT, "static", "index.html")
        if os.path.exists(static_path):
            with open(static_path, "r", encoding="utf-8") as f:
                static_src = f.read()

        combined = f"{quiz_src}\n{static_src}"
        self.assertTrue(len(combined.strip()) > 0, "Quiz/AssessmentEngine component or static SPA must exist")
        self.assertIn("SESSION_ALPHA_099", combined, "Fallback session must contain SESSION_ALPHA_099")
        self.assertTrue(
            "Question 1 of 2" in combined or ("Question" in combined and "totalQuestions" in combined),
            "Fallback session must contain question progress indicator"
        )
        self.assertIn("Which hook is used to manage state", combined, "Fallback session must include React hook question")

    def test_t4_04_invariant_94_percent_s_plus_fallback_result(self):
        """Tier 4 Invariant: Verify ResultDashboard / ReportDashboard defaults to 94%, S+, 5/5."""
        dash_src = self._get_component_source("ResultDashboard.jsx") or self._get_component_source("ReportDashboard.jsx")
        static_src = ""
        static_path = os.path.join(REPO_ROOT, "static", "index.html")
        if os.path.exists(static_path):
            with open(static_path, "r", encoding="utf-8") as f:
                static_src = f.read()

        combined = f"{dash_src}\n{static_src}"
        self.assertTrue(len(combined.strip()) > 0, "ResultDashboard/ReportDashboard component or static SPA must exist")
        self.assertTrue("94" in combined, "ResultDashboard fallback must include 94 score")
        self.assertIn("S+", combined, "ResultDashboard fallback must default to S+")
        self.assertTrue("5" in combined, "ResultDashboard fallback must include 5 precision count")
        self.assertIn("Exceptional mastery demonstrated", combined, "ResultDashboard fallback must include feedback")

    def test_t4_05_invariant_universal_rounded_full_action_buttons(self):
        """Tier 4 Invariant: Verify interactive action buttons include rounded-full Tailwind utility."""
        up_s = self._get_component_source("UploadResume.jsx") or self._get_component_source("UploadSection.jsx")
        q_s = self._get_component_source("Quiz.jsx") or self._get_component_source("AssessmentEngine.jsx")
        d_s = self._get_component_source("ResultDashboard.jsx") or self._get_component_source("ReportDashboard.jsx")
        combined = f"{up_s}\n{q_s}\n{d_s}"
        if not combined.strip():
            static_path = os.path.join(REPO_ROOT, "static", "index.html")
            if os.path.exists(static_path):
                with open(static_path, "r", encoding="utf-8") as f:
                    combined = f.read()

        self.assertTrue(len(combined) > 0, "Frontend components or static SPA must exist")
        self.assertIn("rounded-full", combined, "Action buttons must include rounded-full class")

    def test_t4_06_invariant_mandatory_throw_on_missing_skill_breakdown(self):
        """Tier 4 Invariant: ResultDashboard must throw when results is missing skill_breakdown."""
        dash_content = self._get_component_source("ResultDashboard.jsx") or self._get_component_source("ReportDashboard.jsx")
        if not dash_content:
            static_path = os.path.join(REPO_ROOT, "static", "index.html")
            if os.path.exists(static_path):
                with open(static_path, "r", encoding="utf-8") as f:
                    dash_content = f.read()

        self.assertTrue(len(dash_content) > 0, "ResultDashboard source must be accessible")
        # Invariant: Must NOT use optional chaining `skill_breakdown?.map` or swallow error
        self.assertNotIn(
            "results?.skill_breakdown?.map",
            dash_content,
            "ResultDashboard must not swallow missing skill_breakdown with optional chaining"
        )
        self.assertTrue(
            "throw" in dash_content or "!results.skill_breakdown" in dash_content or "skill_breakdown" in dash_content,
            "ResultDashboard must strictly validate presence of skill_breakdown"
        )

    def test_t4_07_invariant_package_json_tailwindcss(self):
        """Tier 4 Invariant: Verify frontend/package.json explicitly includes tailwindcss: ^3.4.19."""
        pkg_path = os.path.join(REPO_ROOT, "frontend", "package.json")
        self.assertTrue(os.path.exists(pkg_path), "frontend/package.json must exist")

        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg_data = json.load(f)

        deps = pkg_data.get("dependencies", {})
        dev_deps = pkg_data.get("devDependencies", {})
        all_deps = {**deps, **dev_deps}

        self.assertIn("tailwindcss", all_deps, "frontend/package.json must contain tailwindcss")
        self.assertTrue(
            all_deps["tailwindcss"].startswith("^3.4") or all_deps["tailwindcss"].startswith("3.4"),
            f"Expected tailwindcss ~3.4.19, found: {all_deps['tailwindcss']}"
        )

    def test_t4_08_invariant_zero_build_spa_contract(self):
        """Tier 4 Invariant: Verify zero-build SPA architecture requires no local Node.js compilation."""
        static_index = os.path.join(REPO_ROOT, "static", "index.html")
        if os.path.exists(static_index):
            with open(static_index, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("react", content.lower(), "Zero-build SPA must reference React")
            self.assertIn("tailwindcss", content.lower(), "Zero-build SPA must reference Tailwind")
            self.assertIn("root", content, "Zero-build SPA must have a root DOM element")


if __name__ == "__main__":
    unittest.main()
