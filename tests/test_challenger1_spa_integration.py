"""
tests/test_challenger1_spa_integration.py

Comprehensive Empirical Adversarial Verification Suite by Challenger 1.
Tests:
1. Route serving (GET / and GET /static/index.html) with zero-build React 18 tags
2. Robustness:
   - Empty / whitespace code submissions
   - Syntax error grading without 500 errors
   - Salary boundary clamping [0.0, 35.0] LPA under extreme / outlier inputs
   - Timer expiration on 90m/120m sessions and duplicate submissions
3. Invariants 1-7:
   - Invariant 1: 1000ms upload fallback timer (setTimeout, 1000)
   - Invariant 2: SESSION_ALPHA_099 and standard React state hook question
   - Invariant 3: 94%, S+, 5/5, Exceptional mastery demonstrated defaults
   - Invariant 4: Universal rounded-full on EVERY <button> tag
   - Invariant 5: Mandatory throw guard on missing skill_breakdown (no optional chaining)
   - Invariant 6: frontend/package.json declares 'tailwindcss': '^3.4.19'
   - Invariant 7: Standalone zero-build React 18 SPA
"""

import os
import sys
import glob
import json
import re
import uuid
import unittest
from datetime import datetime, timezone, timedelta

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


def extract_button_tags(content: str):
    """Parses JSX/HTML to extract every opening <button ...> tag."""
    buttons = []
    i = 0
    n = len(content)
    while i < n:
        if content[i:i+7].lower() == '<button' and (i + 7 == n or content[i+7] in ' \t\r\n>'):
            start = i
            i += 7
            in_quote = None
            brace_depth = 0
            while i < n:
                ch = content[i]
                if in_quote:
                    if ch == in_quote and (i == 0 or content[i-1] != '\\'):
                        in_quote = None
                elif ch in ('"', "'", '`'):
                    in_quote = ch
                elif ch == '{':
                    brace_depth += 1
                elif ch == '}':
                    brace_depth = max(0, brace_depth - 1)
                elif ch == '>' and brace_depth == 0 and in_quote is None:
                    buttons.append((start, i + 1, content[start:i+1]))
                    break
                i += 1
        else:
            i += 1
    return buttons


