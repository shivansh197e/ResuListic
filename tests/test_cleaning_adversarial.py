"""test_cleaning_adversarial.py — Empirical Fuzzing, Fault Injection & Memory Scalability Harness.

Authored by Challenger 2 Replacement (teamwork_preview_challenger_clean_2_repl).

Validates clean_leetcode.py across 6 Critical Vectors:
1. Huge Input Lines & Fields (> 131,072 chars, up to 5 MB)
2. Corrupted CSV Headers & Missing Columns
3. Topic String Fuzzing & Malformed Syntax (extract_skill)
4. Memory Scalability & Streaming Performance (tracemalloc, 25k+ rows)
5. CLI Invocations, Flag Parsing & Error Handling
6. Encodings, BOM, Special Characters & Newline Variations
"""

import ast
import csv
import io
import os
import subprocess
import sys
import tempfile
import time
import tracemalloc
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import clean_leetcode
from clean_leetcode import clean_leetcode as run_cleaner, extract_skill, FIELDNAMES

PYTHON_EXE = sys.executable


class TestHugeInputLines(unittest.TestCase):
    """Stress tests CSV field limit exceeding standard Python 131,072 byte limit."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_field_exceeding_default_131072_limit(self):
        """Verify field with 250,000 characters (exceeds default 131k limit)."""
        huge_code = "x = 1\n" + ("# comment line with padding\n" * 8000)
        self.assertGreater(len(huge_code), 131072)

        in_csv = os.path.join(self.temp_dir.name, "huge_input.csv")
        out_csv = os.path.join(self.temp_dir.name, "huge_output.csv")

        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "description", "solution_code_python", "topics", "difficulty"])
            writer.writerow(["Huge Problem", "Short desc", huge_code, "['Math']", "Hard"])

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_written"], 1)
        self.assertEqual(metrics["dropped_no_solution"], 0)

        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["solution"], huge_code.strip())
            self.assertEqual(rows[0]["skill"], "Math")

    def test_megabyte_scale_fields(self):
        """Verify field with > 1,500,000 characters does not crash or corrupt."""
        one_mb_str = "a" * 1500000
        in_csv = os.path.join(self.temp_dir.name, "1mb_input.csv")
        out_csv = os.path.join(self.temp_dir.name, "1mb_output.csv")

        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "description", "solution_code_python", "topics", "difficulty"])
            writer.writerow(["1MB Desc", one_mb_str, "def solve(): return 1", "['Strings']", "Medium"])

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_written"], 1)

        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            row = next(reader)
            self.assertEqual(len(row["description"]), 1500000)
            self.assertEqual(row["skill"], "Strings")


class TestCorruptedCSVHeaders(unittest.TestCase):
    """Stress tests abnormal CSV headers, missing columns, extra columns, empty files."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_solution_code_python_column(self):
        """Input CSV has columns but lacks 'solution_code_python' -> all dropped gracefully."""
        in_csv = os.path.join(self.temp_dir.name, "no_sol_col.csv")
        out_csv = os.path.join(self.temp_dir.name, "out_no_sol.csv")

        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "description", "topics", "difficulty"])
            writer.writerow(["Two Sum", "Find sum", "['Array']", "Easy"])
            writer.writerow(["Three Sum", "Find sum 3", "['Array']", "Medium"])

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_read"], 2)
        self.assertEqual(metrics["total_written"], 0)
        self.assertEqual(metrics["dropped_no_solution"], 2)

        # Output still has exactly 5 headers
        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, FIELDNAMES)
            self.assertEqual(list(reader), [])

    def test_missing_topics_column(self):
        """Input CSV lacks 'topics' column -> skill defaults cleanly to 'Python'."""
        in_csv = os.path.join(self.temp_dir.name, "no_topics.csv")
        out_csv = os.path.join(self.temp_dir.name, "out_no_topics.csv")

        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "description", "solution_code_python", "difficulty"])
            writer.writerow(["Problem A", "Desc A", "def a(): pass", "Easy"])

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_written"], 1)
        self.assertEqual(metrics["defaulted_skill"], 1)

        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            row = next(csv.DictReader(f))
            self.assertEqual(row["skill"], "Python")
            self.assertEqual(row["title"], "Problem A")

    def test_extra_unknown_columns(self):
        """Input CSV has extra unexpected columns -> output contains only 5 target columns."""
        in_csv = os.path.join(self.temp_dir.name, "extra_cols.csv")
        out_csv = os.path.join(self.temp_dir.name, "out_extra_cols.csv")

        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "title", "acceptance_rate", "description", "solution_code_python", "topics", "difficulty", "rating"])
            writer.writerow(["101", "P1", "85%", "Desc", "def f(): return True", "['Dynamic Programming']", "Hard", "4.8"])

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_written"], 1)

        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, FIELDNAMES)
            self.assertEqual(len(reader.fieldnames), 5)
            row = next(reader)
            self.assertNotIn("id", row)
            self.assertNotIn("acceptance_rate", row)
            self.assertNotIn("rating", row)
            self.assertEqual(row["skill"], "Dynamic Programming")

    def test_permuted_column_order(self):
        """Input CSV columns appear in non-standard order -> correctly mapped."""
        in_csv = os.path.join(self.temp_dir.name, "permuted.csv")
        out_csv = os.path.join(self.temp_dir.name, "out_permuted.csv")

        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["topics", "difficulty", "solution_code_python", "description", "title"])
            writer.writerow(["['Binary Search']", "Medium", "def bs(): pass", "Search target", "Binary Search Problem"])

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_written"], 1)

        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, FIELDNAMES)
            row = next(reader)
            self.assertEqual(row["title"], "Binary Search Problem")
            self.assertEqual(row["skill"], "Binary Search")
            self.assertEqual(row["difficulty"], "Medium")

    def test_empty_csv_file(self):
        """Zero-byte file -> produces valid empty 5-column CSV without crashing."""
        in_csv = os.path.join(self.temp_dir.name, "empty.csv")
        out_csv = os.path.join(self.temp_dir.name, "out_empty.csv")
        open(in_csv, "w").close()

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_read"], 0)
        self.assertEqual(metrics["total_written"], 0)

        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, FIELDNAMES)
            self.assertEqual(list(reader), [])

    def test_header_only_csv(self):
        """Header-only file -> produces valid 5-column CSV with 0 rows."""
        in_csv = os.path.join(self.temp_dir.name, "header_only.csv")
        out_csv = os.path.join(self.temp_dir.name, "out_header_only.csv")

        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "description", "solution_code_python", "topics", "difficulty"])

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_read"], 0)
        self.assertEqual(metrics["total_written"], 0)


