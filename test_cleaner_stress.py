"""Independent Adversarial Stress Test Suite for Heterogeneous Cleaner and Schema Invariants.

Authored by: challenger_pipe_1
Objective: Empirically challenge clean_datasets.py and verify schema invariants across all 5 directories.
"""

import csv
import json
import os
import shutil
import sys
import tempfile
import traceback
from typing import Dict, List

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clean_datasets import (
    FIELDNAMES,
    FOLDER_SKILL_MAP,
    clean_all_datasets,
    clean_directory,
    clean_markdown_text,
    is_valid_text,
    parse_csv_file,
    parse_ipynb_file,
)

TARGET_FOLDERS = [
    "Data Structure Questions",
    "Datascience questions",
    "mix skill questions",
    "OOPS questions",
    "System design Question",
]


def test_schema_invariants_across_all_5_directories() -> Dict[str, int]:
    """Test 1: Mathematical schema invariant assertion on existing 5 cleaned_dataset.csv files."""
    print("\n" + "=" * 70)
    print(" [CHALLENGER TEST 1] Validating Invariants Across All 5 Datasets")
    print("=" * 70)

    # Allow large fields
    csv.field_size_limit(min(sys.maxsize, 2147483647))

    summary = {}
    for folder in TARGET_FOLDERS:
        path = os.path.join("datasets", folder, "cleaned_dataset.csv")
        print(f"  Validating: {path} ...")
        assert os.path.exists(path), f"FAIL: {path} does not exist!"
        assert os.path.getsize(path) > 0, f"FAIL: {path} is 0 bytes!"

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            assert header == FIELDNAMES, f"FAIL in {folder}: Header {header} != {FIELDNAMES}"

            row_count = 0
            for line_idx, row in enumerate(reader, start=2):
                row_count += 1
                # Invariant: exactly 5 columns
                assert len(row) == 5, (
                    f"FAIL in {folder} line {line_idx}: expected 5 columns, got {len(row)}: {row}"
                )

                title, desc, sol, skill, diff = row

                # Invariant: title non-empty, non-null
                assert title is not None, f"FAIL in {folder} line {line_idx}: title is None"
                t_str = title.strip()
                assert len(t_str) > 0, f"FAIL in {folder} line {line_idx}: empty title string"
                assert t_str.lower() not in ("nan", "null", "none", "n/a", "[]"), (
                    f"FAIL in {folder} line {line_idx}: null-like title: {t_str}"
                )

                # Invariant: solution non-empty, non-null
                assert sol is not None, f"FAIL in {folder} line {line_idx}: sol is None"
                s_str = sol.strip()
                assert len(s_str) > 0, f"FAIL in {folder} line {line_idx}: empty solution string"
                assert s_str.lower() not in ("nan", "null", "none", "n/a", "[]"), (
                    f"FAIL in {folder} line {line_idx}: null-like solution: {s_str}"
                )

                # Invariant: skill matches folder mapping
                expected_skill = FOLDER_SKILL_MAP[folder]
                assert skill == expected_skill, (
                    f"FAIL in {folder} line {line_idx}: skill '{skill}' != '{expected_skill}'"
                )

                # Invariant: difficulty non-empty
                assert len(diff.strip()) > 0, f"FAIL in {folder} line {line_idx}: empty difficulty"

            assert row_count > 0, f"FAIL: {folder} has 0 rows!"
            summary[folder] = row_count
            print(f"    -> OK: {row_count} rows passed all strict schema checks.")

    # Validate with pandas if available
    try:
        import pandas as pd
        for folder in TARGET_FOLDERS:
            path = os.path.join("datasets", folder, "cleaned_dataset.csv")
            df = pd.read_csv(path, keep_default_na=False)
            assert list(df.columns) == FIELDNAMES, f"Pandas columns mismatch in {folder}"
            assert df.isna().sum().sum() == 0, f"Pandas found NaNs in {folder}"
            assert (df["title"].str.strip() == "").sum() == 0, f"Pandas found empty titles in {folder}"
            assert (df["solution"].str.strip() == "").sum() == 0, f"Pandas found empty solutions in {folder}"
            assert not df["title"].str.lower().isin(["nan", "null", "none", "n/a"]).any()
            assert not df["solution"].str.lower().isin(["nan", "null", "none", "n/a"]).any()
        print("  -> Pandas verified: 0 NaNs, 0 empty titles/solutions across all files.")
    except ImportError:
        pass

    return summary


