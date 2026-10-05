"""
test_clean_leetcode_adversarial.py — Empirical Adversarial Stress Suite for clean_leetcode.py.
Authored by Challenger 1 (teamwork_preview_challenger_clean_1).

Tests 5 Adversarial Vectors:
1. Skill Extraction Oracle & Topic Parsing (unusual quotes, commas, unicode, whitespace, escapes)
2. Pathological & Malformed Topic Inputs (nested brackets, non-list collections, pseudo-nulls)
3. CSV Streaming Edge Cases (0-byte, header-only, ragged rows, BOM, missing columns)
4. Multi-line Code & Field Escaping Integrity (RFC-4180 quotes, 2GB field size limit)
5. Cleaned Dataset Invariant Verification (zero null solutions, exact 5 columns, clean skills)
"""

import ast
import csv
import io
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import clean_leetcode
from clean_leetcode import clean_leetcode as run_cleaner, extract_skill, FIELDNAMES


def independent_skill_oracle(raw_topics: str) -> str:
    """Independent reference oracle for skill extraction."""
    if not raw_topics or not raw_topics.strip():
        return "Python"

    s = raw_topics.strip()
    if s.lower() in ("[]", "none", "nan", "null"):
        return "Python"

    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, (list, tuple, set)):
            items = list(parsed)
            if not items:
                return "Python"
            first = items[0]
            # Recursively unwrap nested lists
            while isinstance(first, (list, tuple, set)) and len(first) > 0:
                first = list(first)[0]
            if first and str(first).strip():
                clean_str = str(first).strip()
                if clean_str.lower() in ("none", "nan", "null", ""):
                    return "Python"
                return clean_str
    except (ValueError, SyntaxError):
        pass

    # Fallback parsing
    clean = s.strip("[](){}'\" ").split(",")[0].strip("[](){}'\" ")
    if clean and clean.lower() not in ("none", "nan", "null", ""):
        return clean

    return "Python"


class TestSkillExtractionAdversarial(unittest.TestCase):
    """Stress tests for extract_skill() against synthetic pathological inputs."""

    def test_standard_formats(self):
        cases = [
            ("['Array', 'Hash Table']", "Array"),
            ('["Dynamic Programming", "Math"]', "Dynamic Programming"),
            ("['Binary Search']", "Binary Search"),
            ("['Two Pointers', 'String']", "Two Pointers"),
        ]
        for inp, expected in cases:
            skill, defaulted = extract_skill(inp)
            self.assertEqual(skill, expected)
            self.assertFalse(defaulted)

    def test_empty_and_null_defaults(self):
        null_cases = [
            "",
            "   ",
            "\n\t",
            "[]",
            "[  ]",
            "None",
            "none",
            "nan",
            "null",
            "['']",
            "['   ']",
        ]
        for inp in null_cases:
            skill, defaulted = extract_skill(inp)
            self.assertEqual(skill, "Python", f"Failed on input: {inp!r}")
            self.assertTrue(defaulted, f"Expected defaulted=True for: {inp!r}")

    def test_unicode_and_special_characters(self):
        cases = [
            ("['グラフ理論', '動的計画法']", "グラフ理論"),  # Japanese (Graph Theory)
            ("['Trie (Prefix 树)']", "Trie (Prefix 树)"),    # Chinese + Latin
            ("['Café & Algorithms']", "Café & Algorithms"),  # Accented chars
            ("['C++']", "C++"),                             # Programming language symbol
            ("['C#']", "C#"),                               # Hash symbol
            ("['Euler\\'s Totient']", "Euler's Totient"),    # Escaped apostrophe
        ]
        for inp, expected in cases:
            skill, defaulted = extract_skill(inp)
            self.assertEqual(skill, expected)
            self.assertFalse(defaulted)

    def test_topic_with_embedded_commas(self):
        # Topic name itself contains a comma inside quotes
        inp = "['Divide and Conquer, Recursion', 'Math']"
        skill, defaulted = extract_skill(inp)
        self.assertEqual(skill, "Divide and Conquer, Recursion")
        self.assertFalse(defaulted)

    def test_unquoted_and_malformed_string_fallback(self):
        # Malformed list missing quotes
        inp = "[Array, Math]"
        skill, _ = extract_skill(inp)
        self.assertEqual(skill, "Array")

        # Comma-separated string without brackets
        inp2 = "Math, Dynamic Programming"
        skill2, _ = extract_skill(inp2)
        self.assertEqual(skill2, "Math")


