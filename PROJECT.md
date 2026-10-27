# Project: ResuListic Presentation-Ready System Integration

## Architecture
ResuListic is an AI-powered career recommendation platform featuring:
- **Backend**: FastAPI (`main.py`) serving ML/NLP models (`ml-services/`), MongoDB storage, Groq/Gemini AI question generation, AST mock code evaluation, Scikit-learn job domain classification, and salary regression models.
- **Frontend**: React 19 application (`frontend/src/`) styled with Tailwind CSS 3.4 using a Minimalist & Approachable pastel design system (soft blue, mint green, rounded cards, rounded-full buttons, soft shadows).
- **Service Layer**: Centralized API client (`frontend/src/services/api.js`) providing HTTP requests with 10s timeouts, non-intrusive demo notifications, and seamless high-fidelity mock fallbacks so the live presentation never hangs or crashes.
- **Data Flow**:
  1. `UploadResume`: Uploads resume to `POST /api/parse-resume`, receives parsed profile & skills.
  2. `SkillSelection`: Fetches skills from `GET /api/user-skills/{userId}`, allows interactive verification, passes selected skills.
  3. `Quiz`: Fetches 25 questions (20 MCQs + 3 Moderate + 2 Hard coding) from `POST /api/start-test`, tracks answers, enables real-time code evaluation via `POST /api/evaluate`, and submits to `POST /api/submit-test`.
  4. `ResultDashboard`: Gathers test scores, invokes `POST /api/predict-domain` and `POST /api/predict-salary`, and renders a 4-in-1 career intelligence suite (Test Performance, Domain Prediction, Career Switch Pathways & Skill Gaps, Compensation Intelligence in LPA).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | API Client & Demo Fallback Layer | Centralized `src/services/api.js` for all 7 endpoints with 10s timeouts & high-fidelity demo fallback models | M1 | Survey / R4 |
| 2 | Dependency & Build Safety | Ensure `tailwindcss: ^3.4.19` is explicitly in `package.json` and build succeeds | M1 | Survey / AC |
| 3 | Resume Upload Integration | Multipart form upload to `/api/parse-resume`, profile extraction, 1000ms error fallback preservation | M2 | R1.1 |
| 4 | Skill Verification Flow | Auto-fetch from `/api/user-skills/{userId}`, interactive pastel checkboxes, transfer to assessment | M2 | R1.2, R5 |
| 5 | Clean 4-Stage App Workflow | Step transitions (Upload -> Skills -> Assessment -> Intelligence), demo notification badge, state persistence | M2 | R1, R4 |
| 6 | Dynamic Assessment Engine | Start a 25-question live or deterministic mock test with a 120-minute timer, 20 MCQs, 3 moderate coding tasks, and 2 hard coding tasks | M3 | R1.3 |
| 7 | Live Code Evaluation | Real-time candidate code evaluation calling `/api/evaluate`, displaying feedback, score %, and time complexity insights | M3 | R2 |
| 8 | Test Submission & Grading | Submit answers to `/api/submit-test`, validate ownership/question indexes, compute the 5/45/50 mark breakdown, and prevent replay | M3 | R1.4 |
| 9 | 4-in-1 Dashboard: Test Performance | Overall score, precision rate, correct answer count, question-level review | M4 | R3 |
| 10 | 4-in-1 Dashboard: Domain Prediction | Primary recommended domain, confidence %, probability distribution bars via `/api/predict-domain` | M4 | R3 |
| 11 | 4-in-1 Dashboard: Career Switch Pathways | Alternative domains, feasibility tier, overlapping skills, missing skill gap analysis | M4 | R3 |
| 12 | 4-in-1 Dashboard: Compensation in LPA | Predicted salary in LPA, min-max range, compensation tier, contributing factors via `/api/predict-salary` | M4 | R3 |
| 13 | Minimalist & Approachable Pastel Polish | Soft pastel cards, friendly typography, soft shadows, rounded-full on all buttons across all views | M2-M4 | R5 |
| 14 | Regression & Build Verification | Pass all 19 existing tests (`npm test -- --watchAll=false`) and clean build (`npm run build`) | M5 | AC |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | API Client Foundation & Resilient Fallback Layer | `src/services/api.js`, `frontend/package.json` | none | DONE |
| M2 | Step Flow, Resume Parsing & Skill Verification | `src/App.js`, `src/components/UploadResume.jsx`, `src/components/SkillSelection.jsx` | M1 | DONE |
| M3 | Dynamic Assessment & Live Code Evaluation | `src/components/Quiz.jsx` (MCQs, coding challenges, `/api/evaluate`, `/api/submit-test`) | M1, M2 | DONE |
| M4 | Comprehensive 4-in-1 Career Intelligence Dashboard | `src/components/ResultDashboard.jsx` (`/api/predict-domain`, `/api/predict-salary`) | M1, M3 | DONE |
| M5 | Verification Swarm & Gate Auditing | Build verification, test suite regression checks, 2 Reviewers, 2 Challengers, 1 Auditor | M1-M4 | DONE |

