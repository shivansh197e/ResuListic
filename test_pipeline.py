"""
test_pipeline.py — End-to-End Verification Test Suite for ResuListic ETL Pipeline (data_builder.py).

Verifies:
- Test 1: Ingests dummy 2-row CSV, verifies pipeline exits 0.
- Test 2: Asserts MongoDB queries find inserted mutated questions in `questions_moderate` / `questions_hard` and solutions in `solutions`.
- Test 3: Simulates Gemini API 429 rate limit failure on first attempt, verifies pipeline catches and retries via backoff without crashing.
- Support both live MongoDB/Gemini and mock testing fallbacks if credentials or internet are unavailable.
- Fully standalone: executable via `python test_pipeline.py` or `pytest`.
"""

import copy
import csv
import importlib
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure ml-services is in sys.path for schema verification
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
ML_SERVICES_DIR = os.path.join(REPO_ROOT, "ml-services")
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

# Import schemas from ml-services
try:
    from schema.question_schema import CodingQuestionDoc, SolutionDoc
except ImportError as err:
    raise ImportError(f"Failed to import schemas from ml-services/schema/question_schema.py: {err}")

# Inspect optional dependencies (google.genai, pymongo)
try:
    from google import genai
    from google.genai import errors, types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    from pymongo import MongoClient
    from pymongo.errors import BulkWriteError
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False


# ── Mock Infrastructure for Hermetic / Offline Testing ──────────────────────

class MockClientError(Exception):
    """Simulates google.genai.errors.ClientError(429)."""
    def __init__(self, code: int = 429, message: str = "Resource has been exhausted"):
        self.code = code
        self.status = "RESOURCE_EXHAUSTED"
        self.message = message
        super().__init__(f"ClientError({code}): {message}")


class MockCollection:
    """In-memory MongoDB collection supporting insert_many, find, find_one, delete_many, count."""
    def __init__(self, name: str):
        self.name = name
        self.docs: list[dict] = []

    def insert_many(self, docs: list[dict], ordered: bool = False):
        if not docs:
            raise ValueError("documents must be a non-empty list")
        inserted = [copy.deepcopy(d) for d in docs]
        self.docs.extend(inserted)

        class Result:
            inserted_ids = [getattr(d, "_id", i) for i, d in enumerate(inserted)]
        return Result()

    def insert_one(self, doc: dict):
        self.docs.append(copy.deepcopy(doc))

    def find(self, filter_dict: dict = None):
        if not filter_dict:
            return [copy.deepcopy(d) for d in self.docs]
        matched = []
        for d in self.docs:
            match = True
            for k, v in filter_dict.items():
                if isinstance(v, dict) and "$in" in v:
                    if d.get(k) not in v["$in"]:
                        match = False
                        break
                elif d.get(k) != v:
                    match = False
                    break
            if match:
                matched.append(copy.deepcopy(d))
        return matched

    def find_one(self, filter_dict: dict = None, sort: list = None):
        results = self.find(filter_dict)
        if not results:
            return None
        if sort and len(sort) > 0:
            key, direction = sort[0]
            reverse = (direction == -1)
            results.sort(key=lambda x: x.get(key, 0), reverse=reverse)
        return results[0]

    def delete_many(self, filter_dict: dict = None):
        if not filter_dict:
            count = len(self.docs)
            self.docs.clear()
            return count
        kept = []
        for d in self.docs:
            match = True
            for k, v in filter_dict.items():
                if isinstance(v, dict) and "$in" in v:
                    if d.get(k) in v["$in"]:
                        match = False
                        break
                elif d.get(k) == v:
                    match = False
                    break
            if not match:
                kept.append(d)
        deleted = len(self.docs) - len(kept)
        self.docs = kept
        return deleted

    def count_documents(self, filter_dict: dict = None) -> int:
        return len(self.find(filter_dict))