def test_idempotency() -> None:
    """Test 2: Assert clean_all_datasets() is strictly idempotent across multiple runs."""
    print("\n" + "=" * 70)
    print(" [CHALLENGER TEST 2] Asserting Idempotency Over Successive Runs")
    print("=" * 70)

    # 1. Snapshot initial content
    initial_snapshots = {}
    for folder in TARGET_FOLDERS:
        path = os.path.join("datasets", folder, "cleaned_dataset.csv")
        with open(path, "r", encoding="utf-8") as f:
            initial_snapshots[folder] = f.read()

    # 2. Run cleaner pass 1
    print("  Executing clean_all_datasets() pass 1...")
    clean_all_datasets("datasets")

    # Verify pass 1 matches snapshot
    for folder in TARGET_FOLDERS:
        path = os.path.join("datasets", folder, "cleaned_dataset.csv")
        with open(path, "r", encoding="utf-8") as f:
            content_pass_1 = f.read()
        assert content_pass_1 == initial_snapshots[folder], (
            f"Idempotency violation in {folder} after pass 1! Content diverged."
        )

    # 3. Run cleaner pass 2
    print("  Executing clean_all_datasets() pass 2...")
    clean_all_datasets("datasets")

    # Verify pass 2 matches snapshot
    for folder in TARGET_FOLDERS:
        path = os.path.join("datasets", folder, "cleaned_dataset.csv")
        with open(path, "r", encoding="utf-8") as f:
            content_pass_2 = f.read()
        assert content_pass_2 == initial_snapshots[folder], (
            f"Idempotency violation in {folder} after pass 2! Content diverged."
        )

    print("  -> PASSED: All 5 files are byte-for-byte identical across repeated cleaner executions.")


