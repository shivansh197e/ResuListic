"""Deterministic, dependency-free assessment used for demos and offline practice."""

from datetime import datetime, timezone, timedelta
import uuid


MOCK_TIME_LIMIT_MINUTES = 120


CANONICAL_MCQ_EXPLANATIONS = {
    0: "Hash tables compute an array index via a hash function, enabling O(1) average time complexity for key lookups and insertions by mapping keys directly to buckets.",
    1: "HTTP PUT is defined in RFC 7231 as replacing the target resource in its entirety with the request payload, whereas PATCH is used for partial modifications.",
    2: "Isolation in ACID transactions guarantees that concurrent transactions cannot view uncommitted, in-flight data modifications (dirty reads).",
    3: "The Python built-in len() function queries the __len__() descriptor of the list sequence object, returning 3 for a 3-element list.",
    4: "Caching stores frequently accessed data in high-speed volatile memory (e.g. RAM or Redis), significantly reducing data retrieval round-trip latency and backend database load.",
    5: "Dynamic programming caches solutions to overlapping subproblems (via memoization or bottom-up tabulation) to avoid redundant exponential recalculations.",
    6: "TCP (Transmission Control Protocol) establishes a connection-oriented session with sequence numbering, flow control, and acknowledgments to ensure in-order, lossless byte streams.",
    7: "Unit tests validate discrete, individual functions or components in complete isolation from external network, filesystem, or database dependencies.",
    8: "Parameterized queries cleanly separate SQL commands from user input values, neutralizing malicious SQL injection payloads.",
    9: "Horizontal scaling (scale-out) distributes incoming traffic across multiple independent server instances or worker nodes rather than adding compute resources to a single machine.",
    10: "In Python 3.7+, the standard dict collection guarantees key-to-value mapping while deterministically preserving insertion order.",
    11: "HTTP 201 Created explicitly indicates that the request succeeded and resulted in the provisioning of one or more new resources on the server.",
    12: "Database indices construct balanced search trees (B-Trees) or hash maps that speed up read queries from full-table scans to O(log N) or O(1) lookups.",
    13: "Binary search eliminates half of the remaining search interval with each comparison step, achieving logarithmic O(log N) time on sorted collections.",
    14: "The Circuit Breaker pattern trips upon repeated downstream service faults, quickly failing requests to prevent cascading resource exhaustion across distributed microservices.",
    15: "Race conditions occur when concurrent execution threads access and modify shared mutable memory without proper synchronization or locking mechanisms.",
    16: "Continuous Integration (CI) automates the continuous compilation, automated testing, and validation of code merges to detect regressions early.",
    17: "JSON (JavaScript Object Notation) is a lightweight, human-readable, ubiquitous standard for serializing structured key-value data across network APIs.",
    18: "An idempotent operation produces the exact same end result on the server regardless of whether it is called once or multiple times consecutively.",
    19: "Robert C. Martin's Single Responsibility Principle states that a module, class, or function should have one, and only one, reason to change, encapsulating a single cohesive concern.",
}

