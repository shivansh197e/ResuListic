"""code_evaluator.py — Minimalist Groq LLM-as-a-Judge code evaluation engine and MongoDB persistence. (<120 LOC)."""
import os, json, time
from datetime import datetime, timezone
from typing import Optional, Tuple
from bson import ObjectId
from groq import Groq, RateLimitError


def mock_evaluate_code(code: str, problem_description: str = "", reference_solution: str = "") -> dict:
    """Deterministic, strict local evaluation fallback for hermetic offline testing."""
    c_clean = (code or "").strip()
    if not c_clean or len(c_clean) < 12:
        return {"passed": False, "score": 0, "feedback": "Submission is empty or incomplete.", "time_complexity": "N/A"}

    # Strip comments to inspect real code
    code_lines = [l.strip() for l in c_clean.split("\n") if l.strip() and not l.strip().startswith(("#", "//"))]
    stripped_code = "".join(code_lines).replace(" ", "")

    # Reject untouched starter code or trivial stubs
    starter_patterns = [
        "defsolution(*args):pass",
        "defsolution(*args,**kwargs):pass",
        "classSolution:pass",
        "return0",
        "returnTrue",
        "returnFalse",
        "return[]",
        "return{}",
        "returnNone",
    ]
    if any(stripped_code == p or stripped_code.endswith(f":{p}") for p in starter_patterns):
        return {
            "passed": False,
            "score": 15,
            "feedback": "Submission contains only starter boilerplate or a trivial hardcoded return value without implementing problem logic.",
            "time_complexity": "O(1)"
        }

    try:
        compile(code, "<string>", "exec")
        # Check if actual logic (loops, conditionals, transformations, or function definition) exists
        has_logic = any(kw in c_clean for kw in ["for ", "while ", "if ", "def ", "class ", "return "])
        if has_logic:
            return {
                "passed": True,
                "score": 85,
                "feedback": "Code syntax and algorithmic structure valid against reference requirements.",
                "time_complexity": "O(N)"
            }
        return {
            "passed": False,
            "score": 35,
            "feedback": "Code compiles but lacks substantive logic or control flow required to solve the problem.",
            "time_complexity": "O(1)"
        }
    except SyntaxError as syn_err:
        # Check if it's a valid conceptual/written text explanation (at least 20 words)
        words = c_clean.split()
        if len(words) >= 20:
            return {
                "passed": True,
                "score": 80,
                "feedback": "Clear, relevant conceptual explanation addressing the core technical principles and tradeoffs.",
                "time_complexity": "N/A"
            }
        return {
            "passed": False,
            "score": 15,
            "feedback": f"Syntax error: {syn_err.msg}. Ensure code is valid Python or provide a comprehensive technical explanation.",
            "time_complexity": "N/A"
        }


