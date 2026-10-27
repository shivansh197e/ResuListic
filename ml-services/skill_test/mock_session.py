"""Deterministic, dependency-free assessment used for demos and offline practice."""

from datetime import datetime, timezone, timedelta
import uuid


MOCK_TIME_LIMIT_MINUTES = 120


def build_mock_session(user_id: str) -> dict:
    """Return a complete 25-question session without MongoDB or an AI provider."""
    started = datetime.now(timezone.utc)
    expires = started + timedelta(minutes=MOCK_TIME_LIMIT_MINUTES)
    mcq_templates = [
        ("Data Structures", "Which data structure provides average O(1) key lookup?", ["Hash table", "Linked list", "Binary heap", "Queue"], "A"),
        ("APIs", "Which HTTP method is normally used to replace a resource?", ["GET", "PUT", "PATCH", "DELETE"], "B"),
        ("Databases", "Which property prevents dirty reads?", ["Atomicity", "Consistency", "Isolation", "Durability"], "C"),
        ("Python", "What is the result of len([1, 2, 3])?", ["2", "3", "4", "Error"], "B"),
        ("System Design", "What does a cache primarily reduce?", ["Latency", "Type errors", "Source size", "Authentication"], "A"),
        ("Algorithms", "Which technique stores results of overlapping subproblems?", ["Greedy search", "Dynamic programming", "Random search", "Backtracking only"], "B"),
        ("Networking", "Which protocol provides ordered reliable byte delivery?", ["UDP", "TCP", "ICMP", "ARP"], "B"),
        ("Testing", "What is the main purpose of a unit test?", ["Test one small behaviour in isolation", "Deploy an application", "Replace monitoring", "Create database indexes"], "A"),
        ("Security", "What do parameterized queries primarily prevent?", ["SQL injection", "Cache misses", "Memory allocation", "DNS failures"], "A"),
        ("Cloud", "What does horizontal scaling add?", ["More service instances", "More code comments", "A larger function", "A single larger request"], "A"),
        ("Python", "Which collection preserves insertion order and maps keys to values?", ["set", "dict", "tuple", "bytes"], "B"),
        ("APIs", "Which status code commonly represents a successful resource creation?", ["200", "201", "301", "404"], "B"),
        ("Databases", "What does an index usually improve?", ["Read lookup speed", "Password entropy", "Source formatting", "Image resolution"], "A"),
        ("Algorithms", "What is binary search complexity on sorted data?", ["O(1)", "O(log n)", "O(n)", "O(n²)"], "B"),
        ("System Design", "What does a circuit breaker help prevent?", ["Cascading service failures", "Syntax errors", "Duplicate imports", "Slow local loops"], "A"),
        ("Concurrency", "What is a race condition caused by?", ["Uncontrolled shared access", "Too many comments", "A sorted list", "A cache hit"], "A"),
        ("DevOps", "What is CI mainly intended to automate?", ["Frequent integration and validation", "Manual salary reviews", "Resume OCR", "Database deletion"], "A"),
        ("Data", "Which format is commonly used for structured API payloads?", ["JSON", "BMP", "WAV", "EXE"], "A"),
        ("Architecture", "What does an idempotent operation guarantee?", ["Repeated requests have the same intended effect", "Every request is faster", "No request is authenticated", "All data is cached"], "A"),
        ("Code Quality", "What does the single-responsibility principle limit?", ["Reasons for a module to change", "Number of users", "Network bandwidth", "Database rows"], "A"),
    ]
    questions = [
        {
            "q_index": index, "skill": skill, "difficulty": "easy",
            "question_type": "mcq", "question_id": f"demo_mcq_{index}",
            "question": question, "options": options, "marks": 1,
        }
        for index, (skill, question, options, _answer) in enumerate(mcq_templates)
    ]
    coding = [
        (20, "Two Sum", "Given nums and target, return the indices of two values that add to target.", "moderate", 10),
        (21, "Valid Parentheses", "Return true when every bracket is correctly opened and closed.", "moderate", 10),
        (22, "Maximum Subarray", "Return the largest sum of a contiguous non-empty subarray.", "moderate", 10),
        (23, "Longest Palindromic Substring", "Return the longest palindromic substring in s.", "hard", 25),
        (24, "Word Break", "Return whether s can be segmented into words from wordDict.", "hard", 25),
    ]
    for index, title, description, difficulty, marks in coding:
        questions.append({
            "q_index": index,
            "question_id": f"demo_code_{index}",
            "skill": "Algorithms",
            "difficulty": difficulty,
            "question_type": "coding",
            "title": title,
            "description": description,
            "starter_code": "def solution(*args):\n    # Implement your solution\n    pass\n",
            "marks": marks,
        })

    return {
        "session_id": f"demo_{uuid.uuid4().hex[:10]}",
        "user_id": user_id,
        "mode": "mock",
        "skills_tested": ["Data Structures", "APIs", "Databases", "Python", "Algorithms"],
        "time_limit_minutes": MOCK_TIME_LIMIT_MINUTES,
        "started_at": started.isoformat(),
        "expires_at": expires.isoformat(),
        "frontend_payload": {
            "session_id": "", "user_id": user_id, "mode": "mock",
            "skills_tested": ["Data Structures", "APIs", "Databases", "Python", "Algorithms"],
            "total_questions": 25, "questions": questions,
            "created_at": started.isoformat(), "time_limit_minutes": MOCK_TIME_LIMIT_MINUTES,
            "started_at": started.isoformat(), "expires_at": expires.isoformat(),
        },
        "evaluation_key": {
            **{str(i): {"question_type": "mcq", "correct_answer": answer, "skill": skill}
               for i, (skill, _question, _options, answer) in enumerate(mcq_templates)},
            **{str(i): {"question_type": "coding", "difficulty": "hard" if i >= 23 else "moderate",
                        "max_marks": 25.0 if i >= 23 else 10.0, "skill": "Algorithms"}
               for i in range(20, 25)},
        },
    }


def finalize_mock_session(session: dict) -> dict:
    """Fill the generated session ID into the public payload before returning it."""
    session["frontend_payload"]["session_id"] = session["session_id"]
    return session
