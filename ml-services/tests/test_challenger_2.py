"""
test_challenger_2.py — Empirical Verification and Adversarial Challenge Suite (challenger_2).

Focus Areas:
1. Challenge 1: Memory overhead stress-test on large simulated CSV stream (tracemalloc profiling).
   - Verifies bounded memory O(chunk_size) across 1k, 5k, 20k, 50k rows.
   - Compares streaming chunk memory consumption vs naive full-file load.
2. Challenge 2: Modulo pointer arithmetic stress-test with circular_tracker.py (HARD_POOL_SIZE = 50).
   - Verifies 0-based consecutive indices (0..N-1) without gaps or duplicates.
   - Simulates 50 users x 100 test iterations (5,000 queries) with modulo wraparounds.
   - Verifies pointer advancement, test_count increments, document ordering, and schema validity.
3. Challenge 3: Backward compatibility verification of ml-services/skill_test/data_builder.py.
   - Tests module imports and re-exports of all required symbols.
   - Tests seed_mock_data seeder logic and document schemas.
   - Tests CLI argument parsing and execution from ml-services path.
4. Challenge 4: Incremental loading & boundary checks.
   - Multi-chunk sequential index preservation without collisions.
   - Behavior when hard pool is exactly 50 vs > 50 vs < 50.
"""

import copy
import csv
import importlib
import io
import os
import subprocess
import sys
import tempfile
import time
import tracemalloc
import unittest
from unittest.mock import patch
from typing import Any, Optional

# Setup import paths
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ML_SERVICES_DIR = os.path.join(REPO_ROOT, "ml-services")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

from schema.question_schema import CodingQuestionDoc, SolutionDoc, UserTestState, TestSessionOut
from skill_test.circular_tracker import HARD_POOL_SIZE, get_hard_questions, get_user_test_count
import data_builder
from skill_test import data_builder as ml_data_builder


# ── Hermetic Mock Database with update_one ($set, $inc) support ─────────────

class MockCollection:
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
        d = copy.deepcopy(doc)
        self.docs.append(d)
        return d

    def find(self, filter_dict: Optional[dict] = None):
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

    def find_one(self, filter_dict: Optional[dict] = None, sort: Optional[list] = None):
        results = self.find(filter_dict)
        if not results:
            return None
        if sort and len(sort) > 0:
            key, direction = sort[0]
            reverse = (direction == -1)
            results.sort(key=lambda x: x.get(key, 0), reverse=reverse)
        return results[0]

    def update_one(self, filter_dict: dict, update_dict: dict):
        """Mock update_one supporting $set and $inc operators."""
        target = None
        for d in self.docs:
            match = True
            for k, v in filter_dict.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                target = d
                break

        if target is not None:
            if "$set" in update_dict:
                for k, v in update_dict["$set"].items():
                    target[k] = copy.deepcopy(v)
            if "$inc" in update_dict:
                for k, v in update_dict["$inc"].items():
                    target[k] = target.get(k, 0) + v

        class UpdateResult:
            matched_count = 1 if target else 0
            modified_count = 1 if target else 0
        return UpdateResult()

    def delete_many(self, filter_dict: Optional[dict] = None):
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

    def count_documents(self, filter_dict: Optional[dict] = None) -> int:
        return len(self.find(filter_dict))


class MockDatabase:
    def __init__(self, name: str = "resulistic_db"):
        self.name = name
        self.questions_moderate = MockCollection("questions_moderate")
        self.questions_hard = MockCollection("questions_hard")
        self.solutions = MockCollection("solutions")
        self.user_test_state = MockCollection("user_test_state")

    def __getitem__(self, name: str) -> MockCollection:
        if not hasattr(self, name):
            setattr(self, name, MockCollection(name))
        return getattr(self, name)


# ── Challenge Test Suite ───────────────────────────────────────────────────

