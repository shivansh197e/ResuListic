# TEST_INFRA.md — ResuListic React SPA Integration E2E Test Infrastructure

## 1. Executive Summary & Architecture Overview

This document specifies the end-to-end (E2E) testing infrastructure for **Milestone 7: React SPA Integration** of the ResuListic recruitment and assessment platform. The testing infrastructure is designed around the **Project Pattern 4-Tier Test Case Design Methodology**, verifying all functional requirements (R1–R4 from `ORIGINAL_REQUEST.md`), interface contracts from `SCOPE.md`, and adversarial regression invariants across feature contracts, boundary conditions, cross-module workflows, and real-world workloads.

The integrated full-stack architecture encompasses:
1. **Zero-Build React + Tailwind SPA Delivery via FastAPI** (`http://localhost:8000/`):
   - Fast static route serving from `static/index.html` via Starlette `FileResponse` / `StaticFiles`.
   - Browser runtime: React 18 UMD, ReactDOM 18 UMD, Babel Standalone, Tailwind CSS Play CDN (with pastel theme configuration), and Axios.
   - Immediate zero-build execution without requiring local Node.js or npm dependencies.
2. **Resume Intake & Skill Extraction**:
   - `POST /api/parse-resume`: Multipart upload (`.pdf`, `.docx`, `.png`, `.jpg`, `.jpeg`), OCR/text parsing, MongoDB Atlas `resumes` persistence.
   - `GET /api/user-skills/{user_id}`: High and Medium confidence skill taxonomy retrieval.
3. **2-Hour Time-Bound Assessment Engine**:
   - `POST /api/start-test`: 25-question dynamic session (20 MCQs, 3 Moderate Coding, 2 Hard Coding, 120:00 countdown timer contract, `TestSessionOut` public payload).
   - `POST /api/submit-test`: 120-minute deadline boundary enforcement (`submitted` vs. `submitted_expired`), completed MCQ auto-grading, and answer persistence.
4. **Code Evaluator (LLM-as-a-Judge)**:
   - `POST /api/evaluate`: Groq LLM-as-a-Judge (`qwen/qwen3.8-27b`) with exponential backoff and deterministic offline AST mock fallback (<5ms), returning `passed`, `score`, `feedback`, `time_complexity`.
5. **Career Intelligence & Salary Prediction**:
   - `POST /api/predict-domain`: 5-domain classifier, match confidence, class probabilities, and career switch pathways with skill gap pills.
   - `POST /api/predict-salary`: Gradient Boosting Regressor (4.0 to 35.0 LPA), min-max range, compensation tiers, and itemized value drivers.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   4-Tier E2E Testing Architecture                      │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 1: Feature Coverage (Isolated Functional Verification)            │
│   ├── Static SPA Route Serving (`GET /`, `static/index.html`)          │
│   ├── Resume Upload & Parsing (`POST /api/parse-resume`)               │
│   ├── User Skill Taxonomy Fetching (`GET /api/user-skills/{id}`)       │
│   ├── 25-Question Assessment Session Start (`POST /api/start-test`)    │
│   ├── Code Evaluation Engine (`POST /api/evaluate`)                    │
│   ├── Test Submission & Auto-Grading (`POST /api/submit-test`)         │
│   ├── Job Domain & Career Switch Engine (`POST /api/predict-domain`)   │
│   └── 4.0-35.0 LPA Salary Prediction (`POST /api/predict-salary`)      │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 2: Boundary & Corner Cases                                        │
│   ├── Unsupported Upload Extensions (.txt, .exe, .bin -> HTTP 400)    │
│   ├── 120m Timer Expiration Status ("submitted_expired", is_expired)   │
│   ├── Python Code Syntax Error AST Evaluation (score <= 30, no 500)   │
│   ├── Empty String & Whitespace Code Evaluation Rejection              │
│   ├── Missing Optional Parameters (skills, scores, resume text)        │
│   ├── Score Normalization ([0, 5] scale -> [0, 100], extreme bounds)   │
│   ├── Boundary Salary Clamping ([4.0, 35.0] LPA invariants)            │
│   └── Non-Existent User & Session Handling (HTTP 404)                  │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 3: Cross-Feature Combinations & State Transitions                 │
│   ├── Full Candidate Workflow (Upload -> Skills -> Test -> Dashboard)  │
│   ├── Deterministic Mock Evaluation Fallback Resilience                │
│   ├── Salary Predictor Domain Auto-Inference from Skill Keywords       │
│   └── Hybrid MongoDB User Resolution vs. Direct Parameter Overrides    │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 4: Real-World Workloads & Invariants Assertion                    │
│   ├── Complete Real-World Candidate Lifecycle Roundtrip                │
│   ├── Invariant 1: 1000ms Upload Fallback Timer (`setTimeout`, 1000)   │
│   ├── Invariant 2: `SESSION_ALPHA_099` 2-Question Fallback Session     │
│   ├── Invariant 3: `94%`, `S+`, `5/5` Fallback Result Values           │
│   ├── Invariant 4: Universal `rounded-full` Action Button Styling      │
│   ├── Invariant 5: Mandatory Throw on Missing `skill_breakdown`        │
│   ├── Invariant 6: `package.json` Explicit `"tailwindcss": "^3.4.19"`  │
│   └── Invariant 7: Zero-Build React 18 SPA Architecture Contract       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 4-Tier Test Methodology & Coverage Matrix

