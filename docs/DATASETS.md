# ResuListic Technical Assessment Dataset Documentation & Ingestion Blueprint

## 1. Executive Summary & Question Bank Architecture

ResuListic powers automated, objective technical capability evaluations across software engineering stacks. The evaluation engine employs a calibrated 25-question assessment model:
- **Phase 1 (Questions 1–20):** 20 Screening MCQs evaluating core domain principles, language idioms, and architectural concepts (1 mark each = 20 marks).
- **Phase 2 (Questions 21–23):** 3 Moderate Coding Challenges testing data structures, algorithms, query construction, or design patterns (10 marks each = 30 marks).
- **Phase 3 (Questions 24–25):** 2 Hard Algorithmic & System Challenges served through circular pointer tracking to eliminate test fatigue and repetition (25 marks each = 50 marks).
- **Total:** 25 questions, 100 marks total, 120-minute enforced deadline.

All assessment content is persisted in MongoDB Atlas (`resulistic_db`) across three core collections:
1. `questions_moderate`: Moderate-tier technical problems.
2. `questions_hard`: Hard-tier technical challenges.
3. `solutions`: Reference solutions and pedagogical explanations linked by compound key `(skill, index, difficulty)`.

---

## 2. Dataset 1: LeetCode Problems Dataset

### 2.1 Sources, Endpoints & Formats
- **Official GraphQL API Endpoint:** `https://leetcode.com/graphql`
- **Query Operation:** `questionData`, `problemsetQuestionList`
- **GraphQL Request Signature:**
  ```graphql
  query getProblemDetails($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
      questionId
      questionFrontendId
      title
      titleSlug
      difficulty
      categoryTitle
      content
      topicTags {
        name
        slug
      }
      codeSnippets {
        lang
        langSlug
        code
      }
      hints
      sampleTestCase
    }
  }
  ```
- **Local Dataset Repository File:** `datasets/leetcode_problems.json`
  - **Total Problems:** 3,549 problems
  - **File Size:** ~20.5 MB JSON
  - **Category Breakdown:**
    - `Algorithms`: 3,142 problems
    - `Database` (SQL): 302 problems
    - `JavaScript`: 67 problems
    - `pandas`: 15 problems
    - `Concurrency`: 9 problems
    - `Shell`: 4 problems
  - **Top Algorithmic Topics:**
    `Array` (1,906), `String` (786), `Hash Table` (694), `Dynamic Programming` (582), `Math` (575), `Sorting` (449), `Greedy` (412), `Depth-First Search` (320), `Binary Search` (307), `Tree` (244), `Stack` (168), `Graph` (166), `Two Pointers` (217).

### 2.2 Schema Mapping to `resulistic_db`

