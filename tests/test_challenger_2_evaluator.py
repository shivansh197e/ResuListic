"""
test_challenger_2_evaluator.py — Empirical Verification and Adversarial Challenge Suite (Challenger 2).

Scope:
1. Question context resolution across questions_moderate and questions_hard linked with solutions.
   - Multi-skill sampling (Array, Dynamic Programming, String, Hash Table, etc.)
   - Collision resistance between moderate and hard questions sharing identical index numbers.
   - Boundary inputs (None, empty string, non-existent ObjectId, malformed formats).
2. MongoDB submissions document persistence with diverse payload combinations and complete 9-field verification.
   - Strict type checking for all 9 fields (user_id, question_id, submitted_code, timestamp, passed, score, feedback, time_complexity, evaluation).
   - Diverse payloads: failing (score 0), perfect (score 100), Unicode/emojis, SQL/NoSQL tokens, 50KB payload, empty eval fallbacks.
   - Zero database pollution: automatic tracking, purge, and post-cleanup verification.
3. FastAPI POST /api/evaluate end-to-end integration via TestClient.
   - Moderate & Hard question resolution through endpoint.
   - Context override with custom description and reference solution.
   - Defensive error handling: 404 on missing question, 422 on invalid schema, strictly zero 500 errors.
   - Stress testing with 20 sequential calls and complete purge.
"""

import os
import sys
import time
import unittest
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from starlette.testclient import TestClient

# Ensure repo root and ml-services are in sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ML_SERVICES_DIR = os.path.join(REPO_ROOT, "ml-services")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(REPO_ROOT, ".env"))

import main
from skill_test.code_evaluator import (
    get_question_and_solution,
    save_submission,
    evaluate_code,
    mock_evaluate_code,
)
from schema.question_schema import EvaluateRequest, EvaluateResponse