class TestPipelineStreamingAdversarial(unittest.TestCase):
    """Stress tests for clean_leetcode() streaming and error resilience."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_empty_zero_byte_file(self):
        in_path = os.path.join(self.temp_dir.name, "empty.csv")
        out_path = os.path.join(self.temp_dir.name, "out_empty.csv")
        with open(in_path, "w", encoding="utf-8") as f:
            pass

        metrics = run_cleaner(in_path, out_path)
        self.assertEqual(metrics["total_read"], 0)
        self.assertEqual(metrics["total_written"], 0)

        with open(out_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
            self.assertEqual(headers, FIELDNAMES)

    def test_header_only_file(self):
        in_path = os.path.join(self.temp_dir.name, "header_only.csv")
        out_path = os.path.join(self.temp_dir.name, "out_header.csv")
        with open(in_path, "w", encoding="utf-8") as f:
            f.write("difficulty,title,solution_code_python,topics,description\n")

        metrics = run_cleaner(in_path, out_path)
        self.assertEqual(metrics["total_read"], 0)
        self.assertEqual(metrics["total_written"], 0)

    def test_utf8_bom_handling(self):
        in_path = os.path.join(self.temp_dir.name, "bom.csv")
        out_path = os.path.join(self.temp_dir.name, "out_bom.csv")
        with open(in_path, "w", encoding="utf-8-sig") as f:
            f.write("difficulty,title,solution_code_python,topics,description\n")
            f.write("Easy,Two Sum,print(1),['Array'],Desc\n")

        metrics = run_cleaner(in_path, out_path)
        self.assertEqual(metrics["total_written"], 1)

        with open(out_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "Two Sum")
            self.assertEqual(rows[0]["difficulty"], "Easy")

    def test_ragged_rows_missing_columns(self):
        in_path = os.path.join(self.temp_dir.name, "ragged.csv")
        out_path = os.path.join(self.temp_dir.name, "out_ragged.csv")
        with open(in_path, "w", encoding="utf-8") as f:
            # Header has 3 columns, but row only has 1
            f.write("title,solution_code_python,topics\n")
            f.write("Only Title\n")  # Missing solution_code_python -> None
            f.write("Valid,def solve(): pass,['Math']\n")

        metrics = run_cleaner(in_path, out_path)
        self.assertEqual(metrics["total_read"], 2)
        self.assertEqual(metrics["total_written"], 1)
        self.assertEqual(metrics["dropped_no_solution"], 1)

    def test_multiline_solution_with_quotes(self):
        in_path = os.path.join(self.temp_dir.name, "multiline.csv")
        out_path = os.path.join(self.temp_dir.name, "out_multiline.csv")

        complex_solution = (
            'class Solution:\n'
            '    """Docstring with "quotes" and \'single quotes\'"""\n'
            '    def solve(self, s: str):\n'
            '        # comment with comma, and newline\n'
            '        return "done"\n'
        )

        with open(in_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["title", "description", "solution_code_python", "topics", "difficulty"])
            writer.writeheader()
            writer.writerow({
                "title": "Complex Quotes",
                "description": "<p>Description with <code>quotes</code></p>",
                "solution_code_python": complex_solution,
                "topics": "['String']",
                "difficulty": "Medium",
            })

        metrics = run_cleaner(in_path, out_path)
        self.assertEqual(metrics["total_written"], 1)

        with open(out_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["solution"], complex_solution.strip())
            self.assertEqual(rows[0]["skill"], "String")


class TestProductionDatasetIntegrity(unittest.TestCase):
    """Assertions on the actual generated cleaned dataset."""

    CLEANED_PATH = "datasets/cleaned_leetcode.csv"

    def test_file_exists_and_exact_five_columns(self):
        self.assertTrue(os.path.exists(self.CLEANED_PATH), "Cleaned dataset does not exist")
        with open(self.CLEANED_PATH, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            headers = next(reader)
            self.assertEqual(headers, ["title", "description", "solution", "skill", "difficulty"])

    def test_solution_never_empty_and_skill_never_bracketed(self):
        csv.field_size_limit(min(sys.maxsize, 2147483647))
        with open(self.CLEANED_PATH, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            count = 0
            python_count = 0
            for r in reader:
                count += 1
                sol = r["solution"]
                skill = r["skill"]
                self.assertTrue(sol and sol.strip(), f"Empty solution on row {count}: {r['title']}")
                self.assertFalse(skill.startswith("[") or skill.endswith("]"), f"Bracketed skill on row {count}: {skill}")
                if skill == "Python":
                    python_count += 1

            self.assertEqual(count, 840, f"Expected 840 rows, got {count}")
            self.assertEqual(python_count, 2, f"Expected exactly 2 fallback rows, got {python_count}")


if __name__ == "__main__":
    unittest.main()
