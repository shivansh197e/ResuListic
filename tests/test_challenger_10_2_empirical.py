"""
Empirical Adversarial Stress Test Suite for Step 4 Test Solutions & Answer Review.
Role: Challenger 10_2 Replacement (Empirical Data & Filter Challenger).

Tests:
1. POST /api/submit-test with 0 answers (empty submission)
2. POST /api/submit-test with 1 answer (Q0 MCQ)
3. POST /api/submit-test with 1 coding answer (Q20 Two Sum)
4. POST /api/submit-test with all 25 answers (20 MCQs + 3 Moderate Coding + 2 Hard Coding)
5. Comprehensive schema validation on all 25 answer_review items:
   - 20 MCQs: question_type='mcq', correct_answer, pedagogical explanation, 1 Mark
   - 5 Coding: question_type='coding', reference_solution, pedagogical explanation,
     time_complexity, space_complexity, marks/difficulty (10M Moderate, 25M Hard)
6. 4-way Filter Tab Logic verification:
   - ALL: length == 25
   - MCQ: length == 20
   - CODING: length == 5
   - INCORRECT: length matches missed count, zero crashes, no unexpected empty state
7. Frontend benchmarkSolutions.js fallback dataset schema validation
8. End-to-end /api/start-test -> /api/submit-test integration
"""

import sys
import uuid
from pathlib import Path
from starlette.testclient import TestClient

# Ensure workspace and ml-services are in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "ml-services"))
sys.path.insert(0, str(BASE_DIR))

import main
from skill_test.mock_session import (
    CANONICAL_MCQ_EXPLANATIONS,
    CANONICAL_CODING_BENCHMARKS,
    build_mock_session,
    finalize_mock_session,
)

client = TestClient(main.app)

findings = []

def record_finding(test_id, severity, description, expected, actual):
    findings.append({
        "test_id": test_id,
        "severity": severity,
        "description": description,
        "expected": expected,
        "actual": actual,
    })
    print(f"\n[FAIL - {severity}] {test_id}: {description}")
    print(f"   Expected: {expected}")
    print(f"   Actual:   {actual}")

def filter_reviews(items, filter_name):
    """Simulates ResultDashboard.jsx & static/index.html filter logic."""
    res = []
    for idx, item in enumerate(items):
        q_idx = item.get("q_index")
        if q_idx is None:
            q_idx = idx
        else:
            try:
                q_idx = int(q_idx)
            except Exception:
                q_idx = idx
        q_type = item.get("question_type") or item.get("type") or ("coding" if q_idx >= 20 else "mcq")
        if filter_name == "incorrect":
            if not item.get("is_correct", False):
                res.append(item)
        elif filter_name == "mcq":
            if q_type == "mcq":
                res.append(item)
        elif filter_name == "coding":
            if q_type != "mcq":
                res.append(item)
        else: # "all"
            res.append(item)
    return res


print("=" * 80)
print("RUNNING EMPIRICAL ADVERSARIAL STRESS SUITE (CHALLENGER 10_2)")
print("=" * 80)

# ------------------------------------------------------------------------------
# TEST 1: Submitting 0 answers
# ------------------------------------------------------------------------------
print("\n[TEST 1] Submitting 0 answers (empty submission)...")
sess_0 = finalize_mock_session(build_mock_session("cand_zero"))
main._mock_sessions[sess_0["session_id"]] = sess_0

resp_0 = client.post("/api/submit-test", json={
    "session_id": sess_0["session_id"],
    "user_id": "cand_zero",
    "answers": []
})

if resp_0.status_code != 200:
    record_finding("T1_STATUS", "CRITICAL", "Submit 0 answers returned non-200", 200, resp_0.status_code)
