# Project: ResuListic Phase 3b — Code Evaluator (LLM-as-a-Judge)

## Architecture
The Code Evaluator module serves as the automated technical interviewer for the ResuListic platform. It analyzes a candidate's submitted Python code against problem descriptions and hidden reference solutions stored in MongoDB Atlas, using Groq API (Llama-3) in structured JSON mode. Every graded submission is persisted to the MongoDB `submissions` collection, and the capability is exposed via a FastAPI endpoint `POST /api/evaluate`.

```
Candidate / Frontend
        │
        ▼ POST /api/evaluate (user_id, question_id, code)
   [FastAPI app (main.py)]
        │
        ├──▶ [Question Resolver (code_evaluator.py)] ──▶ [MongoDB: questions_moderate / questions_hard / solutions]
        │
        ├──▶ [Groq LLM-as-a-Judge (code_evaluator.py)] ──▶ [Groq API: llama-3.3-70b-versatile / Mock Fallback]
        │         └── Returns structured JSON: {passed, score, feedback, time_complexity}
        │
        └──▶ [Submissions Persistence (code_evaluator.py)] ──▶ [MongoDB: submissions collection]
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Groq LLM-as-a-Judge Engine | Python module with official `groq` SDK invoking Llama-3 (`llama-3.3-70b-versatile`) with structured JSON mode returning exact 4 keys: `passed`, `score`, `feedback`, `time_complexity` | M1 | ORIGINAL_REQUEST R1 |
| F2 | MongoDB Stateful Tracking | Function saving every submission into `submissions` collection containing `user_id`, `question_id`, `submitted_code`, `timestamp`, and full evaluation result | M1 | ORIGINAL_REQUEST R2 |
| F3 | Question & Solution Context Resolution | Resolves question description and hidden reference solution by `question_id` (ObjectId or index) from `questions_moderate`, `questions_hard`, and `solutions` | M1 | Survey Finding |
| F4 | FastAPI Integration | Exposes `POST /api/evaluate` accepting `user_id`, `question_id`, `code`, executing evaluation, persisting to DB, returning HTTP 200 with grade | M2 | ORIGINAL_REQUEST R3 |
| F5 | Ponytail Minimalism & Resilience | Minimalist code (<120 LOC in evaluator), no heavy abstractions, exponential backoff for rate limits, deterministic mock fallback for offline testability | M1, M2 | ORIGINAL_REQUEST R4 |
| F6 | Automated E2E Verification Suite | Test script `verify_evaluator.py` asserting exact 4-key JSON schema, MongoDB insertion verification, and FastAPI HTTP 200 without 500 errors | E2E / M3 | ORIGINAL_REQUEST Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Requirement-driven test suite (`TEST_INFRA.md`, `verify_evaluator.py`, `TEST_READY.md`) covering Tiers 1-4 | Survey complete | DONE |
| M1 | Core Evaluator & MongoDB Storage | `ml-services/skill_test/code_evaluator.py` and `ml-services/schema/question_schema.py` | None | DONE |
| M2 | FastAPI Route Integration | Mount `POST /api/evaluate` in `main.py` with payload validation and error handling | M1 | DONE |
| M3 | Final Milestone & Hardening | Pass 100% of E2E tests (`verify_evaluator.py`), adversarial coverage hardening, Forensic Audit | M1, M2, E2E | DONE |

## Interface Contracts

### Data Contracts (`ml-services/schema/question_schema.py`)
```python
class EvaluateRequest(BaseModel):
    user_id: str
    question_id: str
    code: str
    problem_description: Optional[str] = None
    reference_solution: Optional[str] = None
    mock: Optional[bool] = False

class CodeEvaluationResult(BaseModel):
    passed: bool
    score: int = Field(ge=0, le=100)
    feedback: str
    time_complexity: str

class EvaluateResponse(BaseModel):
    passed: bool
    score: int
    feedback: str
    time_complexity: str
    submission_id: str
```

### Module Interface (`ml-services/skill_test/code_evaluator.py`)
```python
def evaluate_code(
    code: str,
    problem_description: str,
    reference_solution: str,
    client: Optional[object] = None,
    model: str = "llama-3.3-70b-versatile",
    mock: bool = False,
    max_retries: int = 3,
) -> dict: ...

def get_question_and_solution(db, question_id: str) -> tuple[dict, dict]: ...

def save_submission(
    db,
    user_id: str,
    question_id: str,
    submitted_code: str,
    evaluation_result: dict,
) -> str: ...
```

### API Endpoint (`main.py`)
- Route: `POST /api/evaluate`
- Input: `EvaluateRequest` (JSON)
- Output: `EvaluateResponse` (JSON, status 200)
- Errors: 404 if question not found, 422 on invalid schema, 500 prevented via graceful handling

## Code Layout
- `ml-services/skill_test/code_evaluator.py`: Core Groq evaluator, mock engine, and db persistence
- `ml-services/schema/question_schema.py`: Pydantic request and response models
- `main.py`: FastAPI application mounting `POST /api/evaluate`
- `verify_evaluator.py`: Acceptance test script at project root
- `requirements.txt`: Project dependencies (adding `groq>=0.11.0` and `python-multipart`)
