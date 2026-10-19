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


def _call_groq_mcq_batch(client, model: str, skills_str: str, count: int) -> List[LLMMCQResponse]:
    """Fetches high-quality blind screening MCQs from Groq in a single fast call (~2-3s) respecting 1000 OTPM limit."""
    safe_count = min(count, 5)
    prompt = (
        f"Generate exactly {safe_count} distinct multiple-choice questions evaluating technical aptitude in: [{skills_str}].\n"
        f"Difficulty: Fundamental / Technical screening. Exactly 4 options each (A, B, C, D).\n"
        f"STRICT BLIND SCREENING RULES:\n"
        f"1. Do NOT mention, prefix, or leak the skill name, language name, framework name, or topic name in the question text or options (e.g. NEVER write '[Python]', '[FastAPI]', 'In React...', 'Which SQL clause...').\n"
        f"2. The candidate must deduce the answer purely from code snippets, technical logic, realistic architectural scenarios, or algorithmic principles.\n"
        f"3. Return strict JSON with key 'questions' containing exactly {safe_count} question objects.\n"
        f"Each object must have:\n"
        f"- 'skill' (string category)\n- 'question' (clean question string, NO topic prefixes)\n- 'options' (list of 4 strings prefixed with A), B), C), D))\n"
        f"- 'correct_answer' (one of: 'A', 'B', 'C', 'D')\n- 'explanation' (concise 1-sentence rationale)"
    )
    try:
        resp = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior technical interviewer creating blind technical screening MCQs. Never mention or prefix the tested skill name in question text or options. Concise options. Output strict valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            model=model,
            temperature=0.25,
            max_tokens=850,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        batch = _parse_llm_mcq_batch(content)
        if batch and batch.questions:
            sanitized = []
            for q in batch.questions:
                # Strip any accidental [Skill] or Topic: prefix from question text
                clean_q_text = re.sub(r"^\[.*?\]\s*", "", q.question).strip()
                clean_q_text = re.sub(r"^(topic|skill):\s*.*?\n", "", clean_q_text, flags=re.IGNORECASE).strip()
                q.question = clean_q_text
                sanitized.append(q)
            return sanitized
    except Exception as e:
        print(f"[Groq MCQ Warning] Model {model} call failed: {e}", flush=True)
    return []


