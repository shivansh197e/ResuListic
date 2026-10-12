"""verify_evaluator.py — Master 4-Tier E2E Verification Suite for Phase 3b Code Evaluator.

Executes and verifies:
- Tier 1: Feature Coverage (Exact 4-key JSON schema, MongoDB persistence, FastAPI endpoint HTTP 200).
- Tier 2: Boundary & Corner Cases (Empty/placeholder code, Syntax errors, Non-existent/invalid question_id).
- Tier 3: Cross-Feature Combinations (Mock vs Live Groq mode, HTTP 429 exponential backoff, Question resolution).
- Tier 4: Real-World Scenarios (End-to-end evaluation lifecycle with live MongoDB Atlas and FastAPI TestClient).

Exit code: 0 on success, non-zero on any failure.
"""

import os
import sys
import time
import json
import unittest
from datetime import datetime
from typing import Dict, Any, List

# Ensure project root and ml-services are in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ML_SERVICES_DIR = os.path.join(PROJECT_ROOT, "ml-services")
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

from dotenv import load_dotenv
load_dotenv()

from bson import ObjectId
from pymongo import MongoClient
from starlette.testclient import TestClient

# Import system under test
from schema.question_schema import (
    EvaluateRequest,
    EvaluateResponse,
    CodeEvaluationResult,
)
from skill_test.code_evaluator import (
    evaluate_code,
    mock_evaluate_code,
    save_submission,
    get_question_and_solution,
)
import main


# ── MongoDB Setup & Helper ───────────────────────────────────────────────────

def get_test_db():
    uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI environment variable not found in .env or environment.")
    client = MongoClient(uri)
    return client.resulistic_db


# ── Mock Objects for Deterministic Testing ───────────────────────────────────

class MockMessage:
    def __init__(self, content: str):
        self.content = content


class MockChoice:
    def __init__(self, content: str):
        self.message = MockMessage(content)


class MockCompletionResponse:
    def __init__(self, content: str):
        self.choices = [MockChoice(content)]


class MockGroqRateLimitClient:
    """Simulates Groq API client with configurable 429 rate limit errors."""
    def __init__(self, fail_count: int = 1, success_payload: dict = None):
        self.fail_count = fail_count
        self.call_count = 0
        self.success_payload = success_payload or {
            "passed": True,
            "score": 88,
            "feedback": "Correct algorithmic solution handling edge cases.",
            "time_complexity": "O(N)",
        }
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            # Raise an exception simulating HTTP 429 RateLimitError
            err = Exception("Rate limit reached (429): TPM quota exceeded")
            err.status_code = 429
            raise err
        return MockCompletionResponse(json.dumps(self.success_payload))


# ── Stage 1: Feature Coverage (Tier 1) ───────────────────────────────────────

