"""
question_schema.py
──────────────────
Pydantic models (data contracts) for the Skill Test Module.

WHY PYDANTIC?
─────────────
We could define our data as plain Python dicts (like we do in resume_builder.py),
but Pydantic gives us 3 superpowers:

  1. VALIDATION  → If someone sends "difficulty": "super_hard", Pydantic rejects 
     it automatically. With plain dicts, you'd write manual if-else checks.
  
  2. SERIALIZATION → Pydantic auto-converts to/from JSON for API responses.
     FastAPI uses Pydantic natively, so our response models "just work".
  
  3. DOCUMENTATION → FastAPI reads Pydantic models and generates Swagger docs
     automatically. Your friend building the React frontend can open 
     /docs and see exactly what the API returns.

ALTERNATIVES WE DIDN'T USE:
────────────────────────────
  - dataclasses (Python stdlib) → Good for simple data, but NO validation 
    and NO JSON serialization out of the box.
  - TypedDict → Just type hints, zero runtime validation. Errors only 
    show in IDE, never caught at runtime.
  - attrs → Similar to Pydantic but less integrated with FastAPI.
  - marshmallow → Good serialization library, but Pydantic is FastAPI's 
    native choice, so using marshmallow would mean extra glue code.

DESIGN DECISION: Schema-First
──────────────────────────────
We define ALL data shapes here BEFORE writing any logic. This means:
  - circular_tracker.py knows exactly what a question looks like
  - question_selector.py knows exactly what a test session looks like
  - main.py knows exactly what the API request/response looks like
  - Your friend's React frontend knows exactly what JSON to expect

This is "Contract-Driven Development" — the schema IS the contract 
between all parts of the system.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS — Restricting values to a fixed set
# ══════════════════════════════════════════════════════════════════════════════
# 
# WHY ENUMS?
# Without Enum, difficulty could be "hard", "Hard", "HARD", "difficult", etc.
# Enum forces everyone (frontend, backend, DB) to use the EXACT same values.
#
# ALTERNATIVE: Plain strings with manual validation
#   if difficulty not in ["easy", "moderate", "hard"]:
#       raise ValueError(...)
# This works but is fragile — you'd repeat this check in every function.
# Enum centralizes it: define once, validate everywhere.
# ══════════════════════════════════════════════════════════════════════════════

class Difficulty(str, Enum):
    """
    Why (str, Enum) and not just Enum?
    
    By inheriting from BOTH str and Enum, we get:
      - Difficulty.EASY == "easy"  → True  (string comparison works)
      - json.dumps(Difficulty.EASY) → "easy"  (auto JSON serialization)
    
    Without str: Difficulty.EASY == "easy" → False, which breaks 
    MongoDB queries where we need the raw string value.
    """
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"


class QuestionSource(str, Enum):
    """Where did this question come from?"""
    AI_GENERATED = "ai_generated"    # Generated on-the-fly by Gemini
    DATABASE = "database"            # From our scraped/curated question bank


# ══════════════════════════════════════════════════════════════════════════════
# MONGODB DOCUMENT SCHEMAS — What gets stored in the database
# ══════════════════════════════════════════════════════════════════════════════
#
# These models mirror the MongoDB document structure.
# They're used for:
#   1. Validating data BEFORE inserting into MongoDB
#   2. Documenting the exact shape of each collection
#   3. Type hints in our Python code (IDE autocomplete!)
#
# DESIGN DECISION: Separate collections for moderate vs hard
# ──────────────────────────────────────────────────────────────
# Your choice! Instead of one `question_bank` with a difficulty filter,
# we have `questions_moderate` and `questions_hard`.
# 
# Pros:
#   - Structurally impossible to mix difficulties
#   - Cleaner queries: db.questions_hard.find() vs db.question_bank.find({difficulty: "hard"})
#   - MongoDB can optimize each collection independently
#
# Cons:
#   - Two collections to manage (indexes, migrations, etc.)
#   - If we add a 3rd difficulty later, we need a 3rd collection
#
# The cons are acceptable for our use case (only 2 difficulty levels).
# ══════════════════════════════════════════════════════════════════════════════

class CodingQuestionDoc(BaseModel):
    """
    Schema for a single coding question in MongoDB.
    Used in BOTH `questions_moderate` and `questions_hard` collections.
    
    WHY `index` field?
    ──────────────────
    The `index` is critical for the circular linked list logic in hard questions.
    Each hard question has a position (0-49), and we traverse them circularly.
    For moderate questions, index (0-99) is just for ordering/deduplication.
    
    WHY we keep it simple (title + description only)?
    ──────────────────────────────────────────────────
    Your choice! We skip constraints, test cases, and starter code.
    This means:
      - Easier to scrape (most sites have title + description)
      - Less data to curate per question
      - AI evaluator (future) will judge the approach, not exact output
    """
    skill: str = Field(..., description="e.g. 'Python', 'FastAPI', 'MongoDB'")
    index: int = Field(..., description="Position in the pool. 0-99 for moderate, 0-49 for hard")
    title: str = Field(..., description="Short problem title, e.g. 'LRU Cache'")
    description: str = Field(..., description="Full problem statement")
    source: str = Field(default="manual", description="Where this question came from: 'geeksforgeeks', 'kaggle', 'manual', 'gemini_batch'")
    source_url: str = Field(default="", description="URL of the original source, if scraped")
    tags: list[str] = Field(default_factory=list, description="e.g. ['recursion', 'trees']")

    # NOTE: No `difficulty` field here!
    # The difficulty is implicit — if it's in `questions_moderate`, it's moderate.
    # This is a direct consequence of your "separate collections" decision.
    # If we had a single collection, we'd need this field.


class SolutionDoc(BaseModel):
    """
    Schema for reference solutions in the `solutions` collection.
    
    WHY SEPARATE FROM QUESTIONS?
    ────────────────────────────
    Your choice! Solutions live in their own collection because:
    
    1. SECURITY: The /api/start-test endpoint queries questions but NEVER 
       touches the solutions collection. Even if there's a bug in the API, 
       solutions can't leak — they're in a different collection entirely.
       
       Compare to: storing solution inside the question document, where 
       you'd need to remember to exclude it with MongoDB projection:
         db.questions.find({}, {"reference_solution": 0})  ← easy to forget!
    
    2. DIFFERENT ACCESS PATTERNS: Questions are read on every test. Solutions 
       are read only during evaluation (Phase 5). Different read frequencies 
       → different collections is a MongoDB best practice.
    
    3. INDEPENDENT UPDATES: You can add/fix solutions without touching 
       the questions collection at all.
    
    LINKING STRATEGY: We use skill + index + difficulty as the composite key.
    
    ALTERNATIVE APPROACHES WE DIDN'T USE:
    ─────────────────────────────────────
    - ObjectId reference: question._id → solution.question_id
      Problem: ObjectIds are auto-generated, hard to manage across imports.
    
    - Embedded in question document: question.reference_solution
      Problem: Leaks solution if you forget to exclude it in queries.
    
    - Separate file per solution (on disk, not DB):
      Problem: Harder to query, no MongoDB querying/indexing benefits.
    """
    skill: str = Field(..., description="Must match the question's skill")
    index: int = Field(..., description="Must match the question's index")
    difficulty: str = Field(..., description="'moderate' or 'hard' — tells us which collection the question is in")
    reference_solution: str = Field(..., description="The model answer / reference code")
    explanation: str = Field(default="", description="Why this solution works (optional)")


# ══════════════════════════════════════════════════════════════════════════════
# API SCHEMAS — What the frontend sees (request/response models)
# ══════════════════════════════════════════════════════════════════════════════
#
# These are DIFFERENT from the DB schemas on purpose.
# The frontend should NEVER see:
#   - reference_solution (that's cheating)
#   - MongoDB _id internals
#   - Internal metadata like source_url
#
# This is the "API Layer" pattern — your DB schema and API schema are 
# separate. FastAPI will serialize these models to JSON automatically.
# ══════════════════════════════════════════════════════════════════════════════

class MCQQuestionOut(BaseModel):
    """
    What the frontend receives for an AI-generated MCQ question.
    
    Note: `correct_answer` is NOT here. The frontend should never 
    know the answer until the user submits and we evaluate.
    """
    q_index: int = Field(..., description="Position in the test (0-9)")
    skill: str
    difficulty: str = "easy"
    source: str = "ai_generated"
    question_type: str = "mcq"
    question: str
    options: list[str] = Field(..., description="Exactly 4 options: ['A) ...', 'B) ...', 'C) ...', 'D) ...']")


class CodingQuestionOut(BaseModel):
    """
    What the frontend receives for a coding question (moderate/hard).
    
    Compare to CodingQuestionDoc (DB schema):
    - DB has: source, source_url, tags  → frontend doesn't need these
    - DB has no: q_index, difficulty     → frontend needs these
    - Solutions are in a separate collection → never reaches frontend
    """
    q_index: int = Field(..., description="Position in the test (0-9)")
    skill: str
    difficulty: str  # "moderate" or "hard"
    source: str = "database"
    question_type: str = "coding"
    title: str
    description: str


class TestSessionOut(BaseModel):
    """
    Complete test session response sent to the frontend.
    Contains a mix of MCQ and Coding questions (10 total).
    """
    session_id: str
    user_id: str
    skills_tested: list[str]
    total_questions: int = 10
    questions: list[dict]  # Mix of MCQQuestionOut and CodingQuestionOut
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST SCHEMAS — What the frontend sends to us
# ══════════════════════════════════════════════════════════════════════════════

class StartTestRequest(BaseModel):
    """
    Request body for POST /api/start-test
    
    WHY `selected_skills` is Optional?
    ───────────────────────────────────
    Two flows:
      Flow 1: User picks skills manually → selected_skills = ["Python", "FastAPI"]
      Flow 2: User clicks "Auto-pick"    → selected_skills = None (we pick top 5)
    
    Optional with a default of None lets us handle both flows with 
    one endpoint instead of two. This is the "Optional Parameter Pattern".
    
    ALTERNATIVE: Two separate endpoints
      POST /api/start-test/auto     ← auto-pick
      POST /api/start-test/manual   ← user-pick
    This would work but violates DRY — both endpoints do 90% the same thing.
    """
    user_id: str
    selected_skills: Optional[list[str]] = None


class AnswerSubmission(BaseModel):
    """
    Request body for POST /api/submit-test
    
    WHY `answers` is list[dict] and not a stricter type?
    ────────────────────────────────────────────────────
    Because MCQ answers are strings ("B") and coding answers are 
    multi-line code strings. A dict gives flexibility:
      {"q_index": 0, "user_answer": "B"}           ← MCQ
      {"q_index": 5, "user_answer": "def solve():..."} ← Coding
    
    ALTERNATIVE: Separate answer types
      class MCQAnswer(BaseModel): q_index: int, answer: str
      class CodingAnswer(BaseModel): q_index: int, code: str
    This is "more correct" but adds complexity. Since our evaluator 
    (Phase 5) will handle both types anyway, dict is simpler for now.
    
    This is a classic "pragmatism vs purity" tradeoff — we chose pragmatism.
    """
    session_id: str
    user_id: str
    answers: list[dict]


# ══════════════════════════════════════════════════════════════════════════════
# INTERNAL SCHEMAS — Used only inside the backend (never sent to frontend)
# ══════════════════════════════════════════════════════════════════════════════

class UserTestState(BaseModel):
    """
    Tracks the circular pointer for hard questions per user per skill.
    Stored in `user_test_state` collection.
    
    WHY composite _id?
    ──────────────────
    MongoDB's _id must be unique. We use {user_id, skill} as a composite key:
      _id: {"user_id": "firebase_123", "skill": "Python"}
    
    This guarantees ONE state document per user-skill combo.
    
    ALTERNATIVE: Auto-generated _id + unique index
      _id: ObjectId(...)
      + create_index([("user_id", 1), ("skill", 1)], unique=True)
    
    Both work, but composite _id is simpler — no need for a separate 
    unique index, and lookups by user+skill are O(1) via _id.
    """
    user_id: str
    skill: str
    hard_pointer: int = Field(..., description="Current position in hard pool (0-49)")
    test_count: int = Field(default=1, description="How many tests taken for this skill")
    last_test_at: Optional[str] = None
