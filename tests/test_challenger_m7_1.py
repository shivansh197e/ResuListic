"""
tests/test_challenger_m7_1.py — Empirical Adversarial Stress Suite for ResuListic Milestone 7.

Mission:
Adversarially probe and stress-test the ResuListic React SPA integration endpoints and boundary contracts:
1. Unsupported file extension fuzzing (.txt, .exe, .bin, .py, .sh, etc.) on POST /api/parse-resume (assert 400 Bad Request, zero 500).
2. 90-minute deadline expiration boundary enforcement on POST /api/submit-test (assert status='submitted_expired', is_expired=True).
3. Invalid Python syntax stress-testing on POST /api/evaluate (assert passed=False, score <= 30, graceful feedback, zero 500).
4. Extreme boundary score clamping on POST /api/predict-domain and POST /api/predict-salary (assert scores in [0, 100], salary in [4.0, 35.0] LPA).
5. Non-existent entity queries (user IDs, session IDs, question IDs) across all routes (assert 404 Client Error, zero 500).
"""

import os
import sys
import io
import uuid
from datetime import datetime, timezone, timedelta
import unittest

# Ensure project root and ml-services are in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_SITE = os.path.join(PROJECT_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

ML_SERVICES_DIR = os.path.join(PROJECT_ROOT, "ml-services")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from pymongo import MongoClient
from starlette.testclient import TestClient
import main


