"""Master Pipeline Verification Suite.

Executes all pipeline modules end-to-end and validates:
1. Module 1: Heterogeneous dataset cleaner across all 5 directories.
2. Module 2: Streaming PDF extractor mock unit test (LLM extraction + 429 retry)
   and O(1) memory profiling assertion (< 12MB peak).
3. Module 3: Stealth Playwright web scraper live integration test (>= 5 questions).
4. Mathematical Schema Contract:
   - Exactly 5 columns (title, description, solution, skill, difficulty)
   - Zero null, NaN, or empty values in title and solution across ALL 5 CSVs.
   - Every directory has >= 1 validated Q&A records.
"""

import asyncio
import csv
import os
import sys
from typing import Dict, List

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clean_datasets import FIELDNAMES, FOLDER_SKILL_MAP, clean_all_datasets
from pdf_extractor import test_mock_pdf_extraction_and_retry, test_streaming_memory_footprint
from scraper import test_live_scraping

EXPECTED_COLUMNS = ["title", "description", "solution", "skill", "difficulty"]
TARGET_FOLDERS = [
    "Data Structure Questions",
    "Datascience questions",
    "mix skill questions",
    "OOPS questions",
    "System design Question",
]


def run_stage_1_cleaner() -> List[Dict[str, int]]:
    """Stage 1: Execute heterogeneous dataset cleaner across 5 directories."""
    print("=" * 70)
    print(" [STAGE 1] Executing Heterogeneous Data Cleaner (clean_datasets.py)...")
    print("=" * 70)
    results = clean_all_datasets("datasets")
    for r in results:
        print(f"  -> {r['folder']}: {r['written']} rows written to {r['target']}")
    return results


def run_stage_2_pdf_tests() -> None:
    """Stage 2: Run PDF unit test with 429 retry and streaming memory profiling."""
    print("\n" + "=" * 70)
    print(" [STAGE 2] Executing PDF Extractor Unit Test & Memory Profiler...")
    print("=" * 70)
    # Unit test with mocked LLM and 429 retry
    test_mock_pdf_extraction_and_retry()

    # O(1) Memory footprint test on 17.5MB PDF
    pdf_path = os.path.join("datasets", "Datascience questions", "1632827939589.pdf")
    if os.path.exists(pdf_path):
        peak_mb = test_streaming_memory_footprint(pdf_path, max_peak_mb=12.0)
        print(f"  -> Peak streaming RAM verified: {peak_mb:.2f} MB (< 12.0 MB threshold)")
    else:
        print(f"  -> Notice: {pdf_path} not found, checking alternative PDFs...")
        for alt in os.listdir(os.path.join("datasets", "Datascience questions")):
            if alt.endswith(".pdf"):
                alt_path = os.path.join("datasets", "Datascience questions", alt)
                test_streaming_memory_footprint(alt_path, max_peak_mb=12.0)
                break


def run_stage_3_scraper() -> None:
    """Stage 3: Run live Playwright scraper integration test (>= 5 questions)."""
    print("\n" + "=" * 70)
    print(" [STAGE 3] Executing Playwright Stealth Scraper Live Integration Test...")
    print("=" * 70)
    sys_design_csv = os.path.join("datasets", "System design Question", "cleaned_dataset.csv")
    scraped = asyncio.run(test_live_scraping(target_csv=sys_design_csv, min_questions=5))
    print(f"  -> Live scraper scraped {len(scraped)} questions successfully without block.")