else:
    data_0 = resp_0.json()
    review_0 = data_0.get("answer_review", [])
    if len(review_0) != 25:
        record_finding("T1_LEN", "CRITICAL", "Submit 0 answers did not return 25 items", 25, len(review_0))
    else:
        print(f" -> PASS: 25 items returned in answer_review for 0 submitted answers.")

    f_all = filter_reviews(review_0, "all")
    f_mcq = filter_reviews(review_0, "mcq")
    f_coding = filter_reviews(review_0, "coding")
    f_inc = filter_reviews(review_0, "incorrect")

    if len(f_all) != 25:
        record_finding("T1_FILTER_ALL", "HIGH", "Filter ALL mismatch on 0 answers", 25, len(f_all))
    if len(f_mcq) != 20:
        record_finding("T1_FILTER_MCQ", "HIGH", "Filter MCQ mismatch on 0 answers", 20, len(f_mcq))
    if len(f_coding) != 5:
        record_finding("T1_FILTER_CODING", "HIGH", "Filter CODING mismatch on 0 answers", 5, len(f_coding))
    if len(f_inc) != 25:
        record_finding("T1_FILTER_INC", "HIGH", "Filter INCORRECT mismatch on 0 answers", 25, len(f_inc))

    if len(f_all) == 25 and len(f_mcq) == 20 and len(f_coding) == 5 and len(f_inc) == 25:
        print(f" -> PASS: Filters on 0 answers: ALL=25, MCQ=20, CODING=5, INCORRECT=25 (no empty states).")


# ------------------------------------------------------------------------------
# TEST 2: Submitting 1 answer (Q0 MCQ)
# ------------------------------------------------------------------------------
print("\n[TEST 2] Submitting 1 answer (Q0 MCQ)...")
sess_1 = finalize_mock_session(build_mock_session("cand_one"))
main._mock_sessions[sess_1["session_id"]] = sess_1

resp_1 = client.post("/api/submit-test", json={
    "session_id": sess_1["session_id"],
    "user_id": "cand_one",
    "answers": [{"q_index": 0, "user_answer": "A"}]
})

if resp_1.status_code != 200:
    record_finding("T2_STATUS", "CRITICAL", "Submit 1 answer returned non-200", 200, resp_1.status_code)
else:
    data_1 = resp_1.json()
    review_1 = data_1.get("answer_review", [])
    if len(review_1) != 25:
        record_finding("T2_LEN", "CRITICAL", "Submit 1 answer did not return 25 items", 25, len(review_1))
    else:
        print(f" -> PASS: 25 items returned in answer_review for 1 submitted answer.")

    f_all = filter_reviews(review_1, "all")
    f_mcq = filter_reviews(review_1, "mcq")
    f_coding = filter_reviews(review_1, "coding")
    f_inc = filter_reviews(review_1, "incorrect")

    if len(f_all) != 25:
        record_finding("T2_FILTER_ALL", "HIGH", "Filter ALL mismatch on 1 answer", 25, len(f_all))
    if len(f_mcq) != 20:
        record_finding("T2_FILTER_MCQ", "HIGH", "Filter MCQ mismatch on 1 answer", 20, len(f_mcq))
    if len(f_coding) != 5:
        record_finding("T2_FILTER_CODING", "HIGH", "Filter CODING mismatch on 1 answer", 5, len(f_coding))
    if len(f_inc) != 24:
        record_finding("T2_FILTER_INC", "HIGH", "Filter INCORRECT mismatch on 1 answer (Q0 correct)", 24, len(f_inc))

    if len(f_all) == 25 and len(f_mcq) == 20 and len(f_coding) == 5 and len(f_inc) == 24:
        print(f" -> PASS: Filters on 1 answer: ALL=25, MCQ=20, CODING=5, INCORRECT=24 (no empty states).")


# ------------------------------------------------------------------------------
# TEST 3: Submitting 1 Coding answer (Q20 Two Sum)
# ------------------------------------------------------------------------------
print("\n[TEST 3] Submitting 1 coding answer (Q20 Two Sum benchmark code)...")
sess_code1 = finalize_mock_session(build_mock_session("cand_code1"))
main._mock_sessions[sess_code1["session_id"]] = sess_code1

two_sum_code = CANONICAL_CODING_BENCHMARKS[20]["reference_solution"]
resp_code1 = client.post("/api/submit-test", json={
    "session_id": sess_code1["session_id"],
    "user_id": "cand_code1",
    "answers": [{"q_index": 20, "user_answer": two_sum_code}]
})

if resp_code1.status_code != 200:
    record_finding("T3_STATUS", "CRITICAL", "Submit 1 coding answer returned non-200", 200, resp_code1.status_code)