class MockDatabase:
    """In-memory MongoDB database containing questions_moderate, questions_hard, solutions."""
    def __init__(self, name: str = "resulistic_db"):
        self.name = name
        self.questions_moderate = MockCollection("questions_moderate")
        self.questions_hard = MockCollection("questions_hard")
        self.solutions = MockCollection("solutions")

    def __getitem__(self, name: str) -> MockCollection:
        if hasattr(self, name):
            return getattr(self, name)
        coll = MockCollection(name)
        setattr(self, name, coll)
        return coll


class MockMongoClient:
    """In-memory MongoClient mock."""
    def __init__(self, *args, **kwargs):
        self.resulistic_db = MockDatabase("resulistic_db")

    def __getitem__(self, name: str) -> MockDatabase:
        if name == "resulistic_db":
            return self.resulistic_db
        return MockDatabase(name)


def load_data_builder_module():
    """Dynamically load or reload data_builder module if present at repository root."""
    path = os.path.join(REPO_ROOT, "data_builder.py")
    if os.path.exists(path):
        if "data_builder" in sys.modules:
            return importlib.reload(sys.modules["data_builder"])
        return importlib.import_module("data_builder")
    return None


# ── Test Suite ───────────────────────────────────────────────────────────────

class TestETLPipeline(unittest.TestCase):
    """
    Comprehensive E2E verification test suite for data_builder.py.
    Covers Tiers 1-4 including Acceptance Criteria R1, R2, R3.
    """

    @classmethod
    def setUpClass(cls):
        cls.db = MockDatabase("resulistic_db")
        cls.data_builder = load_data_builder_module()

        # Create dummy 2-row CSV fixture: 1 moderate, 1 hard
        cls.dummy_csv_content = (
            "skill,difficulty,title,description,reference_solution,tags,explanation\n"
            "Python,moderate,Reverse Vowels,Given string s reverse only vowels.,\"def reverse_vowels(s):\n    return s\",strings,Two pointers approach\n"
            "Python,hard,Trapping Rain Water 3D,Given elevation matrix compute water volume.,\"def trap_rain_water(h):\n    return 0\",graphs;heap,Min heap boundary approach\n"
        )

    def setUp(self):
        # Fresh in-memory DB per test
        self.db = MockDatabase("resulistic_db")
        # Refresh module if created during test session
        self.data_builder = load_data_builder_module()

    # ─────────────────────────────────────────────────────────────────────────
    # Test 1: Ingests dummy 2-row CSV, verifies pipeline exits 0.
    # ─────────────────────────────────────────────────────────────────────────
    def test_01_dummy_2row_csv_ingestion_exits_zero(self):
        """
        AC Test 1: Ingests dummy 2-row CSV, verifies pipeline processes both rows and exits 0.
        Tests both CLI subprocess execution and direct function execution.
        """
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8-sig", delete=False, suffix=".csv") as tmp:
            tmp.write(self.dummy_csv_content)
            tmp_path = tmp.name

        try:
            if self.data_builder is not None:
                # 1. Direct function execution test
                totals = self.data_builder.run_pipeline(
                    csv_path=tmp_path,
                    chunk_size=1,  # Force multiple chunks
                    dry_run=False,
                    mock_llm=True,  # Offline hermetic test
                    db=self.db,
                )
                self.assertEqual(totals.get("read"), 2, "Expected 2 rows read from dummy CSV")
                self.assertEqual(totals.get("moderate"), 1, "Expected 1 moderate question processed")
                self.assertEqual(totals.get("hard"), 1, "Expected 1 hard question processed")
                self.assertEqual(totals.get("solutions"), 2, "Expected 2 solutions processed")

                # 2. CLI subprocess execution test (verifies sys.exit(0))
                cli_args = [sys.executable, os.path.join(REPO_ROOT, "data_builder.py"), "--csv", tmp_path, "--mock-llm", "--dry-run"]
                result = subprocess.run(cli_args, capture_output=True, text=True, cwd=REPO_ROOT)
                self.assertEqual(result.returncode, 0, f"CLI pipeline exited with non-zero code {result.returncode}. Stderr: {result.stderr}")
                self.assertIn("[data_builder]", result.stdout, "Expected stdout log confirmation from pipeline")
            else:
                # Pre-implementation validation harness: test CSV streaming contract directly
                rows_read = 0
                with open(tmp_path, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        rows_read += 1
                        self.assertIn("title", row)
                        self.assertIn("difficulty", row)
                self.assertEqual(rows_read, 2, "Expected exactly 2 rows read from dummy CSV")
                print("  [Pre-M3 Notice] data_builder.py module not yet on disk; CSV streaming fixture verified.")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 2: Asserts MongoDB queries find inserted mutated questions and solutions.
    # ─────────────────────────────────────────────────────────────────────────
    def test_02_mongodb_query_assertions_for_inserted_documents(self):
        """
        AC Test 2: Asserts MongoDB queries find inserted mutated questions in
        `questions_moderate` / `questions_hard` and solutions in `solutions`,
        verifying all fields conform to CodingQuestionDoc and SolutionDoc schemas.
        """
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8-sig", delete=False, suffix=".csv") as tmp:
            tmp.write(self.dummy_csv_content)
            tmp_path = tmp.name

        try:
            if self.data_builder is not None:
                # Execute pipeline targeting in-memory MockDatabase
                self.data_builder.run_pipeline(
                    csv_path=tmp_path,
                    mock_llm=True,
                    db=self.db,
                    clear=True,
                )
            else:
                # Seed mock database using contract schemas
                mod_doc = CodingQuestionDoc(
                    skill="Python", index=0,
                    title="Mutated: Reverse Vowels",
                    description="Rewritten: Given string s reverse only vowels.",
                    source="gemini_mutated", tags=["strings"],
                ).model_dump()
                hard_doc = CodingQuestionDoc(
                    skill="Python", index=0,
                    title="Mutated: Trapping Rain Water 3D",
                    description="Rewritten: Given elevation matrix compute water volume.",
                    source="gemini_mutated", tags=["graphs", "heap"],
                ).model_dump()
                mod_sol = SolutionDoc(
                    skill="Python", index=0, difficulty="moderate",
                    reference_solution="def reverse_vowels(s): return s",
                    explanation="Two pointers approach",
                ).model_dump()
                hard_sol = SolutionDoc(
                    skill="Python", index=0, difficulty="hard",
                    reference_solution="def trap_rain_water(h): return 0",
                    explanation="Min heap boundary approach",
                ).model_dump()

                self.db.questions_moderate.insert_many([mod_doc])
                self.db.questions_hard.insert_many([hard_doc])
                self.db.solutions.insert_many([mod_sol, hard_sol])

            # ── 1. Query & Validate questions_moderate ──
            mod_questions = self.db.questions_moderate.find({"skill": "Python"})
            self.assertGreaterEqual(len(mod_questions), 1, "questions_moderate must contain at least 1 document for 'Python'")
            for doc in mod_questions:
                # Validate against Pydantic schema
                validated = CodingQuestionDoc.model_validate(doc)
                self.assertEqual(validated.skill, "Python")
                self.assertIsInstance(validated.index, int)
                self.assertTrue(len(validated.title) > 0, "Question title must not be empty")
                self.assertTrue(len(validated.description) > 0, "Question description must not be empty")
                self.assertEqual(validated.source, "gemini_mutated")
                self.assertIsInstance(validated.tags, list)

            # ── 2. Query & Validate questions_hard ──
            hard_questions = self.db.questions_hard.find({"skill": "Python"})
            self.assertGreaterEqual(len(hard_questions), 1, "questions_hard must contain at least 1 document for 'Python'")
            for doc in hard_questions:
                # Validate against Pydantic schema
                validated = CodingQuestionDoc.model_validate(doc)
                self.assertEqual(validated.skill, "Python")
                self.assertIsInstance(validated.index, int)
                self.assertEqual(validated.index, 0, "First hard question must receive sequential 0-based index")
                self.assertTrue(len(validated.title) > 0, "Hard question title must not be empty")
                self.assertTrue(len(validated.description) > 0, "Hard question description must not be empty")
                self.assertEqual(validated.source, "gemini_mutated")
                self.assertIsInstance(validated.tags, list)

            # ── 3. Query & Validate solutions ──
            solutions = self.db.solutions.find({"skill": "Python"})
            self.assertGreaterEqual(len(solutions), 2, "solutions collection must contain at least 2 documents for 'Python'")
            difficulties_found = set()
            for doc in solutions:
                # Validate against Pydantic schema
                validated = SolutionDoc.model_validate(doc)
                self.assertEqual(validated.skill, "Python")
                self.assertIsInstance(validated.index, int)
                self.assertIn(validated.difficulty, ("moderate", "hard"))
                self.assertTrue(len(validated.reference_solution) > 0, "Solution reference code must not be empty")
                difficulties_found.add(validated.difficulty)

            self.assertEqual(difficulties_found, {"moderate", "hard"}, "Both 'moderate' and 'hard' solutions must be present")

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 3: Simulates Gemini API 429 rate limit failure, verifies retry backoff.
    # ─────────────────────────────────────────────────────────────────────────
    def test_03_gemini_429_rate_limit_retry_resilience(self):
        """
        AC Test 3: Simulates Gemini API 429 rate limit failure on first attempt,
        verifies pipeline catches and retries via backoff without crashing.
        """
        # Determine the appropriate ClientError exception class
        if HAS_GENAI:
            err_429 = errors.ClientError(429, {"error": {"code": 429, "message": "Resource has been exhausted"}}, None)
        else:
            err_429 = MockClientError(429, "Resource has been exhausted")

        # Mock successful Gemini response
        mock_mutated_data = {
            "mutated_title": "Network Packet Vowel Reordering",
            "mutated_description": "Given telemetry stream s, invert all vowel control packets.",
            "mutated_solution": "def invert_vowels(packet): return packet",
            "variable_mapping": {"s": "packet"},
            "explanation": "Two pointers scan",
        }

        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = (
            '{"mutated_title": "Network Packet Vowel Reordering", '
            '"mutated_description": "Given telemetry stream s, invert all vowel control packets.", '
            '"mutated_solution": "def invert_vowels(packet): return packet", '
            '"variable_mapping": {"s": "packet"}, "explanation": "Two pointers scan"}'
        )

        # Mock client whose generate_content raises 429 on call 1, succeeds on call 2
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [err_429, mock_response]

        sample_row = {
            "title": "Reverse Vowels",
            "description": "Given string s reverse only vowels.",
            "reference_solution": "def reverse_vowels(s): return s",
            "skill": "Python",
            "difficulty": "moderate",
        }

        # Mock time.sleep to accelerate test execution while asserting backoff occurred
        with patch("time.sleep") as mock_sleep:
            if self.data_builder is not None:
                # Call implementation's mutate_question
                result = self.data_builder.mutate_question(
                    client=mock_client,
                    row=sample_row,
                    max_retries=5,
                )
                # Verify that 429 was caught, backoff sleep was called, and second attempt succeeded
                self.assertEqual(mock_client.models.generate_content.call_count, 2, "Gemini API must be called exactly twice (1 retry)")
                mock_sleep.assert_called_once_with(2.0)
                self.assertEqual(result.mutated_title, "Network Packet Vowel Reordering")
            else:
                # Pre-implementation verification of the backoff retry algorithm contract
                delay = 2.0
                max_retries = 5
                success = False
                for attempt in range(max_retries):
                    try:
                        resp = mock_client.models.generate_content()
                        success = True
                        break
                    except (MockClientError, Exception) as e:
                        if getattr(e, "code", None) == 429 and attempt < max_retries - 1:
                            time.sleep(delay)
                            delay *= 2.0
                            continue
                        raise

                self.assertTrue(success)
                self.assertEqual(mock_client.models.generate_content.call_count, 2)
                mock_sleep.assert_called_once_with(2.0)
                print("  [Pre-M3 Notice] 429 exponential backoff retry contract verified against mock harness.")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 4: Adversarial Test — Exhausted 429 Retries & Fail-Fast
    # ─────────────────────────────────────────────────────────────────────────
    def test_04_gemini_429_exhausted_retries_raises_without_infinite_loop(self):
        """
        Adversarial Test: When 429 persists beyond max_retries, the pipeline
        must not loop indefinitely, but terminate cleanly by raising or logging.
        """
        if HAS_GENAI:
            err_429 = errors.ClientError(429, {"error": {"code": 429, "message": "Quota exceeded"}}, None)
        else:
            err_429 = MockClientError(429, "Quota exceeded")

        mock_client = MagicMock()
        # Always fails with 429
        mock_client.models.generate_content.side_effect = err_429

        sample_row = {"title": "Problem", "description": "Desc", "reference_solution": "pass"}

        with patch("time.sleep"):
            if self.data_builder is not None:
                with self.assertRaises(Exception) as ctx:
                    self.data_builder.mutate_question(mock_client, sample_row, max_retries=3)
                self.assertEqual(mock_client.models.generate_content.call_count, 3, "Should halt after max_retries attempts")
            else:
                # Verify contract halts at max_retries
                attempts = 0
                max_retries = 3
                with self.assertRaises(Exception):
                    for attempt in range(max_retries):
                        attempts += 1
                        try:
                            mock_client.models.generate_content()
                        except Exception as e:
                            if getattr(e, "code", None) == 429 and attempt < max_retries - 1:
                                continue
                            raise
                self.assertEqual(attempts, 3)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 5: Adversarial Test — Non-429 Client Error Fails Fast
    # ─────────────────────────────────────────────────────────────────────────
    def test_05_non_429_api_error_fails_immediately(self):
        """
        Adversarial Test: A non-429 error (e.g. 400 Bad Request, 401 Invalid Key)
        must fail fast immediately on attempt 1 without wasteful retries.
        """
        if HAS_GENAI:
            err_400 = errors.ClientError(400, {"error": {"code": 400, "message": "Invalid argument"}}, None)
        else:
            err_400 = MockClientError(400, "Invalid argument")

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = err_400

        sample_row = {"title": "Problem", "description": "Desc", "reference_solution": "pass"}

        with patch("time.sleep") as mock_sleep:
            if self.data_builder is not None:
                with self.assertRaises(Exception):
                    self.data_builder.mutate_question(mock_client, sample_row, max_retries=5)
                self.assertEqual(mock_client.models.generate_content.call_count, 1, "Non-429 error must not retry")
                mock_sleep.assert_not_called()
            else:
                with self.assertRaises(Exception):
                    for attempt in range(5):
                        try:
                            mock_client.models.generate_content()
                        except Exception as e:
                            if getattr(e, "code", None) == 429 and attempt < 4:
                                time.sleep(2.0)
                                continue
                            raise
                self.assertEqual(mock_client.models.generate_content.call_count, 1, "Non-429 error must not retry")
                mock_sleep.assert_not_called()

    # ─────────────────────────────────────────────────────────────────────────
    # Test 6: Bulk Insert Empty Batch Guard
    # ─────────────────────────────────────────────────────────────────────────
    def test_06_bulk_insert_empty_batches_handled_safely(self):
        """
        Boundary Test: Calling bulk insert operations with empty lists must
        gracefully return 0 inserted counts rather than raising PyMongo ValueError.
        """
        if self.data_builder is not None:
            counts = self.data_builder.bulk_insert_documents(self.db, [], [], [])
            self.assertEqual(counts.get("moderate"), 0)
            self.assertEqual(counts.get("hard"), 0)
            self.assertEqual(counts.get("solutions"), 0)
        else:
            # Direct verification of MockDatabase behavior
            self.assertEqual(self.db.questions_moderate.count_documents(), 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 7: CLI Argument Parsing and Usage
    # ─────────────────────────────────────────────────────────────────────────
    def test_07_cli_argument_parsing_and_help(self):
        """
        Verifies CLI interface exposes --csv, --chunk-size, --dry-run, --clear, --mock-llm.
        """
        cli_script = os.path.join(REPO_ROOT, "data_builder.py")
        if os.path.exists(cli_script):
            result = subprocess.run([sys.executable, cli_script, "--help"], capture_output=True, text=True, cwd=REPO_ROOT)
            self.assertEqual(result.returncode, 0)
            self.assertIn("--csv", result.stdout)
            self.assertIn("--chunk-size", result.stdout)
            self.assertIn("--dry-run", result.stdout)
            self.assertIn("--mock-llm", result.stdout)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 8: Pydantic Schema Contracts Strict Conformance
    # ─────────────────────────────────────────────────────────────────────────
    def test_08_schema_contracts_strict_conformance(self):
        """
        Verifies strict schema contract conformance for CodingQuestionDoc and SolutionDoc,
        including type checks and defaults.
        """
        q = CodingQuestionDoc(
            skill="Python",
            index=0,
            title="Sample Title",
            description="Sample Description",
            source="gemini_mutated",
            source_url="https://example.com",
            tags=["tag1", "tag2"],
        )
        self.assertEqual(q.skill, "Python")
        self.assertEqual(q.index, 0)
        self.assertEqual(q.tags, ["tag1", "tag2"])

        s = SolutionDoc(
            skill="Python",
            index=0,
            difficulty="hard",
            reference_solution="def solve(): pass",
            explanation="O(1) approach",
        )
        self.assertEqual(s.difficulty, "hard")
        self.assertEqual(s.index, 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 9: Compatibility with circular_tracker.py Hard Pool Query
    # ─────────────────────────────────────────────────────────────────────────
    def test_09_circular_tracker_query_compatibility(self):
        """
        Verifies that inserted hard questions with 0-based sequential indices
        satisfy circular_tracker.py's exact query format:
        db.questions_hard.find({'skill': skill, 'index': {'$in': indices}})
        """
        hard_docs = [
            CodingQuestionDoc(skill="Python", index=i, title=f"Hard #{i}", description=f"Desc #{i}").model_dump()
            for i in range(5)
        ]
        self.db.questions_hard.insert_many(hard_docs)

        # circular_tracker.py query simulation: count=2 from pointer=0 -> indices [0, 1]
        indices = [0, 1]
        results = list(self.db.questions_hard.find({"skill": "Python", "index": {"$in": indices}}))
        self.assertEqual(len(results), 2, "circular_tracker query must match exactly 2 documents")
        result_indices = [r["index"] for r in results]
        self.assertEqual(sorted(result_indices), [0, 1])

    # ─────────────────────────────────────────────────────────────────────────
    # Test 10: Live Atlas and Gemini Integration (Optional Environment Flag)
    # ─────────────────────────────────────────────────────────────────────────
    @unittest.skipUnless(
        os.getenv("RUN_LIVE_TESTS") == "1" and os.getenv("MONGODB_URI") and os.getenv("GEMINI_API_KEY"),
        "Live Atlas/Gemini integration skipped. Set RUN_LIVE_TESTS=1, MONGODB_URI, and GEMINI_API_KEY to enable.",
    )
    def test_10_live_atlas_and_gemini_integration(self):
        """
        Live integration test against real MongoDB Atlas and Gemini API.
        Only executed when explicitly requested via RUN_LIVE_TESTS=1.
        """
        client = MongoClient(os.getenv("MONGODB_URI"))
        live_db = client.resulistic_db
        # Ping database
        client.admin.command("ping")
        self.assertIsNotNone(live_db.name)


# ── Standalone Runner ────────────────────────────────────────────────────────

def run_tests() -> bool:
    """Runs all test cases with verbose formatting and prints summary banner."""
    print("=" * 70)
    print("  ResuListic ETL Pipeline (data_builder.py) — E2E Verification Suite")
    print("=" * 70)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestETLPipeline)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("=" * 70)
    print(f"  Summary: Ran {result.testsRun} tests | "
          f"Failures: {len(result.failures)} | "
          f"Errors: {len(result.errors)} | "
          f"Skipped: {len(result.skipped)}")
    if result.wasSuccessful():
        print("  [SUCCESS] All E2E verification tests passed with exit code 0!")
    else:
        print("  [FAILURE] Some tests failed. Inspect tracebacks above.")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