def run_stage_4_mathematical_assertions() -> Dict[str, int]:
    """Stage 4: Mathematical schema validation across all 5 cleaned_dataset.csv files."""
    print("\n" + "=" * 70)
    print(" [STAGE 4] Mathematical Schema Contract & Zero-Null Assertions...")
    print("=" * 70)

    # Increase CSV limit
    csv.field_size_limit(min(sys.maxsize, 2147483647))

    summary_counts: Dict[str, int] = {}

    for folder in TARGET_FOLDERS:
        csv_path = os.path.join("datasets", folder, "cleaned_dataset.csv")
        print(f"  Checking '{folder}' -> {csv_path}...")

        # 1. Existence and non-empty file
        assert os.path.exists(csv_path), f"CRITICAL: {csv_path} does not exist!"
        file_size = os.path.getsize(csv_path)
        assert file_size > 0, f"CRITICAL: {csv_path} is empty (0 bytes)!"

        # 2. Schema headers
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == EXPECTED_COLUMNS, (
                f"Column mismatch in {folder}: expected {EXPECTED_COLUMNS}, got {reader.fieldnames}"
            )
            assert len(reader.fieldnames) == 5, f"Expected exactly 5 columns, got {len(reader.fieldnames)}"

            rows = list(reader)

        # 3. Non-empty row count
        assert len(rows) >= 1, f"CRITICAL: {folder}/cleaned_dataset.csv has 0 rows!"

        # 4. Invariant: Strictly zero NaN, null, or empty strings in title and solution
        for idx, row in enumerate(rows, start=1):
            title = row.get("title")
            sol = row.get("solution")
            skill = row.get("skill")
            diff = row.get("difficulty")

            # Validate title
            assert title is not None, f"Row {idx} in {folder} has None title"
            title_str = title.strip()
            assert len(title_str) > 0, f"Row {idx} in {folder} has empty title"
            assert title_str.lower() not in ("nan", "null", "none"), (
                f"Row {idx} in {folder} has null-like title: '{title_str}'"
            )

            # Validate solution
            assert sol is not None, f"Row {idx} in {folder} has None solution"
            sol_str = sol.strip()
            assert len(sol_str) > 0, f"Row {idx} in {folder} has empty solution"
            assert sol_str.lower() not in ("nan", "null", "none"), (
                f"Row {idx} in {folder} has null-like solution: '{sol_str}'"
            )

            # Validate skill
            assert skill is not None and len(skill.strip()) > 0, f"Row {idx} in {folder} has empty skill"
            assert not skill.strip().startswith("[") and not skill.strip().endswith("]"), (
                f"Row {idx} in {folder} has stringified list skill: '{skill}'"
            )

            # Validate difficulty
            assert diff is not None and len(diff.strip()) > 0, f"Row {idx} in {folder} has empty difficulty"

        summary_counts[folder] = len(rows)
        print(f"    PASSED: {len(rows)} rows mathematically verified. 0 nulls, 0 empty strings.")

    # 5. Pandas verification if available
    try:
        import pandas as pd
        for folder in TARGET_FOLDERS:
            p_csv = os.path.join("datasets", folder, "cleaned_dataset.csv")
            df = pd.read_csv(p_csv, keep_default_na=False)
            assert list(df.columns) == EXPECTED_COLUMNS
            assert (df["title"] == "").sum() == 0, f"Pandas found empty titles in {folder}"
            assert (df["solution"] == "").sum() == 0, f"Pandas found empty solutions in {folder}"
            assert not df["title"].str.lower().isin(["nan", "null", "none"]).any()
            assert not df["solution"].str.lower().isin(["nan", "null", "none"]).any()
        print("  Pandas verification across all 5 datasets: 100% clean, 0 NaNs.")
    except ImportError:
        pass

    return summary_counts


def main() -> None:
    print("*" * 70)
    print(" RESULISTIC DATA ENGINEERING PIPELINE MASTER VERIFIER")
    print("*" * 70)

    try:
        run_stage_1_cleaner()
        run_stage_2_pdf_tests()
        run_stage_3_scraper()
        counts = run_stage_4_mathematical_assertions()

        print("\n" + "*" * 70)
        print(" PIPELINE VERIFICATION SUMMARY:")
        for folder, cnt in counts.items():
            print(f"   - {folder:30s} : {cnt:6d} verified rows")
        print("*" * 70)
        print(" ALL ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY (EXIT 0)")
        print("*" * 70)
        sys.exit(0)
    except AssertionError as ae:
        print(f"\n[FAIL] Assertion failed: {ae}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] Pipeline verification encountered an unexpected error: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