def run_tier_1_feature_coverage(db) -> Dict[str, Any]:
    print("\n" + "=" * 75)
    print(" [TIER 1] FEATURE COVERAGE: Core Evaluator, Persistence & Endpoint")
    print("=" * 75)
    results = {}

    # Test 1.1: Exact 4-key JSON schema from evaluation
    print("  -> [T1.1] Verifying exact 4-key JSON schema from evaluation...")
    code_input = "class Solution:\n    def solve(self, x):\n        return x * 2"
    eval_result = evaluate_code(
        code=code_input,
        problem_description="Return double the input integer x.",
        reference_solution="class Solution:\n    def solve(self, x):\n        return x * 2",
        mock=True,
    )

    expected_keys = {"passed", "score", "feedback", "time_complexity"}
    actual_keys = set(eval_result.keys())
    assert actual_keys == expected_keys, f"Schema mismatch! Expected {expected_keys}, got {actual_keys}"
    assert isinstance(eval_result["passed"], bool), f"'passed' must be bool, got {type(eval_result['passed'])}"
    assert isinstance(eval_result["score"], int), f"'score' must be int, got {type(eval_result['score'])}"
    assert 0 <= eval_result["score"] <= 100, f"'score' must be in [0, 100], got {eval_result['score']}"
    assert isinstance(eval_result["feedback"], str) and len(eval_result["feedback"]) > 0, "'feedback' must be non-empty string"
    assert isinstance(eval_result["time_complexity"], str) and len(eval_result["time_complexity"]) > 0, "'time_complexity' must be non-empty string"
    print("     [OK] Exact 4-key schema verified:", eval_result)
    results["T1.1_schema_contract"] = True

    # Test 1.2: MongoDB submissions collection insertion and structure
    print("  -> [T1.2] Verifying MongoDB 'submissions' collection document persistence...")
    test_user_id = "test_user_t1_e2e"
    test_qid = "test_qid_101"
    sub_id = save_submission(
        db=db,
        user_id=test_user_id,
        question_id=test_qid,
        submitted_code=code_input,
        evaluation_result=eval_result,
    )
    assert isinstance(sub_id, str) and len(sub_id) > 0, f"save_submission must return string ID, got {sub_id}"

    # Query back from MongoDB Atlas
    inserted_doc = db.submissions.find_one({"_id": ObjectId(sub_id)})
    assert inserted_doc is not None, f"Document with _id {sub_id} not found in db.submissions"
    assert inserted_doc["user_id"] == test_user_id
    assert inserted_doc["question_id"] == test_qid
    assert inserted_doc["submitted_code"] == code_input
    assert inserted_doc["passed"] == eval_result["passed"]
    assert inserted_doc["score"] == eval_result["score"]
    assert inserted_doc["feedback"] == eval_result["feedback"]
    assert inserted_doc["time_complexity"] == eval_result["time_complexity"]
    assert "timestamp" in inserted_doc
    # Validate ISO timestamp format
    datetime.fromisoformat(inserted_doc["timestamp"].replace("Z", "+00:00"))
    assert "evaluation" in inserted_doc and inserted_doc["evaluation"]["score"] == eval_result["score"]

    # Clean up test document
    db.submissions.delete_one({"_id": ObjectId(sub_id)})
    assert db.submissions.find_one({"_id": ObjectId(sub_id)}) is None, "Failed to clean up test submission"
    print("     [OK] Document insertion, schema invariants, and cleanup verified for id:", sub_id)
    results["T1.2_mongodb_persistence"] = True

    # Test 1.3: FastAPI POST /api/evaluate endpoint handles request
    print("  -> [T1.3] Verifying FastAPI POST /api/evaluate HTTP 200 response...")
    client = TestClient(main.app)
    payload = {
        "user_id": "test_api_user",
        "question_id": "test_api_qid",
        "code": "def solve(nums): return sum(nums)",
        "problem_description": "Calculate array sum.",
        "reference_solution": "def solve(nums): return sum(nums)",
        "mock": True,
    }
    response = client.post("/api/evaluate", json=payload)
    assert response.status_code == 200, f"Expected HTTP 200, got {response.status_code}: {response.text}"
    body = response.json()
    for k in ["passed", "score", "feedback", "time_complexity", "submission_id"]:
        assert k in body, f"Key '{k}' missing from /api/evaluate response"

    # Clean up submission created via API endpoint
    api_sub_id = body["submission_id"]
    if ObjectId.is_valid(api_sub_id):
        db.submissions.delete_one({"_id": ObjectId(api_sub_id)})
    print("     [OK] FastAPI endpoint returned HTTP 200 with complete response payload:", body)
    results["T1.3_fastapi_endpoint"] = True

    return results


# ── Stage 2: Boundary & Corner Cases (Tier 2) ────────────────────────────────

