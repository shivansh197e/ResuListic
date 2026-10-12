# TEST_INFRA.md — Phase 3b Code Evaluator E2E Test Infrastructure

## 1. Executive Summary & Architecture Overview

This document specifies the end-to-end (E2E) testing infrastructure for **Phase 3b: Code Evaluator (LLM-as-a-Judge)** of the ResuListic platform. The testing infrastructure is designed around the **Project Pattern 4-Tier Methodology**, verifying requirements R1 through R4 across feature contracts, edge cases, cross-feature integrations, and real-world system flows.

The Code Evaluator architecture spans:
1. **Groq LLM-as-a-Judge Engine** (`ml-services/skill_test/code_evaluator.py`): Invokes Llama-3 (`llama-3.3-70b-versatile`) with structured JSON mode and exponential backoff retry.
2. **MongoDB Stateful Persistence** (`resulistic_db.submissions`): Tracks every candidate submission with metadata, timestamp, and evaluation grades.
3. **Question & Solution Context Resolver**: Links `questions_moderate`, `questions_hard`, and `solutions` by `_id`, `(skill, index, difficulty)`.
4. **FastAPI Application Endpoint** (`POST /api/evaluate` in `main.py`): Exposes evaluation to the client with strict validation, returning HTTP 200 without unhandled 500 errors.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   4-Tier E2E Testing Architecture                      │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 1: Feature Coverage                                               │
│   ├── Exact 4-Key JSON Schema Verification                             │
│   ├── MongoDB `submissions` Document Insertion & Field Invariants      │
│   └── FastAPI `POST /api/evaluate` HTTP 200 Response Contract           │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 2: Boundary & Corner Cases                                        │
│   ├── Empty String & Minimal Placeholder (`pass`) Submission           │
│   ├── Python Syntax Error Submission Parsing & Low Scoring             │
│   └── Invalid & Non-Existent `question_id` (404/422 without 500)       │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 3: Cross-Feature Combinations                                     │
│   ├── Mock Mode vs. Live Groq Mode Dual-Execution                      │
│   ├── Rate-Limit HTTP 429 Exponential Backoff & Retry Logic            │
│   └── Cross-Collection Context Resolution (Moderate, Hard, Solutions)  │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 4: Real-World Application Scenarios                               │
│   ├── End-to-End Live MongoDB Atlas & FastAPI TestClient Integration   │
│   └── Full Lifecycle CRUD, Assessment, Assertion & Cleanup             │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 4-Tier Test Methodology & Coverage Matrix

| Tier | Test ID | Target Component | Description / Assertion | Authoritative Source | Pass Criteria |
|---|---|---|---|---|---|
| **Tier 1: Feature Coverage** | `T1.1` | `evaluate_code` | Verifies evaluation returns exact 4 keys: `passed`, `score`, `feedback`, `time_complexity` with correct types. | ORIGINAL_REQUEST R1, PROJECT.md F1 | Exactly 4 keys; `passed` is bool; `score` in [0, 100]; non-empty strings for `feedback` & `time_complexity`. |
| | `T1.2` | `save_submission` | Verifies document insertion into MongoDB `submissions` with required fields (`user_id`, `question_id`, `submitted_code`, `timestamp`, `evaluation`). | ORIGINAL_REQUEST R2, PROJECT.md F2 | Document exists in MongoDB Atlas; valid ObjectId string returned; cleanup completes. |
| | `T1.3` | `POST /api/evaluate` | Verifies FastAPI endpoint processes valid submission payload and returns HTTP 200 with `EvaluateResponse` schema. | ORIGINAL_REQUEST R3, PROJECT.md F4 | HTTP 200; valid JSON matching schema; zero 500 Internal Server Errors. |
| **Tier 2: Boundary & Corner Cases** | `T2.1` | Empty / Placeholder Code | Submitting empty string `""` or placeholder `pass`. | ORIGINAL_REQUEST R1, R4 | Returns valid 4-key schema; `passed=False`; `score <= 30`. |
| | `T2.2` | Syntax Error Code | Submitting code with invalid Python syntax (e.g. unclosed parenthesis/blocks). | ORIGINAL_REQUEST R1 | Returns valid 4-key schema; `passed=False`; `score <= 30`; feedback cites syntax issue. |
| | `T2.3` | Invalid / Non-Existent Question ID | Submitting non-existent or malformed `question_id` without explicit problem text. | ORIGINAL_REQUEST R3, PROJECT.md F4 | Returns HTTP 404 / 422; no unhandled 500 Internal Server Error. |
| **Tier 3: Cross-Feature Combinations** | `T3.1` | Mock vs. Live Dual-Mode | Tests deterministic execution via `mock=True` / `GROQ_MOCK=1` and live Groq SDK if configured. | ORIGINAL_REQUEST R4, PROJECT.md F5 | Deterministic 0ms execution offline; seamless live execution if `GROQ_API_KEY` present. |
| | `T3.2` | Rate Limit Exponential Backoff | Simulates Groq HTTP 429 `RateLimitError` on attempt 1, followed by successful response on attempt 2. | ORIGINAL_REQUEST R2, PROJECT.md F5 | Exponential delay observed; retry count matches; evaluation completes successfully. |
| | `T3.3` | Question Context Resolution | Resolves question details and hidden reference solutions across `questions_moderate`, `questions_hard`, and `solutions`. | PROJECT.md F3 | Successfully resolves both moderate and hard questions with corresponding reference solutions. |
| **Tier 4: Real-World Scenarios** | `T4.1` | Live E2E Integration | Full lifecycle execution using live MongoDB Atlas connection and FastAPI `TestClient`: submit -> grade -> persist -> retrieve -> cleanup. | ORIGINAL_REQUEST Criteria, PROJECT.md F6 | Complete round-trip succeeds; HTTP 200; valid submission stored and cleanly deleted. |