else:
    data_c1 = resp_code1.json()
    review_c1 = data_c1.get("answer_review", [])
    if len(review_c1) != 25:
        record_finding("T3_LEN", "CRITICAL", "Submit 1 coding answer did not return 25 items", 25, len(review_c1))
    else:
        q20 = review_c1[20]
        print(f" -> Q20 evaluated as: question_type={q20.get('question_type')}, max_marks={q20.get('max_marks')}, marks_obtained={q20.get('marks_obtained')}")
        if q20.get("question_type") != "coding":
            record_finding("T3_Q20_TYPE", "CRITICAL",
                           "Submitted coding question Q20 was classified as MCQ instead of coding",
                           "coding", q20.get("question_type"))
        if q20.get("max_marks") != 10.0:
            record_finding("T3_Q20_MARKS", "CRITICAL",
                           "Submitted coding question Q20 max_marks is incorrect",
                           10.0, q20.get("max_marks"))
        if not q20.get("time_complexity"):
            record_finding("T3_Q20_TIME", "HIGH",
                           "Submitted coding question Q20 missing time_complexity",
                           "O(N)", q20.get("time_complexity"))
        if not q20.get("space_complexity"):
            record_finding("T3_Q20_SPACE", "HIGH",
                           "Submitted coding question Q20 missing space_complexity",
                           "O(N)", q20.get("space_complexity"))

    f_coding = filter_reviews(review_c1, "coding")
    if len(f_coding) != 5:
        record_finding("T3_FILTER_CODING", "CRITICAL",
                       "Filter CODING length mismatch after submitting Q20",
                       5, len(f_coding))


# ------------------------------------------------------------------------------
# TEST 4: Submitting all 25 answers (including all 5 coding questions)
# ------------------------------------------------------------------------------
print("\n[TEST 4] Submitting all 25 answers (20 MCQs + 5 Coding)...")
sess_25 = finalize_mock_session(build_mock_session("cand_25"))
main._mock_sessions[sess_25["session_id"]] = sess_25

answers_25 = [
    {"q_index": 0, "user_answer": "A"},
    {"q_index": 1, "user_answer": "B"},
    {"q_index": 2, "user_answer": "C"},
    {"q_index": 3, "user_answer": "B"},
    {"q_index": 4, "user_answer": "A"},
    {"q_index": 5, "user_answer": "B"},
    {"q_index": 6, "user_answer": "B"},
    {"q_index": 7, "user_answer": "A"},
    {"q_index": 8, "user_answer": "A"},
    {"q_index": 9, "user_answer": "A"},
    {"q_index": 10, "user_answer": "B"},
    {"q_index": 11, "user_answer": "B"},
    {"q_index": 12, "user_answer": "A"},
    {"q_index": 13, "user_answer": "B"},
    {"q_index": 14, "user_answer": "A"},
    {"q_index": 15, "user_answer": "A"},
    {"q_index": 16, "user_answer": "A"},
    {"q_index": 17, "user_answer": "A"},
    {"q_index": 18, "user_answer": "A"},
    {"q_index": 19, "user_answer": "A"},
    {"q_index": 20, "user_answer": CANONICAL_CODING_BENCHMARKS[20]["reference_solution"]},
    {"q_index": 21, "user_answer": CANONICAL_CODING_BENCHMARKS[21]["reference_solution"]},
    {"q_index": 22, "user_answer": CANONICAL_CODING_BENCHMARKS[22]["reference_solution"]},
    {"q_index": 23, "user_answer": CANONICAL_CODING_BENCHMARKS[23]["reference_solution"]},
    {"q_index": 24, "user_answer": CANONICAL_CODING_BENCHMARKS[24]["reference_solution"]},
]

resp_25 = client.post("/api/submit-test", json={
    "session_id": sess_25["session_id"],
    "user_id": "cand_25",
    "answers": answers_25
})

if resp_25.status_code != 200:
    record_finding("T4_STATUS", "CRITICAL", "Submit 25 answers returned non-200", 200, resp_25.status_code)
