"""Clean raw LeetCode dataset for ResuListic ETL pipeline.

Transforms datasets/leetcode_problems.csv into datasets/cleaned_leetcode.csv:
- Exact 5 columns: title, description, solution, skill, difficulty
- Solution sourced strictly from solution_code_python
- Rows with missing/empty Python solutions are dropped
- Skill extracted from primary topic in topics list (defaulting to 'Python')
"""

import argparse
import ast
import csv
import os
import re
import sys

FIELDNAMES = ["title", "description", "solution", "skill", "difficulty"]


def extract_skill(raw_topics: str) -> tuple[str, bool]:
    """Safely extracts primary topic as a clean string.

    Returns (skill, was_defaulted).
    """
    if not raw_topics or not raw_topics.strip():
        return "Python", True

    s = raw_topics.strip()
    if s.lower() in ("[]", "none", "nan", "null") or re.sub(r"\s+", "", s) == "[]":
        return "Python", True

    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            if not parsed or all(not str(item).strip() for item in parsed):
                return "Python", True
            for item in parsed:
                # If item is an empty list/tuple/dict, it has no valid topic
                if isinstance(item, (list, tuple, dict)) and not item:
                    continue
                clean = str(item).strip()
                if clean and clean.lower() not in ("none", "nan", "null", "[]"):
                    return clean, False
            return "Python", True
    except (ValueError, SyntaxError):
        pass

    # Fallback strip for malformed list strings
    clean = s.strip("[]'\" ").split(",")[0].strip("[]'\" ")
    if clean and clean.lower() not in ("none", "nan", "null"):
        return clean, False

    return "Python", True


def clean_leetcode(
    input_path: str = "datasets/leetcode_problems.csv",
    output_path: str = "datasets/cleaned_leetcode.csv",
) -> dict[str, int]:
    """Streams and cleans raw LeetCode dataset into ETL-ready CSV.

    Returns metrics dict with total_read, total_written, dropped_no_solution, defaulted_skill.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input dataset not found: {input_path}")

    # Ensure parent output directory exists
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Increase CSV field size limit for large multi-line code/HTML fields
    csv.field_size_limit(min(sys.maxsize, 2147483647))

    total_read = 0
    total_written = 0
    dropped_no_solution = 0
    defaulted_skill = 0

    with open(input_path, mode="r", encoding="utf-8-sig", errors="replace", newline="") as fin, \
         open(output_path, mode="w", encoding="utf-8", newline="") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=FIELDNAMES, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()

        for row in reader:
            total_read += 1
            sol = (row.get("solution_code_python") or "").strip()
            if not sol:
                dropped_no_solution += 1
                continue

            skill, is_default = extract_skill(row.get("topics") or "")
            if is_default:
                defaulted_skill += 1

            writer.writerow({
                "title": (row.get("title") or "").strip(),
                "description": row.get("description") or "",
                "solution": sol,
                "skill": skill,
                "difficulty": (row.get("difficulty") or "").strip(),
            })
            total_written += 1

    return {
        "total_read": total_read,
        "total_written": total_written,
        "kept": total_written,
        "dropped": dropped_no_solution,
        "dropped_no_solution": dropped_no_solution,
        "defaulted_skill": defaulted_skill,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean raw LeetCode dataset for ResuListic ETL pipeline.")
    parser.add_argument("--input", default="datasets/leetcode_problems.csv", help="Path to raw input CSV")
    parser.add_argument("--output", default="datasets/cleaned_leetcode.csv", help="Path to cleaned output CSV")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    args = parser.parse_args()

    try:
        metrics = clean_leetcode(args.input, args.output)
        if not args.quiet:
            print(
                f"[clean_leetcode] Success! Read: {metrics['total_read']}, "
                f"Written: {metrics['total_written']}, Dropped: {metrics['dropped_no_solution']}, "
                f"Defaulted skill: {metrics['defaulted_skill']} -> {args.output}"
            )
        sys.exit(0)
    except Exception as exc:
        print(f"[clean_leetcode] Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
