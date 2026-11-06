"""
verify_challenger2_ui.py — Empirical AST & Static Code Verification Suite for Challenger 2.
"""

import os
import sys
import glob
import json
import re

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def extract_button_tags(content: str):
    """
    Parses JSX/HTML to extract every opening <button ...> tag.
    Handles curly braces { ... } for JSX expressions (e.g. arrow functions () =>),
    and quotes ('...', "...", `...`).
    """
    buttons = []
    i = 0
    n = len(content)
    while i < n:
        if content[i:i+7].lower() == '<button' and (i + 7 == n or content[i+7] in ' \t\r\n>'):
            start = i
            i += 7
            in_quote = None
            brace_depth = 0
            while i < n:
                ch = content[i]
                if in_quote:
                    if ch == in_quote and (i == 0 or content[i-1] != '\\'):
                        in_quote = None
                elif ch in ('"', "'", '`'):
                    in_quote = ch
                elif ch == '{':
                    brace_depth += 1
                elif ch == '}':
                    brace_depth = max(0, brace_depth - 1)
                elif ch == '>' and brace_depth == 0 and in_quote is None:
                    buttons.append((start, i + 1, content[start:i+1]))
                    break
                i += 1
        else:
            i += 1
    return buttons


def check_buttons():
    print("=" * 80)
    print("CHECK 1: Universal rounded-full utility on all <button> elements")
    print("=" * 80)

    files = [os.path.join(PROJECT_ROOT, "static", "index.html")] + sorted(
        glob.glob(os.path.join(PROJECT_ROOT, "frontend", "src", "components", "*.jsx"))
    )

    total_buttons = 0
    passed_buttons = 0
    violations = []

    for fpath in files:
        rel_path = os.path.relpath(fpath, PROJECT_ROOT)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        btns = extract_button_tags(content)
        total_buttons += len(btns)
        print(f"File: {rel_path} ({len(btns)} buttons)")

        for start_pos, end_pos, tag in btns:
            line_no = content[:start_pos].count("\n") + 1
            has_rounded_full = "rounded-full" in tag
            cleaned_tag = " ".join(tag.split())
            if len(cleaned_tag) > 120:
                preview = cleaned_tag[:120] + "..."
            else:
                preview = cleaned_tag

            if has_rounded_full:
                passed_buttons += 1
                print(f"  [PASS] line {line_no:4d}: {preview}")
            else:
                violations.append({
                    "file": rel_path,
                    "line": line_no,
                    "tag": cleaned_tag
                })
                print(f"  [FAIL] line {line_no:4d}: MISSING rounded-full\n         Tag: {cleaned_tag}")

    print("-" * 80)
    print(f"Total buttons inspected: {total_buttons}")
    print(f"Buttons with rounded-full: {passed_buttons}")
    print(f"Buttons VIOLATING rounded-full: {len(violations)}")
    print("=" * 80 + "\n")
    return {
        "total": total_buttons,
        "passed": passed_buttons,
        "violations": violations,
        "success": len(violations) == 0,
    }