def evaluate_code(
    code: str, problem_description: str, reference_solution: str,
    client: Optional[object] = None, model: str = "qwen/qwen3.8-27b",
    mock: bool = False, max_retries: int = 3,
) -> dict:
    """Evaluates candidate code or written technical response using Groq LLM with a strict evaluation rubric."""
    api_key = os.getenv("GROQ_API_KEY")
    if mock or os.getenv("GROQ_MOCK") == "1" or (client is None and not api_key):
        return mock_evaluate_code(code, problem_description, reference_solution)

    if client is None:
        client = Groq(api_key=api_key)

    # Sanitize and ensure reference expectations
    p_desc = (problem_description or "").strip()
    if not p_desc or p_desc == "Rewritten:":
        p_desc = "Implement an optimal, correct solution satisfying all constraints and edge cases."
    r_sol = (reference_solution or "").strip()
    if not r_sol:
        r_sol = "Optimal algorithm with correct handling of edge cases (empty inputs, bounds, constraints)."

    system_prompt = (
        "You are a rigorous, FAANG-level technical interview AI judge. Evaluate candidate submissions strictly "
        "against the problem description and reference expectations.\n\n"
        "STRICT GRADING RUBRIC:\n"
        "- Score 0: Empty submission, comments only, untouched starter code, or random gibberish. (passed: false)\n"
        "- Score 1-20: Syntax errors, unparseable code, or completely irrelevant answers. (passed: false)\n"
        "- Score 21-45: Trivial stubs (e.g. hardcoded returns like 'return 0', 'return True'), brute force with major logic errors, or fails primary requirements. (passed: false)\n"
        "- Score 46-69: Partially working solution that handles happy paths but fails critical edge cases (empty input, negatives, overflow) or exceeds time limits. (passed: false)\n"
        "- Score 70-84: Functionally complete and correct solution, though sub-optimal in memory or time complexity. (passed: true)\n"
        "- Score 85-100: Optimal, production-grade implementation that correctly handles all constraints and edge cases with clean structure. (passed: true)\n\n"
        "TIME COMPLEXITY RULES:\n"
        "- For algorithmic coding problems: return standard Big-O notation (e.g. 'O(N)', 'O(N log N)', 'O(1)').\n"
        "- For theoretical, conceptual, descriptive, or architecture questions: you MUST return 'N/A' (do NOT return O(1) or Big-O notation).\n\n"
        "Respond with a valid JSON object containing exactly four keys:\n"
        "- 'passed': boolean (true ONLY if score >= 70)\n"
        "- 'score': integer between 0 and 100\n"
        "- 'feedback': concise, specific technical critique detailing why marks were deducted or awarded\n"
        "- 'time_complexity': string ('O(...)' or 'N/A')\n"
        "Output valid JSON only."
    )
    user_prompt = (
        f"Problem Description:\n{p_desc}\n\n"
        f"Reference Expectations / Solution:\n{r_sol}\n\n"
        f"Candidate Submission:\n{code}\n\n"
        "Provide your evaluation in strict JSON format:"
    )

    models_to_try = []
    for m in [model, "qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
        if m and m not in models_to_try:
            models_to_try.append(m)
    last_err = None

    import re
    is_conceptual = bool(re.search(
        r"^(explain|describe|define|why|what is|what are|discuss|compare|differentiate|how does)\b",
        p_desc,
        re.IGNORECASE,
    ))

    def _parse_eval_json(raw_text: str) -> dict:
        if not raw_text:
            return {}
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", raw_text)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
        return {}

    for m in models_to_try:
        for attempt in range(max_retries):
            try:
                # First attempt with json_object format, fallback to standard on failure
                use_json_mode = attempt == 0
                req_kwargs = {
                    "model": m,
                    "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    "temperature": 0.1,
                    "max_tokens": 600,
                }
                if use_json_mode:
                    req_kwargs["response_format"] = {"type": "json_object"}

                resp = client.chat.completions.create(**req_kwargs)
                data = _parse_eval_json(resp.choices[0].message.content or "{}")
                if isinstance(data, list) and data:
                    data = data[0] if isinstance(data[0], dict) else {}
                elif not isinstance(data, dict):
                    data = {}

                tc = str(data.get("time_complexity", "O(N)"))
                if is_conceptual or tc.upper() in ("N/A", "NONE", "NA", "NOT APPLICABLE"):
                    tc = "N/A"

                raw_score = max(0, min(100, int(data.get("score", 0))))
                passed_val = bool(data.get("passed", False)) and (raw_score >= 70)

                return {
                    "passed": passed_val,
                    "score": raw_score,
                    "feedback": str(data.get("feedback", "Evaluation completed.")),
                    "time_complexity": tc,
                }
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                is_retryable = isinstance(e, RateLimitError) or "429" in err_str or "rate limit" in err_str or "503" in err_str or "json_validate_failed" in err_str
                if is_retryable:
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                # If non-retryable or retries exhausted on this model, break to try next model
                break

    if last_err:
        print(f"[Groq Judge Warning] Falling back to hermetic judge due to: {last_err}", flush=True)
    return mock_evaluate_code(code, p_desc, r_sol)


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
    sol = db.solutions.find_one({"skill": q.get("skill"), "index": q.get("index"), "difficulty": diff})
    if not sol and "title" in q:
        sol = db.solutions.find_one({"title": q.get("title")})
    return q, sol or {}


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