## Interface Contracts
### `src/services/api.js` Contracts
- `parseResume(file, userId)` -> Promise<{ data: { profile: { name, email, ... }, enrichment: { skills: { high: [], medium: [] } } } }>
- `getUserSkills(userId)` -> Promise<{ high_confidence: string[], medium_confidence: string[] }>
- `startTest(userId, selectedSkills, mode)` -> Promise<{ session_id: string, mode: 'live'|'mock', total_questions: 25, time_limit_minutes: 120, questions: Array<{ question_type: 'mcq'|'coding', question?: string, options?: string[], title?: string, description?: string, skill?: string, difficulty?: string }> }>
- `submitTest(sessionId, userId, answers)` -> Promise<{ score: number, mcq_score: number, questions_answered: number, status: string }>
- `evaluateCode(userId, questionId, code, problemDescription, referenceSolution, mock)` -> Promise<{ passed: boolean, score: number, feedback: string, time_complexity: string }>
- `predictDomain({ userId, skills, mcqScore, codingScore })` -> Promise<{ primary_domain: string, confidence: number, domain_probabilities: Record<string, number>, switch_domains: Array<{ domain: string, feasibility: string, overlap_skills: string[], missing_skills: string[] }> }>
- `predictSalary({ userId, skills, domain, mcqScore, codingScore, experienceTier })` -> Promise<{ predicted_lpa: number, salary_range: { min_lpa: number, max_lpa: number }, compensation_tier: string, factors: Record<string, number> }>

### State Flow in `App.js`
- `currentStep`: 1 (Upload), 2 (Skills), 3 (Assessment), 4 (Intelligence)
- `userId`: defaults to "user_123"
- `resumeData`: object returned from `parseResume`
- `verifiedSkills`: array of selected skill strings passed to `startTest`
- `testResults`: object returned from `submitTest` passed to `ResultDashboard`
- `isDemoMode`: boolean flag set when fallback data is utilized, rendered as a soft pastel pill badge

### Test Suite Invariants (Critical Regression Guards)
1. `UploadResume.jsx`: Error state MUST invoke `onUploadSuccess` after exactly 1000ms (`setTimeout(..., 1000)`).
2. Live assessments MUST contain 25 questions and use a 120-minute server timestamp contract.
3. Mock assessments MUST contain 25 questions and use the same deterministic 120-minute structure without external services.
4. `ResultDashboard.jsx`: MUST intentionally throw if `results` is passed without `skill_breakdown` (required by adversarial unit test).
5. All buttons in all views MUST include `rounded-full` utility class.

## Code Layout
- `frontend/src/App.js`: Stepper navigation & step switching
- `frontend/src/services/api.js`: Centralized resilient API client with timeouts & mock fallback models
- `frontend/src/components/UploadResume.jsx`: File upload dropzone, status, and 1000ms error timer
- `frontend/src/components/SkillSelection.jsx`: Pastel skill checkboxes, auto-fetch, selection confirm
- `frontend/src/components/Quiz.jsx`: MCQ radio pills, coding editor, `/api/evaluate` trigger, submission
- `frontend/src/components/ResultDashboard.jsx`: 4-in-1 intelligence modules (Test Score, Domain Prediction, Career Switch, Salary LPA)
