"""
test_adversarial.py — Empirical Adversarial Stress Harness for data_builder.py.
Authored by challenger_1.

Tests 3 Core Challenge Vectors:
1. CSV Streaming & Edge Cases (0-byte, header-only, 1-row, 2000-row stress, ragged rows, BOM, Unicode, whitespace, empty skill)
2. Gemini 429 Exponential Backoff & Fail-Fast (full backoff sequence, max_retries exhaustion, fail-fast on 400/401/403/500, markdown parsing)
3. MongoDB Bulk Loading & Duplicate Prevention (empty batches, BulkWriteError handling, unique index collision, sequential index continuation)
"""

import copy
import csv
import io
import os
import sys
import tempfile
import time
import unittest
from collections import defaultdict
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
ML_SERVICES_DIR = os.path.join(REPO_ROOT, "ml-services")
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

import data_builder
from schema.question_schema import CodingQuestionDoc, SolutionDoc
from pymongo.errors import BulkWriteError


# ── Mock Database & Collection with Realistic Semantics ─────────────────────

class RealisticMockCollection:
    """Mock MongoDB Collection supporting unique index enforcement and BulkWriteError."""
    def __init__(self, name: str):
        self.name = name
        self.docs: list[dict] = []
        self.unique_keys: list[tuple[str, ...]] = []

    def create_index(self, keys: list[tuple[str, int]], unique: bool = False):
        if unique:
            key_names = tuple(k for k, _ in keys)
            if key_names not in self.unique_keys:
                self.unique_keys.append(key_names)

    def insert_many(self, docs: list[dict], ordered: bool = False):
        if not docs:
            raise ValueError("documents must be a non-empty list")
        inserted = []
        write_errors = []
        existing_signatures = {
            ukey: {tuple(d.get(k) for k in ukey) for d in self.docs}
            for ukey in self.unique_keys
        }

        for idx, doc in enumerate(docs):
            conflict = False
            for ukey in self.unique_keys:
                sig = tuple(doc.get(k) for k in ukey)
                if sig in existing_signatures[ukey]:
                    conflict = True
                    write_errors.append({
                        "index": idx,
                        "code": 11000,
                        "errmsg": f"E11000 duplicate key error collection {self.name} index {ukey}",
                        "op": doc
                    })
                    break
                existing_signatures[ukey].add(sig)

            if not conflict:
                copy_doc = copy.deepcopy(doc)
                if "_id" not in copy_doc:
                    copy_doc["_id"] = len(self.docs) + len(inserted) + 1
                inserted.append(copy_doc)
                self.docs.append(copy_doc)
            elif ordered:
                break

        if write_errors:
            details = {
                "writeErrors": write_errors,
                "nInserted": len(inserted),
                "nMatched": 0,
                "nModified": 0,
                "nRemoved": 0,
                "upserted": []
            }
            raise BulkWriteError(details)

        class Result:
            inserted_ids = [d["_id"] for d in inserted]
        return Result()

    def insert_one(self, doc: dict):
        return self.insert_many([doc], ordered=True)

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
            c = len(self.docs)
            self.docs.clear()
            return c
        kept = []
        for d in self.docs:
            should_delete = True
            for k, v in filter_dict.items():
                if isinstance(v, dict) and "$in" in v:
                    if d.get(k) not in v["$in"]:
                        should_delete = False
                        break
                elif d.get(k) != v:
                    should_delete = False
                    break
            if not should_delete:
                kept.append(d)
        deleted = len(self.docs) - len(kept)
        self.docs = kept
        return deleted

    def count_documents(self, filter_dict: dict = None) -> int:
        return len(self.find(filter_dict))


class RealisticMockDatabase:
    def __init__(self, name: str = "resulistic_db"):
        self.name = name
        self.questions_moderate = RealisticMockCollection("questions_moderate")
        self.questions_hard = RealisticMockCollection("questions_hard")
        self.solutions = RealisticMockCollection("solutions")


# ── Test Suite ───────────────────────────────────────────────────────────────