| Tier | Test ID | Target Component | Description / Assertion | Authoritative Source | Pass Criteria |
|---|---|---|---|---|---|
| **Tier 1: Feature Coverage** | `T1.1` | Static SPA Serving | `GET /` returns HTTP 200 with HTML or SPA container, scripts for React/Tailwind/Babel. | SCOPE.md F1, ORIGINAL_REQUEST R1 | Status 200; HTML contains `<div id="root">`, React 18, and Tailwind CDN. |
| | `T1.2` | Resume Parsing | `POST /api/parse-resume` parses candidate resume (PDF/DOCX) and returns profile + skills. | SCOPE.md F5, ORIGINAL_REQUEST R2 | Status 200; returns extracted profile, contact, and high/medium skills. |
| | `T1.3` | User Skills | `GET /api/user-skills/{id}` returns candidate high and medium confidence skills. | SCOPE.md F6, ORIGINAL_REQUEST R2 | Status 200; `high_confidence` and `medium_confidence` are lists of strings. |
| | `T1.4` | Start Test Session | `POST /api/start-test` generates 25-question session with 120m deadline contract. | SCOPE.md F7, F8, ORIGINAL_REQUEST R3 | Status 200; 25 questions (20 MCQ, 3 Mod, 2 Hard); `time_limit_minutes: 120`; answers stripped. |
| | `T1.5` | Code Evaluator | `POST /api/evaluate` evaluates Python code via Groq LLM or deterministic AST mock. | SCOPE.md F9, ORIGINAL_REQUEST R3 | Status 200; exact 4 keys: `passed` (bool), `score` (0-100), `feedback`, `time_complexity`. |
| | `T1.6` | Submit Test | `POST /api/submit-test` submits answers within deadline; returns score & status. | SCOPE.md F10, ORIGINAL_REQUEST R3 | Status 200; `status: "submitted"`; `is_expired: false`; completed MCQs graded. |
| | `T1.7` | Domain Predictor | `POST /api/predict-domain` predicts job domain, probabilities, and switch gaps. | SCOPE.md F12, F13, ORIGINAL_REQUEST R4 | Status 200; 5 domain probabilities sum to ~1.0; top 3 switch domains identified. |
| | `T1.8` | Salary Predictor | `POST /api/predict-salary` predicts compensation package (4.0 - 35.0 LPA) & drivers. | SCOPE.md F14, ORIGINAL_REQUEST R4 | Status 200; `predicted_lpa` in [4.0, 35.0]; `salary_range` bounded; factors list populated. |
| **Tier 2: Boundary & Corner Cases** | `T2.1` | Unsupported Upload | `POST /api/parse-resume` with unsupported extension (`.txt`, `.exe`, `.bin`). | explorer_survey_7_3 Edge Case 1 | Status 400 Bad Request; detail `"Unsupported file format."`. |
| | `T2.2` | Timer Expiration | `POST /api/submit-test` after 120m deadline has elapsed (`> 7200s`). | ORIGINAL_REQUEST 2026-10-12 R3 | Status 200; `status: "submitted_expired"`; `is_expired: true`; answers preserved. |
| | `T2.3` | Code Syntax Error | `POST /api/evaluate` with invalid Python syntax (`def foo(:`). | explorer_survey_7_3 Edge Case 12 | Status 200; `passed: false`; `score <= 30`; feedback identifies syntax error; zero 500s. |
| | `T2.4` | Empty/Blank Code | `POST /api/evaluate` with empty string `""` or whitespace. | explorer_survey_7_3 Edge Case 13 | Status 200; `passed: false`; `score <= 30`. |
| | `T2.5` | Missing Parameters | `POST /api/predict-domain` and `predict-salary` with omitted optional fields. | explorer_survey_7_3 Edge Case 16 | Status 200; handles gracefully using defaults; zero 500 errors. |
| | `T2.6` | Score Normalization | `POST /api/predict-domain` with 0-5 scale score (`4.5` -> `90.0`); outlier clamping. | explorer_survey_7_3 Edge Case 15, 17 | Status 200; normalized to [0, 100] scale safely. |
| | `T2.7` | Salary Clamping | `POST /api/predict-salary` with extreme minimal and maximal profiles. | ORIGINAL_REQUEST R4, SCOPE.md F14 | `predicted_lpa` strictly clamped to $[4.0, 35.0]$ LPA across all profiles. |
| | `T2.8` | Non-Existent Resources | `GET /api/user-skills/ghost` and invalid session submit. | explorer_survey_7_3 Edge Case 3, 8 | Status 404 Not Found; clean client error handling. |
| **Tier 3: Cross-Feature Combinations** | `T3.1` | Full Workflow Transitions | Upload -> Skills -> Assessment -> Career Intelligence end-to-end chain. | SCOPE.md Workflow, ORIGINAL_REQUEST AC | State transitions seamlessly; outputs from earlier steps feed later steps. |
| | `T3.2` | Mock Evaluator Fallback | `POST /api/evaluate` with `mock: true` or offline environment. | SCOPE.md F9, ORIGINAL_REQUEST R3 | Returns structured 4-key grade in < 5ms without external API dependencies. |
| | `T3.3` | Salary Domain Inference | `POST /api/predict-salary` with omitted domain auto-infers from skill keywords. | explorer_survey_7_3 Edge Case 18 | Successfully maps skills to domain (e.g. React -> Frontend, PyTorch -> AI/ML). |
| | `T3.4` | MongoDB User Resolution | `POST /api/predict-domain` & `predict-salary` with `user_id` resolves profile from DB. | explorer_survey_7_3 Section 5.4, 5.5 | Auto-fetches skills and generates predictions without redundant payload data. |
| **Tier 4: Real-World Workloads & Invariants** | `T4.1` | Real-World Candidate Lifecycle | Full candidate journey simulation with timing, evaluation, scoring, and cleanup. | ORIGINAL_REQUEST AC, SCOPE.md M5 | Full lifecycle succeeds with HTTP 200, valid records persisted, and clean purge. |
| | `T4.2` | Invariant: 1000ms Upload Timer | `UploadResume` / `UploadSection` triggers fallback after exactly 1000ms. | SCOPE.md Guard 1, adversarial test | `setTimeout(..., 1000)` present; verified via source AST/string inspection. |
| | `T4.3` | Invariant: SESSION_ALPHA_099 | `Quiz` / `AssessmentEngine` fallback includes `SESSION_ALPHA_099` & 2 questions. | SCOPE.md Guard 2, challenger test | Contains `SESSION_ALPHA_099`, `Question 1 of 2`, `Question 2 of 2`. |
| | `T4.4` | Invariant: 94% / S+ / 5/5 | `ResultDashboard` / `ReportDashboard` fallback defaults to 94%, S+, 5/5. | SCOPE.md Guard 3, adversarial test | Contains `94%`, `S+`, `5/5`, and `"Exceptional mastery demonstrated"`. |
| | `T4.5` | Invariant: Universal rounded-full | All interactive action buttons include Tailwind class `rounded-full`. | SCOPE.md Guard 5, challenger test | Buttons in components and static SPA use `rounded-full` styling. |
| | `T4.6` | Invariant: Throw on Missing Breakdown | `ResultDashboard` MUST throw if passed `results` without `skill_breakdown`. | SCOPE.md Guard 4, challenger test | Adversarial guard verified: no optional chaining or fallback swallows missing breakdown. |
| | `T4.7` | Invariant: package.json Tailwind | `frontend/package.json` explicitly declares `"tailwindcss": "^3.4.19"`. | SCOPE.md Guard 6 | `package.json` contains `"tailwindcss": "^3.4.19"` in dependencies or devDependencies. |
| | `T4.8` | Invariant: Zero-Build SPA Serving | `static/index.html` runs in-browser with zero Node.js build steps. | SCOPE.md Guard 7, ORIGINAL_REQUEST R1 | Self-contained HTML with React 18 UMD, ReactDOM, Babel, Tailwind Play CDN. |