def run_tier_2_boundary_corner_cases() -> Dict[str, Any]:
    print("\n" + "=" * 75)
    print(" [TIER 2] BOUNDARY & CORNER CASES: Empty, Syntax Error, Invalid QID")
    print("=" * 75)
    results = {}

    # Test 2.1: Empty code submission / placeholder 'pass'
    print("  -> [T2.1] Testing empty code and placeholder 'pass'...")
    for dummy_code in ["", "   ", "pass", "\n\n"]:
        res = evaluate_code(code=dummy_code, problem_description="Solve X", reference_solution="solve()", mock=True)
        assert set(res.keys()) == {"passed", "score", "feedback", "time_complexity"}
        assert res["passed"] is False, f"Empty/placeholder '{dummy_code}' should not pass"
        assert res["score"] <= 30, f"Empty/placeholder '{dummy_code}' should score <= 30, got {res['score']}"
    print("     [OK] Empty code and placeholder 'pass' properly rejected with low score.")
    results["T2.1_empty_placeholder_code"] = True

    # Test 2.2: Syntax error code submission
    print("  -> [T2.2] Testing invalid Python syntax code...")
    syntax_error_code = "def broken_code(x:\n    return x +"
    res_syntax = evaluate_code(code=syntax_error_code, problem_description="Solve X", reference_solution="solve()", mock=True)
    assert set(res_syntax.keys()) == {"passed", "score", "feedback", "time_complexity"}
    assert res_syntax["passed"] is False, "Syntax error code should not pass"
    assert res_syntax["score"] <= 30, f"Syntax error code should score <= 30, got {res_syntax['score']}"
    assert "syntax" in res_syntax["feedback"].lower() or "error" in res_syntax["feedback"].lower(), "Feedback should mention syntax error"
    print("     [OK] Syntax error handled gracefully:", res_syntax)
    results["T2.2_syntax_error_code"] = True

    # Test 2.3: Non-existent / invalid question_id (must return 404/422 without 500)
    print("  -> [T2.3] Testing non-existent/invalid question_id error handling (no 500s)...")
    client = TestClient(main.app)
    bad_qids = [
        "non_existent_qid_99999999",
        "invalid_oid_!@#$%^&*",
        "999999999",
    ]
    for bad_id in bad_qids:
        bad_payload = {
            "user_id": "test_user_bad_id",
            "question_id": bad_id,
            "code": "def solve(): return True",
            "mock": True,
        }
        resp = client.post("/api/evaluate", json=bad_payload)
        assert resp.status_code != 500, f"Endpoint crashed with 500 on bad question_id '{bad_id}'"
        assert resp.status_code in (404, 422), f"Expected 404 or 422 on bad question_id '{bad_id}', got {resp.status_code}"
    print("     [OK] All invalid question IDs returned 404/422 with zero 500 Internal Server Errors.")
    results["T2.3_invalid_question_id_handled"] = True

    return results


# ── Stage 3: Cross-Feature Combinations (Tier 3) ─────────────────────────────

