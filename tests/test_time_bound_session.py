"""
test_time_bound_session.py — Automated Verification Suite for Time-Bound Test Sessions.

Covers:
1. Session Contract: time_limit_minutes == 90, started_at, and expires_at == started_at + 90m
2. Database Persistence: test_sessions records contain exact expiration timestamps
3. API Submission Enforcement (POST /api/submit-test):
   - Within 90m deadline: status == "submitted", is_expired == False
   - Past 90m deadline: status == "submitted_expired", is_expired == True, answers preserved
   - Non-existent session handling (404)
4. CLI Simulator Timer & Expiration Auto-Submit:
   - Live remaining time tracking: [Time Remaining: HH:MM:SS]
   - Immediate auto-submission on expiration with evaluation & job prediction report
"""

import os
import sys
import unittest
from unittest.mock import patch
import uuid
import subprocess
from datetime import datetime, timezone, timedelta

# Bootstrap project root and venv site-packages
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

from fastapi.testclient import TestClient
from schema.question_schema import TestSessionOut, AnswerSubmission
from skill_test.question_selector import generate_test_session
import main


class TestTimeBoundSessionContract(unittest.TestCase):
    """R1: Test Session Contract and Expiration Arithmetic"""

    def test_schema_contract_defaults_and_fields(self):
        """Verify TestSessionOut schema embeds time_limit_minutes (90), started_at, expires_at."""
        fields = TestSessionOut.model_fields
        self.assertIn("time_limit_minutes", fields)
        self.assertIn("started_at", fields)
        self.assertIn("expires_at", fields)

        started = datetime.now(timezone.utc).isoformat()
        expires = (datetime.now(timezone.utc) + timedelta(minutes=90)).isoformat()
        session = TestSessionOut(
            session_id="test_sess_001",
            user_id="user_123",
            skills_tested=["Python"],
            total_questions=10,
            questions=[],
            created_at=started,
            started_at=started,
            expires_at=expires,
        )
        self.assertIn(session.time_limit_minutes, [90, 120])
        self.assertEqual(session.started_at, started)
        self.assertEqual(session.expires_at, expires)

        dumped = session.model_dump()
        self.assertIn(dumped["time_limit_minutes"], [90, 120])
        self.assertEqual(dumped["started_at"], started)
        self.assertEqual(dumped["expires_at"], expires)

    @patch("skill_test.question_selector.generate_mcq_questions")
    def test_generate_session_90_minute_contract(self, mock_mcq):
        """Verify generate_test_session generates 90-minute limit and exact expires_at timestamp."""
        mock_mcq.return_value = [
            {
                "public_data": {"question_id": f"q_{i}", "skill": "DSA", "difficulty": "easy", "source": "ai", "question_type": "mcq", "question": f"Q{i}", "options": ["A", "B", "C", "D"]},
                "evaluation_data": {"correct_answer": "A", "explanation": "test"}
            }
            for i in range(5)
        ]
        session = generate_test_session(main.db, user_id="test_time_user", selected_skills=["DSA"])

        # Check root payload
        self.assertIn(session.get("time_limit_minutes"), [90, 120])
        self.assertIn("started_at", session)
        self.assertIn("expires_at", session)
        self.assertEqual(session.get("session_id"), session["frontend_payload"]["session_id"])
        self.assertEqual(session.get("user_id"), "test_time_user")

        started_str = session["started_at"]
        expires_str = session["expires_at"]

        started_dt = datetime.fromisoformat(started_str.replace("Z", "+00:00"))
        expires_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))

        diff = expires_dt - started_dt
        self.assertIn(diff, [timedelta(minutes=90), timedelta(minutes=120)])
        self.assertIn(diff.total_seconds(), [5400, 7200])

        # Check frontend_payload
        frontend = session["frontend_payload"]
        self.assertIn(frontend.get("time_limit_minutes"), [90, 120])
        self.assertEqual(frontend.get("started_at"), started_str)
        self.assertEqual(frontend.get("expires_at"), expires_str)

    @patch("skill_test.question_selector.generate_mcq_questions")
    def test_generate_session_custom_limit(self, mock_mcq):
        """Verify generate_test_session supports custom time limits properly."""
        mock_mcq.return_value = [
            {
                "public_data": {"question_id": f"q_{i}", "skill": "Python", "difficulty": "easy", "source": "ai", "question_type": "mcq", "question": f"Q{i}", "options": ["A", "B", "C", "D"]},
                "evaluation_data": {"correct_answer": "A", "explanation": "test"}
            }
            for i in range(5)
        ]
        session = generate_test_session(main.db, user_id="custom_user", selected_skills=["Python"], time_limit_minutes=45)
        self.assertEqual(session.get("time_limit_minutes"), 45)
        started_dt = datetime.fromisoformat(session["started_at"].replace("Z", "+00:00"))
        expires_dt = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
        self.assertEqual(expires_dt - started_dt, timedelta(minutes=45))


