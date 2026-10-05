# Project: ResuListic ETL Pipeline (data_builder.py)

## Architecture
- **Input**: CSV datasets (streaming chunks via stdlib `csv.DictReader` + `itertools.islice`).
- **Transformation**: Question mutation via `google-genai` SDK (`gemini-2.5-flash`), enforcing Pydantic schema `MutatedQuestion` for structured JSON output. Resilient 429 exponential backoff retry.
- **Output**: MongoDB Atlas collections in `resulistic_db`:
  - `questions_moderate`: Moderate questions (`CodingQuestionDoc`: `skill`, `index`, `title`, `description`, `source`, `source_url`, `tags`).
  - `questions_hard`: Hard questions (`CodingQuestionDoc`), indexed sequentially `0..N-1` for circular tracker.
  - `solutions`: Reference solutions (`SolutionDoc`: `skill`, `index`, `difficulty`, `reference_solution`, `explanation`).
- **Philosophy**: Ponytail Mode (extreme minimalism, standard library where possible, < 200 lines, zero speculative bloat).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | CSV Chunk Streaming | Memory-efficient chunked streaming of CSV rows using stdlib `csv.DictReader` + `islice` | M1 | Survey (R1, R3) |
| 2 | Column Normalization & Parsing | Flexible column mapping (`skill`, `difficulty`, `title`, `description`, `solution`, `tags`) | M1 | Survey (R1) |
| 3 | Indexing & Model Routing | Assign 0-based sequential indices per skill/difficulty and route to moderate vs hard | M1 | Survey (R1) |
| 4 | Pydantic Mutation Contract | `MutatedQuestion` schema (`mutated_title`, `mutated_description`, `mutated_solution`, `variable_mapping`, `explanation`) | M2 | Survey (R2) |
| 5 | Gemini LLM Mutation | Rewrites problem story/context and solution variables while keeping logic, complexity, constraints intact | M2 | Survey (R2) |
| 6 | 429 Rate Limit Resilience | Exponential backoff retry catching `google.genai.errors.APIError` / `ClientError` (code 429) | M2 | Survey (R2) |
| 7 | MongoDB Bulk Loading | High-performance bulk insert operations via `insert_many(..., ordered=False)` | M3 | Survey (R1) |
| 8 | Pipeline Integration & CLI | End-to-end `data_builder.py` executable from CLI and reusable from `ml-services` | M3 | Survey (R1) |
| 9 | Ponytail Minimalism Guard | Verification that implementation is minimal, stdlib-first, concise, and bloat-free | M3 | Survey (R3) |
| 10 | E2E Testing Infrastructure | Harness and runner for multi-tier opaque-box validation (`test_pipeline.py`) | E2E | Survey (AC) |
| 11 | Acceptance Criteria Automated Tests | Test dummy 2-row CSV, assert MongoDB insertion, assert 429 retry handling | E2E / M4 | Survey (AC) |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Data Extraction & Model Routing | CSV chunk streaming, column normalization, schema mapping, sequential indexing | none | DONE |
| 2 | M2: Gemini Mutation & Resilience | Pydantic schema, structured output, prompt mutation, 429 backoff retry | none | DONE |
| 3 | M3: MongoDB Bulk Loader & CLI Integration | Integrate M1 + M2, bulk insertion into collections, root CLI & module entry | M1, M2 | DONE |
| 4 | M4: Final Acceptance & Adversarial Hardening | Pass 100% of E2E test suite (Tiers 1-4) published by E2E track + Tier 5 hardening | M3, E2E | DONE |

## Interface Contracts
### M1 ↔ M2: Raw Row to Mutation Input
- Function: `mutate_question(client: genai.Client, row: dict, model_name: str) -> MutatedQuestion`
- Inputs: `row` containing `title`, `description`, `reference_solution`, `skill`, `difficulty`.
- Output: `MutatedQuestion` instance or dict with `mutated_title`, `mutated_description`, `mutated_solution`, `variable_mapping`, `explanation`.

### M2 ↔ M3: Mutated Question to Database Documents
- Formatting into `CodingQuestionDoc` dict:
  `{"skill": skill, "index": index, "title": mutated.mutated_title, "description": mutated.mutated_description, "source": "gemini_mutated", "source_url": "", "tags": tags}`
- Formatting into `SolutionDoc` dict:
  `{"skill": skill, "index": index, "difficulty": difficulty, "reference_solution": mutated.mutated_solution, "explanation": mutated.explanation}`

### M3 ↔ MongoDB Collections
- Target DB: `resulistic_db`
- Collections: `questions_moderate`, `questions_hard`, `solutions`
- Operation: `collection.insert_many(docs, ordered=False)`

## Code Layout
- Root CLI Pipeline: `d:\ResuListic\data_builder.py`
- Core Module Link: `d:\ResuListic\ml-services\skill_test\data_builder.py`
- Existing Schemas: `d:\ResuListic\ml-services\schema\question_schema.py`
- E2E Verification Script: `d:\ResuListic\test_pipeline.py`
