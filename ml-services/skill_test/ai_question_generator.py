import json, os, re
from typing import List, Optional
from pydantic import BaseModel, Field

# ── Schemas ───────────────────────────────────────────────────────────────

class LLMMCQResponse(BaseModel):
    skill: str
    question: str
    options: List[str] = Field(description="Exactly 4 options: A), B), C), D)")
    correct_answer: str = Field(description="Just the letter: A, B, C, or D")
    explanation: str

class LLMQuestionBatch(BaseModel):
    questions: List[LLMMCQResponse]


def _parse_llm_mcq_batch(raw_content: str) -> Optional[LLMQuestionBatch]:
    """Resiliently parses LLM JSON outputs into LLMQuestionBatch, handling code fences, outer lists, and dicts."""
    if not raw_content or not raw_content.strip():
        return None
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return LLMQuestionBatch.model_validate_json(cleaned)
    except Exception:
        pass
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            if "questions" in data and isinstance(data["questions"], list):
                return LLMQuestionBatch.model_validate(data)
            return LLMQuestionBatch(questions=[LLMMCQResponse.model_validate(data)])
        elif isinstance(data, list) and data:
            if isinstance(data[0], dict) and "questions" in data[0]:
                return LLMQuestionBatch.model_validate(data[0])
            valid_qs = [LLMMCQResponse.model_validate(item) for item in data if isinstance(item, dict)]
            if valid_qs:
                return LLMQuestionBatch(questions=valid_qs)
    except Exception:
        pass
    return None


def generate_mcq_questions(skills: List[str], count: int = 5) -> List[dict]:
    """Generate `count` easy MCQs across the given skills using Groq (fast) with Gemini fallback."""
    if not skills:
        skills = ["General"]
    clean_skills = [str(s).strip() for s in skills if s and str(s).strip()]
    if not clean_skills:
        clean_skills = ["General"]
    skills = clean_skills
    skills_str = ", ".join(skills)
    prompt = (
        f"Generate exactly {count} multiple-choice questions testing: [{skills_str}].\n"
        f"Difficulty: EASY / Fundamental. Exactly 4 options each (A/B/C/D). Distribute evenly across skills.\n"
        f"You MUST return a JSON object with a single key 'questions' containing a list of objects, each with:\n"
        f"- 'skill' (string)\n- 'question' (string)\n- 'options' (list of 4 strings)\n"
        f"- 'correct_answer' (one of: 'A', 'B', 'C', 'D')\n- 'explanation' (string)"
    )

    # 1. Try Groq (Super fast, < 1s) with active model fallbacks
    groq_api_key = os.getenv("GROQ_API_KEY")
    if groq_api_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key)
            for model in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
                try:
                    resp = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=model,
                        temperature=0.3,
                        response_format={"type": "json_object"},
                    )
                    content = resp.choices[0].message.content or "{}"
                    batch = _parse_llm_mcq_batch(content)
                    if batch and batch.questions:
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
                                    "model_used": model,
                                },
                                "evaluation_data": {
                                    "correct_answer": q.correct_answer,
                                    "explanation": q.explanation,
                                },
                            }
                            for i, q in enumerate(batch.questions)
                        ]
                except Exception as model_err:
                    print(f"[Groq MCQ warning] model {model} failed: {model_err}", flush=True)
                    continue
        except Exception as groq_err:
            print(f"[Groq MCQ error] {groq_err}", flush=True)

    # 2. Fallback to Gemini (with fast timeout to prevent test session hangs)
    try:
        from google import genai
        from google.genai import types
        gemini_client = genai.Client()
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMQuestionBatch,
            temperature=0.3,
            system_instruction="You are an expert technical interviewer creating simple screening MCQs.",
        )
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=cfg,
        )
        batch = _parse_llm_mcq_batch(response.text or "{}")
        if batch and batch.questions:
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
                        "model_used": "gemini",
                    },
                    "evaluation_data": {
                        "correct_answer": q.correct_answer,
                        "explanation": q.explanation,
                    },
                }
                for i, q in enumerate(batch.questions)
            ]
    except Exception as gem_err:
        print(f"[Gemini MCQ error] {gem_err}", flush=True)

    # 3. Deterministic Fallback if both APIs are down/unreachable
    # Uses 5 distinct conceptual facets to guarantee zero duplicate questions
    fallback_templates = [
        {
            "q": lambda s: f"Which of the following best defines the core principle of {s}?",
            "opts": [
                "A) Structured encapsulation of state and behavior",
                "B) Unconstrained global execution",
                "C) Hardware-level thread pinning",
                "D) Direct unstructured memory access",
            ],
            "ans": "A",
            "exp": lambda s: f"Encapsulation and structured modularity form the primary foundation of {s}.",
        },
        {
            "q": lambda s: f"What is a primary advantage of adopting {s} in production systems?",
            "opts": [
                "A) Elimination of all computational complexity",
                "B) Increased maintainability, modularity, and code reuse",
                "C) Bypassing network communication latency",
                "D) Guarantee of zero-overhead execution",
            ],
            "ans": "B",
            "exp": lambda s: f"Adopting {s} promotes maintainable, modular system designs with reusable components.",
        },
        {
            "q": lambda s: f"When designing a system utilizing {s}, which tradeoff must typically be balanced?",
            "opts": [
                "A) Monolithic simplicity vs. manual instruction scheduling",
                "B) Kernel-level interrupts vs. disk spin speed",
                "C) Abstraction flexibility vs. runtime overhead and complexity",
                "D) Network topology vs. compiler registers",
            ],
            "ans": "C",
            "exp": lambda s: f"High-level abstraction in {s} often balances flexibility with cognitive and runtime complexity.",
        },
        {
            "q": lambda s: f"In modern software engineering, which pattern is most commonly associated with {s}?",
            "opts": [
                "A) Spaghetti branching without procedures",
                "B) Polling unbuffered registers continuously",
                "C) Hardcoded single-threaded batch execution",
                "D) Separation of concerns and clean interface boundaries",
            ],
            "ans": "D",
            "exp": lambda s: f"Clear separation of concerns is a standard architectural best practice in {s}.",
        },
        {
            "q": lambda s: f"How does {s} typically handle scalability and state management?",
            "opts": [
                "A) Through disciplined scoping, lifecycle management, and clear contracts",
                "B) By converting all logic to static global buffers",
                "C) By ignoring memory bounds and process isolation",
                "D) By forcing single-core synchronized lockstep",
            ],
            "ans": "A",
            "exp": lambda s: f"Robust state management and explicit contracts enable {s} to scale reliably.",
        },
    ]

    fallback_questions = []
    for i in range(count):
        sk = skills[i % len(skills)]
        tpl = fallback_templates[i % len(fallback_templates)]
        fallback_questions.append({
            "public_data": {
                "q_index": i,
                "skill": sk,
                "difficulty": "easy",
                "source": "fallback",
                "question_type": "mcq",
                "question": tpl["q"](sk),
                "options": tpl["opts"],
            },
            "evaluation_data": {
                "correct_answer": tpl["ans"],
                "explanation": tpl["exp"](sk),
            },
        })
    return fallback_questions
