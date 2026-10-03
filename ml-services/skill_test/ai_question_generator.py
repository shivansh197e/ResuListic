"""
ai_question_generator.py
────────────────────────
Handles generating Dynamic MCQ questions using Google Gemini.

WHY GENERATIVE AI FOR MCQS?
───────────────────────────
You requested 5 AI-generated questions (simple) and 5 DB-pulled questions (moderate/hard).
Using GenAI for the "simple" layer is brilliant because:
  1. Infinite variety: Candidates can't memorize a fixed bank of easy questions.
  2. Contextual generation: We can ask Gemini to generate questions specific 
     to the intersection of skills (e.g., "Python + MongoDB").
  3. Low risk: If the AI hallucinates slightly on an "easy" MCQ, it's less 
     damaging than hallucinating a complex coding problem.

DESIGN DECISION: Structured Outputs
───────────────────────────────────
LLMs are notoriously bad at outputting clean JSON. They love adding 
```json markdown blocks or conversational text ("Here is your JSON...").

Instead of using regex or prompt engineering to strip that out, we use 
Gemini's `response_schema` feature. We pass our Pydantic model directly 
to the API. The Gemini backend uses this to constrain the model's token 
generation, guaranteeing 100% valid JSON that perfectly matches our schema.

DEPENDENCIES:
  pip install google-genai pydantic
"""

import os
from typing import List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# We import the schema we already defined in File 1!
from schema.question_schema import MCQQuestionOut

# ── API Setup ───────────────────────────────────────────────────────────────
# We initialize the client. It automatically picks up GEMINI_API_KEY from 
# the environment (which python-dotenv will load in main.py).
client = genai.Client()

# Which model to use?
# gemini-2.5-flash is perfect here: it's incredibly fast, cheap, and easily 
# smart enough to generate simple technical MCQs.
MODEL_NAME = "gemini-2.5-flash"


# ── Internal Schema ─────────────────────────────────────────────────────────
# Notice something? `MCQQuestionOut` doesn't have a `correct_answer` field 
# (because we don't want to send it to the frontend).
# 
# But we NEED Gemini to tell US the correct answer so we can evaluate it later!
# So, we create an internal schema just for the LLM response that extends it.
class LLMMCQResponse(BaseModel):
    """What we actually ask Gemini to return."""
    skill: str = Field(description="The skill being tested")
    question: str = Field(description="The MCQ question text")
    options: List[str] = Field(description="Exactly 4 options, starting with A), B), C), D)")
    correct_answer: str = Field(description="The correct option letter, e.g., 'A'")
    explanation: str = Field(description="Brief explanation of why the answer is correct")

class LLMQuestionBatch(BaseModel):
    """Wrapper to force Gemini to return a LIST of questions."""
    questions: List[LLMMCQResponse]


# ── Core Logic ──────────────────────────────────────────────────────────────

def generate_mcq_questions(skills: List[str], count: int = 5) -> List[dict]:
    """
    Generate `count` MCQ questions covering the requested `skills`.
    
    Args:
        skills: List of skills to test (e.g., ["Python", "FastAPI"])
        count: How many questions total to generate (default: 5)
        
    Returns:
        List of dictionaries containing the generated questions.
        Note: We return dicts so the orchestrator can mix them with DB questions.
    """
    
    # 1. Craft the Prompt
    # We use a system instruction to set the persona, and a specific prompt 
    # for the task. We emphasize "simple/easy" as per your requirements.
    skills_str = ", ".join(skills)
    prompt = f"""
    Generate exactly {count} multiple-choice questions testing the following skills: [{skills_str}].
    
    Requirements:
    1. The difficulty must be EASY / Fundamental level.
    2. Distribute the questions evenly across the provided skills.
    3. Provide exactly 4 options per question.
    4. Options must start with 'A) ', 'B) ', 'C) ', 'D) '.
    5. The correct_answer must be just the letter (A, B, C, or D).
    """
    
    # 2. Call Gemini with Structured Outputs
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                # This is the magic! We pass our Pydantic model.
                response_mime_type="application/json",
                response_schema=LLMQuestionBatch,
                
                # Temperature 0.3 for a good balance of creativity vs correctness
                temperature=0.3,
                
                # System instructions set the baseline behavior
                system_instruction=(
                    "You are an expert technical interviewer creating simple, "
                    "fundamental screening questions for software engineers."
                )
            ),
        )
        
        # 3. Parse the response
        # The SDK returns the JSON string. Since we used response_schema, 
        # we can confidently parse it straight into our Pydantic model.
        json_data = response.text
        batch = LLMQuestionBatch.model_validate_json(json_data)
        
        # 4. Format for the Orchestrator
        # We need to adapt the LLM's output to fit our internal pipeline.
        # We return dicts containing BOTH the frontend data (MCQQuestionOut) 
        # and the backend evaluation data (correct_answer).
        final_questions = []
        for i, q in enumerate(batch.questions):
            
            # The public part (what the frontend sees)
            public_q = MCQQuestionOut(
                q_index=i,  # The orchestrator will override this, but we set a default
                skill=q.skill,
                question=q.question,
                options=q.options
            )
            
            # We bundle it into a dict that the orchestrator expects
            final_questions.append({
                "public_data": public_q.model_dump(),
                "evaluation_data": {
                    "correct_answer": q.correct_answer,
                    "explanation": q.explanation
                }
            })
            
        return final_questions

    except Exception as e:
        # Fallback mechanism: In a production system, if the LLM API is down,
        # you'd want to fallback to a small pre-curated list of easy DB questions.
        # For now, we'll just raise the error so we can debug it.
        print(f"Error calling Gemini: {e}")
        raise