class TestChallenger2Empirical(unittest.TestCase):
    """Adversarial stress-tests by challenger_2."""

    def setUp(self):
        self.db = MockDatabase("resulistic_db")

    # ─────────────────────────────────────────────────────────────────────────
    # Challenge 1: Memory Overhead Stress-Test on Large CSV Streams
    # ─────────────────────────────────────────────────────────────────────────
    def test_01_memory_bounded_streaming_csv_chunks(self):
        """
        Challenge 1.1: Verify read_csv_chunks uses strictly bounded memory O(chunk_size)
        across 1,000, 5,000, and 20,000 rows, without loading whole files into RAM.
        """
        row_counts = [1000, 5000, 20000]
        chunk_size = 50
        peak_memories = {}

        for n_rows in row_counts:
            # Generate temporary CSV file
            with tempfile.NamedTemporaryFile("w+", encoding="utf-8-sig", delete=False, suffix=".csv") as tmp:
                writer = csv.writer(tmp)
                writer.writerow(["skill", "difficulty", "title", "description", "reference_solution", "tags", "explanation"])
                for i in range(n_rows):
                    diff = "hard" if i % 2 == 0 else "moderate"
                    writer.writerow([
                        "Python", diff,
                        f"Coding Challenge Problem #{i} with long descriptive context",
                        f"Given an array of {i*10} elements, find the maximum contiguous subarray sum with edge constraints. " * 3,
                        f"def solve_{i}(arr):\n    # O(N) Kadane variation\n    return max(arr) if arr else 0",
                        "algorithms;dynamic_programming;arrays",
                        "Dynamic programming running state optimization",
                    ])
                tmp_path = tmp.name

            try:
                # Measure memory for streaming chunks
                tracemalloc.start()
                tracemalloc.reset_peak()
                
                rows_read = 0
                for chunk in data_builder.read_csv_chunks(tmp_path, chunk_size=chunk_size):
                    rows_read += len(chunk)
                    self.assertLessEqual(len(chunk), chunk_size)

                current_mem, peak_mem = tracemalloc.get_traced_memory()
                tracemalloc.stop()

                self.assertEqual(rows_read, n_rows)
                peak_memories[n_rows] = peak_mem

                # Empirical Assertion: Peak memory for chunk_size=50 should stay under 2 MB
                # even for 20,000 rows with long descriptions (~10 MB on disk)
                self.assertLess(peak_mem, 2 * 1024 * 1024,
                                f"Streaming peak memory ({peak_mem / 1024:.1f} KB) exceeded 2 MB threshold for {n_rows} rows")

            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        # Comparative Assertion: Peak memory between 1,000 rows and 20,000 rows must remain
        # within constant factor O(chunk_size) (< 2.5x variance), rather than scaling 20x linearly.
        ratio = peak_memories[20000] / peak_memories[1000]
        print(f"\n  [Memory Profile] 1k rows: {peak_memories[1000]/1024:.1f} KB | 5k rows: {peak_memories[5000]/1024:.1f} KB | 20k rows: {peak_memories[20000]/1024:.1f} KB | Ratio 20k/1k: {ratio:.2f}x")
        self.assertLess(ratio, 2.5, f"Memory footprint scaled with row count ({ratio:.2f}x), violating O(chunk_size) bound!")

    def test_02_memory_streaming_vs_naive_full_read(self):
        """
        Challenge 1.2: Directly compare memory consumption of read_csv_chunks vs naive
        list(DictReader) on a 10,000 row dataset.
        """
        n_rows = 10000
        chunk_size = 50

        with tempfile.NamedTemporaryFile("w+", encoding="utf-8-sig", delete=False, suffix=".csv") as tmp:
            writer = csv.writer(tmp)
            writer.writerow(["skill", "difficulty", "title", "description", "reference_solution", "tags", "explanation"])
            for i in range(n_rows):
                writer.writerow([
                    "Python", "hard", f"Algorithmic Task #{i}",
                    "Complex string pattern matching with finite automata. " * 5,
                    "def match(s, p): pass", "strings;dp", "KMP pattern search",
                ])
            tmp_path = tmp.name

        try:
            # 1. Measure Naive Whole-File Loading
            tracemalloc.start()
            tracemalloc.reset_peak()
            with open(tmp_path, "r", encoding="utf-8-sig") as f:
                all_rows = list(csv.DictReader(f))
            naive_len = len(all_rows)
            _, naive_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            del all_rows

            # 2. Measure Chunked Streaming Loading
            tracemalloc.start()
            tracemalloc.reset_peak()
            stream_len = 0
            for chunk in data_builder.read_csv_chunks(tmp_path, chunk_size=chunk_size):
                stream_len += len(chunk)
            _, chunk_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            self.assertEqual(naive_len, n_rows)
            self.assertEqual(stream_len, n_rows)

            savings_factor = naive_peak / max(chunk_peak, 1)
            print(f"\n  [Memory Comparison] Naive Full Load: {naive_peak/1024:.1f} KB vs Chunked Stream: {chunk_peak/1024:.1f} KB (Savings: {savings_factor:.1f}x)")
            self.assertGreater(savings_factor, 5.0, f"Chunked streaming did not yield sufficient memory savings: {savings_factor:.1f}x")

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_03_run_pipeline_large_stream_memory_and_counters(self):
        """
        Challenge 1.3: Verify run_pipeline end-to-end memory stability and
        counter accuracy on a 5,000 row multi-skill stream in dry-run mode.
        """
        n_rows = 5000
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8-sig", delete=False, suffix=".csv") as tmp:
            writer = csv.writer(tmp)
            writer.writerow(["skill", "difficulty", "title", "description", "reference_solution"])
            skills = ["Python", "JavaScript", "Go", "Rust", "SQL"]
            for i in range(n_rows):
                s = skills[i % len(skills)]
                d = "hard" if (i // len(skills)) % 2 == 0 else "moderate"
                writer.writerow([s, d, f"{s} Problem {i}", f"Description {i}", "def solve(): pass"])
            tmp_path = tmp.name

        try:
            tracemalloc.start()
            tracemalloc.reset_peak()

            totals = data_builder.run_pipeline(
                csv_path=tmp_path,
                chunk_size=100,
                dry_run=True,
                mock_llm=True,
            )

            _, peak_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            self.assertEqual(totals["read"], n_rows)
            self.assertEqual(totals["moderate"] + totals["hard"], n_rows)
            self.assertEqual(totals["solutions"], n_rows)

            print(f"\n  [Pipeline Peak Memory (5,000 rows)] {peak_mem / 1024:.1f} KB")
            self.assertLess(peak_mem, 4 * 1024 * 1024, "Pipeline execution exceeded 4 MB memory budget")

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ─────────────────────────────────────────────────────────────────────────
    # Challenge 2: Modulo Pointer Arithmetic Stress-Test with circular_tracker
    # ─────────────────────────────────────────────────────────────────────────
    def test_04_circular_tracker_sequential_indices_gapless(self):
        """
        Challenge 2.1: Verify data_builder populates strictly consecutive indices
        0..49 (HARD_POOL_SIZE) without gaps, duplicates, or missing entries.
        """
        # Create CSV with 60 hard questions and 60 moderate questions
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8-sig", delete=False, suffix=".csv") as tmp:
            writer = csv.writer(tmp)
            writer.writerow(["skill", "difficulty", "title", "description", "reference_solution", "tags", "explanation"])
            for i in range(60):
                writer.writerow(["Python", "hard", f"Hard Task {i}", f"Desc {i}", f"solve_{i}()", "hard;test", "exp"])
                writer.writerow(["Python", "moderate", f"Mod Task {i}", f"Desc {i}", f"solve_{i}()", "mod;test", "exp"])
            tmp_path = tmp.name

        try:
            totals = data_builder.run_pipeline(
                csv_path=tmp_path,
                chunk_size=20,
                mock_llm=True,
                db=self.db,
                clear=True,
            )
            self.assertEqual(totals["hard"], 60)
            self.assertEqual(totals["moderate"], 60)

            # Assert hard questions indexing
            hard_docs = self.db.questions_hard.find({"skill": "Python"})
            self.assertEqual(len(hard_docs), 60)
            indices = [doc["index"] for doc in hard_docs]
            indices_sorted = sorted(indices)

            # Strictly 0..59 without any missing number
            expected_indices = list(range(60))
            self.assertEqual(indices_sorted, expected_indices, "Indices in questions_hard must be contiguous 0..N-1")
            self.assertEqual(len(indices), len(set(indices)), "Duplicate indices detected in questions_hard")

            # Check that circular pool range [0, HARD_POOL_SIZE - 1] is completely saturated
            pool_set = set(range(HARD_POOL_SIZE))
            actual_set = set(indices)
            self.assertTrue(pool_set.issubset(actual_set), f"Hard questions do not fully cover pool 0..{HARD_POOL_SIZE-1}")

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_05_circular_tracker_multi_user_wraparound_stress(self):
        """
        Challenge 2.2: Simulate 50 users x 100 test iterations (5,000 total test requests)
        calling get_hard_questions on data seeded by data_builder.
        Asserts modulo wraparound across HARD_POOL_SIZE boundary (49 -> 0, 1),
        zero KeyErrors, zero IndexErrors, and exact count preservation.
        """
        # Seed 50 hard questions per skill for Python and Go
        skills = ["Python", "Go"]
        hard_docs = []
        for s in skills:
            for i in range(HARD_POOL_SIZE):
                doc = CodingQuestionDoc(
                    skill=s, index=i, title=f"{s} Hard Question #{i}",
                    description=f"Detailed algorithmic challenge {i}",
                    source="gemini_mutated", tags=["stress_test"],
                ).model_dump()
                hard_docs.append(doc)
        self.db.questions_hard.insert_many(hard_docs)

        n_users = 50
        n_iterations = 100
        count_per_test = 2
        total_queries = 0

        for u_idx in range(n_users):
            user_id = f"user_{u_idx:03d}"
            for it in range(n_iterations):
                for skill in skills:
                    questions = get_hard_questions(self.db, user_id=user_id, skill=skill, count=count_per_test)
                    total_queries += 1

                    # 1. Must always return exact requested count
                    self.assertEqual(len(questions), count_per_test,
                                     f"User {user_id} iter {it} received {len(questions)} questions instead of {count_per_test}")

                    # 2. Verify all questions match schema
                    for q in questions:
                        validated = CodingQuestionDoc.model_validate(q)
                        self.assertEqual(validated.skill, skill)
                        self.assertGreaterEqual(validated.index, 0)
                        self.assertLess(validated.index, HARD_POOL_SIZE)

                    # 3. Verify circular ordering: questions[1]['index'] must be (questions[0]['index'] + 1) % HARD_POOL_SIZE
                    idx_0 = questions[0]["index"]
                    idx_1 = questions[1]["index"]
                    expected_idx_1 = (idx_0 + 1) % HARD_POOL_SIZE
                    self.assertEqual(idx_1, expected_idx_1,
                                     f"Circular order violated at iteration {it}: [{idx_0}, {idx_1}]")

            # 4. Verify user test state tracking
            for skill in skills:
                test_count = get_user_test_count(self.db, user_id, skill)
                self.assertEqual(test_count, n_iterations,
                                 f"Test count for {user_id} {skill} is {test_count}, expected {n_iterations}")

        print(f"\n  [Circular Tracker Stress] Successfully verified {total_queries} queries across {n_users} users with 0 failures!")

    def test_06_circular_tracker_boundary_wraparound_exact_indices(self):
        """
        Challenge 2.3: Explicitly test wraparound when pointer is at 49, count=2 -> [49, 0].
        Verify sorting preserves circular order [49, 0] instead of MongoDB default order [0, 49].
        """
        skill = "Rust"
        for i in range(HARD_POOL_SIZE):
            self.db.questions_hard.insert_one(
                CodingQuestionDoc(skill=skill, index=i, title=f"Task {i}", description=f"Desc {i}").model_dump()
            )

        user_id = "boundary_user"
        # Seed user state with pointer at 47 so next advance with count=2 lands at 49
        self.db.user_test_state.insert_one({
            "_id": {"user_id": user_id, "skill": skill},
            "hard_pointer": 47,
            "test_count": 1,
            "last_test_at": "2026-10-05T00:00:00Z",
        })

        # Next call: pointer should become (47 + 2) % 50 = 49.
        # indices = [49, (49+1)%50] = [49, 0].
        questions = get_hard_questions(self.db, user_id=user_id, skill=skill, count=2)
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]["index"], 49, "First question across wraparound must be index 49")
        self.assertEqual(questions[1]["index"], 0, "Second question across wraparound must be index 0")

        # Next call: pointer should become (49 + 2) % 50 = 1.
        # indices = [1, 2]
        questions_next = get_hard_questions(self.db, user_id=user_id, skill=skill, count=2)
        self.assertEqual(len(questions_next), 2)
        self.assertEqual(questions_next[0]["index"], 1)
        self.assertEqual(questions_next[1]["index"], 2)

    def test_07_underpopulated_pool_edge_case(self):
        """
        Challenge 2.4 (Adversarial Defect Analysis): Test behavior when database has
        fewer hard questions than HARD_POOL_SIZE (e.g., only 10 questions indexed 0..9).
        Demonstrates that random pointer selection can query unpopulated indices [10..49].
        """
        skill = "TypeScript"
        # Insert only 10 questions (indices 0..9)
        for i in range(10):
            self.db.questions_hard.insert_one(
                CodingQuestionDoc(skill=skill, index=i, title=f"TS {i}", description=f"Desc {i}").model_dump()
            )

        # Query with random starting pointer across 100 trials
        underpopulated_failures = 0
        for trial in range(100):
            user_id = f"under_user_{trial}"
            questions = get_hard_questions(self.db, user_id=user_id, skill=skill, count=2)
            if len(questions) < 2:
                underpopulated_failures += 1

        print(f"\n  [Adversarial Analysis] Underpopulated pool (10/50 questions): {underpopulated_failures}/100 queries returned < 2 questions.")
        self.assertGreater(underpopulated_failures, 0, "Expected underpopulated pool to produce shortfall without minimum pool size.")

    # ─────────────────────────────────────────────────────────────────────────
    # Challenge 3: Backward Compatibility Verification of ml-services data_builder
    # ─────────────────────────────────────────────────────────────────────────
    def test_08_backward_compatibility_symbols_and_reexports(self):
        """
        Challenge 3.1: Verify ml-services/skill_test/data_builder.py exports all
        required symbols and maintains exact functional parity with root module.
        """
        required_symbols = [
            "MutatedQuestion",
            "get_db",
            "read_csv_chunks",
            "mock_mutate",
            "mutate_question",
            "bulk_insert_documents",
            "run_pipeline",
            "seed_mock_data",
            "main",
        ]
        for symbol in required_symbols:
            self.assertTrue(hasattr(ml_data_builder, symbol),
                            f"ml-services/skill_test/data_builder missing required symbol: {symbol}")
            root_attr = getattr(data_builder, symbol)
            ml_attr = getattr(ml_data_builder, symbol)
            self.assertIs(ml_attr, root_attr, f"Symbol {symbol} in ml-services is not an exact reference to root data_builder")

    def test_09_seed_mock_data_execution_and_schema_conformance(self):
        """
        Challenge 3.2: Verify seed_mock_data execution generates 100 moderate questions,
        50 hard questions, and 150 solutions per skill, strictly validating Pydantic schemas.
        """
        # Patch get_db in root data_builder to return our MockDatabase
        test_skills = ["Python", "FastAPI"]
        with patch("data_builder.get_db", return_value=self.db):
            ml_data_builder.seed_mock_data(test_skills)

        # Assert moderate questions
        for s in test_skills:
            mod_docs = self.db.questions_moderate.find({"skill": s})
            self.assertEqual(len(mod_docs), 100, f"Expected 100 moderate questions for {s}")
            for d in mod_docs:
                CodingQuestionDoc.model_validate(d)

            hard_docs = self.db.questions_hard.find({"skill": s})
            self.assertEqual(len(hard_docs), 50, f"Expected 50 hard questions for {s}")
            hard_indices = sorted([d["index"] for d in hard_docs])
            self.assertEqual(hard_indices, list(range(50)), f"Hard question indices for {s} must be exactly 0..49")
            for d in hard_docs:
                CodingQuestionDoc.model_validate(d)

            sol_docs = self.db.solutions.find({"skill": s})
            self.assertEqual(len(sol_docs), 150, f"Expected 150 solutions for {s} (100 mod + 50 hard)")
            for d in sol_docs:
                SolutionDoc.model_validate(d)

    def test_10_cli_execution_from_ml_services_module(self):
        """
        Challenge 3.3: Verify ml-services/skill_test/data_builder.py can be invoked
        directly via CLI with subprocess using --help and --csv flags.
        """
        script_path = os.path.join(ML_SERVICES_DIR, "skill_test", "data_builder.py")
        
        # Test 1: --help flag
        cmd_help = [sys.executable, script_path, "--help"]
        res_help = subprocess.run(cmd_help, capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(res_help.returncode, 0, f"CLI --help failed with stderr: {res_help.stderr}")
        self.assertIn("--csv", res_help.stdout)
        self.assertIn("--chunk-size", res_help.stdout)

        # Test 2: Ingestion via ml-services entrypoint
        dummy_content = "skill,difficulty,title,description,reference_solution\nPython,hard,Test Q,Test D,def solve(): pass\n"
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8-sig", delete=False, suffix=".csv") as tmp:
            tmp.write(dummy_content)
            tmp_path = tmp.name

        try:
            cmd_run = [sys.executable, script_path, "--csv", tmp_path, "--mock-llm", "--dry-run"]
            res_run = subprocess.run(cmd_run, capture_output=True, text=True, cwd=REPO_ROOT)
            self.assertEqual(res_run.returncode, 0, f"CLI ingestion via ml-services entrypoint failed: {res_run.stderr}")
            self.assertIn("[data_builder] Complete", res_run.stdout)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ─────────────────────────────────────────────────────────────────────────
    # Challenge 4: Incremental Loading & Multi-Chunk Index Integrity
    # ─────────────────────────────────────────────────────────────────────────
    def test_11_incremental_loading_without_clear_preserves_monotonic_indices(self):
        """
        Challenge 4.1: When clear=False, subsequent runs of run_pipeline must continue
        assigning sequential indices starting from last_index + 1, without reset or collision.
        """
        dummy_batch_1 = (
            "skill,difficulty,title,description,reference_solution\n"
            "Go,hard,Batch 1 Problem A,Desc,pass\n"
            "Go,hard,Batch 1 Problem B,Desc,pass\n"
        )
        dummy_batch_2 = (
            "skill,difficulty,title,description,reference_solution\n"
            "Go,hard,Batch 2 Problem C,Desc,pass\n"
            "Go,hard,Batch 2 Problem D,Desc,pass\n"
        )

        with tempfile.NamedTemporaryFile("w+", encoding="utf-8-sig", delete=False, suffix=".csv") as tmp1:
            tmp1.write(dummy_batch_1)
            tmp1_path = tmp1.name

        with tempfile.NamedTemporaryFile("w+", encoding="utf-8-sig", delete=False, suffix=".csv") as tmp2:
            tmp2.write(dummy_batch_2)
            tmp2_path = tmp2.name

        try:
            # First ingestion with clear=True
            totals_1 = data_builder.run_pipeline(csv_path=tmp1_path, db=self.db, clear=True, mock_llm=True)
            self.assertEqual(totals_1["hard"], 2)

            docs_1 = self.db.questions_hard.find({"skill": "Go"})
            self.assertEqual([d["index"] for d in docs_1], [0, 1])

            # Second ingestion with clear=False (incremental append)
            totals_2 = data_builder.run_pipeline(csv_path=tmp2_path, db=self.db, clear=False, mock_llm=True)
            self.assertEqual(totals_2["hard"], 2)

            docs_all = self.db.questions_hard.find({"skill": "Go"})
            all_indices = [d["index"] for d in docs_all]
            self.assertEqual(all_indices, [0, 1, 2, 3], "Incremental append must produce monotonic 0..3 indices")

        finally:
            for p in (tmp1_path, tmp2_path):
                if os.path.exists(p):
                    os.remove(p)


def run_all_challenger_tests():
    print("=" * 75)
    print("  Empirical Verification & Adversarial Stress Suite (challenger_2)")
    print("=" * 75)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestChallenger2Empirical)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("=" * 75)
    print(f"  Summary: Ran {result.testsRun} tests | Failures: {len(result.failures)} | Errors: {len(result.errors)}")
    if result.wasSuccessful():
        print("  [VERDICT: APPROVE] All empirical stress and challenge tests passed with code 0!")
    else:
        print("  [VERDICT: REJECT] Challenge failures detected. See tracebacks above.")
    print("=" * 75)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_challenger_tests()
    sys.exit(0 if success else 1)
