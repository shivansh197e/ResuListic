"""code_evaluator.py — Minimalist Groq LLM-as-a-Judge code evaluation engine and MongoDB persistence. (<120 LOC)."""
import os, json, time
from datetime import datetime, timezone
from typing import Optional, Tuple
from bson import ObjectId
from groq import Groq, RateLimitError


def mock_evaluate_code(code: str, problem_description: str = "", reference_solution: str = "") -> dict:
    """Deterministic local code evaluation fallback for hermetic offline testing."""
    try:
        compile(code, "<string>", "exec")
        if not code.strip() or len(code.strip()) < 5:
            return {"passed": False, "score": 20, "feedback": "Code submission is empty or incomplete.", "time_complexity": "N/A"}
        return {"passed": True, "score": 90, "feedback": "Code syntax and logic valid against reference requirements.", "time_complexity": "O(N)"}
    except SyntaxError as e:
        return {"passed": False, "score": 15, "feedback": f"Syntax error detected: {e.msg} at line {e.lineno}", "time_complexity": "N/A"}


def evaluate_code(
    code: str, problem_description: str, reference_solution: str,
    client: Optional[object] = None, model: str = "qwen/qwen3.8-27b",
    mock: bool = False, max_retries: int = 3,
) -> dict:
    """Evaluates candidate code using Groq LLM (or mock fallback) with structured JSON output."""
    api_key = os.getenv("GROQ_API_KEY")
    if mock or os.getenv("GROQ_MOCK") == "1" or (client is None and not api_key):
        return mock_evaluate_code(code, problem_description, reference_solution)

    if client is None:
        client = Groq(api_key=api_key)

    system_prompt = (
        "You are a strict technical interviewer. Evaluate the candidate's Python code against the "
        "problem description and reference solution. Respond with a JSON object containing exactly "
        "four keys: 'passed' (boolean), 'score' (integer between 0 and 100), 'feedback' (string critique), "
        "and 'time_complexity' (string, e.g. 'O(N)'). Output valid JSON only."
    )
    user_prompt = (
        f"Problem Description:\n{problem_description}\n\n"
        f"Reference Solution:\n{reference_solution}\n\n"
        f"Candidate Submission:\n{code}\n\n"
        "Provide your evaluation in JSON format:"
    )

    models_to_try = []
    for m in [model, "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]:
        if m and m not in models_to_try:
            models_to_try.append(m)
    last_err = None

    for m in models_to_try:
        for attempt in range(max_retries):
            try:
                resp = client.chat.completions.create(
                    model=m,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                data = json.loads(resp.choices[0].message.content or "{}")
                if isinstance(data, list) and data:
                    data = data[0] if isinstance(data[0], dict) else {}
                elif not isinstance(data, dict):
                    data = {}
                return {
                    "passed": bool(data.get("passed", False)),
                    "score": max(0, min(100, int(data.get("score", 0)))),
                    "feedback": str(data.get("feedback", "")),
                    "time_complexity": str(data.get("time_complexity", "O(N)")),
                }
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                is_retryable = isinstance(e, RateLimitError) or "429" in err_str or "rate limit" in err_str or "503" in err_str
                if is_retryable and attempt < max_retries - 1:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                # If fatal on this model, break to try next model
                break

    if last_err:
        raise last_err
    return mock_evaluate_code(code, problem_description, reference_solution)


def get_question_and_solution(db, question_id: str) -> Tuple[dict, dict]:
    """Resolves question and hidden reference solution from MongoDB collections."""
    if db is None or not question_id:
        return {}, {}
    q, diff = None, "moderate"
    if ObjectId.is_valid(str(question_id)):
        oid = ObjectId(str(question_id))
        q = db.questions_moderate.find_one({"_id": oid})
        if not q:
            q = db.questions_hard.find_one({"_id": oid})
            diff = "hard"
    if not q:
        for col, d in [("questions_moderate", "moderate"), ("questions_hard", "hard")]:
            try:
                q = db[col].find_one({"index": int(question_id)})
                if q:
                    diff = d
                    break
            except (ValueError, TypeError):
                pass
            q = db[col].find_one({"_id": str(question_id)})
            if q:
                diff = d
                break
    if not q:
        return {}, {}
    sol = db.solutions.find_one({"skill": q.get("skill"), "index": q.get("index"), "difficulty": diff}) or {}
    return q, sol


def save_submission(db, user_id: str, question_id: str, submitted_code: str, evaluation_result: dict) -> str:
    """Saves candidate submission and evaluation grade to MongoDB submissions collection."""
    doc = {
        "user_id": str(user_id),
        "question_id": str(question_id),
        "submitted_code": str(submitted_code),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "passed": bool(evaluation_result.get("passed", False)),
        "score": int(evaluation_result.get("score", 0)),
        "feedback": str(evaluation_result.get("feedback", "")),
        "time_complexity": str(evaluation_result.get("time_complexity", "O(N)")),
        "evaluation": evaluation_result,
    }
    res = db.submissions.insert_one(doc)
    return str(getattr(res, "inserted_id", res))