CANONICAL_CODING_BENCHMARKS = {
    20: {
        "title": "Two Sum",
        "description": "Given nums and target, return the indices of two values that add to target.",
        "difficulty": "moderate",
        "marks": 10.0,
        "time_complexity": "O(N)",
        "space_complexity": "O(N)",
        "reference_solution": (
            "def solution(nums, target):\n"
            "    lookup = {}\n"
            "    for i, num in enumerate(nums):\n"
            "        diff = target - num\n"
            "        if diff in lookup:\n"
            "            return [lookup[diff], i]\n"
            "        lookup[num] = i\n"
            "    return []\n"
        ),
        "explanation": "Using a hash table enables O(1) average lookup for the required complement (target - num), reducing the brute-force O(N²) time complexity to linear O(N) with O(N) space.",
    },
    21: {
        "title": "Valid Parentheses",
        "description": "Return true when every bracket is correctly opened and closed.",
        "difficulty": "moderate",
        "marks": 10.0,
        "time_complexity": "O(N)",
        "space_complexity": "O(N)",
        "reference_solution": (
            "def solution(s):\n"
            "    stack = []\n"
            "    mapping = {')': '(', '}': '{', ']': '['}\n"
            "    for char in s:\n"
            "        if char in mapping:\n"
            "            top = stack.pop() if stack else '#'\n"
            "            if mapping[char] != top:\n"
            "                return False\n"
            "        else:\n"
            "            stack.append(char)\n"
            "    return not stack\n"
        ),
        "explanation": "A LIFO stack validates nested bracket symmetry. Every closing bracket must match the most recently pushed opening bracket. The stack is empty at completion if balanced.",
    },
    22: {
        "title": "Maximum Subarray",
        "description": "Return the largest sum of a contiguous non-empty subarray.",
        "difficulty": "moderate",
        "marks": 10.0,
        "time_complexity": "O(N)",
        "space_complexity": "O(1)",
        "reference_solution": (
            "def solution(nums):\n"
            "    if not nums:\n"
            "        return 0\n"
            "    max_sum = current_sum = nums[0]\n"
            "    for num in nums[1:]:\n"
            "        current_sum = max(num, current_sum + num)\n"
            "        max_sum = max(max_sum, current_sum)\n"
            "    return max_sum\n"
        ),
        "explanation": "Kadane's Algorithm computes the maximum contiguous subarray ending at each index in O(N) time and O(1) space, avoiding O(N²) window recalculations.",
    },
    23: {
        "title": "Longest Palindromic Substring",
        "description": "Return the longest palindromic substring in s.",
        "difficulty": "hard",
        "marks": 25.0,
        "time_complexity": "O(N²)",
        "space_complexity": "O(1)",
        "reference_solution": (
            "def solution(s):\n"
            "    if not s:\n"
            "        return \"\"\n"
            "    start = end = 0\n"
            "    def expand(left, right):\n"
            "        while left >= 0 and right < len(s) and s[left] == s[right]:\n"
            "            left -= 1\n"
            "            right += 1\n"
            "        return right - left - 1\n"
            "    for i in range(len(s)):\n"
            "        l1 = expand(i, i)\n"
            "        l2 = expand(i, i + 1)\n"
            "        m = max(l1, l2)\n"
            "        if m > end - start:\n"
            "            start = i - (m - 1) // 2\n"
            "            end = i + m // 2\n"
            "    return s[start:end + 1]\n"
        ),
        "explanation": "Expanding around 2N - 1 possible symmetry centers (odd and even) finds the longest palindrome in O(N²) time without the memory footprint of an O(N²) 2D dynamic programming table.",
    },
    24: {
        "title": "Word Break",
        "description": "Return whether s can be segmented into words from wordDict.",
        "difficulty": "hard",
        "marks": 25.0,
        "time_complexity": "O(N² · K)",
        "space_complexity": "O(N)",
        "reference_solution": (
            "def solution(s, wordDict):\n"
            "    words = set(wordDict)\n"
            "    dp = [False] * (len(s) + 1)\n"
            "    dp[0] = True\n"
            "    for i in range(1, len(s) + 1):\n"
            "        for j in range(i):\n"
            "            if dp[j] and s[j:i] in words:\n"
            "                dp[i] = True\n"
            "                break\n"
            "    return dp[len(s)]\n"
        ),
        "explanation": "Dynamic programming caches whether prefix s[0:i] can be partitioned. For each position i, it checks previous split points j where dp[j] is True and s[j:i] is in wordDict.",
    },
}