else:
    data_25 = resp_25.json()
    review_25 = data_25.get("answer_review", [])
    if len(review_25) != 25:
        record_finding("T4_LEN", "CRITICAL", "Submit 25 answers did not return 25 items", 25, len(review_25))
    else:
        # Check every item
        # MCQs (0..19)
        for i in range(20):
            item = review_25[i]
            if item.get("question_type") != "mcq":
                record_finding(f"T4_MCQ_{i}_TYPE", "HIGH", f"MCQ {i} question_type mismatch", "mcq", item.get("question_type"))
            if not item.get("correct_answer"):
                record_finding(f"T4_MCQ_{i}_CORR", "HIGH", f"MCQ {i} missing correct_answer", "non-empty string", item.get("correct_answer"))
            if not item.get("explanation") or len(item.get("explanation", "")) < 10:
                record_finding(f"T4_MCQ_{i}_EXPL", "HIGH", f"MCQ {i} missing pedagogical explanation", "len > 10", item.get("explanation"))
            if item.get("max_marks") != 1.0 or item.get("marks") != 1.0:
                record_finding(f"T4_MCQ_{i}_MARKS", "HIGH", f"MCQ {i} marks mismatch", 1.0, item.get("max_marks"))

        # Coding (20..24)
        for i in range(20, 25):
            item = review_25[i]
            is_hard = (i >= 23)
            exp_diff = "hard" if is_hard else "moderate"
            exp_marks = 25.0 if is_hard else 10.0

            if item.get("question_type") != "coding":
                record_finding(f"T4_CODING_{i}_TYPE", "CRITICAL",
                               f"Coding question {i} question_type mismatch on full submission",
                               "coding", item.get("question_type"))
            if not item.get("reference_solution") or "def solution" not in item.get("reference_solution", ""):
                record_finding(f"T4_CODING_{i}_SOL", "CRITICAL",
                               f"Coding question {i} missing reference_solution code",
                               "contains 'def solution'", item.get("reference_solution"))
            if not item.get("explanation") or len(item.get("explanation", "")) < 10:
                record_finding(f"T4_CODING_{i}_EXPL", "HIGH",
                               f"Coding question {i} missing pedagogical explanation",
                               "len > 10", item.get("explanation"))
            if not item.get("time_complexity"):
                record_finding(f"T4_CODING_{i}_TIME", "CRITICAL",
                               f"Coding question {i} missing time_complexity",
                               "O(...)", item.get("time_complexity"))
            if not item.get("space_complexity"):
                record_finding(f"T4_CODING_{i}_SPACE", "CRITICAL",
                               f"Coding question {i} missing space_complexity",
                               "O(...)", item.get("space_complexity"))
            if item.get("difficulty") != exp_diff:
                record_finding(f"T4_CODING_{i}_DIFF", "HIGH",
                               f"Coding question {i} difficulty mismatch",
                               exp_diff, item.get("difficulty"))
            if item.get("max_marks") != exp_marks:
                record_finding(f"T4_CODING_{i}_MAX_MARKS", "CRITICAL",
                               f"Coding question {i} max_marks mismatch",
                               exp_marks, item.get("max_marks"))

        # Filter testing on 25 submitted answers
        f_all = filter_reviews(review_25, "all")
        f_mcq = filter_reviews(review_25, "mcq")
        f_coding = filter_reviews(review_25, "coding")
        f_inc = filter_reviews(review_25, "incorrect")

        print(f" -> Filters on 25 answers: ALL={len(f_all)}, MCQ={len(f_mcq)}, CODING={len(f_coding)}, INCORRECT={len(f_inc)}")
        if len(f_all) != 25:
            record_finding("T4_FILTER_ALL", "HIGH", "Filter ALL mismatch on 25 answers", 25, len(f_all))
        if len(f_mcq) != 20:
            record_finding("T4_FILTER_MCQ", "CRITICAL", "Filter MCQ mismatch on 25 answers", 20, len(f_mcq))
        if len(f_coding) != 5:
            record_finding("T4_FILTER_CODING", "CRITICAL",
                           "Filter CODING produced 0 or wrong count on 25 answers (Empty State Bug)",
                           5, len(f_coding))


# ------------------------------------------------------------------------------
# TEST 5: Frontend Fallback Dataset (benchmarkSolutions.js)
# ------------------------------------------------------------------------------
print("\n[TEST 5] Validating frontend/src/data/benchmarkSolutions.js fallback dataset...")
bench_js_path = BASE_DIR / "frontend" / "src" / "data" / "benchmarkSolutions.js"
if not bench_js_path.exists():
    record_finding("T5_FILE", "CRITICAL", "benchmarkSolutions.js does not exist", True, False)
