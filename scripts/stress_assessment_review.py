"""
Adversarial Stress Harness: Assessment Submission, Answer Review Payload & Filter Criteria
Tests all 25 questions across edge-case submissions (0, 1, 25 answers, out-of-order, expired)
and verifies complete pedagogical explanations, complexity analysis, marks, and filter criteria
across BOTH mock mode and live database mode.
"""

import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

VENV_SITE = os.path.join(PROJECT_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

ML_SERVICES_DIR = os.path.join(PROJECT_ROOT, "ml-services")
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from starlette.testclient import TestClient
import main

client = TestClient(main.app)
db = main.db

cleanup_users = set()
cleanup_sessions = set()
cleanup_submissions = set()

def create_session(mode="mock", user_id=None):
    if not user_id:
        user_id = f"c10_user_{uuid.uuid4().hex[:8]}"
    cleanup_users.add(user_id)

    if mode == "live":
        db.resumes.update_one(
            {"_id": user_id},
            {"$set": {
                "_id": user_id,
                "enrichment": {"skills": {"high": ["Python", "Algorithms", "Databases"], "medium": ["APIs"]}}
            }},
            upsert=True
        )
        resp = client.post("/api/start-test", json={
            "user_id": user_id,
            "selected_skills": ["Python", "Algorithms"],
            "mode": "live"
        })
    else:
        resp = client.post("/api/start-test", json={
            "user_id": user_id,
            "mode": "mock"
        })

    assert resp.status_code == 200, f"Failed to start test ({mode}): {resp.text}"
    session_id = resp.json()["session_id"]
    cleanup_sessions.add(session_id)
    return user_id, session_id

def cleanup():
    for u in cleanup_users:
        db.resumes.delete_one({"_id": u})
        db.test_submissions.delete_many({"user_id": u})
    for s in cleanup_sessions:
        db.test_sessions.delete_one({"session_id": s})
        db.test_sessions.delete_one({"frontend_payload.session_id": s})
        db.test_submissions.delete_many({"session_id": s})
        main._mock_sessions.pop(s, None)

def test_scenario_0_answers(mode="mock"):
    print(f"\n--- [TEST SCENARIO 1: SUBMIT 0 ANSWERS ({mode.upper()} MODE)] ---")
    user_id, session_id = create_session(mode=mode)

    sub_resp = client.post("/api/submit-test", json={"session_id": session_id, "user_id": user_id, "answers": []})
    assert sub_resp.status_code == 200, f"submit-test failed: {sub_resp.text}"
    data = sub_resp.json()

    assert data["status"] == "submitted"
    assert "answer_review" in data
    ar = data["answer_review"]
    assert len(ar) == 25, f"Expected 25 items in answer_review, got {len(ar)}"

    # Check order
    indexes = [int(item["q_index"]) for item in ar]
    assert indexes == list(range(25)), f"Indexes are not 0..24: {indexes}"

    # Verify 20 MCQs (0..19)
    for i in range(20):
        item = ar[i]
        assert item["question_type"] == "mcq", f"Q{i} question_type is not mcq: {item.get('question_type')}"
        assert item["difficulty"] == "easy", f"Q{i} difficulty is not easy: {item.get('difficulty')}"
        assert item["marks"] == 1.0, f"Q{i} marks is not 1.0: {item.get('marks')}"
        assert item["max_marks"] == 1.0, f"Q{i} max_marks is not 1.0: {item.get('max_marks')}"
        assert item["marks_obtained"] == 0.0, f"Q{i} marks_obtained is not 0.0: {item.get('marks_obtained')}"
        assert item["is_correct"] is False, f"Q{i} should be False since unanswered"
        assert len(str(item.get("correct_answer", ""))) > 0, f"Q{i} correct_answer is empty"
        assert len(str(item.get("explanation", ""))) > 15, f"Q{i} explanation is missing or trivial: {item.get('explanation')}"

    # Verify 3 Moderate Coding (20..22)
    for i in range(20, 23):
        item = ar[i]
        assert item["question_type"] == "coding", f"Q{i} is not coding: {item.get('question_type')}"
        assert item["difficulty"] == "moderate", f"Q{i} is not moderate: {item.get('difficulty')}"
        assert item["marks"] == 10.0, f"Q{i} marks is not 10.0: {item.get('marks')}"
        assert item["max_marks"] == 10.0, f"Q{i} max_marks is not 10.0: {item.get('max_marks')}"
        assert item["marks_obtained"] == 0.0, f"Q{i} marks_obtained should be 0.0"
        assert item["is_correct"] is False
        assert "def " in str(item.get("reference_solution", "")), f"Q{i} missing reference_solution code"
        assert len(str(item.get("explanation", ""))) > 20, f"Q{i} missing pedagogical explanation"
        assert len(str(item.get("time_complexity", ""))) > 0, f"Q{i} missing time_complexity"
        assert len(str(item.get("space_complexity", ""))) > 0, f"Q{i} missing space_complexity"

    # Verify 2 Hard Coding (23..24)
    for i in range(23, 25):
        item = ar[i]
        assert item["question_type"] == "coding", f"Q{i} is not coding: {item.get('question_type')}"
        assert item["difficulty"] == "hard", f"Q{i} is not hard: {item.get('difficulty')}"
        assert item["marks"] == 25.0, f"Q{i} marks is not 25.0: {item.get('marks')}"
        assert item["max_marks"] == 25.0, f"Q{i} max_marks is not 25.0: {item.get('max_marks')}"
        assert item["marks_obtained"] == 0.0, f"Q{i} marks_obtained should be 0.0"
        assert item["is_correct"] is False
        assert "def " in str(item.get("reference_solution", "")), f"Q{i} missing reference_solution code"
        assert len(str(item.get("explanation", ""))) > 20, f"Q{i} missing pedagogical explanation"
        assert len(str(item.get("time_complexity", ""))) > 0, f"Q{i} missing time_complexity"
        assert len(str(item.get("space_complexity", ""))) > 0, f"Q{i} missing space_complexity"

    print(f" [PASS] 0 answers submission successfully populated all 25 questions with full solutions & explanations ({mode}).")
    return ar

def test_scenario_1_answer(mode="mock"):
    print(f"\n--- [TEST SCENARIO 2: SUBMIT 1 ANSWER (Q0) ({mode.upper()} MODE)] ---")
    user_id, session_id = create_session(mode=mode)

    # Submit Q0 = "A" (which is correct for mock Q0)
    sub_resp = client.post("/api/submit-test", json={
        "session_id": session_id,
        "user_id": user_id,
        "answers": [{"q_index": 0, "user_answer": "A"}]
    })
    assert sub_resp.status_code == 200
    data = sub_resp.json()
    ar = data["answer_review"]
    assert len(ar) == 25, f"Expected 25 items, got {len(ar)}"

    q0 = ar[0]
    assert q0["user_answer"] == "A"
    assert q0["marks_obtained"] in (0.0, 1.0)
    assert len(q0["explanation"]) > 15

    # Check remaining 24
    for i in range(1, 25):
        item = ar[i]
        assert item["q_index"] == i
        assert item["is_correct"] is False
        assert item["marks_obtained"] == 0.0
        assert len(str(item.get("explanation", ""))) > 15
        if i >= 20:
            assert len(str(item.get("time_complexity", ""))) > 0
            assert len(str(item.get("space_complexity", ""))) > 0
            assert "def " in str(item.get("reference_solution", ""))

    print(f" [PASS] 1 answer submission correctly scored Q0 and backfilled Q1..Q24 ({mode}).")
    return ar

def test_scenario_25_answers(mode="mock"):
    print(f"\n--- [TEST SCENARIO 3: SUBMIT ALL 25 ANSWERS ({mode.upper()} MODE)] ---")
    user_id, session_id = create_session(mode=mode)

    answers = []
    # 20 MCQs: some correct, some incorrect
    for i in range(20):
        answers.append({"q_index": i, "user_answer": "A" if i % 2 == 0 else "B"})

    # 5 Coding questions:
    answers.append({
        "q_index": 20,
        "user_answer": "def solution(nums, target):\n    d = {}\n    for i, n in enumerate(nums):\n        if target - n in d: return [d[target-n], i]\n        d[n] = i\n    return []"
    })
    answers.append({
        "q_index": 21,
        "user_answer": "def solution(*args):\n    pass"
    })
    answers.append({
        "q_index": 22,
        "user_answer": "def solution(:\n    syntax error here"
    })
    answers.append({
        "q_index": 23,
        "user_answer": "# Longest palindromic substring partial\ndef solution(s):\n    return s[:1] if s else ''"
    })
    answers.append({
        "q_index": 24,
        "user_answer": "def solution(s, wordDict):\n    dp = [True] + [False]*len(s)\n    for i in range(1, len(s)+1):\n        for j in range(i):\n            if dp[j] and s[j:i] in wordDict: dp[i] = True; break\n    return dp[len(s)]"
    })

    sub_resp = client.post("/api/submit-test", json={
        "session_id": session_id,
        "user_id": user_id,
        "answers": answers
    })
    assert sub_resp.status_code == 200, f"Submission failed: {sub_resp.text}"
    data = sub_resp.json()
    ar = data["answer_review"]
    assert len(ar) == 25, f"Expected 25 items, got {len(ar)}"

    # Check fields for all 25
    for item in ar:
        q_idx = int(item["q_index"])
        assert "question_type" in item
        assert "difficulty" in item
        assert "marks" in item
        assert "max_marks" in item
        assert "marks_obtained" in item
        assert "is_correct" in item
        assert "explanation" in item
        assert "correct_answer" in item
        assert len(str(item["explanation"])) > 10

        if q_idx >= 20:
            assert item["question_type"] == "coding"
            assert "reference_solution" in item
            assert "time_complexity" in item
            assert "space_complexity" in item
            assert len(str(item["time_complexity"])) > 0
            assert len(str(item["space_complexity"])) > 0
            assert "def " in str(item["reference_solution"])

    print(f" [PASS] 25 answers submission validated across all required schema fields ({mode}).")
    return ar

def test_filter_criteria_logic(ar):
    print("\n--- [TEST SCENARIO 4: FILTER CRITERIA LOGIC] ---")
    assert len(ar) == 25

    def apply_filter(reviews, review_filter):
        res = []
        for idx, item in enumerate(reviews):
            q_idx = item.get("q_index")
            q_idx_num = int(q_idx) if q_idx is not None else idx
            q_type = item.get("question_type") or item.get("type") or ("coding" if q_idx_num >= 20 else "mcq")
            if review_filter == "incorrect":
                if not item.get("is_correct"):
                    res.append(item)
            elif review_filter == "mcq":
                if q_type == "mcq":
                    res.append(item)
            elif review_filter == "coding":
                if q_type != "mcq":
                    res.append(item)
            else:
                res.append(item)
        return res

    filter_all = apply_filter(ar, "all")
    filter_mcq = apply_filter(ar, "mcq")
    filter_coding = apply_filter(ar, "coding")
    filter_incorrect = apply_filter(ar, "incorrect")

    print(f" -> Counts: ALL={len(filter_all)}, MCQ={len(filter_mcq)}, CODING={len(filter_coding)}, INCORRECT={len(filter_incorrect)}")

    assert len(filter_all) == 25, f"Expected 25 for ALL, got {len(filter_all)}"
    assert len(filter_mcq) == 20, f"Expected 20 for MCQ, got {len(filter_mcq)}"
    assert len(filter_coding) == 5, f"Expected 5 for CODING, got {len(filter_coding)}"
    assert len(filter_incorrect) > 0, f"Expected > 0 incorrect, got {len(filter_incorrect)}"

    # Ensure no filter tab produces an empty state when matching items exist
    assert len(filter_all) > 0, "Filter ALL produced empty state"
    assert len(filter_mcq) > 0, "Filter MCQ produced empty state"
    assert len(filter_coding) > 0, "Filter CODING produced empty state"
    assert len(filter_incorrect) > 0, "Filter INCORRECT produced empty state"

    # Verify that all items in filter_mcq are indeed MCQ
    for item in filter_mcq:
        q_idx = int(item["q_index"])
        assert q_idx < 20
        assert item["question_type"] == "mcq"

    # Verify that all items in filter_coding are indeed Coding
    for item in filter_coding:
        q_idx = int(item["q_index"])
        assert q_idx >= 20
        assert item["question_type"] == "coding"

    print(" [PASS] Filter logic cleanly filters ALL(25), MCQ(20), CODING(5), and INCORRECT without false empty states.")

def test_out_of_order_submission():
    print("\n--- [TEST SCENARIO 5: OUT-OF-ORDER ANSWERS SUBMISSION] ---")
    user_id, session_id = create_session(mode="mock")

    # Submit out of order: 24, 0, 15, 3
    sub_resp = client.post("/api/submit-test", json={
        "session_id": session_id,
        "user_id": user_id,
        "answers": [
            {"q_index": 24, "user_answer": "def solution(): pass"},
            {"q_index": 0, "user_answer": "A"},
            {"q_index": 15, "user_answer": "B"},
            {"q_index": 3, "user_answer": "B"}
        ]
    })
    assert sub_resp.status_code == 200
    ar = sub_resp.json()["answer_review"]
    assert len(ar) == 25
    indexes = [int(item["q_index"]) for item in ar]
    assert indexes == list(range(25)), f"answer_review is not sorted: {indexes}"
    print(" [PASS] Out of order answers properly sorted 0..24.")

def test_expired_submission():
    print("\n--- [TEST SCENARIO 6: EXPIRED SESSION SUBMISSION] ---")
    mock_sid = f"c10_exp_{uuid.uuid4().hex[:6]}"
    cleanup_sessions.add(mock_sid)
    now_utc = datetime.now(timezone.utc)
    # Session started 150 minutes ago, expired 30 minutes ago
    from skill_test.mock_session import build_mock_session, finalize_mock_session
    raw_mock = finalize_mock_session(build_mock_session("exp_user"))
    raw_mock["session_id"] = mock_sid
    raw_mock["frontend_payload"]["session_id"] = mock_sid
    raw_mock["started_at"] = (now_utc - timedelta(minutes=150)).isoformat()
    raw_mock["expires_at"] = (now_utc - timedelta(minutes=30)).isoformat()
    main._mock_sessions[mock_sid] = raw_mock

    sub_resp = client.post("/api/submit-test", json={
        "session_id": mock_sid,
        "user_id": "exp_user",
        "answers": [{"q_index": 0, "user_answer": "A"}]
    })
    assert sub_resp.status_code == 200, f"Expired submit-test failed: {sub_resp.text}"
    data = sub_resp.json()
    assert data["status"] == "submitted_expired"
    assert data["is_expired"] is True
    assert "answer_review" in data
    ar = data["answer_review"]
    assert len(ar) == 25, f"Expected 25 items on expired session, got {len(ar)}"
    print(" [PASS] Expired session submission returns full 25-question answer_review.")

def test_duplicate_and_invalid_answers():
    print("\n--- [TEST SCENARIO 7: DEFENSIVE ERROR HANDLING] ---")
    user_id, session_id = create_session(mode="mock")

    # Duplicate answer index
    dup_resp = client.post("/api/submit-test", json={
        "session_id": session_id,
        "user_id": user_id,
        "answers": [
            {"q_index": 0, "user_answer": "A"},
            {"q_index": 0, "user_answer": "B"}
        ]
    })
    assert dup_resp.status_code == 400, f"Expected 400 for duplicate answer, got {dup_resp.status_code}"

    # Invalid question index
    inv_resp = client.post("/api/submit-test", json={
        "session_id": session_id,
        "user_id": user_id,
        "answers": [
            {"q_index": 999, "user_answer": "A"}
        ]
    })
    assert inv_resp.status_code == 400, f"Expected 400 for invalid question index, got {inv_resp.status_code}"
    print(" [PASS] Defensive error handling validated (HTTP 400 on duplicate & invalid question indexes).")

def test_frontend_fallback_benchmark_dataset():
    print("\n--- [TEST SCENARIO 8: FRONTEND BENCHMARK DATASET AUDIT] ---")
    js_path = os.path.join(PROJECT_ROOT, "frontend", "src", "data", "benchmarkSolutions.js")
    assert os.path.exists(js_path), f"File missing: {js_path}"
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify 25 items are declared
    for i in range(25):
        assert f"q_index: {i}" in content or f"q_index: {i}," in content, f"Missing q_index {i} in benchmarkSolutions.js"

    # Verify time_complexity and space_complexity for 5 coding questions
    for diff in ["Two Sum", "Valid Parentheses", "Maximum Subarray", "Longest Palindromic Substring", "Word Break"]:
        assert diff in content, f"Coding challenge {diff} missing from benchmarkSolutions.js"

    assert "time_complexity: 'O(N)'" in content or 'time_complexity: "O(N)"' in content
    assert "time_complexity: 'O(N²)'" in content or 'time_complexity: "O(N²)"' in content
    assert "time_complexity: 'O(N² · K)'" in content or 'time_complexity: "O(N² · K)"' in content

    # Verify static/index.html contains BENCHMARK_25_REVIEW with 25 questions
    html_path = os.path.join(PROJECT_ROOT, "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    assert "const BENCHMARK_25_REVIEW = [" in html_content, "Missing BENCHMARK_25_REVIEW in static/index.html"
    for i in range(25):
        assert f"q_index: {i}" in html_content, f"Missing q_index {i} in static/index.html BENCHMARK_25_REVIEW"

    print(" [PASS] Frontend canonical datasets verified in benchmarkSolutions.js and static/index.html.")

if __name__ == "__main__":
    print("================================================================================")
    print("   ADVERSARIAL STRESS TEST: ASSESSMENT SUBMISSION & ANSWER REVIEW HARNESS")
    print("================================================================================")
    try:
        # Mock mode tests
        ar0_mock = test_scenario_0_answers(mode="mock")
        ar1_mock = test_scenario_1_answer(mode="mock")
        ar25_mock = test_scenario_25_answers(mode="mock")
        test_filter_criteria_logic(ar25_mock)

        # Live database mode tests
        ar0_live = test_scenario_0_answers(mode="live")
        ar1_live = test_scenario_1_answer(mode="live")
        ar25_live = test_scenario_25_answers(mode="live")
        test_filter_criteria_logic(ar25_live)

        # Edge cases & defensive
        test_out_of_order_submission()
        test_expired_submission()
        test_duplicate_and_invalid_answers()
        test_frontend_fallback_benchmark_dataset()

        print("================================================================================")
        print("   ALL 8 ADVERSARIAL STRESS SCENARIOS PASSED WITH ZERO FAILURES!")
        print("================================================================================")
    finally:
        cleanup()