class TestAdversarialDataBuilder(unittest.TestCase):

    def setUp(self):
        self.db = RealisticMockDatabase()

    # =========================================================================
    # VECTOR 1: CSV Streaming & Extreme Inputs
    # =========================================================================

    def test_csv_empty_file_0_bytes(self):
        """Hypothesis 1.1: 0-byte CSV file should yield 0 chunks and return 0 totals cleanly without error."""
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv") as tmp:
            tmp_path = tmp.name

        try:
            chunks = list(data_builder.read_csv_chunks(tmp_path, chunk_size=10))
            self.assertEqual(len(chunks), 0)

            totals = data_builder.run_pipeline(csv_path=tmp_path, db=self.db, mock_llm=True)
            self.assertEqual(totals["read"], 0)
            self.assertEqual(totals["moderate"], 0)
            self.assertEqual(totals["hard"], 0)
            self.assertEqual(totals["solutions"], 0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_csv_header_only_no_rows(self):
        """Hypothesis 1.2: Header-only CSV should yield 0 chunks and produce 0 totals."""
        content = "skill,difficulty,title,description,reference_solution,tags,explanation\n"
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            totals = data_builder.run_pipeline(csv_path=tmp_path, db=self.db, mock_llm=True)
            self.assertEqual(totals["read"], 0)
            self.assertEqual(self.db.questions_moderate.count_documents(), 0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_csv_single_row_partial_chunk(self):
        """Hypothesis 1.3: 1-row CSV with large chunk_size (50) should stream 1 chunk and 1 row."""
        content = (
            "skill,difficulty,title,description,reference_solution,tags,explanation\n"
            "Go,hard,Concurrent Channel Sieve,Implement prime sieve with channels,\"func sieve() {}\",concurrency;channels,Sieve of Eratosthenes\n"
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            totals = data_builder.run_pipeline(csv_path=tmp_path, chunk_size=50, db=self.db, mock_llm=True)
            self.assertEqual(totals["read"], 1)
            self.assertEqual(totals["hard"], 1)
            self.assertEqual(totals["moderate"], 0)
            self.assertEqual(totals["solutions"], 1)
            hard_doc = self.db.questions_hard.find_one({"skill": "Go"})
            self.assertIsNotNone(hard_doc)
            self.assertEqual(hard_doc["index"], 0)
            self.assertEqual(hard_doc["tags"], ["concurrency", "channels"])
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_csv_large_row_stress_and_chunk_boundaries(self):
        """Hypothesis 1.4: 1,500 rows across 3 skills with chunk_size=73 (prime chunk size)."""
        skills = ["Python", "Rust", "TypeScript"]
        diffs = ["moderate", "hard"]
        row_count = 1500

        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            writer = csv.writer(tmp)
            writer.writerow(["skill", "difficulty", "title", "description", "reference_solution", "tags", "explanation"])
            for i in range(row_count):
                sk = skills[i % len(skills)]
                df = diffs[i % len(diffs)]
                writer.writerow([
                    sk, df, f"Stress Problem {i}", f"Description {i} with payload.",
                    f"def solve_{i}(): return {i}", f"tag_{i%10},algo", f"Explanation {i}"
                ])
            tmp_path = tmp.name

        try:
            totals = data_builder.run_pipeline(csv_path=tmp_path, chunk_size=73, db=self.db, mock_llm=True)
            self.assertEqual(totals["read"], 1500)
            self.assertEqual(totals["moderate"] + totals["hard"], 1500)
            self.assertEqual(totals["solutions"], 1500)

            # Verify sequential indexing per skill and difficulty
            for sk in skills:
                for df in diffs:
                    col = self.db.questions_hard if df == "hard" else self.db.questions_moderate
                    docs = col.find({"skill": sk})
                    indices = [d["index"] for d in docs]
                    expected_indices = list(range(len(docs)))
                    self.assertEqual(sorted(indices), expected_indices, f"Sequential indexing broken for {sk} {df}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_csv_unicode_bom_and_special_characters(self):
        """Hypothesis 1.7: CSV with UTF-8 BOM, emoji, Asian characters, multiline quotes, and math symbols."""
        content = (
            "skill,difficulty,title,description,reference_solution,tags,explanation\n"
            "Python,moderate,\"🚀 快速排序 (QuickSort) 🚀\",\"Given list L with symbols ∑ and 𝝅, sort it.\nLine 2 with \ttabs.\",\"def sort(l): return sorted(l)\",\"算法;排序;🚀\",\"二分法 分治\"\n"
            "Rust,hard,\"Lock-Free 队列 🦀\",\"Rust 并发 lock-free 队列实现。\",\"fn enqueue() -> ()\",\"rust;并发;锁\",\"CAS 循环\"\n"
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8-sig") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            totals = data_builder.run_pipeline(csv_path=tmp_path, db=self.db, mock_llm=True)
            self.assertEqual(totals["read"], 2)
            py_doc = self.db.questions_moderate.find_one({"skill": "Python"})
            self.assertIsNotNone(py_doc, "Document for Python must be found when opened with UTF-8 BOM")
            self.assertIn("🚀 快速排序", py_doc["title"])
            self.assertIn("Line 2 with \ttabs.", py_doc["description"])
            self.assertEqual(py_doc["tags"], ["算法", "排序", "🚀"])
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_csv_missing_optional_fields_and_alternate_columns(self):
        """Hypothesis 1.8: CSV with alternate headers ('topic', 'level', 'solution') and missing optional columns."""
        content = (
            "topic,level,title,description,solution\n"
            "Docker,3,Container Isolation,Explain cgroups and namespaces,docker run -d alpine\n"
            "SQL,easy,Select All,Query everything from table users,SELECT * FROM users;\n"
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            totals = data_builder.run_pipeline(csv_path=tmp_path, db=self.db, mock_llm=True)
            self.assertEqual(totals["read"], 2)
            self.assertEqual(totals["hard"], 1)  # level 3 maps to hard
            self.assertEqual(totals["moderate"], 1)  # easy maps to moderate
            docker_doc = self.db.questions_hard.find_one({"skill": "Docker"})
            self.assertIsNotNone(docker_doc)
            self.assertEqual(docker_doc["tags"], [])
            self.assertEqual(docker_doc["source_url"], "")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_csv_ragged_rows_with_missing_columns(self):
        """Hypothesis 1.8b: CSV where some rows have fewer fields than the header, testing None handling."""
        content = (
            "skill,difficulty,title,description,reference_solution,tags,explanation\n"
            "Python,moderate,Complete Row,Desc,def f(): pass,tag1,expl\n"
            "Python,moderate,Ragged Row,Short Desc\n"  # Missing remaining fields -> DictReader sets to None
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            totals = data_builder.run_pipeline(csv_path=tmp_path, db=self.db, mock_llm=True)
            self.assertEqual(totals["read"], 2)
            self.assertEqual(totals["moderate"], 2)
            ragged_doc = self.db.questions_moderate.find_one({"title": "Mutated: Ragged Row"})
            self.assertIsNotNone(ragged_doc)
            self.assertEqual(ragged_doc["tags"], [])
            self.assertEqual(ragged_doc["source_url"], "")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


    # =========================================================================
    # VECTOR 2: Gemini 429 Exponential Backoff & Fail-Fast Behavior
    # =========================================================================

    def test_gemini_429_full_exponential_backoff_delays(self):
        """Hypothesis 2.1: Verify exact backoff delays [2.0, 4.0, 8.0, 16.0] across 5 attempts before success."""
        class Mock429(Exception):
            code = 429
            status = "RESOURCE_EXHAUSTED"

        mock_resp = MagicMock()
        mock_resp.parsed = None
        mock_resp.text = '{"mutated_title": "T", "mutated_description": "D", "mutated_solution": "S", "variable_mapping": {}, "explanation": "E"}'

        mock_client = MagicMock()
        # 4 failures with 429, 5th attempt succeeds
        mock_client.models.generate_content.side_effect = [
            Mock429("Rate limit 1"),
            Mock429("Rate limit 2"),
            Mock429("Rate limit 3"),
            Mock429("Rate limit 4"),
            mock_resp
        ]

        sleep_calls = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)), \
             patch.dict(os.environ, {"RETRY_BASE_DELAY": "2.0"}):
            res = data_builder.mutate_question(mock_client, {"title": "A", "description": "B"}, max_retries=5)
            self.assertEqual(res.mutated_title, "T")
            self.assertEqual(mock_client.models.generate_content.call_count, 5)
            self.assertEqual(sleep_calls, [2.0, 4.0, 8.0, 16.0])

    def test_gemini_429_exhaustion_terminates_at_max_retries(self):
        """Hypothesis 2.2: Continuous 429s must terminate after max_retries and raise, no hang/infinite loop."""
        class Mock429(Exception):
            code = 429

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Mock429("Always 429")

        sleep_calls = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            with self.assertRaises(Mock429):
                data_builder.mutate_question(mock_client, {"title": "X"}, max_retries=4)

            self.assertEqual(mock_client.models.generate_content.call_count, 4)
            # Sleep called 3 times: attempts 0, 1, 2
            self.assertEqual(len(sleep_calls), 3)

    def test_gemini_non_429_client_errors_fail_fast(self):
        """Hypothesis 2.3: Non-429 client errors (400, 401, 403, 404, 500) must fail fast with zero retries."""
        error_scenarios = [
            (400, "INVALID_ARGUMENT", "Bad Request"),
            (401, "UNAUTHENTICATED", "Invalid API Key"),
            (403, "PERMISSION_DENIED", "Forbidden"),
            (404, "NOT_FOUND", "Model not found"),
            (500, "INTERNAL", "Internal Server Error"),
        ]

        for code, status, msg in error_scenarios:
            with self.subTest(code=code, status=status):
                class CustomErr(Exception):
                    pass
                err = CustomErr(f"{code} {msg}")
                err.code = code
                err.status = status

                mock_client = MagicMock()
                mock_client.models.generate_content.side_effect = err

                with patch("time.sleep") as mock_sleep:
                    with self.assertRaises(CustomErr):
                        data_builder.mutate_question(mock_client, {"title": "Y"}, max_retries=5)

                    self.assertEqual(mock_client.models.generate_content.call_count, 1,
                                     f"Error code {code} should fail fast without retry")
                    mock_sleep.assert_not_called()

    def test_gemini_markdown_code_fence_json_stripping(self):
        """Hypothesis 2.6: Model output wrapped in ```json ... ``` code fences should parse cleanly."""
        raw_json = '{\n  "mutated_title": "Clean Title",\n  "mutated_description": "Clean Desc",\n  "mutated_solution": "x = 1",\n  "variable_mapping": {"a": "x"},\n  "explanation": "Exp"\n}'
        fenced_text = f"```json\n{raw_json}\n```"

        mock_resp = MagicMock()
        mock_resp.parsed = None
        mock_resp.text = fenced_text

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp

        res = data_builder.mutate_question(mock_client, {"title": "Q"}, max_retries=3)
        self.assertEqual(res.mutated_title, "Clean Title")
        self.assertEqual(res.variable_mapping, {"a": "x"})


    # =========================================================================
    # VECTOR 3: MongoDB Bulk Loading & Duplicate Prevention
    # =========================================================================

    def test_bulk_insert_all_empty_and_partial_empty_lists(self):
        """Hypothesis 3.1: Bulk insert with all empty lists or subset empty lists returns counts safely."""
        # 1. All empty
        counts1 = data_builder.bulk_insert_documents(self.db, [], [], [])
        self.assertEqual(counts1, {"moderate": 0, "hard": 0, "solutions": 0})

        # 2. Only moderate non-empty
        m_doc = CodingQuestionDoc(skill="Py", index=0, title="T", description="D").model_dump()
        counts2 = data_builder.bulk_insert_documents(self.db, [m_doc], [], [])
        self.assertEqual(counts2, {"moderate": 1, "hard": 0, "solutions": 0})

        # 3. Only hard non-empty
        h_doc = CodingQuestionDoc(skill="Py", index=0, title="H", description="D").model_dump()
        counts3 = data_builder.bulk_insert_documents(self.db, [], [h_doc], [])
        self.assertEqual(counts3, {"moderate": 0, "hard": 1, "solutions": 0})

    def test_bulk_insert_duplicate_key_bulk_write_error_handling(self):
        """Hypothesis 3.2: Verify BulkWriteError is caught and successful inserts are counted."""
        # Create unique index on (skill, index) on questions_moderate
        self.db.questions_moderate.create_index([("skill", 1), ("index", 1)], unique=True)

        doc1 = CodingQuestionDoc(skill="Py", index=0, title="T0", description="D0").model_dump()
        doc2 = CodingQuestionDoc(skill="Py", index=1, title="T1", description="D1").model_dump()
        doc_dup = CodingQuestionDoc(skill="Py", index=0, title="T0_dup", description="D0_dup").model_dump()

        # Batch 1: insert 0 and 1
        c1 = data_builder.bulk_insert_documents(self.db, [doc1, doc2], [], [])
        self.assertEqual(c1["moderate"], 2)

        # Batch 2: insert duplicate (0) along with a new one (2)
        doc3 = CodingQuestionDoc(skill="Py", index=2, title="T2", description="D2").model_dump()
        # insert_many with ordered=False: doc_dup fails, doc3 succeeds
        c2 = data_builder.bulk_insert_documents(self.db, [doc_dup, doc3], [], [])
        self.assertEqual(c2["moderate"], 1, "Only doc3 should be inserted when doc_dup conflicts")
        self.assertEqual(self.db.questions_moderate.count_documents({"skill": "Py"}), 3)

    def test_pipeline_sequential_index_continuation_without_clear(self):
        """Hypothesis 3.3: Without clear flag, pipeline detects existing max index and increments sequentially."""
        # Pre-populate DB with existing 3 questions for Python (indices 0, 1, 2)
        for i in range(3):
            self.db.questions_moderate.insert_one(
                CodingQuestionDoc(skill="Python", index=i, title=f"Existing {i}", description="Desc").model_dump()
            )
            self.db.solutions.insert_one(
                SolutionDoc(skill="Python", index=i, difficulty="moderate", reference_solution="pass").model_dump()
            )

        csv_content = (
            "skill,difficulty,title,description,reference_solution\n"
            "Python,moderate,New Q1,Desc 1,pass\n"
            "Python,moderate,New Q2,Desc 2,pass\n"
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        try:
            totals = data_builder.run_pipeline(csv_path=tmp_path, db=self.db, clear=False, mock_llm=True)
            self.assertEqual(totals["moderate"], 2)
            all_py = self.db.questions_moderate.find({"skill": "Python"})
            self.assertEqual(len(all_py), 5)
            indices = sorted([d["index"] for d in all_py])
            self.assertEqual(indices, [0, 1, 2, 3, 4], "Indices must continue sequentially without collisions")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_pipeline_clear_flag_scoping_to_csv_skills_only(self):
        """Hypothesis 3.4: clear=True only clears skills present in the CSV, preserving other skills."""
        # Pre-populate DB with Python and Java
        self.db.questions_moderate.insert_one(CodingQuestionDoc(skill="Java", index=0, title="Java 0", description="D").model_dump())
        self.db.questions_moderate.insert_one(CodingQuestionDoc(skill="Python", index=0, title="Py 0", description="D").model_dump())

        csv_content = (
            "skill,difficulty,title,description,reference_solution\n"
            "Python,moderate,New Py,Desc,pass\n"
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        try:
            totals = data_builder.run_pipeline(csv_path=tmp_path, db=self.db, clear=True, mock_llm=True)
            self.assertEqual(totals["moderate"], 1)

            # Java must NOT have been deleted
            java_doc = self.db.questions_moderate.find_one({"skill": "Java"})
            self.assertIsNotNone(java_doc, "Java document must remain untouched when only Python is cleared")

            # Python old was cleared, new was added with index 0
            py_docs = self.db.questions_moderate.find({"skill": "Python"})
            self.assertEqual(len(py_docs), 1)
            self.assertEqual(py_docs[0]["title"], "Mutated: New Py")
            self.assertEqual(py_docs[0]["index"], 0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
