"""
test_code_evaluator_adversarial.py — Adversarial Stress Testing Harness for Phase 3b Code Evaluator.

Challenge Vectors:
1. Input Fuzzing:
   - Massive code strings (100KB, 500KB)
   - Non-ASCII, multi-byte UTF-8, emojis, Cyrillic, Arabic RTL, zero-width chars
   - Escaped quotes, nested triple quotes, raw strings, escaped backslashes
   - Multi-line docstrings with embedded markdown and code blocks
   - Recursive lambdas and higher-order Y-combinators
   - Null bytes and control character resilience
   - Deeply nested AST structures (nested brackets/parentheses)
   - Static analysis safety against dangerous code (loops, exits, malicious calls)

2. Concurrency & Rate Limiting Stress:
   - 30 concurrent rapid requests via ThreadPoolExecutor
   - Concurrent 429 exponential backoff retries without thread contention
   - Concurrent rate limit exhaustion handling without hanging or process crash
   - MongoDB Atlas concurrent write persistence integrity and clean teardown

3. Schema Fuzzing & Invariant Guarantees:
   - Strict 4-key JSON schema invariants across all inputs
   - Score bounding [0, 100] clamp verification
   - Type coercion resilience (string scores, boolean variants)
   - Extra key stripping and missing key defaults
   - Zero HTTP 500 error guarantee across all adversarial payloads
"""

import os
import sys
import time
import json
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Any, List

# Ensure project root and ml-services are in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

# System Under Test
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


def get_db():
    uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI not found in environment.")
    client = MongoClient(uri)
    return client.resulistic_db


class MockMessage:
    def __init__(self, content: str):
        self.content = content


class MockChoice:
    def __init__(self, content: str):
        self.message = MockMessage(content)


class MockCompletionResponse:
    def __init__(self, content: str):
        self.choices = [MockChoice(content)]


class ConcurrentMockGroqRateLimitClient:
    """Thread-safe mock Groq client simulating 429 errors with tracking."""
    def __init__(self, fail_count_per_thread: int = 1, success_payload: dict = None):
        self.fail_count = fail_count_per_thread
        self.success_payload = success_payload or {
            "passed": True,
            "score": 92,
            "feedback": "Adversarial test passed successfully.",
            "time_complexity": "O(N log N)",
        }
        self.lock = threading.Lock()
        self.thread_call_counts = {}
        self.total_calls = 0
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        thread_id = threading.get_ident()
        with self.lock:
            self.total_calls += 1
            current = self.thread_call_counts.get(thread_id, 0) + 1
            self.thread_call_counts[thread_id] = current

        if current <= self.fail_count:
            err = Exception("Rate limit reached (429): Concurrent TPM quota exceeded")
            err.status_code = 429
            raise err

        return MockCompletionResponse(json.dumps(self.success_payload))


class AdversarialEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.client = TestClient(main.app)
        cls.created_submission_ids: List[str] = []

    @classmethod
    def tearDownClass(cls):
        # Purge any test submissions created during adversarial runs
        if cls.created_submission_ids:
            for sid in cls.created_submission_ids:
                if ObjectId.is_valid(sid):
                    cls.db.submissions.delete_one({"_id": ObjectId(sid)})

    # =========================================================================
    # VECTOR 1: INPUT FUZZING
    # =========================================================================

    def test_v1_1_massive_code_string_100kb(self):
        """Fuzz with 100KB+ code string containing repeated valid functions."""
        func_template = "def helper_{i}(x):\n    return x + {i}\n"
        massive_code = "\n".join(func_template.format(i=i) for i in range(2500))
        massive_code += "\ndef solve(x):\n    return sum(helper_0(x) for _ in range(10))\n"
        self.assertGreater(len(massive_code), 100_000, "Code should exceed 100KB")

        t0 = time.perf_counter()
        res = mock_evaluate_code(massive_code, "Massive problem", "def solve(x): return x")
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 1.0, f"Compilation took too long: {elapsed:.3f}s")
        self.assertEqual(set(res.keys()), {"passed", "score", "feedback", "time_complexity"})
        self.assertTrue(res["passed"])
        self.assertEqual(res["score"], 90)

    def test_v1_2_massive_code_string_via_fastapi(self):
        """Test massive code string through FastAPI POST /api/evaluate."""
        large_comment = "# " + ("A" * 80) + "\n"
        code = large_comment * 1500 + "def solve(x):\n    return x * 2\n"
        self.assertGreater(len(code), 120_000)

        payload = {
            "user_id": "challenger_fuzz_massive",
            "question_id": "fuzz_qid_massive",
            "code": code,
            "problem_description": "Massive input problem",
            "reference_solution": "def solve(x): return x * 2",
            "mock": True,
        }
        resp = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["passed"])
        self.assertEqual(data["score"], 90)
        self.__class__.created_submission_ids.append(data["submission_id"])

    def test_v1_3_non_ascii_unicode_emojis_multibyte(self):
        """Fuzz with UTF-8, emojis, Cyrillic, Chinese, Arabic RTL, and zero-width spaces."""
        unicode_code = (
            "# Тестирование юникода и эмодзи 🚀💻🔥\n"
            "# اللغة العربية: اختبار من اليمين إلى اليسار\n"
            "def 解决问题(数据: list, 因子: int = 42) -> dict:\n"
            "    # Zero-width space embedded \u200b and RTL mark \u200f\n"
            "    resultado = {'статус': 'успех', 'emoji': '🚀'}\n"
            "    return resultado\n"
        )
        res = mock_evaluate_code(unicode_code, "Unicode description 🌐", "def 解决问题(): pass")
        self.assertEqual(set(res.keys()), {"passed", "score", "feedback", "time_complexity"})
        self.assertTrue(res["passed"])
        self.assertEqual(res["score"], 90)

    def test_v1_4_escaped_quotes_and_nested_strings(self):
        """Fuzz with escaped quotes, raw strings, triple-quotes, and regex escapes."""
        escaped_code = (
            'import re\n'
            'def solve(text: str) -> str:\n'
            '    pattern = r"^\"\'[a-zA-Z0-9_\\-\\.]+\'\"$"\n'
            '    nested_str = """Line 1 with \\"quotes\\" and \'single\'\n'
            'Line 2 with \\\\ backslash and \\n newline\n'
            'Line 3 with \'\'\'nested single triple\'\'\'"""\n'
            '    return re.sub(pattern, "\\\\1", text)\n'
        )
        res = mock_evaluate_code(escaped_code, "Escaped quotes problem", "def solve(): pass")
        self.assertEqual(set(res.keys()), {"passed", "score", "feedback", "time_complexity"})
        self.assertTrue(res["passed"])

    def test_v1_5_multiline_docstrings_with_embedded_markdown(self):
        """Fuzz with complex docstrings embedding Markdown and code blocks."""
        docstring_code = (
            'def calculate_solution(n: int) -> int:\n'
            '    """\n'
            '    ## Problem Specification\n'
            '    Given `n`, compute Fibonacci sequence.\n'
            '    \n'
            '    Example:\n'
            '    ```python\n'
            '    >>> calculate_solution(5)\n'
            '    5\n'
            '    ```\n'
            '    \n'
            '    Complexity: `O(N)` time, `O(1)` space.\n'
            '    """\n'
            '    a, b = 0, 1\n'
            '    for _ in range(n):\n'
            '        a, b = b, a + b\n'
            '    return a\n'
        )
        res = mock_evaluate_code(docstring_code, "Fibonacci calculation", "def calculate_solution(n): return n")
        self.assertTrue(res["passed"])
        self.assertEqual(res["score"], 90)

    def test_v1_6_recursive_lambdas_and_combinators(self):
        """Fuzz with recursive lambdas and higher-order Y-combinators."""
        lambda_code = (
            "# Y-Combinator for anonymous recursive factorial\n"
            "Y = lambda f: (lambda x: x(x))(lambda y: f(lambda *args: y(y)(*args)))\n"
            "fact = Y(lambda f: lambda n: 1 if n <= 1 else n * f(n - 1))\n"
            "fib = lambda n: n if n <= 1 else fib(n - 1) + fib(n - 2)\n"
            "def solve(n):\n"
            "    return fact(n) + fib(n)\n"
        )
        res = mock_evaluate_code(lambda_code, "Recursive lambdas", "def solve(n): return n")
        self.assertTrue(res["passed"])
        self.assertEqual(res["score"], 90)

    def test_v1_7_deeply_nested_ast_brackets(self):
        """Fuzz with deeply nested brackets and parentheses (120 levels)."""
        depth = 120
        nested_code = "def solve():\n    return " + ("(" * depth) + "42" + (")" * depth) + "\n"
        res = mock_evaluate_code(nested_code, "Nested AST", "def solve(): return 42")
        self.assertTrue(res["passed"])
        self.assertEqual(res["score"], 90)

    def test_v1_8_static_analysis_safety_malicious_code(self):
        """Verify code evaluation does not execute destructive code or hang on infinite loops."""
        dangerous_snippets = [
            "import os\nos.system('echo dangerous')",
            "import sys\nsys.exit(1)",
            "while True:\n    pass",
            "raise RuntimeError('Boom')",
        ]
        for snippet in dangerous_snippets:
            t0 = time.perf_counter()
            res = mock_evaluate_code(snippet, "Safety check", "safe()")
            elapsed = time.perf_counter() - t0
            # Must evaluate statically in less than 50ms without hanging or crashing
            self.assertLess(elapsed, 0.05, f"Static analysis hung on: {snippet}")
            self.assertEqual(set(res.keys()), {"passed", "score", "feedback", "time_complexity"})

    def test_v1_9_null_byte_resilience_in_fastapi(self):
        """Verify handling of null bytes (\\x00) via FastAPI endpoint without 500 error."""
        null_byte_code = "def solve():\x00 return 42"
        payload = {
            "user_id": "challenger_null_byte",
            "question_id": "null_byte_qid",
            "code": null_byte_code,
            "problem_description": "Null byte test",
            "reference_solution": "def solve(): return 42",
            "mock": True,
        }
        resp = self.client.post("/api/evaluate", json=payload)
        # Should be handled gracefully: 422 Unprocessable Entity or 200, strictly never 500
        self.assertNotEqual(resp.status_code, 500, "FastAPI crashed with HTTP 500 on null byte")
        self.assertIn(resp.status_code, (200, 422))

    # =========================================================================
    # VECTOR 2: CONCURRENCY & RATE LIMITING STRESS
    # =========================================================================

    def test_v2_1_rapid_concurrent_requests_30_threads(self):
        """Execute 30 concurrent rapid evaluate requests against FastAPI TestClient."""
        num_requests = 30
        results = []
        errors = []

        def make_request(idx: int):
            payload = {
                "user_id": f"concurrent_user_{idx}",
                "question_id": f"concurrent_qid_{idx % 5}",
                "code": f"def solve_{idx}(x):\n    return x + {idx}",
                "problem_description": "Concurrent addition test",
                "reference_solution": "def solve(x): return x",
                "mock": True,
            }
            client = TestClient(main.app)
            resp = client.post("/api/evaluate", json=payload)
            return resp.status_code, resp.json()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            for future in as_completed(futures):
                try:
                    status_code, data = future.result()
                    results.append((status_code, data))
                except Exception as e:
                    errors.append(str(e))

        self.assertEqual(len(errors), 0, f"Concurrent request errors: {errors}")
        self.assertEqual(len(results), num_requests)

        for status_code, data in results:
            self.assertEqual(status_code, 200)
            self.assertTrue(data["passed"])
            self.assertEqual(data["score"], 90)
            self.assertIn("submission_id", data)
            self.__class__.created_submission_ids.append(data["submission_id"])

    def test_v2_2_concurrent_rate_limiting_exponential_backoff(self):
        """Verify 10 concurrent threads handling 429 rate limit backoff simultaneously."""
        num_threads = 10
        shared_mock_client = ConcurrentMockGroqRateLimitClient(fail_count_per_thread=1)
        results = []
        errors = []

        def evaluate_worker(idx: int):
            t0 = time.perf_counter()
            res = evaluate_code(
                code=f"def solve_{idx}(): return {idx}",
                problem_description=f"Concurrent backoff problem {idx}",
                reference_solution=f"def solve(): return {idx}",
                client=shared_mock_client,
                mock=False,
                max_retries=3,
            )
            elapsed = time.perf_counter() - t0
            return idx, res, elapsed

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(evaluate_worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                try:
                    idx, res, elapsed = future.result()
                    results.append((idx, res, elapsed))
                except Exception as e:
                    errors.append(str(e))

        self.assertEqual(len(errors), 0, f"Thread backoff errors: {errors}")
        self.assertEqual(len(results), num_threads)

        # Every thread must succeed on retry (call count per thread == 2)
        for idx, res, elapsed in results:
            self.assertTrue(res["passed"])
            self.assertEqual(res["score"], 92)
            self.assertGreaterEqual(elapsed, 0.4, f"Thread {idx} didn't wait for backoff: {elapsed:.2f}s")

        # Total client calls must equal num_threads * 2 (1 fail + 1 success per thread)
        self.assertEqual(shared_mock_client.total_calls, num_threads * 2)

    def test_v2_3_concurrent_rate_limit_exhaustion_safety(self):
        """Verify 5 concurrent threads handle exhausted rate limits cleanly without hanging."""
        num_threads = 5
        exhausted_client = ConcurrentMockGroqRateLimitClient(fail_count_per_thread=10)
        exceptions_caught = []

        def failing_worker(idx: int):
            try:
                evaluate_code(
                    code=f"def solve_{idx}(): pass",
                    problem_description="Exhausted test",
                    reference_solution="solve()",
                    client=exhausted_client,
                    mock=False,
                    max_retries=2,
                )
                return False
            except Exception as e:
                return True

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(failing_worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                exceptions_caught.append(future.result())

        self.assertEqual(len(exceptions_caught), num_threads)
        self.assertTrue(all(exceptions_caught), "All threads must raise exception upon retry exhaustion")

    def test_v2_4_mongodb_concurrent_write_persistence_integrity(self):
        """Verify 15 concurrent saves to MongoDB submissions maintain perfect schema & data integrity."""
        num_submissions = 15
        user_prefix = f"concurrent_db_user_{int(time.time())}"
        eval_result = {"passed": True, "score": 85, "feedback": "Concurrent DB write ok", "time_complexity": "O(N)"}
        sub_ids = []

        def db_write_worker(idx: int):
            sub_id = save_submission(
                db=self.db,
                user_id=f"{user_prefix}_{idx}",
                question_id=f"qid_{idx}",
                submitted_code=f"def solve_{idx}(): return {idx}",
                evaluation_result=eval_result,
            )
            return sub_id

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(db_write_worker, i) for i in range(num_submissions)]
            for future in as_completed(futures):
                sub_ids.append(future.result())

        self.assertEqual(len(sub_ids), num_submissions)
        # Verify all submission IDs are unique
        self.assertEqual(len(set(sub_ids)), num_submissions, "Duplicate submission IDs generated under concurrency!")

        # Verify each document exists in MongoDB Atlas with intact schema
        for sid in sub_ids:
            self.__class__.created_submission_ids.append(sid)
            doc = self.db.submissions.find_one({"_id": ObjectId(sid)})
            self.assertIsNotNone(doc, f"Document {sid} missing from Atlas")
            self.assertTrue(doc["user_id"].startswith(user_prefix))
            self.assertEqual(doc["score"], 85)
            self.assertTrue(doc["passed"])
            # Timestamp must be valid ISO-8601
            datetime.fromisoformat(doc["timestamp"].replace("Z", "+00:00"))

    # =========================================================================
    # VECTOR 3: SCHEMA FUZZING & INVARIANT GUARANTEES
    # =========================================================================

    def test_v3_1_strict_4_key_schema_invariants_across_varied_inputs(self):
        """Verify strict 4-key JSON schema across multiple code variations."""
        test_inputs = [
            ("valid standard", "def solve(a, b): return a + b", True, 90),
            ("valid class", "class Solution:\n    def solve(self): return 1", True, 90),
            ("valid lambda", "solve = lambda x: x ** 2", True, 90),
            ("empty", "", False, 20),
            ("spaces only", "     \n   \t  ", False, 20),
            ("short pass", "pass", False, 20),
            ("syntax error 1", "def broken(: pass", False, 15),
            ("syntax error 2", "for i in range(10)\n    pass", False, 15),
        ]

        expected_keys = {"passed", "score", "feedback", "time_complexity"}
        for name, code, expected_pass, expected_score in test_inputs:
            with self.subTest(case=name):
                res = mock_evaluate_code(code)
                self.assertEqual(set(res.keys()), expected_keys, f"Schema violated in {name}: {res.keys()}")
                self.assertIsInstance(res["passed"], bool)
                self.assertIsInstance(res["score"], int)
                self.assertGreaterEqual(res["score"], 0)
                self.assertLessEqual(res["score"], 100)
                self.assertIsInstance(res["feedback"], str)
                self.assertGreater(len(res["feedback"]), 0)
                self.assertIsInstance(res["time_complexity"], str)
                self.assertGreater(len(res["time_complexity"]), 0)
                self.assertEqual(res["passed"], expected_pass)
                self.assertEqual(res["score"], expected_score)

    def test_v3_2_llm_json_score_clamping_and_extra_key_stripping(self):
        """Verify evaluate_code clamps extreme scores and strips extra hallucinated keys."""
        class MockLLMVarianceClient:
            def __init__(self, response_dict: dict):
                self.response_dict = response_dict
                self.chat = self
                self.completions = self

            def create(self, **kwargs):
                return MockCompletionResponse(json.dumps(self.response_dict))

        # Case A: Out-of-bounds score (150 -> 100, -25 -> 0)
        client_high = MockLLMVarianceClient({"passed": True, "score": 150, "feedback": "Great", "time_complexity": "O(1)"})
        res_high = evaluate_code("code", "desc", "sol", client=client_high, mock=False)
        self.assertEqual(res_high["score"], 100, "Score > 100 was not clamped to 100")

        client_low = MockLLMVarianceClient({"passed": False, "score": -25, "feedback": "Poor", "time_complexity": "O(N)"})
        res_low = evaluate_code("code", "desc", "sol", client=client_low, mock=False)
        self.assertEqual(res_low["score"], 0, "Score < 0 was not clamped to 0")

        # Case B: Extra hallucinated keys stripped
        client_extra = MockLLMVarianceClient({
            "passed": True,
            "score": 85,
            "feedback": "Valid",
            "time_complexity": "O(N)",
            "hallucinated_1": "should be dropped",
            "metadata": {"tokens": 42},
        })
        res_extra = evaluate_code("code", "desc", "sol", client=client_extra, mock=False)
        self.assertEqual(set(res_extra.keys()), {"passed", "score", "feedback", "time_complexity"})

        # Case C: Missing keys defaulted safely
        client_empty = MockLLMVarianceClient({})
        res_empty = evaluate_code("code", "desc", "sol", client=client_empty, mock=False)
        self.assertEqual(set(res_empty.keys()), {"passed", "score", "feedback", "time_complexity"})
        self.assertEqual(res_empty["passed"], False)
        self.assertEqual(res_empty["score"], 0)
        self.assertEqual(res_empty["feedback"], "")
        self.assertEqual(res_empty["time_complexity"], "O(N)")

    def test_v3_3_fastapi_zero_500_guarantee_adversarial_payloads(self):
        """Verify FastAPI endpoint never returns HTTP 500 across wide array of adversarial payloads."""
        adversarial_payloads = [
            {},  # empty body
            {"user_id": 123},  # missing required fields
            {"user_id": "u", "question_id": "q", "code": ""},  # empty code
            {"user_id": "u", "question_id": "non_existent_12345", "code": "def solve(): pass"},  # missing qid in DB
            {"user_id": "u", "question_id": "invalid_oid_!@#", "code": "def solve(): pass"},  # malformed ObjectId
            {"user_id": "u", "question_id": "1", "code": "def broken(:", "mock": True},  # syntax error
            {"user_id": "u", "question_id": "1", "code": "a" * 50000, "mock": True, "problem_description": "d", "reference_solution": "s"},
        ]

        for idx, payload in enumerate(adversarial_payloads):
            with self.subTest(payload_idx=idx):
                resp = self.client.post("/api/evaluate", json=payload)
                self.assertNotEqual(
                    resp.status_code, 500,
                    f"FastAPI crashed with HTTP 500 on payload #{idx}: {payload} -> {resp.text}"
                )
                self.assertIn(resp.status_code, (200, 404, 422))
                if resp.status_code == 200:
                    sid = resp.json().get("submission_id")
                    if sid:
                        self.__class__.created_submission_ids.append(sid)


def run_adversarial_suite():
    suite = unittest.TestLoader().loadTestsFromTestCase(AdversarialEvaluatorTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_adversarial_suite())