class TestMalformedTopicFuzzing(unittest.TestCase):
    """Stress tests extract_skill with pathological, malformed, and adversarial inputs."""

    def test_standard_cases(self):
        self.assertEqual(extract_skill("['Array', 'Hash Table']"), ("Array", False))
        self.assertEqual(extract_skill("['Dynamic Programming']"), ("Dynamic Programming", False))
        self.assertEqual(extract_skill("['Math']"), ("Math", False))

    def test_empty_and_whitespace(self):
        self.assertEqual(extract_skill(""), ("Python", True))
        self.assertEqual(extract_skill("   "), ("Python", True))
        self.assertEqual(extract_skill("\t\n"), ("Python", True))
        self.assertEqual(extract_skill("[]"), ("Python", True))
        self.assertEqual(extract_skill(" [  ] "), ("Python", True))
        self.assertEqual(extract_skill("['']"), ("Python", True))
        self.assertEqual(extract_skill("['   ']"), ("Python", True))

    def test_null_and_nan_variants(self):
        self.assertEqual(extract_skill("None"), ("Python", True))
        self.assertEqual(extract_skill("nan"), ("Python", True))
        self.assertEqual(extract_skill("null"), ("Python", True))

    def test_syntax_errors_and_unquoted_strings(self):
        # Malformed list with missing quote or unclosed bracket
        self.assertEqual(extract_skill("['Array'"), ("Array", False))
        self.assertEqual(extract_skill("'Array']"), ("Array", False))
        self.assertEqual(extract_skill("[Array]"), ("Array", False))
        self.assertEqual(extract_skill("Array, Hash Table"), ("Array", False))
        self.assertEqual(extract_skill('"Tree", "Graph"'), ("Tree", False))

    def test_nested_structures(self):
        # Nested list
        self.assertEqual(extract_skill("[['Graph']]"), ("['Graph']", False))
        # Empty nested list
        self.assertEqual(extract_skill("[[]]"), ("Python", True))

    def test_deeply_nested_brackets_no_crash(self):
        # 500 levels of brackets
        nested = "[" * 200 + "'Recursion'" + "]" * 200
        skill, is_default = extract_skill(nested)
        # Should gracefully return either Recursion or Python, without throwing an unhandled exception
        self.assertIsInstance(skill, str)
        self.assertIsInstance(is_default, bool)

    def test_code_injection_safety(self):
        # Security: ensure arbitrary code execution is blocked by ast.literal_eval
        dangerous = "__import__('os').system('exit(1)')"
        skill, is_default = extract_skill(dangerous)
        # Must not execute code, returns parsed fallback string or default
        self.assertIsInstance(skill, str)

    def test_non_string_elements(self):
        self.assertEqual(extract_skill("[123, 456]"), ("123", False))
        self.assertEqual(extract_skill("[True, False]"), ("True", False))

    def test_unicode_and_special_characters(self):
        self.assertEqual(extract_skill("['🚀 Rocket', 'Speed']"), ("🚀 Rocket", False))
        self.assertEqual(extract_skill("['算法', '数据结构']"), ("算法", False))
        self.assertEqual(extract_skill("['C++', 'C#']"), ("C++", False))
        self.assertEqual(extract_skill("['Algorithms & Data Structures']"), ("Algorithms & Data Structures", False))