---

## 3. Mathematical & Schema Validation Specifications

### 3.1 Strict 4-Key JSON Code Evaluation Invariant
Every evaluation response $E$ from `POST /api/evaluate` must satisfy:
$$\text{keys}(E) \supseteq \{\text{'passed'}, \text{'score'}, \text{'feedback'}, \text{'time\_complexity'}, \text{'submission\_id'}\}$$
$$E[\text{'passed'}] \in \{\text{True}, \text{False}\}$$
$$E[\text{'score'}] \in \mathbb{Z} \quad \text{such that} \quad 0 \le E[\text{'score'}] \le 100$$
$$\text{len}(E[\text{'feedback'}]) > 0 \quad \land \quad \text{len}(E[\text{'time\_complexity'}]) > 0$$

### 3.2 120-Minute Timed Session Invariant
For every generated test session $S$:
$$S[\text{'time\_limit\_minutes'}] = 120$$
$$T_{\text{expires}} = T_{\text{started}} + 120 \times 60 \text{ seconds}$$
For submissions submitted at timestamp $T_{\text{sub}}$:
$$\text{status} = \begin{cases} 
\text{"submitted"}, & \text{if } T_{\text{sub}} \le T_{\text{expires}} \\
\text{"submitted\_expired"}, & \text{if } T_{\text{sub}} > T_{\text{expires}}
\end{cases}$$