else:
    bench_content = bench_js_path.read_text(encoding="utf-8")
    for q_idx in range(25):
        if f"q_index: {q_idx}," not in bench_content:
            record_finding(f"T5_ITEM_{q_idx}", "HIGH", f"Missing q_index {q_idx} in benchmarkSolutions.js", True, False)

    for c_title in ["Two Sum", "Valid Parentheses", "Maximum Subarray", "Longest Palindromic Substring", "Word Break"]:
        if c_title not in bench_content:
            record_finding(f"T5_TITLE_{c_title}", "HIGH", f"Missing title {c_title} in benchmarkSolutions.js", True, False)

    time_count = bench_content.count("time_complexity:")
    space_count = bench_content.count("space_complexity:")
    if time_count != 5:
        record_finding("T5_TIME_COUNT", "HIGH", "benchmarkSolutions.js time_complexity count mismatch", 5, time_count)
    if space_count != 5:
        record_finding("T5_SPACE_COUNT", "HIGH", "benchmarkSolutions.js space_complexity count mismatch", 5, space_count)

    if time_count == 5 and space_count == 5:
        print(" -> PASS: benchmarkSolutions.js has all 25 items and 5 time/space complexity fields.")


# ------------------------------------------------------------------------------
# TEST 6: Real POST /api/start-test -> POST /api/submit-test Lifecycle
# ------------------------------------------------------------------------------
print("\n[TEST 6] Validating POST /api/start-test (mock mode) -> POST /api/submit-test lifecycle...")
start_resp = client.post("/api/start-test", json={
    "user_id": "challenger_lifecycle_user",
    "selected_skills": ["Algorithms", "Python"],
    "mode": "mock"
})

if start_resp.status_code != 200:
    record_finding("T6_START", "CRITICAL", "/api/start-test failed", 200, start_resp.status_code)
else:
    start_payload = start_resp.json()
    sid = start_payload.get("session_id")
    questions = start_payload.get("questions", [])
    if len(questions) != 25:
        record_finding("T6_START_LEN", "CRITICAL", "/api/start-test did not return 25 questions", 25, len(questions))
    else:
        print(f" -> PASS: /api/start-test initialized session {sid} with 25 questions.")

    # Submit 2 answers to this real session: 1 MCQ and 1 Coding
    sub_real = client.post("/api/submit-test", json={
        "session_id": sid,
        "user_id": "challenger_lifecycle_user",
        "answers": [
            {"q_index": 0, "user_answer": "A"},
            {"q_index": 20, "user_answer": CANONICAL_CODING_BENCHMARKS[20]["reference_solution"]}
        ]
    })
    if sub_real.status_code != 200:
        record_finding("T6_SUBMIT", "CRITICAL", "/api/submit-test failed for lifecycle session", 200, sub_real.status_code)
    else:
        real_data = sub_real.json()
        real_review = real_data.get("answer_review", [])
        if len(real_review) != 25:
            record_finding("T6_SUBMIT_LEN", "CRITICAL", "answer_review does not contain 25 items", 25, len(real_review))
        else:
            print(f" -> PASS: Real lifecycle submit-test returned 25 answer_review items.")
            # Check Q20 in real session
            q20_real = real_review[20]
            if q20_real.get("question_type") != "coding":
                record_finding("T6_Q20_TYPE", "CRITICAL",
                               "Q20 in real session submission misclassified as MCQ",
                               "coding", q20_real.get("question_type"))
            if q20_real.get("max_marks") != 10.0:
                record_finding("T6_Q20_MARKS", "CRITICAL",
                               "Q20 max_marks in real session mismatch",
                               10.0, q20_real.get("max_marks"))



# ------------------------------------------------------------------------------
# SUMMARY & VERDICT
# ------------------------------------------------------------------------------
print("\n" + "=" * 80)
print(f"TOTAL FINDINGS: {len(findings)}")
print("=" * 80)
for f in findings:
    print(f"[{f['severity']}] {f['test_id']}: {f['description']} (Expected: {f['expected']}, Got: {f['actual']})")

if len(findings) > 0:
    print("\nOVERALL VERDICT: REQUEST_CHANGES (Defects empirically reproduced)")
else:
    print("\nOVERALL VERDICT: APPROVE (Zero defects found)")