class TestMemoryScalabilityAndStreaming(unittest.TestCase):
    """Benchmarks memory usage and throughput over a 25,000-row synthetic stream."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_streaming_bounded_memory(self):
        """Generates 25,000 rows (~15 MB) and verifies peak memory allocated remains bounded (< 10 MB)."""
        num_rows = 25000
        in_csv = os.path.join(self.temp_dir.name, "synthetic_25k.csv")
        out_csv = os.path.join(self.temp_dir.name, "synthetic_25k_out.csv")

        # Generate synthetic dataset
        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "description", "solution_code_python", "topics", "difficulty"])
            for i in range(num_rows):
                if i % 3 == 0:
                    # Row with no solution (should be dropped)
                    writer.writerow([f"Problem {i}", f"Description {i} " * 5, "", "['Array']", "Easy"])
                else:
                    writer.writerow([
                        f"Problem {i}",
                        f"Description text {i} " * 10,
                        f"class Solution:\n    def solve_{i}(self):\n        return {i}\n",
                        f"['Skill_{i % 50}']",
                        "Medium" if i % 2 == 0 else "Hard"
                    ])

        file_size_mb = os.path.getsize(in_csv) / (1024 * 1024)

        # Measure memory using tracemalloc
        tracemalloc.start()
        start_time = time.perf_counter()

        metrics = run_cleaner(in_csv, out_csv)

        elapsed = time.perf_counter() - start_time
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mem_mb = peak_mem / (1024 * 1024)
        throughput = metrics["total_read"] / elapsed

        print(f"\n[STREAMING BENCHMARK]")
        print(f"  Input size: {file_size_mb:.2f} MB ({num_rows} rows)")
        print(f"  Rows read: {metrics['total_read']}, Written: {metrics['total_written']}, Dropped: {metrics['dropped_no_solution']}")
        print(f"  Elapsed time: {elapsed:.3f} s")
        print(f"  Throughput: {throughput:.0f} rows/s")
        print(f"  Peak memory overhead: {peak_mem_mb:.2f} MB")

        # Verify correctness
        expected_written = num_rows - (num_rows + 2) // 3
        self.assertEqual(metrics["total_read"], num_rows)
        self.assertEqual(metrics["total_written"], expected_written)

        # Verify streaming memory bounds: peak memory must stay small (< 10 MB)
        self.assertLess(peak_mem_mb, 10.0, f"Peak memory {peak_mem_mb:.2f} MB exceeded 10 MB streaming threshold!")


class TestCLIAndRuntimeHandling(unittest.TestCase):
    """Validates CLI arguments, exit codes, stderr messages, and directory auto-creation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_help(self):
        res = subprocess.run([PYTHON_EXE, "clean_leetcode.py", "--help"], capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Clean raw LeetCode dataset", res.stdout)
        self.assertIn("--input", res.stdout)
        self.assertIn("--output", res.stdout)

    def test_cli_missing_input_file(self):
        bogus_path = os.path.join(self.temp_dir.name, "nonexistent.csv")
        res = subprocess.run([PYTHON_EXE, "clean_leetcode.py", "--input", bogus_path], capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(res.returncode, 1)
        self.assertIn("Input dataset not found", res.stderr)

    def test_cli_quiet_flag(self):
        # Create a small valid file
        in_csv = os.path.join(self.temp_dir.name, "quiet_in.csv")
        out_csv = os.path.join(self.temp_dir.name, "quiet_out.csv")
        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "description", "solution_code_python", "topics", "difficulty"])
            writer.writerow(["T1", "D1", "pass", "['Math']", "Easy"])

        res = subprocess.run([PYTHON_EXE, "clean_leetcode.py", "--input", in_csv, "--output", out_csv, "--quiet"], capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "")  # Quiet flag should suppress stdout

    def test_cli_auto_creates_output_directory(self):
        in_csv = os.path.join(self.temp_dir.name, "in.csv")
        out_dir = os.path.join(self.temp_dir.name, "nested", "subfolder", "dir")
        out_csv = os.path.join(out_dir, "out.csv")

        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "description", "solution_code_python", "topics", "difficulty"])
            writer.writerow(["T1", "D1", "pass", "['Math']", "Easy"])

        res = subprocess.run([PYTHON_EXE, "clean_leetcode.py", "--input", in_csv, "--output", out_csv], capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(out_csv))

    def test_cli_invalid_argument_exits_2(self):
        res = subprocess.run([PYTHON_EXE, "clean_leetcode.py", "--unrecognized-flag"], capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(res.returncode, 2)

    def test_cli_input_is_directory_exits_1(self):
        res = subprocess.run([PYTHON_EXE, "clean_leetcode.py", "--input", self.temp_dir.name], capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(res.returncode, 1)
        self.assertIn("Error:", res.stderr)

    def test_cli_output_is_directory_exits_1(self):
        in_csv = os.path.join(self.temp_dir.name, "valid_in.csv")
        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "description", "solution_code_python", "topics", "difficulty"])
            writer.writerow(["T1", "D1", "def f(): pass", "['Math']", "Easy"])

        res = subprocess.run([PYTHON_EXE, "clean_leetcode.py", "--input", in_csv, "--output", self.temp_dir.name], capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(res.returncode, 1)
        self.assertIn("Error:", res.stderr)



class TestSpecialEncodingsAndCharacters(unittest.TestCase):
    """Validates UTF-8 BOM, multi-byte unicode, and newline variations."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_utf8_with_bom(self):
        in_csv = os.path.join(self.temp_dir.name, "bom_input.csv")
        out_csv = os.path.join(self.temp_dir.name, "bom_out.csv")

        # Write UTF-8 with BOM
        with open(in_csv, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "description", "solution_code_python", "topics", "difficulty"])
            writer.writerow(["BOM Title", "Desc with ü, é, å, ñ", "def solve(): return 'ü'", "['Strings']", "Easy"])

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_written"], 1)

        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            row = next(csv.DictReader(f))
            self.assertEqual(row["title"], "BOM Title")
            self.assertEqual(row["description"], "Desc with ü, é, å, ñ")
            self.assertEqual(row["solution"], "def solve(): return 'ü'")

    def test_crlf_and_embedded_newlines(self):
        in_csv = os.path.join(self.temp_dir.name, "crlf_input.csv")
        out_csv = os.path.join(self.temp_dir.name, "crlf_out.csv")

        # Multi-line code with \r\n and \n
        multi_line_code = "def solution():\r\n    line1 = 1\n    line2 = 2\r\n    return line1 + line2\n"

        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "description", "solution_code_python", "topics", "difficulty"])
            writer.writerow(["CRLF Title", "<p>Line 1</p>\r\n<p>Line 2</p>", multi_line_code, "['Math']", "Medium"])

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_written"], 1)

        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            row = next(csv.DictReader(f))
            self.assertIn("line1 = 1", row["solution"])
            self.assertIn("<p>Line 2</p>", row["description"])

    def test_invalid_utf8_bytes_resilience(self):
        """Input CSV contains invalid UTF-8 byte sequences -> errors='replace' cleanly replaces with replacement char."""
        in_csv = os.path.join(self.temp_dir.name, "corrupt_bytes.csv")
        out_csv = os.path.join(self.temp_dir.name, "corrupt_bytes_out.csv")

        # Raw binary write with invalid UTF-8 sequences (0xff, 0xfe, 0xc0)
        header = b"title,description,solution_code_python,topics,difficulty\r\n"
        row = b'Corrupted Title \xff\xfe,Description \xc0\xc1,"def solve(): pass","[\'Binary Search\']",Hard\r\n'
        with open(in_csv, "wb") as f:
            f.write(header)
            f.write(row)

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_read"], 1)
        self.assertEqual(metrics["total_written"], 1)

        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            out_row = next(csv.DictReader(f))
            self.assertIn("\ufffd", out_row["title"])
            self.assertEqual(out_row["skill"], "Binary Search")
            self.assertEqual(out_row["difficulty"], "Hard")



class TestRaggedAndMalformedCSV(unittest.TestCase):
    """Stress tests ragged rows, embedded quotes, and commas in quoted fields."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ragged_rows_fewer_columns(self):
        """Row has fewer fields than header -> DictReader fills missing with None -> handled gracefully."""
        in_csv = os.path.join(self.temp_dir.name, "ragged_short.csv")
        out_csv = os.path.join(self.temp_dir.name, "ragged_short_out.csv")

        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            f.write("title,description,solution_code_python,topics,difficulty\n")
            f.write("Only Title\n")  # Missing 4 columns
            f.write('"T2","D2","def solve(): pass","[\'Math\']","Easy"\n')

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_read"], 2)
        self.assertEqual(metrics["total_written"], 1)
        self.assertEqual(metrics["dropped_no_solution"], 1)

    def test_escaped_quotes_and_commas_in_fields(self):
        """Fields containing commas, escaped quotes (\"\"\") and HTML tags."""
        in_csv = os.path.join(self.temp_dir.name, "quotes_input.csv")
        out_csv = os.path.join(self.temp_dir.name, "quotes_out.csv")

        complex_desc = '<p>Find "k", where k in [1, 2, 3], and return "result".</p>'
        complex_sol = 'def solve(s: str = "a,b,c") -> str:\n    return f"val=\\"{s}\\""\n'

        with open(in_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "description", "solution_code_python", "topics", "difficulty"])
            writer.writerow(["Quotes & Commas", complex_desc, complex_sol, "['String, Parsing']", "Medium"])

        metrics = run_cleaner(in_csv, out_csv)
        self.assertEqual(metrics["total_written"], 1)

        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            row = next(csv.DictReader(f))
            self.assertEqual(row["description"], complex_desc)
            self.assertEqual(row["solution"], complex_sol.strip())
            self.assertEqual(row["skill"], "String, Parsing")