### 3.3 Salary Prediction Bounding Invariant
For any predicted salary result $R_{\text{sal}}$:
$$4.0 \le R_{\text{sal}}[\text{'predicted\_lpa'}] \le 35.0$$
$$R_{\text{sal}}[\text{'salary\_range'}][\text{'min\_lpa'}] \le R_{\text{sal}}[\text{'predicted\_lpa'}] \le R_{\text{sal}}[\text{'salary\_range'}][\text{'max\_lpa'}]$$

### 3.4 Job Domain Classification Probability Invariant
For domain prediction result $D$:
$$D[\text{'primary\_domain'}] \in \{\text{"Frontend Web Development"}, \text{"Backend Web Development"}, \text{"Data Science \& AI/ML"}, \text{"Cloud \& DevOps"}, \text{"Mobile App Development"}\}$$
$$\sum_{k} D[\text{'domain\_probabilities'}][k] \approx 1.0 \quad (\pm 0.05)$$

### 3.5 HTTP Status Code Invariant
For any client payload sent to any endpoint $P \in \{\text{parse-resume, user-skills, start-test, submit-test, evaluate, predict-domain, predict-salary}\}$:
$$\text{status\_code}(P) \in \{200, 400, 404, 422\}$$
$$\text{status\_code}(P) \ne 500 \quad \text{(Zero Unhandled 500 Server Errors on Malformed Inputs)}$$

---

## 4. Test Isolation, Environment Resilience & Demo Fallback Strategy

1. **Deterministic Offline Capability**:
   - The test suite executes completely without requiring active internet connectivity or paid API quotas.
   - Code evaluation uses `mock=True` (AST compiler fallback), job classification and salary regression execute against local pre-trained `joblib` artifacts, and assessment MCQ generation includes deterministic offline templates.
2. **Database Cleanliness & Test Isolation**:
   - Every test case writing to the live MongoDB Atlas database (`resumes`, `test_sessions`, `test_submissions`, `submissions`) registers its unique prefixed ID (e.g. `test_spa_e2e_*`) and executes strict teardown logic in `tearDownClass`, maintaining zero database pollution.
3. **Dual-Layer Architecture Validation**:
   - The test suite validates both Layer A (FastAPI zero-build static route serving on `http://localhost:8000/`) and Layer B (clean modular frontend source tree in `frontend/`).
   - If frontend files are during active materialization, the test suite supports graceful progressive verification while maintaining strict assertion of all critical invariants.

---

## 5. Master Test Runner Specification (`verify_spa.py`) and Unittest Suite

### 5.1 Primary Unittest Framework Runner
```powershell
.\venv\Scripts\python.exe -m unittest tests/test_spa_integration.py
```

### 5.2 Master Verification Runner
```powershell
.\venv\Scripts\python.exe verify_spa.py
```

### 5.3 Verification Output Protocol
- Stage banners for each of the 4 Tiers.
- Granular assertion status messages with elapsed timings.
- Summary scoreboard reporting total tests executed, passed, failed, and skipped.
- Strict process exit code `0` on 100% pass; non-zero exit code on any regression or failure.