def test_delimiter_and_quoting_resilience() -> None:
    """Test 3: Stress-test parse_csv_file on weird delimiters, broken quoting, large text, BOM."""
    print("\n" + "=" * 70)
    print(" [CHALLENGER TEST 3] Stress Testing CSV Delimiters, Quoting & Dirty Data")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Case 1: Semicolon delimiter with embedded quotes and newlines
        semicolon_csv = os.path.join(tmpdir, "semicolon.csv")
        with open(semicolon_csv, "w", encoding="utf-8", newline="") as f:
            f.write('title;description;solution;difficulty\n')
            f.write('"Two Sum";"Find two numbers that add up to target";"def two_sum():\n    return [0, 1]";"Easy"\n')
            f.write('"Dirty Semi";"Has ; inside \"\"quotes\"\"";"print(\"hello; world\")";"Medium"\n')

        res = parse_csv_file(semicolon_csv, "TestSkill")
        assert len(res) >= 1, f"Expected at least 1 valid row from semicolon CSV, got {len(res)}"
        assert res[0]["title"] == "Two Sum"
        print("  -> Semicolon delimited parsing passed.")

        # Case 1b: Semicolon with RFC 4180 escaped double quotes
        rfc_csv = os.path.join(tmpdir, "rfc.csv")
        with open(rfc_csv, "w", encoding="utf-8", newline="") as f:
            f.write('title;description;solution;difficulty\n')
            f.write('"RFC Test";"Description with ; inside";"print(""hello; world"")";"Medium"\n')
        res_rfc = parse_csv_file(rfc_csv, "TestSkill")
        assert len(res_rfc) == 1
        assert res_rfc[0]["title"] == "RFC Test"
        assert 'print("hello; world")' == res_rfc[0]["solution"]
        print("  -> RFC 4180 doubled quotes with embedded semicolons passed.")

        # Case 2: Tab delimiter
        tab_csv = os.path.join(tmpdir, "tabs.csv")
        with open(tab_csv, "w", encoding="utf-8", newline="") as f:
            f.write("Question\tAnswer\n")
            f.write("What is Overfitting?\tOverfitting happens when a model learns noise.\n")
            f.write("What is Regularization?\tL1 and L2 penalty terms.\n")

        res_tab = parse_csv_file(tab_csv, "Data Science")
        assert len(res_tab) == 2, f"Expected 2 rows from tab CSV, got {len(res_tab)}"
        assert res_tab[0]["title"] == "What is Overfitting?"
        assert res_tab[0]["solution"] == "Overfitting happens when a model learns noise."
        assert res_tab[0]["skill"] == "Data Science"
        print("  -> Tab delimited parsing passed.")

        # Case 3: Column Aliases (name, reference_solution, difficulty_level)
        alias_csv = os.path.join(tmpdir, "aliases.csv")
        with open(alias_csv, "w", encoding="utf-8", newline="") as f:
            f.write("name,reference_solution,difficulty_level\n")
            f.write("LRU Cache,class LRUCache: pass,Hard\n")

        res_alias = parse_csv_file(alias_csv, "System Design")
        assert len(res_alias) == 1, f"Expected 1 row, got {len(res_alias)}"
        assert res_alias[0]["title"] == "LRU Cache"
        assert res_alias[0]["solution"] == "class LRUCache: pass"
        assert res_alias[0]["difficulty"] == "Hard"
        print("  -> Column alias mapping passed.")

        # Case 4: UTF-8 BOM encoding
        bom_csv = os.path.join(tmpdir, "bom.csv")
        with open(bom_csv, "w", encoding="utf-8-sig", newline="") as f:
            f.write("title,solution\n")
            f.write("BOM Title,def bom_solution(): return True\n")

        res_bom = parse_csv_file(bom_csv, "General")
        assert len(res_bom) == 1, f"Expected 1 row from BOM CSV, got {len(res_bom)}"
        assert res_bom[0]["title"] == "BOM Title"
        print("  -> UTF-8 BOM encoding passed.")

        # Case 5: Non-UTF8 Latin-1 high bytes (replaced without crashing)
        latin_csv = os.path.join(tmpdir, "latin.csv")
        with open(latin_csv, "wb") as f:
            # write raw bytes with 0xe9 (e-acute in latin-1)
            content = b"title,solution\nCaf\xe9 Problem,def solve(): return 'caf\xe9'\n"
            f.write(content)

        res_latin = parse_csv_file(latin_csv, "General")
        assert len(res_latin) == 1
        assert "Caf" in res_latin[0]["title"]
        print("  -> Latin-1 fallback/replace decoding passed.")

        # Case 6: Dirty data filtering (null, NaN, empty, whitespace)
        dirty_csv = os.path.join(tmpdir, "dirty.csv")
        with open(dirty_csv, "w", encoding="utf-8", newline="") as f:
            f.write("title,description,solution\n")
            f.write("Valid Title,Desc,Valid Solution\n")
            f.write(",Desc,Missing Title\n")                       # empty title
            f.write("Missing Sol,Desc,\n")                         # empty sol
            f.write("NaN,Desc,Valid Solution\n")                   # NaN title
            f.write("Valid Title 2,Desc,NaN\n")                    # NaN sol
            f.write("null,Desc,Valid Solution\n")                  # null title
            f.write("Valid Title 3,Desc,null\n")                   # null sol
            f.write("None,Desc,Valid Solution\n")                  # None title
            f.write("Valid Title 4,Desc,None\n")                   # None sol
            f.write("N/A,Desc,Valid Solution\n")                   # N/A title
            f.write("   ,Desc,Valid Solution\n")                   # whitespace title
            f.write("Valid Title 5,Desc,   \n")                    # whitespace sol

        res_dirty = parse_csv_file(dirty_csv, "General")
        assert len(res_dirty) == 1, f"Expected strictly 1 valid row, got {len(res_dirty)}"
        assert res_dirty[0]["title"] == "Valid Title"
        print("  -> Dirty/null/empty/NaN record dropping passed.")

        # Case 7: Huge field size (500 KB solution string)
        huge_csv = os.path.join(tmpdir, "huge.csv")
        huge_sol = "print('x')\n" * 50000
        with open(huge_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["title", "solution"])
            writer.writeheader()
            writer.writerow({"title": "Huge Problem", "solution": huge_sol})

        res_huge = parse_csv_file(huge_csv, "General")
        assert len(res_huge) == 1, "Failed to parse huge field size"
        assert res_huge[0]["solution"] == huge_sol.strip()
        print("  -> Huge field size (500KB) handling passed.")

        # Case 8: 0-byte file and empty file
        empty_csv = os.path.join(tmpdir, "empty.csv")
        open(empty_csv, "w").close()
        res_empty = parse_csv_file(empty_csv, "General")
        assert len(res_empty) == 0, "Expected 0 rows for empty file"
        print("  -> 0-byte CSV file handled gracefully.")