---

## 3. Mathematical & Schema Validation Specifications

### 3.1 Strict 4-Key JSON Output Invariant
Every evaluation result $R$ must satisfy:
$$\text{keys}(R) = \{\text{'passed'}, \text{'score'}, \text{'feedback'}, \text{'time\_complexity'}\}$$
$$R[\text{'passed'}] \in \{\text{True}, \text{False}\}$$
$$R[\text{'score'}] \in \mathbb{Z} \quad \text{such that} \quad 0 \le R[\text{'score'}] \le 100$$
$$\text{len}(R[\text{'feedback'}]) > 0 \quad \land \quad \text{len}(R[\text{'time\_complexity'}]) > 0$$

### 3.2 MongoDB `submissions` Document Invariant
Each persisted submission document $D$ in `db.submissions` must satisfy:
$$D \supseteq \{\text{'user\_id'}, \text{'question\_id'}, \text{'submitted\_code'}, \text{'timestamp'}, \text{'passed'}, \text{'score'}, \text{'feedback'}, \text{'time\_complexity'}, \text{'evaluation'}\}$$
$$\text{is\_valid\_iso8601}(D[\text{'timestamp'}]) = \text{True}$$

### 3.3 HTTP Status Invariant
For any client payload $P$ sent to `POST /api/evaluate`:
$$\text{status\_code}(P) \in \{200, 400, 404, 422\}$$
$$\text{status\_code}(P) \ne 500 \quad \text{(Zero Unhandled 500 Server Errors)}$$

---

## 4. Test Isolation and Environment Resilience

1. **Deterministic Offline Capability**:
   The test suite supports complete offline execution without requiring internet access or paid API keys by using `mock=True` and built-in mock clients. When `GROQ_API_KEY` is present, live Groq evaluation is automatically tested.
2. **Database Cleanliness & Test Isolation**:
   Every test case writing to the live MongoDB `submissions` collection registers its inserted `_id` and executes an explicit post-test cleanup (`delete_one({"_id": inserted_id})`), ensuring zero database pollution.
3. **Resilience to Optional Subsystems**:
   FastAPI `app` in `main.py` is loaded via `starlette.testclient.TestClient`. Optional ML modules (such as spaCy models or Gemini generators) are safeguarded with graceful fallbacks so the code evaluator can be tested without unnecessary dependencies.

---

## 5. Master Test Runner Specification (`verify_evaluator.py`)

- **Executable Location**: `d:\ResuListic\verify_evaluator.py`
- **Execution Command**: `.\venv\Scripts\python.exe verify_evaluator.py`
- **Output Protocol**:
  - Detailed per-stage banner logging.
  - Granular assertion status messages.
  - Summary table reporting total tests passed, failed, and skipped.
  - Process exit code `0` on 100% test pass; non-zero exit code on any failure.