class TestChallenger1MasterSPAIntegration(unittest.TestCase):
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

    @classmethod
    def tearDownClass(cls):
        for sid in cls.created_sessions:
            cls.db.test_sessions.delete_many({"session_id": sid})
            cls.db.test_submissions.delete_many({"session_id": sid})
        for sub_id in cls.created_submissions:
            cls.db.submissions.delete_many({"_id": sub_id})

    # =========================================================================
    # PART 1: ROUTE SERVING & ZERO-BUILD REACT 18 SPA SCRIPT TAGS
    # =========================================================================

    def test_r1_root_route_serves_html_with_react18_scripts(self):
        """GET / returns HTTP 200 with text/html and zero-build React 18 script tags."""
        resp = self.api_client.get("/")
        self.assertEqual(resp.status_code, 200, f"GET / returned status {resp.status_code}")
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        body = resp.text

        # Verify React 18 & ReactDOM 18 UMD scripts
        self.assertIn("react@18/umd/react.production.min.js", body, "Missing React 18 script tag")
        self.assertIn("react-dom@18/umd/react-dom.production.min.js", body, "Missing ReactDOM 18 script tag")
        self.assertIn("@babel/standalone/babel.min.js", body, "Missing Babel Standalone script tag")
        self.assertIn("cdn.tailwindcss.com", body, "Missing Tailwind CSS CDN script tag")
        self.assertIn('id="root"', body, "Missing #root mount element")

    def test_r2_static_index_html_route_serves_identical_bundle(self):
        """GET /static/index.html returns HTTP 200 with zero-build React 18 scripts."""
        resp = self.api_client.get("/static/index.html")
        self.assertEqual(resp.status_code, 200, f"GET /static/index.html returned status {resp.status_code}")
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        body = resp.text

        self.assertIn("react@18/umd/react.production.min.js", body)
        self.assertIn("react-dom@18/umd/react-dom.production.min.js", body)
        self.assertIn("@babel/standalone/babel.min.js", body)
        self.assertIn('id="root"', body)

    # =========================================================================
    # PART 2: ROBUSTNESS & ADVERSARIAL STRESS PROBING
    # =========================================================================

    def test_adv_empty_and_whitespace_code_submissions(self):
        """Adversarial probe: empty, tab, and whitespace code submissions to POST /api/evaluate."""
        empty_payloads = ["", "   ", "\t\t\n\r  \n"]
        for p in empty_payloads:
            resp = self.api_client.post(
                "/api/evaluate",
                json={
                    "user_id": "challenger1_tester",
                    "question_id": "adv_q_empty",
                    "code": p,
                    "problem_description": "Implement binary search.",
                    "reference_solution": "def search(nums, target): return 0",
                    "mock": True,
                }
            )
            self.assertEqual(resp.status_code, 200, f"Empty code payload caused status {resp.status_code}")
            data = resp.json()
            self.assertIn("passed", data)
            self.assertFalse(data["passed"], "Empty code should not pass evaluation")
            self.assertEqual(data["score"], 0, "Pure empty/whitespace code score must be 0")
            if "submission_id" in data:
                self.created_submissions.append(data["submission_id"])

        # Also probe non-substantive comment-only submission
        resp_comment = self.api_client.post(
            "/api/evaluate",
            json={
                "user_id": "challenger1_tester",
                "question_id": "adv_q_comment",
                "code": "# only comments\n   ",
                "problem_description": "Implement binary search.",
                "reference_solution": "def search(nums, target): return 0",
                "mock": True,
            }
        )
        self.assertEqual(resp_comment.status_code, 200)
        c_data = resp_comment.json()
        self.assertFalse(c_data["passed"])
        self.assertLessEqual(c_data["score"], 35, "Non-substantive comment code score must be penalized (<= 35)")
        if "submission_id" in c_data:
            self.created_submissions.append(c_data["submission_id"])

    def test_adv_syntax_error_defensive_grading(self):
        """Adversarial probe: invalid Python syntax AST evaluation without 500 server crashes."""
        bad_snippets = [
            "def broken_syntax(:\n    return 42",
            "for x in range(10\n    print(x)",
            "class NonTerminated:\n    def __init__(self):\n        pass???",
            "import @#$ invalid",
        ]
        for snippet in bad_snippets:
            resp = self.api_client.post(
                "/api/evaluate",
                json={
                    "user_id": "challenger1_tester",
                    "question_id": "adv_q_syntax",
                    "code": snippet,
                    "problem_description": "Return target sum.",
                    "reference_solution": "def twoSum(): pass",
                    "mock": True,
                }
            )
            self.assertEqual(resp.status_code, 200, f"Syntax error triggered HTTP {resp.status_code}")
            data = resp.json()
            self.assertFalse(data["passed"], "Syntax error must fail")
            self.assertLessEqual(data["score"], 30, "Syntax error score must be penalized (<= 30)")
            self.assertIn("syntax", data["feedback"].lower(), "Feedback should notify candidate of syntax error")
            if "submission_id" in data:
                self.created_submissions.append(data["submission_id"])

    def test_adv_salary_boundary_clamping_range_0_to_35_lpa(self):
        """Adversarial probe: POST /api/predict-salary clamps between [0.0, 35.0] LPA across extreme inputs."""
        extreme_cases = [
            # Minimal / zeroed out
            {"skills": [], "mcq_score": 0.0, "coding_score": 0.0, "experience_tier": "fresher"},
            # Negative scores
            {"skills": [], "mcq_score": -999.0, "coding_score": -500.0, "experience_tier": "fresher"},
            # Extreme high outlier scores (> 1000)
            {"skills": ["Python", "AWS", "Kubernetes", "System Design"], "mcq_score": 1000.0, "coding_score": 5000.0, "experience_tier": "lead"},
            # Maximum skills payload
            {
                "skills": ["Python", "Go", "Java", "C++", "Rust", "Docker", "Kubernetes", "AWS", "GCP", "Microservices", "Kafka", "PostgreSQL", "Redis"],
                "domain": "Cloud & DevOps",
                "mcq_score": 100.0,
                "coding_score": 100.0,
                "experience_tier": "lead"
            },
            # Empty dictionary payload
            {}
        ]

        for case in extreme_cases:
            resp = self.api_client.post("/api/predict-salary", json=case)
            self.assertEqual(resp.status_code, 200, f"Predict salary returned {resp.status_code} for {case}")
            data = resp.json()
            lpa = data.get("predicted_lpa")
            self.assertIsNotNone(lpa, "predicted_lpa must be present")
            self.assertGreaterEqual(lpa, 0.0, f"Predicted LPA {lpa} is below 0.0 minimum boundary")
            self.assertLessEqual(lpa, 35.0, f"Predicted LPA {lpa} exceeds 35.0 maximum boundary")

    def test_adv_timer_expiration_and_anti_tampering(self):
        """Adversarial probe: 90m/120m assessment deadline expiration and duplicate submission handling."""
        sid = f"c1_exp_{uuid.uuid4().hex[:6]}"
        now_utc = datetime.now(timezone.utc)
        # Create an already expired session in MongoDB
        self.db.test_sessions.insert_one({
            "session_id": sid,
            "user_id": "c1_cand",
            "time_limit_minutes": 120,
            "started_at": (now_utc - timedelta(minutes=130)).isoformat(),
            "expires_at": (now_utc - timedelta(minutes=10)).isoformat(),
            "frontend_payload": {"session_id": sid, "questions": []},
            "evaluation_key": {"0": {"correct_answer": "C"}},
        })
        self.created_sessions.append(sid)

        # 1. Submit expired session
        resp = self.api_client.post(
            "/api/submit-test",
            json={"session_id": sid, "user_id": "c1_cand", "answers": [{"q_index": 0, "user_answer": "C"}]}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "submitted_expired", "Session submitted past deadline must have submitted_expired status")
        self.assertTrue(data.get("is_expired"), "is_expired flag must be True")

        # 2. Resubmit attempt (anti-cheat idempotent/conflict prevention)
        resp2 = self.api_client.post(
            "/api/submit-test",
            json={"session_id": sid, "user_id": "c1_cand", "answers": [{"q_index": 0, "user_answer": "A"}]}
        )
        # Resubmitting must either gracefully reject with 409 or return the existing submission without corruption
        self.assertIn(resp2.status_code, (200, 409), f"Duplicate submission returned unexpected status {resp2.status_code}")

    # =========================================================================
    # PART 3: INVARIANTS 1-7 DEEP AST & CODE INSPECTION
    # =========================================================================

    def test_inv1_upload_1000ms_fallback_timer(self):
        """Invariant 1: UploadResume retains 1000ms fallback timer (setTimeout, 1000)."""
        fe_path = os.path.join(PROJECT_ROOT, "frontend", "src", "components", "UploadResume.jsx")
        st_path = os.path.join(PROJECT_ROOT, "static", "index.html")

        with open(fe_path, "r", encoding="utf-8") as f:
            fe_content = f.read()
        with open(st_path, "r", encoding="utf-8") as f:
            st_content = f.read()

        self.assertIn("setTimeout", fe_content, "UploadResume.jsx missing setTimeout")
        self.assertIn("1000", fe_content, "UploadResume.jsx missing 1000ms timer constant")
        self.assertIn("setTimeout", st_content, "static/index.html missing setTimeout")
        self.assertIn("1000", st_content, "static/index.html missing 1000ms timer constant")

    def test_inv2_quiz_session_alpha_099_and_react_state_question(self):
        """Invariant 2: Quiz retains SESSION_ALPHA_099 and 'Which hook is used to manage state'."""
        fe_path = os.path.join(PROJECT_ROOT, "frontend", "src", "components", "Quiz.jsx")
        st_path = os.path.join(PROJECT_ROOT, "static", "index.html")

        with open(fe_path, "r", encoding="utf-8") as f:
            fe_content = f.read()
        with open(st_path, "r", encoding="utf-8") as f:
            st_content = f.read()

        self.assertIn("SESSION_ALPHA_099", fe_content, "Quiz.jsx missing SESSION_ALPHA_099")
        self.assertIn("Which hook is used to manage state", fe_content, "Quiz.jsx missing hook question")
        self.assertIn("SESSION_ALPHA_099", st_content, "static/index.html missing SESSION_ALPHA_099")
        self.assertIn("Which hook is used to manage state", st_content, "static/index.html missing hook question")

    def test_inv3_result_dashboard_defaults(self):
        """Invariant 3: ResultDashboard retains fallback defaults (94, S+, 5, Exceptional mastery demonstrated)."""
        fe_path = os.path.join(PROJECT_ROOT, "frontend", "src", "components", "ResultDashboard.jsx")
        st_path = os.path.join(PROJECT_ROOT, "static", "index.html")

        with open(fe_path, "r", encoding="utf-8") as f:
            fe_content = f.read()
        with open(st_path, "r", encoding="utf-8") as f:
            st_content = f.read()

        for item in ["94", "S+", "5", "Exceptional mastery demonstrated"]:
            self.assertIn(item, fe_content, f"ResultDashboard.jsx missing default '{item}'")
            self.assertIn(item, st_content, f"static/index.html missing default '{item}'")

    def test_inv4_universal_rounded_full_on_all_buttons(self):
        """Invariant 4: Universal rounded-full styling on EVERY <button> tag across all HTML/JSX files."""
        files = [os.path.join(PROJECT_ROOT, "static", "index.html")] + sorted(
            glob.glob(os.path.join(PROJECT_ROOT, "frontend", "src", "components", "*.jsx"))
        )

        violations = []
        total_buttons = 0

        for fpath in files:
            rel = os.path.relpath(fpath, PROJECT_ROOT)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            btns = extract_button_tags(content)
            total_buttons += len(btns)
            for start_pos, end_pos, tag in btns:
                line_no = content[:start_pos].count("\n") + 1
                if "rounded-full" not in tag:
                    violations.append((rel, line_no, " ".join(tag.split())))

        self.assertGreater(total_buttons, 0, "No buttons found to inspect")
        self.assertEqual(
            len(violations),
            0,
            f"Found {len(violations)} button(s) violating rounded-full invariant: {violations}"
        )

    def test_inv5_mandatory_throw_on_missing_skill_breakdown(self):
        """Invariant 5: ResultDashboard MUST throw if results && !results.skill_breakdown (no optional chaining)."""
        target_files = [
            os.path.join(PROJECT_ROOT, "static", "index.html"),
            os.path.join(PROJECT_ROOT, "frontend", "src", "components", "ResultDashboard.jsx"),
        ]

        throw_regex = re.compile(
            r"if\s*\(\s*results\s*&&\s*!results\.skill_breakdown\s*\)\s*\{?\s*throw\s+new\s+Error\s*\(",
            re.DOTALL,
        )

        for fpath in target_files:
            rel = os.path.relpath(fpath, PROJECT_ROOT)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn(
                "results?.skill_breakdown?.map",
                content,
                f"Forbidden optional chaining 'results?.skill_breakdown?.map' detected in {rel}"
            )
            self.assertTrue(
                bool(throw_regex.search(content)),
                f"Missing mandatory throw guard 'if (results && !results.skill_breakdown) throw new Error(...)' in {rel}"
            )

    def test_inv6_package_json_tailwindcss_version(self):
        """Invariant 6: frontend/package.json retains 'tailwindcss': '^3.4.19'."""
        pkg_path = os.path.join(PROJECT_ROOT, "frontend", "package.json")
        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
        deps = pkg.get("dependencies", {})
        dev_deps = pkg.get("devDependencies", {})
        tw_ver = deps.get("tailwindcss") or dev_deps.get("tailwindcss")
        self.assertEqual(tw_ver, "^3.4.19", f"Expected tailwindcss '^3.4.19', got '{tw_ver}'")

    def test_inv7_zero_build_spa_contract(self):
        """Invariant 7: static/index.html is a standalone zero-build React 18 SPA."""
        st_path = os.path.join(PROJECT_ROOT, "static", "index.html")
        with open(st_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('<div id="root"></div>', content, "Missing #root mount element")
        self.assertIn("ReactDOM.createRoot", content, "Missing React 18 createRoot invocation")
        self.assertIn("text/babel", content, "Missing text/babel script block for in-browser transpilation")
        self.assertIn("cdn.tailwindcss.com", content, "Missing Tailwind CDN for zero-build styling")


if __name__ == "__main__":
    unittest.main()