def test_notebook_parsing_resilience() -> None:
    """Test 4: Adversarial stress test for parse_ipynb_file."""
    print("\n" + "=" * 70)
    print(" [CHALLENGER TEST 4] Stress Testing Jupyter Notebook Parsing")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Case 1: Corrupted / invalid JSON
        bad_json = os.path.join(tmpdir, "corrupt.ipynb")
        with open(bad_json, "w", encoding="utf-8") as f:
            f.write("{ invalid json [ [")
        res_bad = parse_ipynb_file(bad_json, "OOPS")
        assert len(res_bad) == 0, "Corrupt JSON should return empty list without crash"
        print("  -> Corrupted JSON handled gracefully.")

        # Case 2: Empty JSON
        empty_json = os.path.join(tmpdir, "empty.ipynb")
        with open(empty_json, "w", encoding="utf-8") as f:
            f.write("{}")
        res_empty = parse_ipynb_file(empty_json, "OOPS")
        assert len(res_empty) == 0
        print("  -> Empty JSON {} handled gracefully.")

        # Case 3: Notebook with base64 embedded images, single-line snippets, classes
        valid_nb_path = os.path.join(tmpdir, "valid.ipynb")
        nb_data = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": [
                        "# Problem: Animal Hierarchy\n",
                        "![img](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=)\n",
                        "Define an abstract Animal class with sound method.\n",
                    ],
                },
                {
                    "cell_type": "code",
                    "source": [
                        "class Animal:\n",
                        "    def make_sound(self):\n",
                        "        raise NotImplementedError()\n",
                    ],
                },
                {
                    "cell_type": "markdown",
                    "source": ["## Test Driver Code\n"],
                },
                {
                    "cell_type": "code",
                    "source": ["a = Animal()\n"],  # single-line snippet: should be ignored
                },
                {
                    "cell_type": "code",
                    "source": "def helper_calc(x, y):\n    return x + y\n",  # string source
                },
            ]
        }
        with open(valid_nb_path, "w", encoding="utf-8") as f:
            json.dump(nb_data, f)

        res_nb = parse_ipynb_file(valid_nb_path, "OOPS")
        assert len(res_nb) == 2, f"Expected 2 classes/functions extracted, got {len(res_nb)}"
        # Check image was stripped
        assert "data:image/png;base64" not in res_nb[0]["description"]
        assert "Animal Hierarchy" in res_nb[0]["title"]
        assert "class Animal" in res_nb[0]["solution"]
        assert "helper_calc" in res_nb[1]["solution"]
        print("  -> Notebook with base64 images and string source handled correctly.")

        # Case 4: Malformed cell structures (missing cell_type, missing source)
        malformed_nb_path = os.path.join(tmpdir, "malformed_cells.ipynb")
        malformed_data = {
            "cells": [
                {"foo": "bar"},
                {"cell_type": "unknown", "source": ["hello"]},
                {"cell_type": "code"},  # missing source
                {"cell_type": "code", "source": None},  # None source
            ]
        }
        with open(malformed_nb_path, "w", encoding="utf-8") as f:
            json.dump(malformed_data, f)

        res_malformed = parse_ipynb_file(malformed_nb_path, "OOPS")
        assert len(res_malformed) == 0
        print("  -> Notebook with missing/malformed cell keys handled safely.")


def test_helper_functions_edge_cases() -> None:
    """Test 5: Edge cases on is_valid_text and clean_markdown_text."""
    print("\n" + "=" * 70)
    print(" [CHALLENGER TEST 5] Testing Helper Functions Edge Cases")
    print("=" * 70)

    # is_valid_text
    invalid_cases = [None, "", "   ", "\t\n\r", "nan", "NaN", "NAN", "null", "Null", "NULL", "none", "None", "n/a", "N/A", "[]"]
    for case in invalid_cases:
        assert not is_valid_text(case), f"Expected is_valid_text({case!r}) to be False"

    valid_cases = ["0", "False", "class NoneClass:", "def null_check():", "NaN_constant = 123", "[1, 2, 3]", "Valid text"]
    for case in valid_cases:
        assert is_valid_text(case), f"Expected is_valid_text({case!r}) to be True"
    print("  -> is_valid_text boundary cases verified.")

    # clean_markdown_text
    sample_md = "# Title Header\n![img](data:image/jpeg;base64,12345)\n**Bold Description**\n* List item\n"
    cleaned = clean_markdown_text(sample_md)
    assert "data:image/jpeg;base64" not in cleaned
    assert "Title Header" in cleaned
    assert "Bold Description" in cleaned
    print("  -> clean_markdown_text sanitization verified.")


