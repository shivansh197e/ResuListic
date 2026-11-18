"""
Comprehensive Backend & Data Review Suite for Worker 10_1 Deliverables.
Tests mock_session.py, main.py /api/submit-test, benchmarkSolutions.js, api.js fallbacks,
filtering logic, and data structure integrity.
"""
import sys
import json
import re
from pathlib import Path
from starlette.testclient import TestClient

# 1. Test mock_session.py
print("=" * 80)
print("[TEST 1] Testing ml-services/skill_test/mock_session.py")
print("=" * 80)
sys.path.insert(0, str(Path(__file__).parent.parent / "ml-services"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from skill_test.mock_session import (
    CANONICAL_MCQ_EXPLANATIONS,
    CANONICAL_CODING_BENCHMARKS,
    build_mock_session,
    finalize_mock_session
)

assert len(CANONICAL_MCQ_EXPLANATIONS) == 20, f"Expected 20 MCQ explanations, got {len(CANONICAL_MCQ_EXPLANATIONS)}"
for idx in range(20):
    assert idx in CANONICAL_MCQ_EXPLANATIONS, f"Missing MCQ explanation for index {idx}"
    expl = CANONICAL_MCQ_EXPLANATIONS[idx]
    assert isinstance(expl, str) and len(expl) > 20, f"MCQ {idx} explanation too short or invalid: '{expl}'"

print(f" -> CANONICAL_MCQ_EXPLANATIONS: 20/20 valid pedagogical explanations.")

assert len(CANONICAL_CODING_BENCHMARKS) == 5, f"Expected 5 coding benchmarks, got {len(CANONICAL_CODING_BENCHMARKS)}"
expected_coding = {
    20: ("Two Sum", "moderate", 10.0, "O(N)", "O(N)"),
    21: ("Valid Parentheses", "moderate", 10.0, "O(N)", "O(N)"),
    22: ("Maximum Subarray", "moderate", 10.0, "O(N)", "O(1)"),
    23: ("Longest Palindromic Substring", "hard", 25.0, "O(N²)", "O(1)"),
    24: ("Word Break", "hard", 25.0, "O(N² · K)", "O(N)"),
}

for idx, (title, diff, marks, time_c, space_c) in expected_coding.items():
    assert idx in CANONICAL_CODING_BENCHMARKS, f"Missing coding benchmark for index {idx}"
    bench = CANONICAL_CODING_BENCHMARKS[idx]
    assert bench["title"] == title, f"Idx {idx} title mismatch: {bench['title']} vs {title}"
    assert bench["difficulty"] == diff, f"Idx {idx} difficulty mismatch: {bench['difficulty']} vs {diff}"
    assert bench["marks"] == marks, f"Idx {idx} marks mismatch: {bench['marks']} vs {marks}"
    assert bench["time_complexity"] == time_c, f"Idx {idx} time_complexity mismatch: {bench['time_complexity']} vs {time_c}"
    assert bench["space_complexity"] == space_c, f"Idx {idx} space_complexity mismatch: {bench['space_complexity']} vs {space_c}"
    assert "def solution" in bench["reference_solution"], f"Idx {idx} reference_solution missing solution function"
    assert len(bench["explanation"]) > 20, f"Idx {idx} explanation too short: '{bench['explanation']}'"

print(f" -> CANONICAL_CODING_BENCHMARKS: 5/5 benchmarks verified with explicit time/space complexity and reference solutions.")

sess = build_mock_session("test_reviewer_user")
sess = finalize_mock_session(sess)

q_list = sess["frontend_payload"]["questions"]
assert len(q_list) == 25, f"Expected 25 questions in session, got {len(q_list)}"
eval_key = sess["evaluation_key"]
assert len(eval_key) == 25, f"Expected 25 items in evaluation_key, got {len(eval_key)}"

total_session_marks = sum(q.get("marks", 0) for q in q_list)
assert total_session_marks == 100, f"Expected total 100 marks across 25 questions, got {total_session_marks}"
print(f" -> build_mock_session: 25 questions with 100 marks total (20x1M + 3x10M + 2x25M) verified.")


# 2. Test main.py /api/submit-test
print("=" * 80)
print("[TEST 2] Testing main.py /api/submit-test under multiple scenarios")
print("=" * 80)
import main
client = TestClient(main.app)

# Register mock session into in-memory mock sessions
main._mock_sessions[sess["session_id"]] = sess

# Scenario A: Full perfect submission
answers_perfect = [
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

resp = client.post("/api/submit-test", json={
    "session_id": sess["session_id"],
    "user_id": "test_reviewer_user",
    "answers": answers_perfect
})
assert resp.status_code == 200, f"Submit failed: {resp.text}"
data = resp.json()
assert data["status"] == "submitted"
assert "answer_review" in data
review = data["answer_review"]
assert len(review) == 25, f"Expected 25 review items, got {len(review)}"

assert data.get("score") == 100.0, f"Expected 100.0 score, got {data.get('score')}"
assert data.get("mcq_marks") == 20.0, f"Expected 20.0 mcq_marks, got {data.get('mcq_marks')}"
assert data.get("moderate_marks") == 30.0, f"Expected 30.0 moderate_marks, got {data.get('moderate_marks')}"
assert data.get("hard_marks") == 50.0, f"Expected 50.0 hard_marks, got {data.get('hard_marks')}"
assert review[20].get("question_type") == "coding", f"Expected Q20 coding, got {review[20].get('question_type')}"
assert review[20].get("max_marks") == 10.0, f"Expected Q20 max_marks 10.0, got {review[20].get('max_marks')}"
assert review[20].get("marks_obtained") == 10.0, f"Expected Q20 marks_obtained 10.0, got {review[20].get('marks_obtained')}"
assert review[23].get("question_type") == "coding", f"Expected Q23 coding, got {review[23].get('question_type')}"
assert review[23].get("max_marks") == 25.0, f"Expected Q23 max_marks 25.0, got {review[23].get('max_marks')}"
assert review[23].get("marks_obtained") == 25.0, f"Expected Q23 marks_obtained 25.0, got {review[23].get('marks_obtained')}"

print(" -> Scenario A (Full Perfect Submission): PASS. All 25 items reviewed with complete metadata, score=", data["score"])

# Scenario B: Partial submission (unanswered backfill check)
sess_b = finalize_mock_session(build_mock_session("test_user_b"))
main._mock_sessions[sess_b["session_id"]] = sess_b

# Answer only 3 MCQs and 1 coding challenge
answers_partial = [
    {"q_index": 0, "user_answer": "A"},
    {"q_index": 1, "user_answer": "WRONG_ANSWER"},
    {"q_index": 20, "user_answer": CANONICAL_CODING_BENCHMARKS[20]["reference_solution"]},
]

resp_b = client.post("/api/submit-test", json={
    "session_id": sess_b["session_id"],
    "user_id": "test_user_b",
    "answers": answers_partial
})
assert resp_b.status_code == 200, f"Partial submit failed: {resp_b.text}"
data_b = resp_b.json()
review_b = data_b["answer_review"]
assert len(review_b) == 25, f"Expected 25 review items in partial submission, got {len(review_b)}"

# Verify unanswered items (e.g. index 2..19 and 21..24)
for i, item in enumerate(review_b):
    assert item["q_index"] == i
    assert "explanation" in item and len(item["explanation"]) > 10, f"Unanswered item {i} missing explanation"
    if i == 0:
        assert item["is_correct"] is True
        assert item["marks_obtained"] == 1.0
    elif i == 1:
        assert item["is_correct"] is False
        assert item["marks_obtained"] == 0.0
    elif i == 20:
        assert item["is_correct"] is True
        assert item["marks_obtained"] == 10.0
    else:
        assert item["is_correct"] is False
        assert item["marks_obtained"] == 0.0
        if i >= 20:
            assert item["time_complexity"] != ""
            assert item["space_complexity"] != ""
            assert item["reference_solution"] != ""

print(" -> Scenario B (Partial Submission & Unanswered Backfill): PASS. All 25 items populated, unanswered questions have explanations and benchmark solutions.")

# Scenario C: Empty submission answers: []
sess_c = finalize_mock_session(build_mock_session("test_user_c"))
main._mock_sessions[sess_c["session_id"]] = sess_c

resp_c = client.post("/api/submit-test", json={
    "session_id": sess_c["session_id"],
    "user_id": "test_user_c",
    "answers": []
})
assert resp_c.status_code == 200, f"Empty submit failed: {resp_c.text}"
data_c = resp_c.json()
review_c = data_c["answer_review"]
assert len(review_c) == 25, f"Expected 25 review items in empty submission, got {len(review_c)}"
assert data_c["score"] == 0.0
print(" -> Scenario C (Empty Submission): PASS. Returns 25 items with score 0.0 without crash.")

# Scenario D: Adversarial edge cases
# Duplicate index -> 400
sess_d = finalize_mock_session(build_mock_session("test_user_d"))
main._mock_sessions[sess_d["session_id"]] = sess_d
resp_d1 = client.post("/api/submit-test", json={
    "session_id": sess_d["session_id"],
    "user_id": "test_user_d",
    "answers": [{"q_index": 0, "user_answer": "A"}, {"q_index": 0, "user_answer": "B"}]
})
assert resp_d1.status_code == 400, f"Expected 400 for duplicate index, got {resp_d1.status_code}"

# Invalid index 999 -> 400
resp_d2 = client.post("/api/submit-test", json={
    "session_id": sess_d["session_id"],
    "user_id": "test_user_d",
    "answers": [{"q_index": 999, "user_answer": "A"}]
})
assert resp_d2.status_code == 400, f"Expected 400 for invalid index, got {resp_d2.status_code}"

# Re-submission of already submitted session -> 409
resp_d3 = client.post("/api/submit-test", json={
    "session_id": sess["session_id"],
    "user_id": "test_reviewer_user",
    "answers": []
})
assert resp_d3.status_code == 409, f"Expected 409 for duplicate session submit, got {resp_d3.status_code}"
print(" -> Scenario D (Adversarial Edge Cases): PASS. Handled 400 duplicate, 400 unknown, 409 duplicate submission.")


# 3. Test frontend/src/data/benchmarkSolutions.js
print("=" * 80)
print("[TEST 3] Testing frontend/src/data/benchmarkSolutions.js")
print("=" * 80)
bench_file = Path("frontend/src/data/benchmarkSolutions.js").read_text(encoding="utf-8")
assert "export const BENCHMARK_25_REVIEW = [" in bench_file

# Check all 25 items exist in benchmarkSolutions.js
for q_idx in range(25):
    assert f"q_index: {q_idx}," in bench_file, f"Missing q_index {q_idx} in benchmarkSolutions.js"

# Check coding items have complexity
for title in ["Two Sum", "Valid Parentheses", "Maximum Subarray", "Longest Palindromic Substring", "Word Break"]:
    assert title in bench_file, f"Missing title {title} in benchmarkSolutions.js"

assert bench_file.count("time_complexity:") == 5, f"Expected 5 time_complexity declarations, got {bench_file.count('time_complexity:')}"
assert bench_file.count("space_complexity:") == 5, f"Expected 5 space_complexity declarations, got {bench_file.count('space_complexity:')}"
print(" -> benchmarkSolutions.js: All 25 items and 5 time/space complexity definitions present.")


# 4. Test filter logic across (ALL, INCORRECT, MCQ, CODING)
print("=" * 80)
print("[TEST 4] Testing Filter Tab Logic")
print("=" * 80)
# We test the filter logic using the exact logic from ResultDashboard.jsx and static/index.html:
# qType = item.question_type || item.type || (qIdx >= 20 ? 'coding' : 'mcq')
# if (reviewFilter === 'incorrect') return !item.is_correct;
# if (reviewFilter === 'mcq') return qType === 'mcq';
# if (reviewFilter === 'coding') return qType !== 'mcq';
# return true;

def run_filters(reviews):
    def filter_items(items, f):
        res = []
        for idx, item in enumerate(items):
            q_idx = item.get("q_index", idx)
            q_type = item.get("question_type") or item.get("type") or ("coding" if int(q_idx) >= 20 else "mcq")
            if f == "incorrect":
                if not item.get("is_correct", False):
                    res.append(item)
            elif f == "mcq":
                if q_type == "mcq":
                    res.append(item)
            elif f == "coding":
                if q_type != "mcq":
                    res.append(item)
            else:
                res.append(item)
        return res

    all_items = filter_items(reviews, "all")
    mcq_items = filter_items(reviews, "mcq")
    coding_items = filter_items(reviews, "coding")
    incorrect_items = filter_items(reviews, "incorrect")
    return len(all_items), len(mcq_items), len(coding_items), len(incorrect_items)

# On Scenario A (Perfect: all 25 correct)
a_all, a_mcq, a_coding, a_inc = run_filters(review)
assert a_all == 25, f"Expected 25 all items, got {a_all}"
assert a_mcq == 20, f"Expected 20 mcq items, got {a_mcq}"
assert a_coding == 5, f"Expected 5 coding items, got {a_coding}"
assert a_inc == 0, f"Expected 0 incorrect items, got {a_inc}"

# On Scenario B (Partial: 2 correct, 23 incorrect)
b_all, b_mcq, b_coding, b_inc = run_filters(review_b)
assert b_all == 25
assert b_mcq == 20
assert b_coding == 5
assert b_inc == 23

# On Scenario C (Empty: 0 correct, 25 incorrect)
c_all, c_mcq, c_coding, c_inc = run_filters(review_c)
assert c_all == 25
assert c_mcq == 20
assert c_coding == 5
assert c_inc == 25

print(" -> Filter Logic: Verified on all scenarios (ALL=25, MCQ=20, CODING=5, INCORRECT reflects exact status).")

print("=" * 80)
print("ALL BACKEND & DATA REVIEW TESTS PASSED CLEANLY!")
print("=" * 80)