| LeetCode Raw Field | ResuListic Target Field | Target Collection | Transformation & Cleansing Logic |
| :--- | :--- | :--- | :--- |
| `title` | `title` | `questions_moderate`, `questions_hard` | Strip scraping prefixes (`Mutated: `, `Rewritten: `). Preserve canonical title. |
| `description` | `description` | `questions_moderate`, `questions_hard` | Validate length >= 100 characters. Ensure structured `<p><strong class="example">Example:</strong></p>` and `<p><strong>Constraints:</strong></p>` exist. |
| `difficulty` | Target Collection Routing | `questions_moderate` vs `questions_hard` | `Easy`/`Medium` -> `questions_moderate` (`difficulty: "moderate"`).<br>`Hard` -> `questions_hard` (`difficulty: "hard"`). |
| `category` / `topics` | `skill`, `tags` | Both collections | Map `category == 'Database'` to skill `"SQL"`.<br>Map `category == 'JavaScript'` to skill `"JavaScript"`.<br>Map primary topic (e.g. `Array`, `Hash Table`) or candidate skill to `"skill"`. Append other topics to `tags`. |
| `solution_code_python` / `solution` | `reference_solution` | `solutions` | Extract valid Python/JS/SQL function definition (e.g. `def solution(...)`). Strip Markdown code fences. |
| `explanation` / `hints` | `explanation` | `solutions` | Synthesize approach description (e.g. hash lookup, Kadane's algorithm, dynamic programming). |
| `stats` / computed | `time_complexity`, `space_complexity` | `solutions` | Determine standard Big-O notation: e.g. `O(N)`, `O(N log N)`, `O(1)`. |

---

## 3. Dataset 2: Codeforces Problemset Dataset

### 3.1 Sources & API Endpoints
- **Public REST API Endpoint:** `https://codeforces.com/api/problemset.problems`
- **Authentication:** Free, public access (rate limit 5 requests/sec).
- **JSON Response Structure:**
  ```json
  {
    "status": "OK",
    "result": {
      "problems": [
        {
          "contestId": 1850,
          "index": "E",
          "name": "Cardboard for Pictures",
          "type": "PROGRAMMING",
          "points": 1500.0,
          "rating": 1500,
          "tags": ["binary search", "geometry", "math"]
        }
      ],
      "problemStatistics": [
        {
          "contestId": 1850,
          "index": "E",
          "solvedCount": 16420
        }
      ]
    }
  }
  ```

### 3.2 Rating Calibration & Difficulty Mapping
Codeforces problem ratings provide objective mathematical difficulty tiers based on Elo ratings:
- **Rating < 1400 (Div. 4 / Div. 3 A-C):** Basic logic, linear scans, string manipulation. Ideal for screening MCQs and beginner coding tests.
- **Rating 1400 – 1799 (Div. 2 C-D / Div. 3 D-F):** Moderate tier -> maps to `questions_moderate` (10 marks). Topics: Binary search, Two Pointers, Greedy, Hash Tables, BFS/DFS.
- **Rating >= 1800 (Div. 1 A-C / Div. 2 E-F):** Hard tier -> maps to `questions_hard` (25 marks). Topics: Dynamic Programming on Trees, Segment Trees, Bitmask DP, Flow, Disjoint Set Union.

### 3.3 Skill & Tag Translation

| Codeforces Tag | ResuListic Canonical Skill | Target Subtopics |
| :--- | :--- | :--- |
| `data structures`, `dsu` | `Data Structures` | Disjoint Set Union, Segment Trees, Fenwick Trees |
| `dp`, `bitmasks` | `Dynamic Programming` | State Tabulation, Memoization, Bitmask Compression |
| `graphs`, `dfs and similar` | `Graph` / `Algorithms` | Topological Sort, Dijkstra, Kosaraju, Bridges |
| `binary search`, `two pointers` | `Algorithms` / `Array` | Monotonic Predicates, Sliding Window, Pointers |
| `math`, `number theory` | `Math` | GCD, Prime Factorization, Modular Arithmetic |

---

## 4. Dataset 3: HackerRank Assessment Datasets

### 4.1 Domains & Problem Tracks
HackerRank organizes engineering challenges into clean role-based tracks:
1. **Core CS Track:**
   - `Algorithms`: Warmup, Implementation, Strings, Sorting, Search, Graph Theory, Greedy, Dynamic Programming.
   - `Data Structures`: Arrays, Linked Lists, Trees, Balanced Trees, Stacks, Queues, Heap.
2. **Specialized Backend & Database Track:**
   - `SQL`: Basic Select, Advanced Select, Aggregations, Basic Join, Advanced Join, Alternative Queries.
   - Dialects supported: MySQL, PostgreSQL, Oracle, MS SQL Server.
3. **Language Tracks:**
   - `Python`: Data Types, Strings, Sets, Math, Itertools, Collections, Date & Time, Errors & Exceptions, Classes, Built-ins.
   - `Java`: OOP, Collections, Concurrency, Exception Handling.

### 4.2 Standard Structure & Ingestion Conversion
HackerRank problems follow a standardized markdown format:
```markdown
### Problem Statement
[Narrative context and core objective]

### Input Format
- First line contains integer N...
- Second line contains N space-separated integers...

### Constraints
- 1 <= N <= 10^5
- -10^9 <= A[i] <= 10^9

### Output Format
Print the computed integer result.

### Sample Input 0
...
### Sample Output 0
...
```
**Ingestion Conversion:**
- The Problem Statement, Input Format, Constraints, and Sample Input/Output are parsed into HTML using semantic tags (`<p>`, `<pre>`, `<ul>`, `<li>`, `<strong class="example">`).
- Function signatures are wrapped into standard Python/JS `solution(*args)` interfaces for AST evaluation.

---

## 5. Dataset 4: CS Theory & System Design Datasets

To support full-stack career intelligence, the ResuListic question bank incorporates curated foundational theory and system design challenges:

### 5.1 Operating Systems & Concurrency
- **Topics:** Process Lifecycle, Thread Scheduling, Mutex/Semaphore Synchronization, Deadlock Prevention (Banker's Algorithm), Virtual Memory, Page Fault Handling, Copy-On-Write (COW).
- **Format:** Conceptual MCQs and systems programming coding tasks (e.g. Thread-Safe Queue, Read-Write Lock, LRU Page Cache).
- **Sources:** Silberschatz Operating System Concepts, OSTEP (Operating Systems: Three Easy Pieces).

### 5.2 Database Systems & ACID Engineering
- **Topics:** Relational Normalization (1NF through BCNF), Isolation Levels (Dirty Read, Non-Repeatable Read, Phantom Read), Write-Ahead Logging (WAL), B+ Tree vs LSM Tree, Query Optimization, Index Selectivity.
- **Format:** Complex SQL schema challenges, transaction simulation, and query plan optimization exercises.

### 5.3 Computer Networking & Protocols
- **Topics:** OSI 7-Layer vs TCP/IP 4-Layer, TCP 3-Way Handshake & 4-Way Teardown, TCP Windowing & Congestion Control, TLS 1.3 Cryptographic Handshake, HTTP/1.1 vs HTTP/2 vs HTTP/3 (QUIC), DNS Resolution, WebSockets.
- **Format:** Protocol state analysis, HTTP response code selection, network flow simulation.

### 5.4 System Design & Scalable Architecture
- **Topics:** Distributed Rate Limiter (Token Bucket / Leaky Bucket), URL Shortener with Consistent Hashing, Distributed In-Memory Cache (LRU/LFU with TTL), Message Broker Pub/Sub with At-Least-Once Delivery, Resilient Circuit Breaker.
- **Sources:** `donnemartin/system-design-primer`, Martin Kleppmann's *Designing Data-Intensive Applications*.

---

## 6. Dataset 5: Open-Source Technical MCQs

For Phase 1 (20 Screening MCQs), ResuListic utilizes high-quality, verified technical question repositories:

### 6.1 Public Quiz APIs
1. **QuizAPI.io:**
   - **Endpoint:** `https://quizapi.io/api/v1/questions`
   - **Topics:** Linux, Bash, Docker, Kubernetes, DevOps, Python, JavaScript, SQL.
   - **Schema:**
     ```json
     {
       "id": 1,
       "question": "How to redirect stderr to stdout in Bash?",
       "answers": {
         "answer_a": "2>&1",
         "answer_b": "1>&2",
         "answer_c": "&>1",
         "answer_d": "2>1"
       },
       "multiple_correct_answers": "false",
       "correct_answers": {
         "answer_a_correct": "true", ...
       },
       "explanation": "2>&1 redirects file descriptor 2 (stderr) to file descriptor 1 (stdout).",
       "category": "Linux",
       "difficulty": "Easy"
     }
     ```
2. **Open Trivia Database (Computer Science):**
   - **Endpoint:** `https://opentdb.com/api.php?amount=50&category=18&type=multiple`
   - **Features:** Clean JSON, verified answers, multiple choice.

### 6.2 Curated Open-Source Question Repositories
- **JavaScript Fundamentals & Tricky Parts:** `lydiahallie/javascript-questions` (event loop, hoisting, coercion, prototype chain, microtasks).
- **Python Idioms & Internals:** `tux/python-interview-questions` (GIL, generators, dunder methods, garbage collection, memory management).
- **React Architecture:** `reactjs/react-interview-questions` (reconciliation, virtual DOM, fibers, custom hooks, context, memoization).
- **Git & Version Control:** `k88hudson/git-flight-rules` (commit graphs, interactive rebase, merge strategies, reflog, detached HEAD).

---

## 7. ResuListic Target Database Schemas (`resulistic_db`)

### 7.1 `questions_moderate` & `questions_hard` Collections
```json
{
  "_id": "ObjectId('672b1234abcd5678ef901234')",
  "skill": "Python",
  "index": 0,
  "title": "Group Anagrams with Frequency Hash",
  "description": "<p>Given an array of strings <code>strs</code>, group the <strong>anagrams</strong> together into sublists. You can return the answer in any order.</p>\n\n<p><strong class=\"example\">Example 1:</strong></p>\n<pre>\n<strong>Input:</strong> strs = [\"eat\",\"tea\",\"tan\",\"ate\",\"nat\",\"bat\"]\n<strong>Output:</strong> [[\"bat\"],[\"nat\",\"tan\"],[\"ate\",\"eat\",\"tea\"]]\n</pre>\n\n<p><strong>Constraints:</strong></p>\n<ul>\n<li><code>1 <= strs.length <= 10<sup>4</sup></code></li>\n<li><code>0 <= strs[i].length <= 100</code></li>\n<li><code>strs[i]</code> consists of lowercase English letters.</li>\n</ul>",
  "source": "curated_engineering",
  "source_url": "https://github.com/resulistic/question-bank",
  "tags": ["Python", "Hash Table", "String", "Sorting"]
}
```

### 7.2 `solutions` Collection
```json
{
  "_id": "ObjectId('672b1234abcd5678ef905678')",
  "skill": "Python",
  "index": 0,
  "difficulty": "moderate",
  "reference_solution": "from collections import defaultdict\n\ndef solution(strs):\n    groups = defaultdict(list)\n    for s in strs:\n        key = tuple(sorted(s))\n        groups[key].append(s)\n    return list(groups.values())\n",
  "explanation": "Grouping by sorted character tuple or 26-element frequency counts allows O(N * K log K) or O(N * K) grouping using a hash table where N is array length and K is maximum string length.",
  "time_complexity": "O(N · K log K)",
  "space_complexity": "O(N · K)"
}
```

### 7.3 Database Indexing Requirements
To ensure strict data integrity and sub-millisecond query lookups:
1. `questions_moderate`:
   - Unique Compound Index: `{"skill": 1, "index": 1}` (`unique: true`)
   - Query Index: `{"skill": 1}`
2. `questions_hard`:
   - Unique Compound Index: `{"skill": 1, "index": 1}` (`unique: true`)
   - Query Index: `{"skill": 1}`
3. `solutions`:
   - Unique Compound Index: `{"skill": 1, "index": 1, "difficulty": 1}` (`unique: true`)
   - Query Index: `{"skill": 1}`

### 7.4 Quality & Invariant Filters (`VALID_DESC_QUERY`)
Every question document admitted into `resulistic_db` must satisfy:
1. `description` length >= 100 characters.
2. `description` is not empty, null, or a template placeholder (`Rewritten:`).
3. Non-subjective check (`_is_subjective_doc`): question must require executable algorithmic logic, data transformation, or query code (rejects purely conceptual essay prompts).
4. Full reference solution in `solutions` collection matching `(skill, index, difficulty)`.

---

## 8. Automated Ingestion & Seeding Workflow

To execute database ingestion:
```bash
# 1. Run production question bank seeder
python scripts/seed_question_bank.py

# 2. Verify database population status and 100% solution coverage
python data_builder.py --status
```
The seeder parses local repository datasets (`datasets/leetcode_problems.json`) and injects verified, production-grade coding challenges for all core candidate skills: **Python, JavaScript, React, System Design, SQL, Algorithms, and Git**.