def test_multilingual_and_directory_isolation() -> None:
    """Test 6: Multilingual unicode preservation, jagged CSV lines, and directory isolation."""
    print("\n" + "=" * 70)
    print(" [CHALLENGER TEST 6] Multilingual Symbols, Jagged CSVs & Directory Isolation")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Unicode & Math symbols
        unicode_csv = os.path.join(tmpdir, "unicode.csv")
        with open(unicode_csv, "w", encoding="utf-8", newline="") as f:
            f.write("title,description,solution,difficulty\n")
            f.write('"二分探索 (Binary Search)";"数学: ∀ x ∈ ℝ, θ, λ, α 🚀";"def search(nums): return θ";"Hard"\n'.replace(";", ","))

        res_uni = parse_csv_file(unicode_csv, "Math")
        assert len(res_uni) == 1
        assert "二分探索" in res_uni[0]["title"]
        assert "∀ x ∈ ℝ" in res_uni[0]["description"]
        assert "🚀" in res_uni[0]["description"]
        assert "θ" in res_uni[0]["solution"]
        print("  -> Unicode and mathematical symbols preserved cleanly.")

        # 2. Jagged / Corrupted line CSV (doesn't crash)
        jagged_csv = os.path.join(tmpdir, "jagged.csv")
        with open(jagged_csv, "w", encoding="utf-8", newline="") as f:
            f.write("title,description,solution\n")
            f.write("Valid 1,Desc 1,Sol 1\n")
            f.write("OnlyOneCol\n")
            f.write("Col1,Col2,Col3,Col4,Col5,Col6,Col7\n")
            f.write("Valid 2,Desc 2,Sol 2\n")

        res_jagged = parse_csv_file(jagged_csv, "Test")
        assert len(res_jagged) >= 2
        assert res_jagged[0]["title"] == "Valid 1"
        assert res_jagged[-1]["title"] == "Valid 2"
        print("  -> Jagged rows parsed safely without crash.")

        # 3. Directory isolation test: clean_directory ignores subdirs and non-csv/ipynb
        test_dir = os.path.join(tmpdir, "Data Structure Questions")
        os.makedirs(test_dir, exist_ok=True)
        # Create subfolder that shouldn't be read
        os.makedirs(os.path.join(test_dir, "nested_dir"), exist_ok=True)
        with open(os.path.join(test_dir, "nested_dir", "nested.csv"), "w") as f:
            f.write("title,solution\nNested,NestedSol\n")
        # Create non-csv file
        with open(os.path.join(test_dir, "notes.txt"), "w") as f:
            f.write("Some notes\n")
        # Create valid CSV
        with open(os.path.join(test_dir, "data.csv"), "w", encoding="utf-8") as f:
            f.write("title,solution\nValid Problem,def solve(): pass\n")

        summary = clean_directory(test_dir, tmpdir)
        assert summary["written"] == 1
        out_csv = os.path.join(test_dir, "cleaned_dataset.csv")
        assert os.path.exists(out_csv)
        with open(out_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["title"] == "Valid Problem"
        assert rows[0]["skill"] == "Data Structures"
        print("  -> Directory isolation (skipping subdirs, notes.txt, correct skill) verified.")


def main():
    print("*" * 70)
    print(" CHALLENGER_PIPE_1 INDEPENDENT ADVERSARIAL STRESS TEST HARNESS")
    print("*" * 70)

    try:
        counts = test_schema_invariants_across_all_5_directories()
        test_idempotency()
        test_delimiter_and_quoting_resilience()
        test_notebook_parsing_resilience()
        test_helper_functions_edge_cases()
        test_multilingual_and_directory_isolation()

        print("\n" + "*" * 70)
        print(" ALL EMPIRICAL CHALLENGER TESTS PASSED (100% SUCCESS)")
        print(f" Datasets Verified: {len(counts)} folders, {sum(counts.values())} rows")
        print("*" * 70)
        sys.exit(0)
    except AssertionError as ae:
        print(f"\n[FAIL] Empirical Challenge failed assertion: {ae}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] Empirical Challenge encountered exception: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