def build_mock_session(user_id: str, selected_skills: list[str] | None = None) -> dict:
    """Return a complete 25-question session without MongoDB or an AI provider."""
    started = datetime.now(timezone.utc)
    expires = started + timedelta(minutes=MOCK_TIME_LIMIT_MINUTES)
    
    clean_skills = [str(s).strip() for s in (selected_skills or []) if s and str(s).strip()]
    skills_tested = clean_skills if clean_skills else ["Data Structures", "APIs", "Databases", "Python", "Algorithms"]

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

    adjusted_mcqs = []
    for index, (default_skill, question, options, answer) in enumerate(mcq_templates):
        skill_assigned = skills_tested[index % len(skills_tested)] if clean_skills else default_skill
        adjusted_mcqs.append((skill_assigned, question, options, answer))

    questions = [
        {
            "q_index": index, "skill": skill, "difficulty": "easy",
            "question_type": "mcq", "question_id": f"demo_mcq_{index}",
            "question": question, "options": options, "marks": 1,
        }
        for index, (skill, question, options, _answer) in enumerate(adjusted_mcqs)
    ]
    coding = [
        (20, "Two Sum", "Given nums and target, return the indices of two values that add to target.", "moderate", 10),
        (21, "Valid Parentheses", "Return true when every bracket is correctly opened and closed.", "moderate", 10),
        (22, "Maximum Subarray", "Return the largest sum of a contiguous non-empty subarray.", "moderate", 10),
        (23, "Longest Palindromic Substring", "Return the longest palindromic substring in s.", "hard", 25),
        (24, "Word Break", "Return whether s can be segmented into words from wordDict.", "hard", 25),
    ]
    for index, title, description, difficulty, marks in coding:
        coding_skill = "Algorithms"
        if clean_skills:
            matching = [s for s in clean_skills if s.lower() in ("algorithms", "python", "data structures", "javascript", "react", "sql", "system design")]
            if matching:
                coding_skill = matching[index % len(matching)]
        questions.append({
            "q_index": index,
            "question_id": f"demo_code_{index}",
            "skill": coding_skill,
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
        "skills_tested": skills_tested,
        "time_limit_minutes": MOCK_TIME_LIMIT_MINUTES,
        "started_at": started.isoformat(),
        "expires_at": expires.isoformat(),
        "frontend_payload": {
            "session_id": "", "user_id": user_id, "mode": "mock",
            "skills_tested": skills_tested,
            "total_questions": 25, "questions": questions,
            "created_at": started.isoformat(), "time_limit_minutes": MOCK_TIME_LIMIT_MINUTES,
            "started_at": started.isoformat(), "expires_at": expires.isoformat(),
        },
        "evaluation_key": {
            **{str(i): {
                "question_type": "mcq",
                "correct_answer": answer,
                "skill": skill,
                "difficulty": "easy",
                "marks": 1.0,
                "max_marks": 1.0,
                "explanation": CANONICAL_MCQ_EXPLANATIONS.get(i, ""),
               }
               for i, (skill, _question, _options, answer) in enumerate(adjusted_mcqs)},
            **{str(i): {
                "question_type": "coding",
                "difficulty": CANONICAL_CODING_BENCHMARKS[i]["difficulty"],
                "max_marks": CANONICAL_CODING_BENCHMARKS[i]["marks"],
                "marks": CANONICAL_CODING_BENCHMARKS[i]["marks"],
                "skill": questions[i]["skill"],
                "title": CANONICAL_CODING_BENCHMARKS[i]["title"],
                "reference_solution": CANONICAL_CODING_BENCHMARKS[i]["reference_solution"],
                "correct_answer": CANONICAL_CODING_BENCHMARKS[i]["reference_solution"],
                "time_complexity": CANONICAL_CODING_BENCHMARKS[i]["time_complexity"],
                "space_complexity": CANONICAL_CODING_BENCHMARKS[i]["space_complexity"],
                "explanation": CANONICAL_CODING_BENCHMARKS[i]["explanation"],
               }
               for i in range(20, 25)},
        },
    }


def finalize_mock_session(session: dict) -> dict:
    """Fill the generated session ID into the public payload before returning it."""
    session["frontend_payload"]["session_id"] = session["session_id"]
    return session