class TestChallenger2Evaluator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI not set.")
        cls.client = MongoClient(uri)
        cls.db = cls.client.resulistic_db
        cls.api_client = TestClient(main.app)
        cls.inserted_sub_ids = []

    @classmethod
    def tearDownClass(cls):
        # Strict cleanup of all inserted test documents
        if cls.inserted_sub_ids:
            valid_oids = [ObjectId(sid) for sid in cls.inserted_sub_ids if ObjectId.is_valid(sid)]
            if valid_oids:
                cls.db.submissions.delete_many({"_id": {"$in": valid_oids}})
        cls.client.close()

    def record_sub_id(self, sub_id: str):
        if sub_id and sub_id not in self.inserted_sub_ids:
            self.inserted_sub_ids.append(sub_id)

    # =========================================================================
    # PART 1: Question Context Resolution across Moderate, Hard & Solutions
    # =========================================================================

    def test_01_question_resolution_moderate_collection_by_object_id(self):
        """Verify resolution of moderate questions linked to solutions using ObjectId across multiple skills."""
        sample_mod_questions = list(self.db.questions_moderate.find().limit(10))
        self.assertGreaterEqual(len(sample_mod_questions), 1, "questions_moderate collection is empty")

        for q in sample_mod_questions:
            qid_str = str(q["_id"])
            resolved_q, resolved_sol = get_question_and_solution(self.db, qid_str)

            # Assert question document
            self.assertEqual(resolved_q["_id"], q["_id"])
            self.assertEqual(resolved_q["skill"], q["skill"])
            self.assertEqual(resolved_q["index"], q["index"])
            self.assertEqual(resolved_q["title"], q["title"])
            self.assertTrue(bool(resolved_q.get("description")), "Moderate question description is empty")

            # Assert linked solution document
            self.assertIn("reference_solution", resolved_sol, f"No reference solution for moderate question {qid_str}")
            self.assertTrue(len(resolved_sol["reference_solution"]) > 0, "Reference solution is empty")
            self.assertEqual(resolved_sol.get("difficulty"), "moderate", f"Expected difficulty 'moderate', got {resolved_sol.get('difficulty')}")
            self.assertEqual(resolved_sol.get("skill"), q["skill"])
            self.assertEqual(resolved_sol.get("index"), q["index"])

    def test_02_question_resolution_hard_collection_by_object_id(self):
        """Verify resolution of hard questions linked to solutions using ObjectId across multiple skills."""
        sample_hard_questions = list(self.db.questions_hard.find().limit(10))
        self.assertGreaterEqual(len(sample_hard_questions), 1, "questions_hard collection is empty")

        for q in sample_hard_questions:
            qid_str = str(q["_id"])
            resolved_q, resolved_sol = get_question_and_solution(self.db, qid_str)

            # Assert question document
            self.assertEqual(resolved_q["_id"], q["_id"])
            self.assertEqual(resolved_q["skill"], q["skill"])
            self.assertEqual(resolved_q["index"], q["index"])
            self.assertEqual(resolved_q["title"], q["title"])
            self.assertTrue(bool(resolved_q.get("description")), "Hard question description is empty")

            # Assert linked solution document
            self.assertIn("reference_solution", resolved_sol, f"No reference solution for hard question {qid_str}")
            self.assertTrue(len(resolved_sol["reference_solution"]) > 0, "Reference solution is empty")
            self.assertEqual(resolved_sol.get("difficulty"), "hard", f"Expected difficulty 'hard', got {resolved_sol.get('difficulty')}")
            self.assertEqual(resolved_sol.get("skill"), q["skill"])
            self.assertEqual(resolved_sol.get("index"), q["index"])

    def test_03_question_resolution_collision_resistance_same_index(self):
        """Verify that hard questions sharing the same index number as moderate questions link to HARD solution."""
        # Find index 0 in both collections for skill 'Array'
        mod_q0 = self.db.questions_moderate.find_one({"skill": "Array", "index": 0})
        hard_q0 = self.db.questions_hard.find_one({"skill": "Array", "index": 0})

        self.assertIsNotNone(mod_q0)
        self.assertIsNotNone(hard_q0)
        self.assertNotEqual(mod_q0["_id"], hard_q0["_id"])

        # Resolve moderate question by ObjectId
        res_mq, res_msol = get_question_and_solution(self.db, str(mod_q0["_id"]))
        self.assertEqual(res_mq["_id"], mod_q0["_id"])
        self.assertEqual(res_msol["difficulty"], "moderate")
        self.assertEqual(res_msol["skill"], "Array")
        self.assertEqual(res_msol["index"], 0)

        # Resolve hard question by ObjectId
        res_hq, res_hsol = get_question_and_solution(self.db, str(hard_q0["_id"]))
        self.assertEqual(res_hq["_id"], hard_q0["_id"])
        self.assertEqual(res_hsol["difficulty"], "hard")
        self.assertEqual(res_hsol["skill"], "Array")
        self.assertEqual(res_hsol["index"], 0)

        # Confirm reference solutions are distinct
        self.assertNotEqual(res_msol["reference_solution"], res_hsol["reference_solution"])

    def test_04_question_resolution_by_integer_index(self):
        """Verify fallback resolution using string integer index."""
        mod_q = self.db.questions_moderate.find_one({"index": 0})
        self.assertIsNotNone(mod_q, "No moderate question with index 0")

        resolved_q, resolved_sol = get_question_and_solution(self.db, "0")
        self.assertEqual(resolved_q["index"], 0)
        self.assertIn("reference_solution", resolved_sol)
        self.assertTrue(len(resolved_sol["reference_solution"]) > 0)

    def test_05_question_resolution_boundary_and_invalid_inputs(self):
        """Verify defensive handling of invalid question IDs, missing DB, and None inputs."""
        # Non-existent ObjectId
        fake_oid = str(ObjectId())
        q, sol = get_question_and_solution(self.db, fake_oid)
        self.assertEqual(q, {})
        self.assertEqual(sol, {})

        # Arbitrary strings and special characters
        for invalid_id in ["", "not_an_id", "!!@@##$$", "-999", "99999999", "   "]:
            q, sol = get_question_and_solution(self.db, invalid_id)
            self.assertEqual(q, {})
            self.assertEqual(sol, {})

        # None database or None question_id
        q, sol = get_question_and_solution(None, "some_id")
        self.assertEqual(q, {})
        self.assertEqual(sol, {})

        q, sol = get_question_and_solution(self.db, None)
        self.assertEqual(q, {})
        self.assertEqual(sol, {})

    # =========================================================================
    # PART 2: MongoDB Submissions Document Persistence & Diverse Payloads
    # =========================================================================

    def test_06_submissions_strict_9_fields_verification(self):
        """Verify all 9 fields with strict type checking: user_id, question_id, submitted_code, timestamp, passed, score, feedback, time_complexity, evaluation."""
        user_id = "test_user_challenger2_fields_strict"
        qid = "test_qid_123"
        code = "def solve(): return 42"
        eval_result = {
            "passed": True,
            "score": 95,
            "feedback": "Optimal solution with O(1) space.",
            "time_complexity": "O(1)",
        }

        sub_id = save_submission(
            db=self.db,
            user_id=user_id,
            question_id=qid,
            submitted_code=code,
            evaluation_result=eval_result,
        )
        self.record_sub_id(sub_id)

        # Assert returned ID format
        self.assertTrue(ObjectId.is_valid(sub_id), f"Invalid ObjectId returned: {sub_id}")

        # Fetch from MongoDB
        doc = self.db.submissions.find_one({"_id": ObjectId(sub_id)})
        self.assertIsNotNone(doc, f"Submission {sub_id} not found in MongoDB")

        # 1. user_id: strict str
        self.assertTrue(type(doc["user_id"]) is str)
        self.assertEqual(doc["user_id"], user_id)

        # 2. question_id: strict str
        self.assertTrue(type(doc["question_id"]) is str)
        self.assertEqual(doc["question_id"], qid)

        # 3. submitted_code: strict str
        self.assertTrue(type(doc["submitted_code"]) is str)
        self.assertEqual(doc["submitted_code"], code)

        # 4. timestamp: strict str and valid ISO-8601 with tzinfo
        self.assertTrue(type(doc["timestamp"]) is str)
        parsed_dt = datetime.fromisoformat(doc["timestamp"])
        self.assertIsNotNone(parsed_dt.tzinfo, "Timestamp must contain timezone info")

        # 5. passed: strict bool
        self.assertTrue(type(doc["passed"]) is bool)
        self.assertEqual(doc["passed"], True)

        # 6. score: strict int
        self.assertTrue(type(doc["score"]) is int)
        self.assertEqual(doc["score"], 95)

        # 7. feedback: strict str
        self.assertTrue(type(doc["feedback"]) is str)
        self.assertEqual(doc["feedback"], eval_result["feedback"])

        # 8. time_complexity: strict str
        self.assertTrue(type(doc["time_complexity"]) is str)
        self.assertEqual(doc["time_complexity"], "O(1)")

        # 9. evaluation: strict dict
        self.assertTrue(type(doc["evaluation"]) is dict)
        self.assertEqual(doc["evaluation"], eval_result)

    def test_07_submissions_diverse_payload_combinations(self):
        """Test diverse payloads: zero score, perfect score, Unicode/emoji, injection tokens, 50KB payload, empty eval."""
        test_payloads = [
            # 1. Failing / Zero score
            {
                "user_id": "candidate_fail_0",
                "question_id": "qid_zero",
                "code": "syntax error :::: broken",
                "eval": {"passed": False, "score": 0, "feedback": "Syntax error at line 1", "time_complexity": "N/A"},
                "expected_passed": False,
                "expected_score": 0,
            },
            # 2. Perfect score 100
            {
                "user_id": "candidate_perfect_100",
                "question_id": "qid_perfect",
                "code": "def solution(x): return x",
                "eval": {"passed": True, "score": 100, "feedback": "Flawless code.", "time_complexity": "O(1)"},
                "expected_passed": True,
                "expected_score": 100,
            },
            # 3. Unicode, multi-language, Emojis, and special characters
            {
                "user_id": "user_🚀_🔥_你好_123",
                "question_id": "qid_unicode_测试",
                "code": "# Python code with unicode comments: 你好\nprint('🚀 Testing Emojis!')\n'quote\"escaped\\'",
                "eval": {"passed": True, "score": 85, "feedback": "Special characters preserved ✨", "time_complexity": "O(N)"},
                "expected_passed": True,
                "expected_score": 85,
            },
            # 4. Injection-style strings in IDs
            {
                "user_id": "admin' OR '1'='1; --",
                "question_id": "{\"$gt\": \"\"}",
                "code": "class Exploit:\n    def __init__(self): pass",
                "eval": {"passed": False, "score": 10, "feedback": "Suspicious payload", "time_complexity": "O(N)"},
                "expected_passed": False,
                "expected_score": 10,
            },
            # 5. Large 50 KB code submission
            {
                "user_id": "heavy_candidate_50kb",
                "question_id": "qid_large",
                "code": "# Large code block\n" + ("x = 1\n" * 5000),
                "eval": {"passed": True, "score": 75, "feedback": "Large submission", "time_complexity": "O(N)"},
                "expected_passed": True,
                "expected_score": 75,
            },
            # 6. Sparse evaluation result with missing keys (tests fallbacks)
            {
                "user_id": "sparse_candidate",
                "question_id": "qid_sparse",
                "code": "def pass_code(): pass",
                "eval": {},
                "expected_passed": False,
                "expected_score": 0,
            },
        ]

        for p in test_payloads:
            sub_id = save_submission(
                db=self.db,
                user_id=p["user_id"],
                question_id=p["question_id"],
                submitted_code=p["code"],
                evaluation_result=p["eval"],
            )
            self.record_sub_id(sub_id)

            saved_doc = self.db.submissions.find_one({"_id": ObjectId(sub_id)})
            self.assertIsNotNone(saved_doc, f"Failed to persist payload for user {p['user_id']}")
            self.assertEqual(saved_doc["user_id"], p["user_id"])
            self.assertEqual(saved_doc["question_id"], p["question_id"])
            self.assertEqual(saved_doc["submitted_code"], p["code"])
            self.assertEqual(saved_doc["passed"], p["expected_passed"])
            self.assertEqual(saved_doc["score"], p["expected_score"])

    # =========================================================================
    # PART 3: FastAPI POST /api/evaluate End-to-End Integration via TestClient
    # =========================================================================

    def test_08_fastapi_evaluate_moderate_question_success(self):
        """End-to-end evaluation of moderate question via POST /api/evaluate."""
        mod_q = self.db.questions_moderate.find_one()
        self.assertIsNotNone(mod_q)
        qid_str = str(mod_q["_id"])

        mod_sol = self.db.solutions.find_one({"skill": mod_q["skill"], "index": mod_q["index"], "difficulty": "moderate"})
        self.assertIsNotNone(mod_sol)

        payload = {
            "user_id": "testclient_user_mod",
            "question_id": qid_str,
            "code": mod_sol["reference_solution"],
            "mock": True,
        }

        resp = self.api_client.post("/api/evaluate", json=payload)
        self.assertEqual(resp.status_code, 200, f"Failed with {resp.status_code}: {resp.text}")

        data = resp.json()
        validated_response = EvaluateResponse.model_validate(data)
        self.assertTrue(validated_response.passed)
        self.assertGreaterEqual(validated_response.score, 80)
        self.assertTrue(bool(validated_response.feedback))
        self.assertTrue(bool(validated_response.time_complexity))
        self.assertTrue(bool(validated_response.submission_id))
        self.record_sub_id(validated_response.submission_id)

        # Check DB persistence
        db_doc = self.db.submissions.find_one({"_id": ObjectId(validated_response.submission_id)})
        self.assertIsNotNone(db_doc)
        self.assertEqual(db_doc["user_id"], payload["user_id"])
        self.assertEqual(db_doc["question_id"], qid_str)

    def test_09_fastapi_evaluate_hard_question_success(self):
        """End-to-end evaluation of hard question via POST /api/evaluate."""
        hard_q = self.db.questions_hard.find_one()
        self.assertIsNotNone(hard_q)
        qid_str = str(hard_q["_id"])

        hard_sol = self.db.solutions.find_one({"skill": hard_q["skill"], "index": hard_q["index"], "difficulty": "hard"})
        self.assertIsNotNone(hard_sol)

        payload = {
            "user_id": "testclient_user_hard",
            "question_id": qid_str,
            "code": hard_sol["reference_solution"],
            "mock": True,
        }

        resp = self.api_client.post("/api/evaluate", json=payload)
        self.assertEqual(resp.status_code, 200, f"Failed with {resp.status_code}: {resp.text}")

        data = resp.json()
        validated_response = EvaluateResponse.model_validate(data)
        self.assertTrue(validated_response.passed)
        self.assertGreaterEqual(validated_response.score, 80)
        self.record_sub_id(validated_response.submission_id)

        # Check DB persistence
        db_doc = self.db.submissions.find_one({"_id": ObjectId(validated_response.submission_id)})
        self.assertIsNotNone(db_doc)
        self.assertEqual(db_doc["user_id"], payload["user_id"])
        self.assertEqual(db_doc["question_id"], qid_str)

    def test_10_fastapi_evaluate_direct_problem_and_solution_override(self):
        """Verify API allows passing custom problem_description and reference_solution."""
        payload = {
            "user_id": "testclient_custom_override",
            "question_id": "custom_override_qid",
            "code": "def custom(): return 100",
            "problem_description": "Custom prompt description",
            "reference_solution": "def custom(): return 100",
            "mock": True,
        }

        resp = self.api_client.post("/api/evaluate", json=payload)
        self.assertEqual(resp.status_code, 200, f"Failed with {resp.status_code}: {resp.text}")

        data = resp.json()
        validated_response = EvaluateResponse.model_validate(data)
        self.assertTrue(validated_response.passed)
        self.record_sub_id(validated_response.submission_id)

    def test_11_fastapi_evaluate_error_scenarios_no_500_errors(self):
        """Verify defensive HTTP responses: 404 on missing question, 422 on bad schema, strictly 0 500 errors."""
        # 1. Non-existent question_id without problem_description -> HTTP 404
        resp_404 = self.api_client.post("/api/evaluate", json={
            "user_id": "user_404",
            "question_id": "completely_fake_qid_9999",
            "code": "def solve(): pass",
            "mock": True,
        })
        self.assertEqual(resp_404.status_code, 404, f"Expected 404, got {resp_404.status_code}")
        self.assertNotEqual(resp_404.status_code, 500)

        # 2. Missing required fields (e.g. missing 'code') -> HTTP 422
        resp_missing_code = self.api_client.post("/api/evaluate", json={
            "user_id": "user_bad_schema",
            "question_id": "qid_123",
        })
        self.assertEqual(resp_missing_code.status_code, 422, f"Expected 422, got {resp_missing_code.status_code}")
        self.assertNotEqual(resp_missing_code.status_code, 500)

        # 3. Missing user_id -> HTTP 422
        resp_missing_user = self.api_client.post("/api/evaluate", json={
            "question_id": "qid_123",
            "code": "pass",
        })
        self.assertEqual(resp_missing_user.status_code, 422)
        self.assertNotEqual(resp_missing_user.status_code, 500)

        # 4. Invalid JSON payload format (raw string) -> HTTP 422
        resp_empty_body = self.api_client.post(
            "/api/evaluate",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(resp_empty_body.status_code, 422)
        self.assertNotEqual(resp_empty_body.status_code, 500)

        # 5. Python Syntax error submission should return 200 with passed=False and low score, NOT 500
        resp_syntax = self.api_client.post("/api/evaluate", json={
            "user_id": "user_syntax_err",
            "question_id": "custom_syntax_q",
            "code": "def broken(:::",
            "problem_description": "Fix broken code",
            "reference_solution": "def broken(): pass",
            "mock": True,
        })
        self.assertEqual(resp_syntax.status_code, 200)
        syntax_data = resp_syntax.json()
        self.assertFalse(syntax_data["passed"])
        self.assertLessEqual(syntax_data["score"], 30)
        self.record_sub_id(syntax_data["submission_id"])

    def test_12_fastapi_evaluate_concurrent_stress_and_cleanup(self):
        """Stress-test with 20 consecutive API calls, verifying all return 200 and all documents are cleaned up."""
        mod_q = self.db.questions_moderate.find_one()
        qid = str(mod_q["_id"])

        created_in_stress = []
        for i in range(20):
            payload = {
                "user_id": f"stress_user_{i}_{int(time.time())}",
                "question_id": qid,
                "code": f"# Iteration {i}\ndef solve(): return {i}",
                "mock": True,
            }
            resp = self.api_client.post("/api/evaluate", json=payload)
            self.assertEqual(resp.status_code, 200, f"Request {i} failed: {resp.text}")
            sid = resp.json()["submission_id"]
            created_in_stress.append(sid)
            self.record_sub_id(sid)

        self.assertEqual(len(created_in_stress), 20)

        # Verify all 20 are present in MongoDB
        count = self.db.submissions.count_documents({
            "_id": {"$in": [ObjectId(s) for s in created_in_stress]}
        })
        self.assertEqual(count, 20, "Not all 20 submissions were saved to MongoDB")

        # Explicitly delete stress-test documents
        del_res = self.db.submissions.delete_many({
            "_id": {"$in": [ObjectId(s) for s in created_in_stress]}
        })
        self.assertEqual(del_res.deleted_count, 20)

        # Remove deleted IDs from tracker so tearDownClass doesn't double-delete
        self.inserted_sub_ids = [s for s in self.inserted_sub_ids if s not in created_in_stress]

        # Verify they are gone from MongoDB
        after_count = self.db.submissions.count_documents({
            "_id": {"$in": [ObjectId(s) for s in created_in_stress]}
        })
        self.assertEqual(after_count, 0, "Stress documents not cleanly deleted from MongoDB")


def run_challenger_suite():
    print("=" * 80)
    print("  EMPIRICAL CHALLENGER 2: Full Verification Suite")
    print("=" * 80)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestChallenger2Evaluator)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("=" * 80)
    print(f"  Summary: Ran {result.testsRun} tests | Failures: {len(result.failures)} | Errors: {len(result.errors)}")
    print("=" * 80)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_challenger_suite()
    sys.exit(0 if success else 1)