class ChallengerM7EmpiricalTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
        if not uri:
            raise RuntimeError("MongoDB URI missing from environment.")
        cls.db_client = MongoClient(uri)
        cls.db = cls.db_client.resulistic_db
        cls.api_client = TestClient(main.app)

        cls.created_sessions = []
        cls.created_submissions = []
        cls.created_code_submissions = []
        cls.created_resumes = []

    @classmethod
    def tearDownClass(cls):
        """Purge all ephemeral test fixtures created during the stress run."""
        for sid in cls.created_sessions:
            cls.db.test_sessions.delete_many({
                "$or": [{"session_id": sid}, {"frontend_payload.session_id": sid}]
            })
            cls.db.test_submissions.delete_many({"session_id": sid})

        for cid in cls.created_code_submissions:
            try:
                from bson import ObjectId
                if ObjectId.is_valid(cid):
                    cls.db.submissions.delete_one({"_id": ObjectId(cid)})
            except Exception:
                pass

        for uid in cls.created_resumes:
            cls.db.resumes.delete_one({"_id": uid})

        cls.db_client.close()

    # =========================================================================
    # CHALLENGE 1: UNSUPPORTED FILE EXTENSIONS ON POST /api/parse-resume
    # =========================================================================

    def test_c1_01_unsupported_txt_file(self):
        """Probe POST /api/parse-resume with .txt file -> HTTP 400, no 500."""
        file_content = b"Candidate John Doe\nSkills: Python, React, SQL\n"
        resp = self.api_client.post(
            "/api/parse-resume",
            data={"user_id": f"challenger_txt_{uuid.uuid4().hex[:6]}"},
            files={"file": ("resume.txt", io.BytesIO(file_content), "text/plain")},
        )
        self.assertEqual(resp.status_code, 400, f"Expected 400, got {resp.status_code}: {resp.text}")
        data = resp.json()
        self.assertEqual(data.get("detail"), "Unsupported file format.")

    def test_c1_02_unsupported_exe_binary(self):
        """Probe POST /api/parse-resume with executable binary (.exe) -> HTTP 400, no 500."""
        # Simulated PE binary header (MZ...)
        pe_bytes = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 64
        resp = self.api_client.post(
            "/api/parse-resume",
            data={"user_id": f"challenger_exe_{uuid.uuid4().hex[:6]}"},
            files={"file": ("malicious_payload.exe", io.BytesIO(pe_bytes), "application/x-msdownload")},
        )
        self.assertEqual(resp.status_code, 400, f"Expected 400, got {resp.status_code}: {resp.text}")
        data = resp.json()
        self.assertEqual(data.get("detail"), "Unsupported file format.")

    def test_c1_03_unsupported_raw_bin_file(self):
        """Probe POST /api/parse-resume with raw binary (.bin) -> HTTP 400, no 500."""
        bin_bytes = os.urandom(256)
        resp = self.api_client.post(
            "/api/parse-resume",
            data={"user_id": f"challenger_bin_{uuid.uuid4().hex[:6]}"},
            files={"file": ("firmware.bin", io.BytesIO(bin_bytes), "application/octet-stream")},
        )
        self.assertEqual(resp.status_code, 400, f"Expected 400, got {resp.status_code}: {resp.text}")
        data = resp.json()
        self.assertEqual(data.get("detail"), "Unsupported file format.")

    def test_c1_04_unsupported_script_and_archive_extensions(self):
        """Probe various adversarial extensions (.py, .sh, .bat, .zip, .tar.gz, no-extension)."""
        adversarial_filenames = [
            ("exploit.py", "text/x-python"),
            ("installer.sh", "application/x-sh"),
            ("payload.bat", "application/x-bat"),
            ("bundle.zip", "application/zip"),
            ("archive.tar.gz", "application/gzip"),
            ("resume_without_extension", "application/octet-stream"),
            ("resume.pdf.exe", "application/x-msdownload"),  # Double extension spoofing
            ("UPPERCASE.TXT", "text/plain"),                 # Case sensitivity
        ]
        for fname, mime in adversarial_filenames:
            with self.subTest(filename=fname):
                resp = self.api_client.post(
                    "/api/parse-resume",
                    data={"user_id": f"adv_{uuid.uuid4().hex[:6]}"},
                    files={"file": (fname, io.BytesIO(b"dummy payload"), mime)},
                )
                self.assertEqual(
                    resp.status_code, 400,
                    f"Filename '{fname}' must be rejected with 400, got {resp.status_code}: {resp.text}"
                )
                self.assertEqual(resp.json().get("detail"), "Unsupported file format.")

    def test_c1_05_empty_filename_rejected(self):
        """Probe POST /api/parse-resume with empty filename -> HTTP 400/422 client error, zero 500."""
        resp = self.api_client.post(
            "/api/parse-resume",
            data={"user_id": f"adv_{uuid.uuid4().hex[:6]}"},
            files={"file": ("", io.BytesIO(b"dummy payload"), "application/octet-stream")},
        )
        self.assertIn(resp.status_code, [400, 422], f"Expected 4xx client error, got {resp.status_code}")
        self.assertNotEqual(resp.status_code, 500)

    # =========================================================================
    # CHALLENGE 2: SUBMITTING TEST SESSION AFTER 90-MINUTE DEADLINE
    # =========================================================================

    def _create_mock_session(self, session_id: str, minutes_elapsed: float, time_limit: int = 90):
        now_dt = datetime.now(timezone.utc)
        started_dt = now_dt - timedelta(minutes=minutes_elapsed)
        expires_dt = started_dt + timedelta(minutes=time_limit)

        doc = {
            "session_id": session_id,
            "user_id": f"user_{session_id}",
            "started_at": started_dt.isoformat(),
            "expires_at": expires_dt.isoformat(),
            "time_limit_minutes": time_limit,
            "frontend_payload": {
                "session_id": session_id,
                "user_id": f"user_{session_id}",
                "started_at": started_dt.isoformat(),
                "expires_at": expires_dt.isoformat(),
                "time_limit_minutes": time_limit,
                "questions": [
                    {"q_index": 0, "question_type": "mcq", "question": "What is Python?"},
                    {"q_index": 1, "question_type": "mcq", "question": "What is Big O?"},
                ]
            },
            "evaluation_key": {
                "0": {"question_type": "mcq", "correct_answer": "A"},
                "1": {"question_type": "mcq", "correct_answer": "B"},
            }
        }
        self.db.test_sessions.insert_one(doc)
        self.created_sessions.append(session_id)
        return doc

    def test_c2_01_expired_session_submission_at_91_minutes(self):
        """Submit session after 91 minutes (1m past 90m limit) -> submitted_expired, is_expired=True."""
        sid = f"challenger_exp_91m_{uuid.uuid4().hex[:6]}"
        self._create_mock_session(sid, minutes_elapsed=91.0, time_limit=90)

        payload = {
            "session_id": sid,
            "user_id": f"user_{sid}",
            "answers": [
                {"q_index": 0, "user_answer": "A"},  # Correct
                {"q_index": 1, "user_answer": "C"},  # Incorrect
            ]
        }
        resp = self.api_client.post("/api/submit-test", json=payload)
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text}")
        body = resp.json()

        self.assertEqual(body["status"], "submitted_expired")
        self.assertTrue(body["is_expired"])
        self.assertGreaterEqual(body["duration_seconds"], 5400.0)
        self.assertEqual(body["questions_answered"], 2)
        self.assertEqual(body["mcq_score"], 50.0)

        # Verify database persistence
        saved_sub = self.db.test_submissions.find_one({"session_id": sid})
        self.assertIsNotNone(saved_sub, "Submission must be persisted in database")
        self.assertEqual(saved_sub["status"], "submitted_expired")
        self.assertTrue(saved_sub["is_expired"])
        self.assertEqual(saved_sub["score"], 50.0)

    def test_c2_02_severely_expired_session_at_180_minutes(self):
        """Submit session after 180 minutes (double the deadline) -> submitted_expired, is_expired=True."""
        sid = f"challenger_exp_180m_{uuid.uuid4().hex[:6]}"
        self._create_mock_session(sid, minutes_elapsed=180.0, time_limit=90)

        payload = {
            "session_id": sid,
            "user_id": f"user_{sid}",
            "answers": [{"q_index": 0, "user_answer": "A"}]
        }
        resp = self.api_client.post("/api/submit-test", json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "submitted_expired")
        self.assertTrue(body["is_expired"])
        self.assertGreaterEqual(body["duration_seconds"], 10000.0)

    def test_c2_03_active_session_within_deadline(self):
        """Submit session after 45 minutes (within 90m deadline) -> submitted, is_expired=False."""
        sid = f"challenger_active_45m_{uuid.uuid4().hex[:6]}"
        self._create_mock_session(sid, minutes_elapsed=45.0, time_limit=90)

        payload = {
            "session_id": sid,
            "user_id": f"user_{sid}",
            "answers": [
                {"q_index": 0, "user_answer": "A"},
                {"q_index": 1, "user_answer": "B"},
            ]
        }
        resp = self.api_client.post("/api/submit-test", json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "submitted")
        self.assertFalse(body["is_expired"])
        self.assertEqual(body["mcq_score"], 100.0)

    def test_c2_04_session_at_exact_90_minute_boundary(self):
        """Submit session at exactly 90.0 minutes -> triggers expiration check -> submitted_expired."""
        sid = f"challenger_exact_90m_{uuid.uuid4().hex[:6]}"
        # Exactly 90.05 minutes elapsed to account for microsecond latency
        self._create_mock_session(sid, minutes_elapsed=90.05, time_limit=90)

        payload = {
            "session_id": sid,
            "user_id": f"user_{sid}",
            "answers": [{"q_index": 0, "user_answer": "A"}]
        }
        resp = self.api_client.post("/api/submit-test", json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "submitted_expired")
        self.assertTrue(body["is_expired"])

    def test_c2_05_re_submission_preserves_expired_status(self):
        """Re-submitting an already expired session does not corrupt state or 500."""
        sid = f"challenger_re_submit_{uuid.uuid4().hex[:6]}"
        self._create_mock_session(sid, minutes_elapsed=95.0, time_limit=90)

        payload = {
            "session_id": sid,
            "user_id": f"user_{sid}",
            "answers": [{"q_index": 0, "user_answer": "A"}]
        }
        resp1 = self.api_client.post("/api/submit-test", json=payload)
        self.assertEqual(resp1.status_code, 200)
        resp2 = self.api_client.post("/api/submit-test", json=payload)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["status"], "submitted_expired")

    # =========================================================================
    # CHALLENGE 3: EVALUATING INVALID PYTHON SYNTAX ON POST /api/evaluate
    # =========================================================================

    def test_c3_01_syntax_error_incomplete_function(self):
        """Evaluate 'def broken(:' -> passed=False, score <= 30, feedback contains syntax, no 500."""
        payload = {
            "user_id": f"challenger_syn_{uuid.uuid4().hex[:6]}",
            "question_id": "test_q_broken_fn",
            "code": "def broken(:\n    pass",
            "problem_description": "Implement broken.",
            "reference_solution": "def broken(): pass",
            "mock": True,
        }
        resp = self.api_client.post("/api/evaluate", json=payload)
        self.assertEqual(resp.status_code, 200, f"Syntax errors must return 200, got {resp.status_code}")
        body = resp.json()
        self.assertFalse(body["passed"])
        self.assertLessEqual(body["score"], 30)
        self.assertIn("syntax", body["feedback"].lower())
        self.assertIsNotNone(body["submission_id"])
        self.created_code_submissions.append(body["submission_id"])

    def test_c3_02_syntax_error_missing_colon_and_indentation(self):
        """Evaluate missing colons, bad indents, and mismatched brackets."""
        broken_snippets = [
            ("missing_colon", "for i in range(10)\n    print(i)"),
            ("indentation_error", "def foo():\nx = 1\nreturn x"),
            ("mismatched_brackets", "def solve(arr):\n    return (arr[0] + arr[1]}}"),
            ("unterminated_string", "def greet():\n    msg = 'hello world\n    return msg"),
            ("raw_symbols", "@@@ ### $$$ %%%"),
        ]
        for name, code in broken_snippets:
            with self.subTest(syntax_type=name):
                payload = {
                    "user_id": f"syn_{name}_{uuid.uuid4().hex[:4]}",
                    "question_id": f"q_{name}",
                    "code": code,
                    "problem_description": "Solve test problem.",
                    "reference_solution": "def solve(): return 42",
                    "mock": True,
                }
                resp = self.api_client.post("/api/evaluate", json=payload)
                self.assertEqual(resp.status_code, 200, f"Failed on {name}: {resp.text}")
                data = resp.json()
                self.assertFalse(data["passed"], f"Failed on {name}: passed must be False")
                self.assertLessEqual(data["score"], 30, f"Failed on {name}: score must be <= 30")
                self.assertTrue(len(data["feedback"]) > 0, f"Failed on {name}: feedback must be populated")
                self.created_code_submissions.append(data["submission_id"])

    def test_c3_03_empty_and_whitespace_only_code_submission(self):
        """Evaluate empty and whitespace-only submissions -> passed=False, score <= 30."""
        for code in ["", "   ", "\n\t  \n"]:
            with self.subTest(code_repr=repr(code)):
                payload = {
                    "user_id": f"syn_empty_{uuid.uuid4().hex[:4]}",
                    "question_id": "q_empty",
                    "code": code,
                    "problem_description": "Solve test problem.",
                    "reference_solution": "def solve(): return 42",
                    "mock": True,
                }
                resp = self.api_client.post("/api/evaluate", json=payload)
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertFalse(data["passed"])
                self.assertLessEqual(data["score"], 30)
                self.created_code_submissions.append(data["submission_id"])

    # =========================================================================
    # CHALLENGE 4: EXTREME BOUNDARY SCORES TO PREDICTORS (CLAMPING VERIFICATION)
    # =========================================================================

    def test_c4_01_predict_domain_extreme_negative_and_excessive_scores(self):
        """POST /api/predict-domain with extreme scores (-999 and +9999) must clamp without 500."""
        extreme_cases = [
            {"mcq_score": -999.0, "coding_score": -500.0, "skills": ["Python", "SQL"]},
            {"mcq_score": 9999.0, "coding_score": 5000.0, "skills": ["React", "CSS"]},
            {"mcq_score": 0.0, "coding_score": 0.0, "skills": ["Docker", "Kubernetes"]},
            {"mcq_score": 100.0, "coding_score": 100.0, "skills": ["PyTorch", "TensorFlow"]},
            {"mcq_score": 4.5, "coding_score": 85.0, "skills": ["Python"]},  # 0-5 scale test
        ]
        for case in extreme_cases:
            with self.subTest(case=case):
                resp = self.api_client.post("/api/predict-domain", json=case)
                self.assertEqual(resp.status_code, 200, f"Error on case {case}: {resp.text}")
                data = resp.json()
                self.assertIn("primary_domain", data)
                self.assertGreaterEqual(data["confidence"], 0.0)
                self.assertLessEqual(data["confidence"], 1.0)
                self.assertIsInstance(data["domain_probabilities"], dict)
                # Verify total probability sums to ~1.0
                total_prob = sum(data["domain_probabilities"].values())
                self.assertAlmostEqual(total_prob, 1.0, places=1)

    def test_c4_02_predict_salary_extreme_negative_scores_clamped_to_min_4_lpa(self):
        """POST /api/predict-salary with negative scores must clamp to at least 4.0 LPA."""
        payload = {
            "skills": [],
            "domain": "Backend Web Development",
            "mcq_score": -1000.0,
            "coding_score": -500.0,
            "experience_tier": "fresher",
        }
        resp = self.api_client.post("/api/predict-salary", json=payload)
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text}")
        data = resp.json()
        self.assertGreaterEqual(data["predicted_lpa"], 4.0, "Salary must be >= 4.0 LPA")
        self.assertLessEqual(data["predicted_lpa"], 35.0, "Salary must be <= 35.0 LPA")
        self.assertGreaterEqual(data["salary_range"]["min_lpa"], 4.0)
        self.assertLessEqual(data["salary_range"]["max_lpa"], 35.0)
        self.assertEqual(data["overall_test_score"], 0.0, "Negative scores must clamp total to 0.0")

    def test_c4_03_predict_salary_extreme_positive_scores_clamped_to_max_35_lpa(self):
        """POST /api/predict-salary with exorbitant scores must clamp to at most 35.0 LPA."""
        payload = {
            "skills": ["Kubernetes", "AWS", "PyTorch", "System Design", "Microservices", "Docker", "FastAPI"],
            "domain": "Cloud & DevOps",
            "mcq_score": 99999.0,
            "coding_score": 88888.0,
            "experience_tier": "mid_level",
        }
        resp = self.api_client.post("/api/predict-salary", json=payload)
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text}")
        data = resp.json()
        self.assertGreaterEqual(data["predicted_lpa"], 4.0)
        self.assertLessEqual(data["predicted_lpa"], 35.0, "Salary must be <= 35.0 LPA")
        self.assertGreaterEqual(data["salary_range"]["min_lpa"], 4.0)
        self.assertLessEqual(data["salary_range"]["max_lpa"], 35.0)
        self.assertEqual(data["overall_test_score"], 100.0, "Excessive scores must clamp total to 100.0")

    def test_c4_04_salary_range_invariant_ordering(self):
        """Assert min_lpa <= predicted_lpa <= max_lpa across random fuzzed score combinations."""
        test_pairs = [
            (-50.0, 150.0),
            (0.0, 0.0),
            (100.0, 100.0),
            (50.0, 50.0),
            (-1.0, 101.0),
        ]
        for mcq, code in test_pairs:
            with self.subTest(mcq=mcq, code=code):
                resp = self.api_client.post("/api/predict-salary", json={
                    "skills": ["Python"],
                    "mcq_score": mcq,
                    "coding_score": code,
                })
                self.assertEqual(resp.status_code, 200)
                d = resp.json()
                min_val = d["salary_range"]["min_lpa"]
                pred_val = d["predicted_lpa"]
                max_val = d["salary_range"]["max_lpa"]
                self.assertTrue(
                    min_val <= pred_val <= max_val,
                    f"Invariant violated: min ({min_val}) <= pred ({pred_val}) <= max ({max_val})"
                )

    def test_c4_05_predict_salary_unrecognized_domain_and_tier_fallback(self):
        """Unrecognized domain string and experience tier default gracefully without crashing."""
        resp = self.api_client.post("/api/predict-salary", json={
            "skills": ["Python", "FastAPI"],
            "domain": "Alien Quantum Computing",
            "experience_tier": "overlord",
            "mcq_score": 85.0,
            "coding_score": 90.0,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["predicted_lpa"], 4.0)
        self.assertLessEqual(data["predicted_lpa"], 35.0)

    # =========================================================================
    # CHALLENGE 5: NON-EXISTENT USER IDs AND SESSION IDs (HTTP 404 RESILIENCE)
    # =========================================================================

    def test_c5_01_nonexistent_user_on_user_skills(self):
        """GET /api/user-skills/{nonexistent_id} -> HTTP 404, zero 500."""
        fake_id = f"ghost_user_{uuid.uuid4().hex}"
        resp = self.api_client.get(f"/api/user-skills/{fake_id}")
        self.assertEqual(resp.status_code, 404, f"Expected 404, got {resp.status_code}: {resp.text}")
        self.assertIn("not found", resp.json().get("detail", "").lower())

    def test_c5_02_nonexistent_user_on_start_test(self):
        """POST /api/start-test with nonexistent user_id -> HTTP 404, zero 500."""
        fake_id = f"ghost_user_{uuid.uuid4().hex}"
        resp = self.api_client.post("/api/start-test", json={"user_id": fake_id, "selected_skills": ["Python"]})
        self.assertEqual(resp.status_code, 404, f"Expected 404, got {resp.status_code}: {resp.text}")
        self.assertIn("not found", resp.json().get("detail", "").lower())

    def test_c5_03_nonexistent_session_on_submit_test(self):
        """POST /api/submit-test with nonexistent session_id -> HTTP 404, zero 500."""
        fake_sid = f"ghost_session_{uuid.uuid4().hex}"
        resp = self.api_client.post("/api/submit-test", json={
            "session_id": fake_sid,
            "user_id": "ghost_user",
            "answers": [{"q_index": 0, "user_answer": "A"}]
        })
        self.assertEqual(resp.status_code, 404, f"Expected 404, got {resp.status_code}: {resp.text}")
        self.assertIn("not found", resp.json().get("detail", "").lower())

    def test_c5_04_nonexistent_user_on_predict_domain_db_resolution(self):
        """POST /api/predict-domain with nonexistent user_id (and no direct skills) -> HTTP 404, zero 500."""
        fake_id = f"ghost_user_{uuid.uuid4().hex}"
        resp = self.api_client.post("/api/predict-domain", json={"user_id": fake_id})
        self.assertEqual(resp.status_code, 404, f"Expected 404, got {resp.status_code}: {resp.text}")
        self.assertIn("not found", resp.json().get("detail", "").lower())

    def test_c5_05_nonexistent_user_on_predict_salary_db_resolution(self):
        """POST /api/predict-salary with nonexistent user_id (and no direct skills) -> HTTP 404, zero 500."""
        fake_id = f"ghost_user_{uuid.uuid4().hex}"
        resp = self.api_client.post("/api/predict-salary", json={"user_id": fake_id})
        self.assertEqual(resp.status_code, 404, f"Expected 404, got {resp.status_code}: {resp.text}")
        self.assertIn("not found", resp.json().get("detail", "").lower())

    def test_c5_06_nonexistent_question_on_evaluate_without_reference(self):
        """POST /api/evaluate with nonexistent question_id and no reference text -> HTTP 404, zero 500."""
        fake_qid = f"ghost_q_{uuid.uuid4().hex}"
        resp = self.api_client.post("/api/evaluate", json={
            "user_id": "challenger_user",
            "question_id": fake_qid,
            "code": "def solve(): return 42",
            "mock": True
        })
        self.assertEqual(resp.status_code, 404, f"Expected 404, got {resp.status_code}: {resp.text}")
        self.assertIn("not found", resp.json().get("detail", "").lower())

    def test_c5_07_whitespace_and_empty_id_queries(self):
        """Empty session_id or user_id returns 404 or 422 cleanly without 500."""
        # Empty string session_id in submit-test
        resp = self.api_client.post("/api/submit-test", json={
            "session_id": "   ",
            "user_id": "ghost_user",
            "answers": []
        })
        self.assertIn(resp.status_code, [400, 404, 422], f"Expected 4xx, got {resp.status_code}")
        self.assertNotEqual(resp.status_code, 500)


if __name__ == "__main__":
    unittest.main()
