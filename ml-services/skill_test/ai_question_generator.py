"""
ai_question_generator.py — Generates easy MCQs via Google Gemini structured output.
"""

from typing import List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

client = genai.Client()
MODEL_NAME = "gemini-flash-latest"


# ── LLM-only schemas (internal, never sent to frontend) ────────────────────

class LLMMCQResponse(BaseModel):
    skill: str
    question: str
    options: List[str] = Field(description="Exactly 4 options: A), B), C), D)")
    correct_answer: str = Field(description="Just the letter: A, B, C, or D")
    explanation: str

class LLMQuestionBatch(BaseModel):
    questions: List[LLMMCQResponse]


def generate_mcq_questions(skills: List[str], count: int = 5) -> List[dict]:
    """Generate `count` easy MCQs across the given skills via Gemini."""
    skills_str = ", ".join(skills)
    prompt = f"""Generate exactly {count} multiple-choice questions testing: [{skills_str}].
    Difficulty: EASY / Fundamental. 4 options each (A/B/C/D). Distribute evenly across skills."""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMQuestionBatch,
            temperature=0.3,
            system_instruction="You are an expert technical interviewer creating simple screening MCQs.",
        ),
    )

    batch = LLMQuestionBatch.model_validate_json(response.text)

    return [
        {
            "public_data": {
                "q_index": i,
                "skill": q.skill,
                "difficulty": "easy",
                "source": "ai_generated",
                "question_type": "mcq",
                "question": q.question,
                "options": q.options,
            },
            "evaluation_data": {
                "correct_answer": q.correct_answer,
                "explanation": q.explanation,
            },
        }
        for i, q in enumerate(batch.questions)
    ]