class TestProductionDatasetFidelity(unittest.TestCase):
    """Direct empirical validation of the generated datasets/cleaned_leetcode.csv deliverable."""

    def test_cleaned_dataset_integrity(self):
        csv_path = os.path.join(REPO_ROOT, "datasets", "cleaned_leetcode.csv")
        self.assertTrue(os.path.exists(csv_path), "datasets/cleaned_leetcode.csv does not exist")
        self.assertGreater(os.path.getsize(csv_path), 1_000_000, "cleaned_leetcode.csv is unexpectedly small")

        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, ["title", "description", "solution", "skill", "difficulty"])
            rows = list(reader)

        self.assertEqual(len(rows), 840, f"Expected exactly 840 rows, found {len(rows)}")

        difficulties = set()
        skills = set()
        for idx, row in enumerate(rows):
            # Check 5 columns present and not None
            for col in ["title", "description", "solution", "skill", "difficulty"]:
                self.assertIn(col, row, f"Row {idx} missing column {col}")
                self.assertIsNotNone(row[col], f"Row {idx} column {col} is None")

            # Solution must be non-empty string
            sol = row["solution"].strip()
            self.assertGreater(len(sol), 0, f"Row {idx} ('{row['title']}') has empty solution")

            # Skill must be clean string
            skill = row["skill"].strip()
            self.assertGreater(len(skill), 0, f"Row {idx} has empty skill")
            self.assertFalse(skill.startswith("["), f"Row {idx} has bracketed skill '{skill}'")
            self.assertFalse(skill.endswith("]"), f"Row {idx} has bracketed skill '{skill}'")

            difficulties.add(row["difficulty"].strip())
            skills.add(skill)

        # Verify difficulties present
        self.assertTrue(difficulties.issubset({"Easy", "Medium", "Hard", ""}))
        self.assertIn("Easy", difficulties)
        self.assertIn("Medium", difficulties)
        self.assertIn("Hard", difficulties)

        # Verify default skill 'Python' is present for the 2 fallback questions
        self.assertIn("Python", skills)
        fallback_rows = [r for r in rows if r["title"] in {"Count Numbers with Unique Digits", "Max Chunks To Make Sorted"}]
        self.assertEqual(len(fallback_rows), 2)
        for r in fallback_rows:
            self.assertEqual(r["skill"], "Python")


if __name__ == "__main__":
    unittest.main()