def generate_mcq_questions(skills: List[str], count: int = 20) -> List[dict]:
    """
    Generate strictly `count` (default 20) blind MCQs across given skills using Groq (qwen/qwen3.8-27b)
    in a fast call (~2-3 seconds) with instant deterministic fallback top-up.
    """
    if not skills:
        skills = ["General Software Engineering"]
    clean_skills = [str(s).strip() for s in skills if s and str(s).strip()]
    if not clean_skills:
        clean_skills = ["General Software Engineering"]
    skills = clean_skills
    skills_str = ", ".join(skills)

    collected_mcqs: List[LLMMCQResponse] = []
    fast_mock = os.getenv("FAST_MOCK_MCQ") == "1"
    groq_api_key = None if fast_mock else os.getenv("GROQ_API_KEY")

    if groq_api_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key)
            model = "qwen/qwen3.8-27b"
            batch = _call_groq_mcq_batch(client, model, skills_str, count=5)
            if batch:
                collected_mcqs.extend(batch)
        except Exception as groq_err:
            print(f"[Groq MCQ Error] {groq_err}", flush=True)

    # 3. Comprehensive Deterministic Fallback if APIs are unreachable or return < count
    fallback_templates = [
        ("Which data structure provides O(1) average time complexity for both key insertion and lookup?",
         ["A) Hash Table", "B) Balanced Binary Search Tree", "C) Doubly Linked List", "D) Sorted Dynamic Array"],
         "A", "Hash tables compute array indices via a hash function, achieving O(1) average lookup and insertion."),
        ("What is the primary motivation for enforcing function purity and immutability in concurrent routines?",
         ["A) Bypassing compile-time validation", "B) Eliminating race conditions and unintended side effects", "C) Ensuring zero memory allocation overhead", "D) Guaranteeing direct hardware register access"],
         "B", "Pure functions and immutable states prevent shared mutable state, eliminating data races."),
        ("In distributed systems, which strategy is primarily employed to protect upstream services during outages?",
         ["A) Busy-waiting thread loops", "B) Circuit Breaker with exponential backoff", "C) Continuous synchronous retries without delay", "D) Hardcoded global process timeouts"],
         "B", "The Circuit Breaker pattern trips on repeated errors, allowing downstream systems to gracefully recover."),
        ("Which HTTP status code is most appropriate when a client request violates input validation constraints?",
         ["A) 400 Bad Request / 422 Unprocessable Content", "B) 500 Internal Server Error", "C) 304 Not Modified", "D) 204 No Content"],
         "A", "400/422 explicitly indicates malformed syntax or unprocessable semantic validation errors on client input."),
        ("What is the worst-case time complexity of searching for an element in an unbalanced Binary Search Tree?",
         ["A) O(1)", "B) O(log N)", "C) O(N)", "D) O(N log N)"],
         "C", "An unbalanced BST can degenerate into a linear linked list where searches degrade to O(N)."),
        ("Which isolation level prevents 'Dirty Reads' by ensuring transactions only read committed data?",
         ["A) Read Uncommitted", "B) Read Committed", "C) Serializable", "D) Repeatable Read"],
         "B", "Read Committed guarantees that transactions will never view uncommitted, in-flight dirty writes."),
        ("When scaling write-heavy database workloads, which architectural pattern is standard practice?",
         ["A) Write-Ahead Logging with read replicas / sharding", "B) Monolithic table locking without indices", "C) Synchronous polling of flat log files", "D) Storing all state in ephemeral client cookies"],
         "A", "Sharding, partitioned tables, and WAL-backed read replicas distribute heavy database load effectively."),
        ("What is the purpose of an idempotent HTTP endpoint in RESTful API design?",
         ["A) Executing only on secure SSL connections", "B) Producing identical server state upon multiple identical requests", "C) Bypassing cross-origin security policies", "D) Guaranteeing sub-millisecond execution times"],
         "B", "Idempotence ensures subsequent identical requests (e.g. PUT/DELETE) have the same effect as a single request."),
        ("Which algorithmic technique solves problems by combining optimal solutions of overlapping subproblems?",
         ["A) Greedy Choice Method", "B) Dynamic Programming (Memoization / Tabulation)", "C) Simple Randomized Exploration", "D) Linear Brute Force Search"],
         "B", "Dynamic Programming caches overlapping subproblem results to prevent redundant exponential recalculation."),
        ("In asynchronous programming, what occurs if an unawaited background task encounters an unhandled exception?",
         ["A) Immediate kernel panic", "B) Silent task termination or unhandled exception warning depending on runtime", "C) Automatic rollback of physical storage", "D) Automatic conversion to synchronous blocking execution"],
         "B", "Unhandled exceptions in unawaited tasks often lead to dropped tasks, swallowed errors, or process warnings."),
        ("Which index type is best suited for range-based queries (e.g. BETWEEN or >=) on relational tables?",
         ["A) Hash Index", "B) B-Tree Index", "C) Full-text Inverted Index", "D) Spatial R-Tree Index"],
         "B", "B-Tree indices maintain sorted key structures, making range scans and inequalities highly efficient."),
        ("What is the primary benefit of connection pooling in database client architectures?",
         ["A) Eliminating query optimization overhead", "B) Reusing existing open network sockets, avoiding TCP/handshake latency", "C) Encrypting disk sectors automatically", "D) Removing the need for SQL transactions"],
         "B", "Connection pooling reuses established TCP connections, eliminating the high cost of per-query handshakes."),
        ("In modern API authentication, how are stateless user sessions typically validated across distributed clusters?",
         ["A) Cryptographically signed JWT tokens", "B) Sticky IP routing without tokens", "C) Storing plaintext credentials in shared files", "D) Querying local operating system user accounts"],
         "A", "Digitally signed tokens allow microservices to verify authenticity independently without central session state."),
        ("Which caching eviction policy removes the item that has not been accessed for the longest duration?",
         ["A) FIFO (First In First Out)", "B) LFU (Least Frequently Used)", "C) LRU (Least Recently Used)", "D) Random Eviction"],
         "C", "LRU tracks access order and evicts items with the stalest access timestamps when capacity is reached."),
        ("What does the 'Single Responsibility Principle' dictate in object-oriented and modular system design?",
         ["A) A class or module should have only one reason to change", "B) Every file must contain only a single function", "C) Code must run strictly on a single thread", "D) Applications must only interact with a single database table"],
         "A", "SRP mandates that each module or class encapsulated a single, cohesive responsibility or actor concern."),
        ("When implementing rate limiting for public web services, which algorithm accommodates brief bursts of traffic smoothly?",
         ["A) Fixed Window Counter", "B) Token Bucket / Leaky Bucket", "C) Unchecked Round Robin", "D) Strict Single-Thread Queue"],
         "B", "Token Bucket allows temporary bursts up to bucket capacity while enforcing a steady long-term replenishment rate."),
        ("Why are prepared statements parameterized queries recommended for relational database execution?",
         ["A) They prevent SQL injection attacks and enable query execution plan reuse", "B) They convert SQL directly to assembly language", "C) They eliminate disk I/O operations", "D) They make database transactions non-blocking"],
         "A", "Parameterized queries separate SQL structure from user data, preventing injection and speeding up query plans."),
        ("What is the primary tradeoff of implementing microservices over a monolithic architecture?",
         ["A) Decreased network latency and zero deployment overhead", "B) Increased distributed complexity, network boundaries, and operational observability overhead", "C) Complete removal of data serialization", "D) Inability to scale independent services"],
         "B", "Microservices offer independent scalability at the cost of distributed networking, data consistency, and operational overhead."),
        ("In memory management, what is a primary cause of memory leaks in garbage-collected environments?",
         ["A) Creating large local primitive variables inside functions", "B) Retaining unintended long-lived references to unused objects in global structures or listeners", "C) Utilizing compiler optimizations", "D) Declaring read-only constant variables"],
         "B", "Garbage collectors cannot reclaim objects that are still reachable through global caches, unremoved event listeners, or static maps."),
        ("Which transport protocol provides connection-oriented, ordered, and guaranteed delivery of byte streams?",
         ["A) UDP", "B) TCP", "C) ICMP", "D) ARP"],
         "B", "TCP guarantees ordered, reliable packet delivery with flow control and error checking."),
    ]

    while len(collected_mcqs) < count:
        idx = len(collected_mcqs)
        sk = skills[idx % len(skills)]
        tpl = fallback_templates[idx % len(fallback_templates)]
        collected_mcqs.append(
            LLMMCQResponse(
                skill=sk,
                question=tpl[0],
                options=tpl[1],
                correct_answer=tpl[2],
                explanation=tpl[3],
            )
        )

    # Strictly enforce exact count
    final_mcqs = collected_mcqs[:count]

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
                "marks": 1,
            },
            "evaluation_data": {
                "correct_answer": q.correct_answer,
                "explanation": q.explanation,
                "difficulty": "easy",
                "marks": 1.0,
                "max_marks": 1.0,
            },
        }
        for i, q in enumerate(final_mcqs)
    ]
