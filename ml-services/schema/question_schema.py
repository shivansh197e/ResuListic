"""
question_schema.py — Pydantic data contracts for the Skill Test Module.
"""

from pydantic import BaseModel, Field, AliasChoices, ConfigDict
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
    mode: str = "live"
    skills_tested: list[str]
    total_questions: int = 25
    questions: list[dict]  # Mix of MCQ and Coding question dicts
    created_at: str
    time_limit_minutes: int = 120
    started_at: Optional[str] = None
    expires_at: Optional[str] = None


# ── API Request Schemas (received from frontend) ───────────────────────────

class StartTestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(validation_alias=AliasChoices("user_id", "userId"))
    selected_skills: Optional[list[str]] = Field(default=None, max_length=20, validation_alias=AliasChoices("selected_skills", "selectedSkills"))  # None = auto-pick top 5
    mode: str = Field(default="live", pattern="^(live|mock)$")


class AnswerSubmission(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(validation_alias=AliasChoices("session_id", "sessionId"))
    user_id: str = Field(validation_alias=AliasChoices("user_id", "userId"))
    answers: list[dict] = Field(max_length=25)  # [{"q_index": 0, "user_answer": "B"}, ...]


TestSubmissionRequest = AnswerSubmission


# ── Internal State Schema ──────────────────────────────────────────────────

class UserTestState(BaseModel):
    """Tracks circular pointer for hard questions per user per skill."""
    user_id: str
    skill: str
    hard_pointer: int
    test_count: int = 1
    last_test_at: Optional[str] = None


# ── Code Evaluator Schemas (Phase 3b) ──────────────────────────────────────

class EvaluateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(validation_alias=AliasChoices("user_id", "userId"))
    question_id: str = Field(validation_alias=AliasChoices("question_id", "questionId"))
    code: str = Field(max_length=50000)
    problem_description: Optional[str] = Field(default=None, max_length=20000, validation_alias=AliasChoices("problem_description", "problemDescription"))
    reference_solution: Optional[str] = Field(default=None, max_length=50000, validation_alias=AliasChoices("reference_solution", "referenceSolution"))
    mock: Optional[bool] = False


class CodeEvaluationResult(BaseModel):
    passed: bool
    score: int = Field(ge=0, le=100)
    feedback: str
    time_complexity: str


EvaluationResult = CodeEvaluationResult


class EvaluateResponse(BaseModel):
    passed: bool
    score: int
    feedback: str
    time_complexity: str
    submission_id: str


# ── Job Domain Prediction & Career Switch Schemas ──────────────────────────

class SwitchDomainRecommendation(BaseModel):
    domain: str
    confidence: float
    feasibility: str = "Moderate"
    overlap_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)


class PredictDomainRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("user_id", "userId"))
    skills: Optional[list[str]] = None
    resume_text: Optional[str] = Field(default=None, validation_alias=AliasChoices("resume_text", "resumeText"))
    mcq_score: Optional[float] = Field(default=None, validation_alias=AliasChoices("mcq_score", "mcqScore"))
    coding_score: Optional[float] = Field(default=None, validation_alias=AliasChoices("coding_score", "codingScore"))


class PredictDomainResponse(BaseModel):
    user_id: Optional[str] = None
    primary_domain: str
    confidence: float
    overall_test_score: float
    domain_probabilities: dict[str, float]
    switch_domains: list[SwitchDomainRecommendation]


# ── Salary Prediction Schemas ──────────────────────────────────────────────

class SalaryFactor(BaseModel):
    factor: str
    impact: str


class SalaryRange(BaseModel):
    min_lpa: float
    max_lpa: float


class PredictSalaryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("user_id", "userId"))
    skills: Optional[list[str]] = None
    domain: Optional[str] = None
    mcq_score: Optional[float] = Field(default=None, validation_alias=AliasChoices("mcq_score", "mcqScore"))
    coding_score: Optional[float] = Field(default=None, validation_alias=AliasChoices("coding_score", "codingScore"))
    overall_score: Optional[float] = Field(default=None, validation_alias=AliasChoices("overall_score", "overallScore", "score"))
    resume_text: Optional[str] = Field(default=None, validation_alias=AliasChoices("resume_text", "resumeText"))
    experience_tier: Optional[str] = Field(default="fresher", validation_alias=AliasChoices("experience_tier", "experienceTier"))


class PredictSalaryResponse(BaseModel):
    user_id: Optional[str] = None
    predicted_lpa: float
    salary_range: SalaryRange
    compensation_tier: str
    domain: str
    overall_test_score: float
    factors: list[SalaryFactor] = Field(default_factory=list)
    is_unemployed: Optional[bool] = False
    status: Optional[str] = "Employed"
    college_tier: Optional[str] = None
    college_name: Optional[str] = None
    domain_baseline_lpa: Optional[float] = None


# ── Test Submission Schemas ────────────────────────────────────────────────

class TestSubmissionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    session_id: str
    is_expired: bool
    score: Optional[float] = None
    mcq_score: Optional[float] = None
    coding_score: Optional[float] = None
    mcq_marks: Optional[float] = None
    moderate_marks: Optional[float] = None
    hard_marks: Optional[float] = None
    score_percentage: Optional[float] = None
    correct_answers: Optional[int] = None
    total_questions: Optional[int] = None
    grade: Optional[str] = None
    skill_breakdown: Optional[list[dict]] = None
    message: str
    duration_seconds: Optional[float] = None
    questions_answered: int