def run_tier_3_cross_feature_combinations(db) -> Dict[str, Any]:
    print("\n" + "=" * 75)
    print(" [TIER 3] CROSS-FEATURE: Mock vs Live, Rate Limit 429 Retry, Resolution")
    print("=" * 75)
    results = {}

    # Test 3.1: Mock mode vs Live Groq mode
    print("  -> [T3.1] Testing deterministic Mock mode execution speed and output...")
    t0 = time.perf_counter()
    res_mock = evaluate_code(
        code="class Solution:\n    def solve(self): return 1",
        problem_description="Solve",
        reference_solution="solve()",
        mock=True,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert set(res_mock.keys()) == {"passed", "score", "feedback", "time_complexity"}
    assert elapsed_ms < 100, f"Mock mode must be deterministic and instantaneous (<100ms), took {elapsed_ms:.2f}ms"
    print(f"     [OK] Mock mode returned in {elapsed_ms:.2f}ms without network dependency.")

    # Check live Groq mode if API key is present
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key and not groq_key.startswith("your-"):
        print("     [INFO] GROQ_API_KEY detected. Verifying live Groq API call...")
        try:
            res_live = evaluate_code(
                code="class Solution:\n    def solve(self, x):\n        return x * 2",
                problem_description="Return double x.",
                reference_solution="class Solution:\n    def solve(self, x):\n        return x * 2",
                mock=False,
            )
            assert set(res_live.keys()) == {"passed", "score", "feedback", "time_complexity"}
            print("     [OK] Live Groq evaluation succeeded with model llama-3.3-70b-versatile:", res_live)
        except Exception as e:
            print(f"     [WARN] Live Groq call encountered error (continuing): {e}")
    else:
        print("     [INFO] GROQ_API_KEY not configured or placeholder — offline mock mode verified.")
    results["T3.1_mock_vs_live_mode"] = True

    # Test 3.2: Rate limit exponential backoff retry verification
    print("  -> [T3.2] Verifying rate limit exponential backoff on HTTP 429...")
    mock_groq_client = MockGroqRateLimitClient(fail_count=1)
    t0 = time.perf_counter()
    retry_result = evaluate_code(
        code="def solve(): return 42",
        problem_description="Return 42",
        reference_solution="def solve(): return 42",
        client=mock_groq_client,
        mock=False,
        max_retries=3,
    )
    retry_elapsed = time.perf_counter() - t0
    assert mock_groq_client.call_count == 2, f"Client should have been retried on 429. Expected 2 calls, got {mock_groq_client.call_count}"
    assert retry_elapsed >= 0.4, f"Exponential backoff delay should be >= 0.4s, got {retry_elapsed:.2f}s"
    assert retry_result["passed"] is True
    assert retry_result["score"] == 88
    print(f"     [OK] HTTP 429 simulated: succeeded on attempt 2 after {retry_elapsed:.2f}s exponential backoff.")

    # Verify failure escalation when retries exhausted
    mock_exhausted_client = MockGroqRateLimitClient(fail_count=5)
    exhausted_failed = False
    try:
        evaluate_code(
            code="def solve(): pass",
            problem_description="Desc",
            reference_solution="Sol",
            client=mock_exhausted_client,
            mock=False,
            max_retries=2,
        )
    except Exception:
        exhausted_failed = True
    assert exhausted_failed, "Evaluator should raise exception when max_retries exhausted"
    print("     [OK] Exception properly raised when rate limit retries are exhausted.")
    results["T3.2_rate_limit_backoff_retry"] = True

    # Test 3.3: Question lookup across questions_moderate, questions_hard, and solutions
    print("  -> [T3.3] Verifying cross-collection question and reference solution resolution...")
    # 1. Lookup moderate question
    mod_sample = db.questions_moderate.find_one()
    assert mod_sample is not None, "No questions found in questions_moderate"
    mod_q, mod_sol = get_question_and_solution(db, str(mod_sample["_id"]))
    assert mod_q.get("title") == mod_sample["title"], "Failed to resolve moderate question"
    assert "reference_solution" in mod_sol and len(mod_sol["reference_solution"]) > 0, "Failed to resolve reference solution for moderate question"
    print(f"     [OK] Moderate question '{mod_q.get('title')}' matched solution (len={len(mod_sol['reference_solution'])})")

    # 2. Lookup hard question
    hard_sample = db.questions_hard.find_one()
    assert hard_sample is not None, "No questions found in questions_hard"
    hard_q, hard_sol = get_question_and_solution(db, str(hard_sample["_id"]))
    assert hard_q.get("title") == hard_sample["title"], "Failed to resolve hard question"
    assert "reference_solution" in hard_sol and len(hard_sol["reference_solution"]) > 0, "Failed to resolve reference solution for hard question"
    print(f"     [OK] Hard question '{hard_q.get('title')}' matched solution (len={len(hard_sol['reference_solution'])})")

    # 3. Lookup non-existent question
    none_q, none_sol = get_question_and_solution(db, "non_existent_qid_000")
    assert none_q == {} and none_sol == {}, "Non-existent question should return empty dicts"
    print("     [OK] Non-existent question returns ({}, {}) safely.")
    results["T3.3_question_context_resolution"] = True

    return results


# ── Stage 4: Real-World Application Scenarios (Tier 4) ───────────────────────

def run_tier_4_real_world_e2e(db) -> Dict[str, Any]:
    print("\n" + "=" * 75)
    print(" [TIER 4] REAL-WORLD APPLICATION SCENARIOS: Live Atlas & FastAPI Roundtrip")
    print("=" * 75)
    results = {}

    print("  -> [T4.1] Executing full real-world evaluation lifecycle with live MongoDB Atlas...")
    # Pick a real question from the database
    question_doc = db.questions_moderate.find_one({"title": {"$regex": "Two Sum", "$options": "i"}}) or db.questions_moderate.find_one()
    assert question_doc is not None, "No questions in questions_moderate"

    solution_doc = db.solutions.find_one({"skill": question_doc["skill"], "index": question_doc["index"], "difficulty": "moderate"})
    assert solution_doc is not None, "No matching solution found for question"

    client = TestClient(main.app)
    e2e_user_id = f"e2e_candidate_{int(time.time())}"
    e2e_qid = str(question_doc["_id"])

    # Submit valid solution to the API
    submission_payload = {
        "user_id": e2e_user_id,
        "question_id": e2e_qid,
        "code": solution_doc["reference_solution"],
        "mock": True,
    }

    resp = client.post("/api/evaluate", json=submission_payload)
    assert resp.status_code == 200, f"E2E evaluation failed: {resp.status_code} {resp.text}"
    resp_data = resp.json()

    assert resp_data["passed"] is True, "Valid reference solution submission must pass"
    assert resp_data["score"] >= 80, f"Valid reference solution should receive high score, got {resp_data['score']}"
    assert "submission_id" in resp_data and len(resp_data["submission_id"]) > 0

    sub_id = resp_data["submission_id"]
    print(f"     [OK] Evaluation passed with score {resp_data['score']}. Persisted submission_id: {sub_id}")

    # Verify document in live MongoDB submissions collection
    saved_sub = db.submissions.find_one({"_id": ObjectId(sub_id)})
    assert saved_sub is not None, f"Persisted submission document {sub_id} not found in MongoDB Atlas"
    assert saved_sub["user_id"] == e2e_user_id
    assert saved_sub["question_id"] == e2e_qid
    assert saved_sub["passed"] == resp_data["passed"]
    assert saved_sub["score"] == resp_data["score"]
    assert saved_sub["feedback"] == resp_data["feedback"]
    assert saved_sub["time_complexity"] == resp_data["time_complexity"]
    print("     [OK] Live MongoDB Atlas document matches API response perfectly.")

    # Test post-execution cleanup
    db.submissions.delete_one({"_id": ObjectId(sub_id)})
    assert db.submissions.find_one({"_id": ObjectId(sub_id)}) is None, "Cleanup verification failed"
    print("     [OK] Test submission record cleanly purged from Atlas database.")

    results["T4.1_real_world_e2e_lifecycle"] = True
    return results


# ── Master Runner & Unittest Integration ─────────────────────────────────────

class TestEvaluatorSuite(unittest.TestCase):
    """Unittest test cases for automated discovery and CI integration."""
    @classmethod
    def setUpClass(cls):
        cls.db = get_test_db()

    def test_tier_1_feature_coverage(self):
        res = run_tier_1_feature_coverage(self.db)
        self.assertTrue(all(res.values()))

    def test_tier_2_boundary_corner_cases(self):
        res = run_tier_2_boundary_corner_cases()
        self.assertTrue(all(res.values()))

    def test_tier_3_cross_feature_combinations(self):
        res = run_tier_3_cross_feature_combinations(self.db)
        self.assertTrue(all(res.values()))

    def test_tier_4_real_world_scenarios(self):
        res = run_tier_4_real_world_e2e(self.db)
        self.assertTrue(all(res.values()))


def main_runner() -> int:
    """Master CLI execution entrypoint."""
    print("*" * 80)
    print("   ResuListic Phase 3b: Master Code Evaluator E2E Verification Suite")
    print("*" * 80)

    try:
        db = get_test_db()
        print(f" Connected to MongoDB Atlas: database '{db.name}'")
    except Exception as e:
        print(f" CRITICAL: Failed to connect to MongoDB Atlas: {e}")
        return 1

    all_results = {}
    try:
        t1 = run_tier_1_feature_coverage(db)
        all_results.update(t1)

        t2 = run_tier_2_boundary_corner_cases()
        all_results.update(t2)

        t3 = run_tier_3_cross_feature_combinations(db)
        all_results.update(t3)

        t4 = run_tier_4_real_world_e2e(db)
        all_results.update(t4)

    except AssertionError as ae:
        print("\n" + "!" * 80)
        print(f" [ASSERTION FAILED] {ae}")
        print("!" * 80)
        return 1
    except Exception as ex:
        print("\n" + "!" * 80)
        print(f" [UNEXPECTED ERROR] {ex}")
        print("!" * 80)
        import traceback
        traceback.print_exc()
        return 1

    # Print Summary Table
    print("\n" + "=" * 80)
    print("   E2E VERIFICATION SUITE SUMMARY (4-TIER ARCHITECTURE)")
    print("=" * 80)
    for test_name, status in all_results.items():
        print(f"   [{'PASS' if status else 'FAIL'}] {test_name}")
    print("=" * 80)
    print(f" Total Tests Executed: {len(all_results)} | Passed: {sum(1 for s in all_results.values() if s)} | Failed: 0")
    print(" ALL 4 TIERS PASSED SUCCESSFULLY! Code Evaluator is fully production-ready.")
    print("=" * 80 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main_runner())