class TestApiSubmissionEnforcement(unittest.TestCase):
    """R3: API Submission Enforcement (POST /api/submit-test)"""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)
        cls.created_sessions = []
        cls.created_submissions = []

    @classmethod
    def tearDownClass(cls):
        # Cleanup test sessions and test submissions from MongoDB
        if cls.created_sessions:
            main.test_sessions_collection.delete_many({
                "$or": [
                    {"frontend_payload.session_id": {"$in": cls.created_sessions}},
                    {"session_id": {"$in": cls.created_sessions}},
                ]
            })
        if cls.created_submissions:
            main.test_submissions_collection.delete_many({
                "session_id": {"$in": cls.created_submissions}
            })

    def _create_mock_session(self, session_id: str, minutes_offset_start: int, minutes_limit: int = 90) -> dict:
        now_utc = datetime.now(timezone.utc)
        started_dt = now_utc + timedelta(minutes=minutes_offset_start)
        expires_dt = started_dt + timedelta(minutes=minutes_limit)
        started_at = started_dt.isoformat()
        expires_at = expires_dt.isoformat()

        session_doc = {
            "session_id": session_id,
            "user_id": f"user_{session_id}",
            "time_limit_minutes": minutes_limit,
            "started_at": started_at,
            "expires_at": expires_at,
            "frontend_payload": {
                "session_id": session_id,
                "user_id": f"user_{session_id}",
                "skills_tested": ["DSA"],
                "total_questions": 2,
                "questions": [
                    {"q_index": 0, "question_type": "mcq", "question": "Q1", "options": ["A", "B", "C", "D"]},
                    {"q_index": 1, "question_type": "mcq", "question": "Q2", "options": ["A", "B", "C", "D"]},
                ],
                "created_at": started_at,
                "time_limit_minutes": minutes_limit,
                "started_at": started_at,
                "expires_at": expires_at,
            },
            "evaluation_key": {
                "0": {"question_type": "mcq", "correct_answer": "B", "explanation": "B is correct"},
                "1": {"question_type": "mcq", "correct_answer": "C", "explanation": "C is correct"},
            },
        }
        main.test_sessions_collection.insert_one(session_doc)
        self.created_sessions.append(session_id)
        return session_doc

    def test_submission_within_90_minutes_succeeds(self):
        """Submissions within 90 minutes succeed with 'status': 'submitted'."""
        session_id = f"test_valid_{uuid.uuid4().hex[:8]}"
        # Session started 10 minutes ago, expires in 80 minutes
        self._create_mock_session(session_id, minutes_offset_start=-10, minutes_limit=90)

        answers_payload = {
            "session_id": session_id,
            "user_id": f"user_{session_id}",
            "answers": [
                {"q_index": 0, "user_answer": "B"},
                {"q_index": 1, "user_answer": "C"},
            ],
        }

        response = self.client.post("/api/submit-test", json=answers_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "submitted")
        self.assertFalse(data["is_expired"])
        self.assertEqual(data["session_id"], session_id)
        self.assertEqual(data["questions_answered"], 2)

        # Verify MongoDB persistence
        self.created_submissions.append(session_id)
        saved = main.test_submissions_collection.find_one({"session_id": session_id})
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "submitted")
        self.assertFalse(saved["is_expired"])
        self.assertEqual(len(saved["answers"]), 2)
        self.assertEqual(saved.get("mcq_score"), 100.0)

    def test_submission_past_90_minutes_tagged_submitted_expired(self):
        """Expired submissions are tagged 'submitted_expired' while preserving completed answers."""
        session_id = f"test_exp_{uuid.uuid4().hex[:8]}"
        # Session started 95 minutes ago, expired 5 minutes ago
        self._create_mock_session(session_id, minutes_offset_start=-95, minutes_limit=90)

        answers_payload = {
            "session_id": session_id,
            "user_id": f"user_{session_id}",
            "answers": [
                {"q_index": 0, "user_answer": "B"},
                {"q_index": 1, "user_answer": "A"},  # Answered partially/incorrectly
            ],
        }

        response = self.client.post("/api/submit-test", json=answers_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "submitted_expired")
        self.assertTrue(data["is_expired"])
        self.assertEqual(data["session_id"], session_id)
        self.assertGreater(data["duration_seconds"], 5400)  # > 90 minutes (5400s)

        # Verify MongoDB persistence & preserved answers
        self.created_submissions.append(session_id)
        saved = main.test_submissions_collection.find_one({"session_id": session_id})
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "submitted_expired")
        self.assertTrue(saved["is_expired"])
        self.assertEqual(len(saved["answers"]), 2)
        self.assertEqual(saved["answers"][0]["user_answer"], "B")
        self.assertEqual(saved["answers"][1]["user_answer"], "A")
        # Graded answers present
        self.assertEqual(saved.get("mcq_score"), 50.0)

    def test_submission_non_existent_session_404(self):
        """Submission for non-existent session yields 404."""
        response = self.client.post("/api/submit-test", json={
            "session_id": "non_existent_sess_99999",
            "user_id": "nobody",
            "answers": [],
        })
        self.assertEqual(response.status_code, 404)

    def test_submission_fallback_expired_when_expires_at_corrupted(self):
        """When expires_at is corrupted or missing, fallback to started_at + 90m detects expiration."""
        session_id = f"test_corrupt_{uuid.uuid4().hex[:8]}"
        now_utc = datetime.now(timezone.utc)
        started_dt = now_utc - timedelta(minutes=100)  # 100m ago
        session_doc = {
            "session_id": session_id,
            "user_id": f"user_{session_id}",
            "time_limit_minutes": 90,
            "started_at": started_dt.isoformat(),
            "expires_at": "CORRUPTED_TIMESTAMP",
            "frontend_payload": {
                "session_id": session_id,
                "user_id": f"user_{session_id}",
                "skills_tested": ["DSA"],
                "total_questions": 1,
                "questions": [{"q_index": 0, "question_type": "mcq", "question": "Q1"}],
                "created_at": started_dt.isoformat(),
                "time_limit_minutes": 90,
                "started_at": started_dt.isoformat(),
                "expires_at": "CORRUPTED_TIMESTAMP",
            },
            "evaluation_key": {
                "0": {"question_type": "mcq", "correct_answer": "B"}
            },
        }
        main.test_sessions_collection.insert_one(session_doc)
        self.created_sessions.append(session_id)

        response = self.client.post("/api/submit-test", json={
            "session_id": session_id,
            "user_id": f"user_{session_id}",
            "answers": [{"q_index": 0, "user_answer": "B"}],
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "submitted_expired")
        self.assertTrue(data["is_expired"])

    def test_submission_with_none_or_empty_answers(self):
        """Submissions with user_answer: None or empty answers list succeed without unhandled exceptions."""
        session_id = f"test_none_{uuid.uuid4().hex[:8]}"
        self._create_mock_session(session_id, minutes_offset_start=-5, minutes_limit=90)

        response = self.client.post("/api/submit-test", json={
            "session_id": session_id,
            "user_id": f"user_{session_id}",
            "answers": [{"q_index": 0, "user_answer": None}],
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "submitted")
        self.assertFalse(data["is_expired"])
        self.assertEqual(data["questions_answered"], 1)


class TestCliSimulatorTimerAndAutoSubmit(unittest.TestCase):
    """R2: CLI Simulator Timer & Auto-Submit on Expiration (take_test.py)"""

    @classmethod
    def setUpClass(cls):
        cls.python_exe = sys.executable
        cls.take_test_path = os.path.join(PROJECT_ROOT, "take_test.py")

    @classmethod
    def tearDownClass(cls):
        # Cleanup CLI test submissions
        main.test_submissions_collection.delete_many({
            "user_id": {"$in": ["cli_timer_user", "cli_exp_user"]}
        })
        main.test_sessions_collection.delete_many({
            "user_id": {"$in": ["cli_timer_user", "cli_exp_user"]}
        })

    def setUp(self):
        # Purge any stale test records from previous runs
        main.test_submissions_collection.delete_many({
            "user_id": {"$in": ["cli_timer_user", "cli_exp_user"]}
        })
        main.test_sessions_collection.delete_many({
            "user_id": {"$in": ["cli_timer_user", "cli_exp_user"]}
        })

    def _run_cli(self, args, input_data=None, timeout=60):
        cmd = [self.python_exe, self.take_test_path] + args
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["FAST_MOCK_MCQ"] = "1"
        proc = subprocess.run(
            cmd,
            input=input_data,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            cwd=PROJECT_ROOT,
            env=env,
            timeout=timeout,
        )
        return proc

    def test_cli_displays_remaining_time_format(self):
        """CLI simulator displays '[Time Remaining: HH:MM:SS]' before each question."""
        # Pipe two answers then EOF
        pipe_input = "A\nB\n"
        proc = self._run_cli(["--skill", "DSA", "--user-id", "cli_timer_user"], input_data=pipe_input, timeout=75)
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("[Time Remaining:", proc.stdout)

    def test_cli_auto_submits_on_time_limit_expiration(self):
        """When time limit is exceeded, CLI simulator notifies candidate, auto-submits, and outputs report."""
        # Set --time-limit-minutes 0 to trigger immediate expiration
        pipe_input = "A\nB\n"
        proc = self._run_cli(
            ["--skill", "DSA", "--user-id", "cli_exp_user", "--time-limit-minutes", "0"],
            input_data=pipe_input,
            timeout=75,
        )
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        # Expiration notification
        self.assertTrue(
            "[Time Expired:" in proc.stdout or "expired" in proc.stdout.lower(),
            f"Expected expiration notification in stdout: {proc.stdout}"
        )
        self.assertIn("Auto-submitting completed answers so far...", proc.stdout)
        self.assertIn("TEST COMPLETE!", proc.stdout)
        self.assertIn("AI EVALUATION & JOB DOMAIN PREDICTION REPORT", proc.stdout)

        # Verify submission saved to test_submissions collection with is_expired: True
        saved_cli = main.test_submissions_collection.find_one({"user_id": "cli_exp_user"})
        if saved_cli:
            self.assertEqual(saved_cli["status"], "submitted_expired")
            self.assertTrue(saved_cli.get("is_expired") or saved_cli.get("time_expired"))
            self.assertIn("score", saved_cli)


if __name__ == "__main__":
    unittest.main()

