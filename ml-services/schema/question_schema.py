"""
question_schema.py — Pydantic data contracts for the Skill Test Module.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── MongoDB Document Schemas ────────────────────────────────────────────────

class CodingQuestionDoc(BaseModel):
    """Schema for coding questions in `questions_moderate` and `questions_hard`."""
    skill: str
    index: int
    title: str
    description: str
    source: str = "manual"
    source_url: str = ""
    tags: list[str] = Field(default_factory=list)


class SolutionDoc(BaseModel):
    """Reference solutions in `solutions` collection, linked by skill+index+difficulty."""
    skill: str
    index: int
    difficulty: str  # "moderate" or "hard"
    reference_solution: str
    explanation: str = ""


# ── API Response Schemas (sent to frontend) ─────────────────────────────────

class TestSessionOut(BaseModel):
    """Complete test session payload for the frontend."""
    session_id: str
    user_id: str
    skills_tested: list[str]
    total_questions: int = 10
    questions: list[dict]  # Mix of MCQ and Coding question dicts
    created_at: str


# ── API Request Schemas (received from frontend) ───────────────────────────

class StartTestRequest(BaseModel):
    user_id: str
    selected_skills: Optional[list[str]] = None  # None = auto-pick top 5


class AnswerSubmission(BaseModel):
    session_id: str
    user_id: str
    answers: list[dict]  # [{"q_index": 0, "user_answer": "B"}, ...]


# ── Internal State Schema ──────────────────────────────────────────────────

class UserTestState(BaseModel):
    """Tracks circular pointer for hard questions per user per skill."""
    user_id: str
    skill: str
    hard_pointer: int
    test_count: int = 1
    last_test_at: Optional[str] = None
