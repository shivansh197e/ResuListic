"""Automated verification suite for LeetCode dataset cleaner.

Verifies all acceptance criteria from ORIGINAL_REQUEST.md:
1. Successfully runs cleaning script and generates datasets/cleaned_leetcode.csv
2. Asserts output CSV has exactly 5 columns: title, description, solution, skill, difficulty
3. Asserts zero NaN/null/empty values in the solution column
4. Asserts skill column contains clean strings (not stringified Python lists)
5. Validates row count (840), fallback rows ('Python'), and pandas compatibility
"""

import csv
import os
import subprocess
import sys

from clean_leetcode import clean_leetcode, FIELDNAMES

INPUT_FILE = "datasets/leetcode_problems.csv"
OUTPUT_FILE = "datasets/cleaned_leetcode.csv"
EXPECTED_COLUMNS = ["title", "description", "solution", "skill", "difficulty"]
EXPECTED_ROW_COUNT = 840
FALLBACK_TITLES = {"Count Numbers with Unique Digits", "Max Chunks To Make Sorted"}


def test_cleaner_execution() -> dict[str, int]:
    """Test 1: Run clean_leetcode programmatically and verify returned metrics."""
    print("[TEST 1] Running clean_leetcode()...")
    metrics = clean_leetcode(input_path=INPUT_FILE, output_path=OUTPUT_FILE)
    print(f"         Metrics: {metrics}")

    assert metrics["total_read"] == 3549, f"Expected 3549 total rows read, got {metrics['total_read']}"
    assert metrics["total_written"] == EXPECTED_ROW_COUNT, (
        f"Expected {EXPECTED_ROW_COUNT} rows written, got {metrics['total_written']}"
    )
    assert metrics["dropped_no_solution"] == 2709, (
        f"Expected 2709 dropped rows, got {metrics['dropped_no_solution']}"
    )
    assert metrics["defaulted_skill"] == 2, (
        f"Expected 2 rows with defaulted skill, got {metrics['defaulted_skill']}"
    )
    assert os.path.exists(OUTPUT_FILE), f"Output file not found at {OUTPUT_FILE}"
    assert os.path.getsize(OUTPUT_FILE) > 0, "Output file is empty"
    print("         PASSED: Cleaner execution & metrics verified.")
    return metrics


def test_schema_and_columns() -> list[dict[str, str]]:
    """Test 2: Verify exact 5 columns and RFC-4180 parsing."""
    print("[TEST 2] Verifying CSV schema and column structure...")
    csv.field_size_limit(min(sys.maxsize, 2147483647))

    with open(OUTPUT_FILE, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == EXPECTED_COLUMNS, (
            f"Expected columns {EXPECTED_COLUMNS}, got {reader.fieldnames}"
        )
        assert len(reader.fieldnames) == 5, f"Expected exactly 5 columns, got {len(reader.fieldnames)}"
        rows = list(reader)

    assert len(rows) == EXPECTED_ROW_COUNT, f"Expected {EXPECTED_ROW_COUNT} rows, got {len(rows)}"
    print(f"         PASSED: Exactly 5 columns present in correct order. Row count: {len(rows)}.")
    return rows


def test_solution_integrity(rows: list[dict[str, str]]) -> None:
    """Test 3: Assert zero NaN / null / empty values in solution column."""
    print("[TEST 3] Verifying solution integrity (0 null / empty / whitespace values)...")
    empty_solutions = []
    for idx, r in enumerate(rows, start=1):
        sol = r.get("solution")
        if sol is None or not sol.strip():
            empty_solutions.append((idx, r.get("title")))

    assert not empty_solutions, f"Found {len(empty_solutions)} rows with empty solution: {empty_solutions[:5]}"
    print("         PASSED: 100% of rows have non-empty Python solutions (0 null/empty).")


def test_skill_formatting(rows: list[dict[str, str]]) -> None:
    """Test 4: Assert skill column contains clean strings (no stringified list syntax)."""
    print("[TEST 4] Verifying skill formatting (clean strings, no stringified lists)...")
    invalid_skills = []
    for idx, r in enumerate(rows, start=1):
        skill = r.get("skill")
        if not skill or not skill.strip():
            invalid_skills.append((idx, r.get("title"), "Empty skill"))
        elif skill.strip().startswith("[") or skill.strip().endswith("]"):
            invalid_skills.append((idx, r.get("title"), f"Stringified list: {skill}"))
        elif skill.strip().startswith(("'", '"')):
            invalid_skills.append((idx, r.get("title"), f"Leading quotes: {skill}"))

    assert not invalid_skills, f"Found {len(invalid_skills)} invalid skill values: {invalid_skills[:5]}"

    # Verify fallback skill on rows with empty topics
    python_skills = [r for r in rows if r.get("skill") == "Python"]
    assert len(python_skills) == 2, f"Expected exactly 2 rows with skill 'Python', got {len(python_skills)}"
    for r in rows:
        if r.get("title") in FALLBACK_TITLES:
            assert r.get("skill") == "Python", (
                f"Row '{r.get('title')}' expected skill 'Python', got '{r.get('skill')}'"
            )
    print(f"         PASSED: All skills are clean plain strings. Exactly 2 fallback rows ('Python') verified.")


def test_pandas_compatibility() -> None:
    """Test 5: Load with pandas (if installed) to confirm zero NaN in solution."""
    print("[TEST 5] Verifying pandas interoperability...")
    try:
        import pandas as pd
        df = pd.read_csv(OUTPUT_FILE, keep_default_na=False)
        assert list(df.columns) == EXPECTED_COLUMNS, f"Pandas columns mismatch: {list(df.columns)}"
        assert len(df) == EXPECTED_ROW_COUNT, f"Pandas row count mismatch: {len(df)}"
        assert (df["solution"] == "").sum() == 0, "Pandas detected empty solution strings"
        assert not df["skill"].str.startswith("[").any(), "Pandas detected '[' in skill column"
        assert not df["skill"].str.endswith("]").any(), "Pandas detected ']' in skill column"
        print("         PASSED: Pandas read_csv validated with 0 errors.")
    except ImportError:
        print("         SKIPPED: pandas not installed in environment, skipping pandas check.")


def main() -> None:
    print("=" * 60)
    print(" ResuListic Dataset Cleaning Verification Suite")
    print("=" * 60)
    test_cleaner_execution()
    rows = test_schema_and_columns()
    test_solution_integrity(rows)
    test_skill_formatting(rows)
    test_pandas_compatibility()
    print("=" * 60)
    print(" ALL ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY (EXIT 0)")
    print("=" * 60)


if __name__ == "__main__":
    main()