def check_emojis():
    print("=" * 80)
    print("CHECK 2: Zero emojis check (Unicode regex & HTML Entity check)")
    print("=" * 80)

    files = [os.path.join(PROJECT_ROOT, "static", "index.html")] + sorted(
        glob.glob(os.path.join(PROJECT_ROOT, "frontend", "src", "components", "*.jsx"))
    )

    emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u27ff]")
    entity_pattern = re.compile(r"&#(?:x1[0-9a-f]{4}|12[0-9]{4}|13[0-9]{4});", re.IGNORECASE)
    violations = []

    for fpath in files:
        rel_path = os.path.relpath(fpath, PROJECT_ROOT)
        with open(fpath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        file_emojis = 0
        for line_num, line in enumerate(lines, 1):
            matches = emoji_pattern.findall(line)
            entities = entity_pattern.findall(line)
            all_matches = matches + entities
            if all_matches:
                file_emojis += len(all_matches)
                violations.append({
                    "file": rel_path,
                    "line": line_num,
                    "emojis": all_matches,
                    "content": line.strip(),
                })
                print(
                    f"  [FAIL] {rel_path}:{line_num} -> Found {len(all_matches)} emoji(s): {all_matches} in line: {line.strip()[:80]}"
                )

        if file_emojis == 0:
            print(f"  [PASS] {rel_path} -> 0 emojis/entities found.")

    print("-" * 80)
    print(f"Total emoji violations: {len(violations)}")
    print("=" * 80 + "\n")
    return {
        "violations": violations,
        "success": len(violations) == 0,
    }


def check_invariant_5():
    print("=" * 80)
    print("CHECK 3: Invariant 5 (Mandatory Throw Guard on missing skill_breakdown)")
    print("=" * 80)

    target_files = [
        os.path.join(PROJECT_ROOT, "static", "index.html"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "ResultDashboard.jsx"),
    ]

    results = {}

    for fpath in target_files:
        rel_path = os.path.relpath(fpath, PROJECT_ROOT)
        if not os.path.exists(fpath):
            print(f"  [FAIL] File not found: {rel_path}")
            results[rel_path] = {"exists": False, "success": False}
            continue

        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        # Condition A: results?.skill_breakdown?.map does NOT exist in code or comments
        has_optional_chain = "results?.skill_breakdown?.map" in content

        # Condition B: throw statement `if (results && !results.skill_breakdown) throw new Error(...)` is present
        throw_regex = re.compile(
            r"if\s*\(\s*results\s*&&\s*!results\.skill_breakdown\s*\)\s*\{?\s*throw\s+new\s+Error\s*\(",
            re.DOTALL,
        )
        has_throw = bool(throw_regex.search(content))

        cond_a_pass = not has_optional_chain
        cond_b_pass = has_throw

        print(f"File: {rel_path}")
        print(f"  Condition A (NO results?.skill_breakdown?.map): {'PASS' if cond_a_pass else 'FAIL'}")
        if not cond_a_pass:
            print("    [VIOLATION] Found forbidden optional chaining 'results?.skill_breakdown?.map'!")
        print(f"  Condition B (Mandatory throw guard present): {'PASS' if cond_b_pass else 'FAIL'}")
        if not cond_b_pass:
            print("    [VIOLATION] Missing throw guard: if (results && !results.skill_breakdown) throw new Error(...)")

        results[rel_path] = {
            "exists": True,
            "no_optional_chaining": cond_a_pass,
            "has_throw_guard": cond_b_pass,
            "success": cond_a_pass and cond_b_pass,
        }

    overall_success = all(r.get("success", False) for r in results.values())
    print("-" * 80)
    print(f"Invariant 5 Result: {'PASS' if overall_success else 'FAIL'}")
    print("=" * 80 + "\n")
    return {
        "results": results,
        "success": overall_success,
    }


def check_invariant_6():
    print("=" * 80)
    print("CHECK 4: Invariant 6 (package.json explicit 'tailwindcss': '^3.4.19')")
    print("=" * 80)

    pkg_path = os.path.join(PROJECT_ROOT, "frontend", "package.json")
    rel_path = os.path.relpath(pkg_path, PROJECT_ROOT)

    if not os.path.exists(pkg_path):
        print(f"  [FAIL] {rel_path} does not exist!")
        return {"success": False, "error": "file missing"}

    with open(pkg_path, "r", encoding="utf-8") as f:
        pkg = json.load(f)

    deps = pkg.get("dependencies", {})
    dev_deps = pkg.get("devDependencies", {})

    dep_tw = deps.get("tailwindcss")
    dev_dep_tw = dev_deps.get("tailwindcss")

    print(f"  dependencies['tailwindcss']: {dep_tw}")
    print(f"  devDependencies['tailwindcss']: {dev_dep_tw}")

    is_valid = dep_tw == "^3.4.19" or dev_dep_tw == "^3.4.19"
    print(f"  Requirement ('tailwindcss': '^3.4.19'): {'PASS' if is_valid else 'FAIL'}")
    print("=" * 80 + "\n")
    return {
        "dep_tailwindcss": dep_tw,
        "dev_dep_tailwindcss": dev_dep_tw,
        "success": is_valid,
    }


def check_invariants_1_2_3():
    print("=" * 80)
    print("CHECK 5: Invariants 1, 2, 3 Fallback Checks (both frontend components & static/index.html)")
    print("=" * 80)

    # Invariant 1: UploadResume has "1000" and "setTimeout"
    up_path = os.path.join(PROJECT_ROOT, "frontend", "src", "components", "UploadResume.jsx")
    with open(up_path, "r", encoding="utf-8") as f:
        up_content = f.read()
    inv1_pass_fe = ("1000" in up_content) and ("setTimeout" in up_content)
    print(f"  Invariant 1 (frontend/UploadResume.jsx -> '1000' & 'setTimeout'): {'PASS' if inv1_pass_fe else 'FAIL'}")

    # Invariant 2: Quiz has "SESSION_ALPHA_099" and "Which hook is used to manage state"
    quiz_path = os.path.join(PROJECT_ROOT, "frontend", "src", "components", "Quiz.jsx")
    with open(quiz_path, "r", encoding="utf-8") as f:
        quiz_content = f.read()
    inv2_pass_fe = ("SESSION_ALPHA_099" in quiz_content) and ("Which hook is used to manage state" in quiz_content)
    print(
        f"  Invariant 2 (frontend/Quiz.jsx -> 'SESSION_ALPHA_099' & 'Which hook is used to manage state'): {'PASS' if inv2_pass_fe else 'FAIL'}"
    )

    # Invariant 3: ResultDashboard has "94", "S+", "5", "Exceptional mastery demonstrated"
    res_path = os.path.join(PROJECT_ROOT, "frontend", "src", "components", "ResultDashboard.jsx")
    with open(res_path, "r", encoding="utf-8") as f:
        res_content = f.read()
    inv3_items_fe = {
        "94": "94" in res_content,
        "S+": "S+" in res_content,
        "5": "5" in res_content,
        "Exceptional mastery demonstrated": "Exceptional mastery demonstrated" in res_content,
    }
    inv3_pass_fe = all(inv3_items_fe.values())
    print(
        f"  Invariant 3 (frontend/ResultDashboard.jsx -> 94, S+, 5, Exceptional mastery demonstrated): {'PASS' if inv3_pass_fe else 'FAIL'}"
    )
    for item, ok in inv3_items_fe.items():
        print(f"    - '{item}': {'PRESENT' if ok else 'MISSING'}")

    # Check static/index.html as well for cross-shell invariant consistency
    st_path = os.path.join(PROJECT_ROOT, "static", "index.html")
    with open(st_path, "r", encoding="utf-8") as f:
        st_content = f.read()
    inv1_pass_st = ("1000" in st_content) and ("setTimeout" in st_content)
    inv2_pass_st = ("SESSION_ALPHA_099" in st_content) and ("Which hook is used to manage state" in st_content)
    inv3_pass_st = ("94" in st_content) and ("S+" in st_content) and ("5" in st_content) and ("Exceptional mastery demonstrated" in st_content)

    print(f"  Cross-shell static/index.html Invariant 1 (1000ms): {'PASS' if inv1_pass_st else 'FAIL'}")
    print(f"  Cross-shell static/index.html Invariant 2 (SESSION_ALPHA_099): {'PASS' if inv2_pass_st else 'FAIL'}")
    print(f"  Cross-shell static/index.html Invariant 3 (94%, S+, 5/5): {'PASS' if inv3_pass_st else 'FAIL'}")

    overall = inv1_pass_fe and inv2_pass_fe and inv3_pass_fe and inv1_pass_st and inv2_pass_st and inv3_pass_st
    print("-" * 80)
    print(f"Invariants 1, 2, 3 Overall Result: {'PASS' if overall else 'FAIL'}")
    print("=" * 80 + "\n")
    return {
        "inv1_fe": inv1_pass_fe,
        "inv2_fe": inv2_pass_fe,
        "inv3_fe": inv3_pass_fe,
        "inv1_st": inv1_pass_st,
        "inv2_st": inv2_pass_st,
        "inv3_st": inv3_pass_st,
        "success": overall,
    }


def main():
    print("\n" + "#" * 80)
    print("   CHALLENGER 2 EMPIRICAL AST & STATIC AUDIT SUITE")
    print("#" * 80 + "\n")

    r1 = check_buttons()
    r2 = check_emojis()
    r3 = check_invariant_5()
    r4 = check_invariant_6()
    r5 = check_invariants_1_2_3()

    print("#" * 80)
    print("   CHALLENGER 2 FINAL SUMMARY")
    print("#" * 80)
    print(f"Check 1 (Universal rounded-full buttons): {'PASS' if r1['success'] else 'FAIL (VIOLATIONS DETECTED)'}")
    print(f"Check 2 (Zero emojis regex scan):         {'PASS' if r2['success'] else 'FAIL (EMOJIS FOUND)'}")
    print(f"Check 3 (Invariant 5 Throw Guard):        {'PASS' if r3['success'] else 'FAIL'}")
    print(f"Check 4 (Invariant 6 Tailwind version):   {'PASS' if r4['success'] else 'FAIL'}")
    print(f"Check 5 (Invariants 1, 2, 3 Fallbacks):   {'PASS' if r5['success'] else 'FAIL'}")

    all_pass = r1["success"] and r2["success"] and r3["success"] and r4["success"] and r5["success"]
    print("#" * 80)
    verdict = "APPROVE" if all_pass else "REJECT"
    print(f"CHALLENGER 2 VERDICT: {verdict}")
    print("#" * 80 + "\n")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
