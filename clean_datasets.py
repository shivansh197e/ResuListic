"""Clean heterogeneous raw datasets (CSV and IPYNB) across 5 target directories.

Generates cleaned_dataset.csv in each directory with exact schema:
title, description, solution, skill, difficulty
Strict invariant: zero null, NaN, or empty values in title and solution.
"""

import csv
import json
import os
import re
import sys
from typing import Dict, List, Optional

FIELDNAMES = ["title", "description", "solution", "skill", "difficulty"]

FOLDER_SKILL_MAP = {
    "Data Structure Questions": "Data Structures",
    "Datascience questions": "Data Science",
    "mix skill questions": "Software Engineering",
    "OOPS questions": "OOPS",
    "System design Question": "System Design",
}

# Expand CSV field size limit for large multi-line code/HTML blocks
csv.field_size_limit(min(sys.maxsize, 2147483647))


def is_valid_text(val: Optional[str]) -> bool:
    if val is None:
        return False
    s = str(val).strip()
    return bool(s) and s.lower() not in ("nan", "null", "none", "n/a", "[]")


def clean_markdown_text(text: str) -> str:
    # Strip base64 embedded images
    text = re.sub(r"!\[.*?\]\(data:image\/[^)]+\)", "", text)
    # Strip markdown headers and bold asterisks for clean text
    lines = [re.sub(r"^[#*\s]+|[#*\s]+$", "", line).strip() for line in text.split("\n")]
    return "\n".join([line for line in lines if line])


def parse_csv_file(file_path: str, default_skill: str) -> List[Dict[str, str]]:
    rows = []
    # Try utf-8-sig, fallback to latin-1
    encoding = "utf-8-sig"
    try:
        with open(file_path, "r", encoding=encoding, errors="replace", newline="") as f:
            header_line = f.readline()
            f.seek(0)
            delimiter = ";" if (";" in header_line and "," not in header_line) else ("\t" if ("\t" in header_line and "," not in header_line) else ",")
            reader = csv.DictReader(f, delimiter=delimiter)
            for raw_row in reader:
                # Column alias extraction
                title = (
                    raw_row.get("title")
                    or raw_row.get("Question")
                    or raw_row.get("name")
                    or ""
                ).strip()
                desc = (
                    raw_row.get("description")
                    or raw_row.get("Question")
                    or title
                    or ""
                ).strip()
                sol = (
                    raw_row.get("solution")
                    or raw_row.get("solution_code_python")
                    or raw_row.get("Answer")
                    or raw_row.get("reference_solution")
                    or ""
                ).strip()
                diff = (
                    raw_row.get("difficulty")
                    or raw_row.get("difficulty_level")
                    or raw_row.get("Difficulty")
                    or "Medium"
                ).strip()

                if not is_valid_text(title) or not is_valid_text(sol):
                    continue

                rows.append({
                    "title": title,
                    "description": desc,
                    "solution": sol,
                    "skill": default_skill,
                    "difficulty": diff if diff else "Medium",
                })
    except Exception as exc:
        print(f"[clean_datasets] Warning: error reading {file_path}: {exc}", file=sys.stderr)
    return rows


def parse_ipynb_file(file_path: str, default_skill: str) -> List[Dict[str, str]]:
    rows = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            nb = json.load(f)

        pending_title = ""
        pending_desc: List[str] = []

        for cell in nb.get("cells", []):
            cell_type = cell.get("cell_type")
            src_raw = cell.get("source", [])
            src = "".join(src_raw) if isinstance(src_raw, list) else str(src_raw)
            cleaned_src = clean_markdown_text(src)

            if cell_type == "markdown":
                if cleaned_src:
                    first_line = cleaned_src.split("\n")[0].strip()
                    if any(kw in first_line.lower() for kw in ("problem", "class", "encapsulation", "inheritance", "polymorphism", "abstraction")):
                        pending_title = first_line
                    elif not pending_title:
                        pending_title = first_line
                    pending_desc.append(cleaned_src)
            elif cell_type == "code":
                code = src.strip()
                # Keep substantive code containing class or function definitions
                if ("class " in code or "def " in code) and len(code.split("\n")) >= 2:
                    # Filter out short driver code snippets
                    if code.startswith("class ") or "\nclass " in code or "def " in code:
                        title = pending_title or f"{default_skill} Concept"
                        desc = "\n\n".join(pending_desc) if pending_desc else title
                        if is_valid_text(title) and is_valid_text(code):
                            rows.append({
                                "title": title,
                                "description": desc,
                                "solution": code,
                                "skill": default_skill,
                                "difficulty": "Medium",
                            })
                        pending_title = ""
                        pending_desc = []
    except Exception as exc:
        print(f"[clean_datasets] Warning: error reading notebook {file_path}: {exc}", file=sys.stderr)
    return rows


def clean_directory(dir_path: str, base_dir: str = "datasets") -> Dict[str, int]:
    folder_name = os.path.basename(os.path.normpath(dir_path))
    default_skill = FOLDER_SKILL_MAP.get(folder_name, "General")
    target_csv = os.path.join(dir_path, "cleaned_dataset.csv")

    collected_rows: List[Dict[str, str]] = []

    # Preserve existing rows if target_csv exists and no other raw sources present
    existing_rows: List[Dict[str, str]] = []
    if os.path.exists(target_csv):
        try:
            with open(target_csv, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    if is_valid_text(r.get("title")) and is_valid_text(r.get("solution")):
                        existing_rows.append({k: (r.get(k) or "").strip() for k in FIELDNAMES})
        except Exception:
            pass

    for fname in sorted(os.listdir(dir_path)):
        full_path = os.path.join(dir_path, fname)
        if fname == "cleaned_dataset.csv" or os.path.isdir(full_path):
            continue

        if fname.lower().endswith(".csv"):
            parsed = parse_csv_file(full_path, default_skill)
            collected_rows.extend(parsed)
        elif fname.lower().endswith(".ipynb"):
            parsed = parse_ipynb_file(full_path, default_skill)
            collected_rows.extend(parsed)

    # If no raw files produced rows, keep valid existing rows (e.g. from scraper)
    if not collected_rows and existing_rows:
        collected_rows = existing_rows

    # Deduplicate by title
    seen_titles = set()
    deduped_rows: List[Dict[str, str]] = []
    for r in collected_rows:
        t_key = r["title"].strip().lower()
        if t_key not in seen_titles:
            seen_titles.add(t_key)
            deduped_rows.append(r)

    # Write cleaned_dataset.csv
    with open(target_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for r in deduped_rows:
            writer.writerow(r)

    return {
        "folder": folder_name,
        "written": len(deduped_rows),
        "target": target_csv,
    }


def clean_all_datasets(base_dir: str = "datasets") -> List[Dict[str, int]]:
    results = []
    for folder_name in FOLDER_SKILL_MAP:
        dir_path = os.path.join(base_dir, folder_name)
        os.makedirs(dir_path, exist_ok=True)
        res = clean_directory(dir_path, base_dir)
        results.append(res)
    return results


def main() -> None:
    base_dir = "datasets"
    if not os.path.exists(base_dir):
        # Fallback if executed from subfolder
        if os.path.exists(os.path.join("..", base_dir)):
            base_dir = os.path.join("..", base_dir)

    results = clean_all_datasets(base_dir)
    print("=" * 60)
    print("Heterogeneous Datasets Cleaning Summary:")
    print("=" * 60)
    for res in results:
        print(f"  [{res['folder']}] Written: {res['written']} rows -> {res['target']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
