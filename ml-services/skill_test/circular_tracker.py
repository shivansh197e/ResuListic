"""
circular_tracker.py
───────────────────
Manages the circular linked list pattern for Hard coding questions 
using modulo arithmetic on MongoDB.

THE CORE IDEA
─────────────
Instead of building an actual linked list (which would be complex in 
a database), we simulate circular traversal with ONE integer and the 
modulo operator:

    next_pointer = (current_pointer + step) % pool_size

This gives us O(1) time, O(1) space, and natural wrap-around.

HOW IT WORKS (Step by step)
───────────────────────────
1. User takes their FIRST test for a skill:
   → We pick a random starting position (e.g., 25)
   → Serve questions at index 25 and 26
   → Save pointer = 25 in MongoDB

2. User takes their SECOND test:
   → Read pointer (25) from MongoDB
   → New pointer = (25 + 2) % 50 = 27
   → Serve questions at index 27 and 28
   → Save new pointer = 27

3. When it wraps around (e.g., pointer is 49):
   → New pointer = (49 + 2) % 50 = 1
   → Serve questions at index 1 and 2
   → The modulo handles the wrap automatically!

ALTERNATIVE APPROACHES WE CONSIDERED
─────────────────────────────────────
1. ACTUAL LINKED LIST in MongoDB:
   Each question doc has a "next_id" field pointing to the next question.
   Problem: Requires N queries to traverse to your position (O(n) vs our O(1)).
   Problem: Inserting/deleting questions breaks the chain.
   
2. STORING "SEEN QUESTION IDS" per user:
   Keep a list of all question _ids the user has seen.
   Problem: The list grows forever. After 25 tests × 2 questions = 50 IDs stored.
   Problem: Querying "give me questions NOT in this list" gets slow.
   
3. RANDOM WITHOUT REPLACEMENT (shuffle + index):
   Pre-generate a shuffled order for each user and step through it.
   Problem: Need to store a 50-element array per user per skill.
   Problem: If we add new questions, the pre-shuffled order is stale.

4. TIMESTAMP-BASED ("show least recently seen"):
   Track when each question was last shown to each user.
   Problem: Need 50 timestamp records per user per skill.
   Problem: Complex queries to find the "oldest" question.

WHY MODULO WINS: One integer per user per skill. One line of math. Done.

MongoDB collection used: `user_test_state`
Document shape:
    {
        "_id": {"user_id": "xxx", "skill": "Python"},
        "hard_pointer": 25,        # Current position (0-49)
        "test_count": 3,           # How many tests taken
        "last_test_at": "ISO..."   # When they last took a test
    }

Public API:
    get_hard_questions(db, user_id, skill, count=2) → list[dict]
    get_user_test_count(db, user_id, skill) → int
"""

import random
from datetime import datetime, timezone
from pymongo.database import Database


# ── Configuration ────────────────────────────────────────────────────────────
# Why 50? This is the hard question pool size per skill.
# 50 questions × 2 per test = 25 unique tests before repeating.
# That's roughly 6 months if someone tests weekly — plenty of variety.
#
# WHY NOT MAKE IT CONFIGURABLE?
# We COULD pass pool_size as a parameter, but YAGNI (You Ain't Gonna Need It).
# If we ever need different pool sizes per skill, we'd read it from the DB.
# For now, 50 is hardcoded — simple and clear.
HARD_POOL_SIZE = 50


def get_hard_questions(db: Database, user_id: str, skill: str, count: int = 2) -> list[dict]:
    """
    Fetch `count` consecutive hard coding questions using circular logic.
    
    Args:
        db:      MongoDB database instance (pymongo Database object)
        user_id: The user's unique ID (from auth system)
        skill:   The skill name (e.g. "Python") — must match question docs
        count:   Number of hard questions to pick (default: 2)
    
    Returns:
        List of question documents from the `questions_hard` collection.
        Returns empty list if no questions found for this skill.
    
    Side Effects:
        - Creates or updates a document in `user_test_state` collection.
        - Advances the circular pointer by `count` positions.
    
    ─── DEEP DIVE: Why we update state BEFORE fetching questions ───
    
    You might wonder: "What if the DB query for questions fails AFTER 
    we already advanced the pointer? Won't we skip questions?"
    
    Yes, technically. But consider the alternatives:
    
    Option A (what we do): Update pointer → fetch questions
      Risk: If fetch fails, 2 questions are "skipped"
      Benefit: Simple, one update + one find
    
    Option B: Fetch questions → update pointer
      Risk: If update fails, user gets SAME questions next time (repeats!)
      Risk: Race condition — two simultaneous requests could get same questions
    
    Option C: Use a MongoDB transaction (atomic update + fetch)
      Benefit: Truly atomic, no skipping or repeating
      Cost: Transactions need a replica set, more complex code
      Verdict: Overkill for our use case. Skipping 2 questions is harmless.
    
    We chose Option A because skipping is better than repeating, 
    and simplicity trumps perfection for a test platform.
    """
    
    state_collection = db.user_test_state
    question_collection = db.questions_hard  # Separate collection! (your design decision)
    
    # ── Step 1: Get or create the user's pointer for this skill ──────────
    #
    # We use a COMPOSITE _id: {"user_id": "xxx", "skill": "Python"}
    # This guarantees ONE document per user-skill combo.
    #
    # WHY NOT use a regular _id + unique index?
    #   Both work. Composite _id saves us from creating a separate index.
    #   Lookups by _id are O(1) in MongoDB (it's the primary key).
    #
    state_key = {"user_id": user_id, "skill": skill}
    state = state_collection.find_one({"_id": state_key})
    
    if state is None:
        # ── FIRST TEST: Random start position ────────────────────────────
        # 
        # Why random? If everyone started at 0, the first 2 questions 
        # would be disproportionately "seen" (heavy traffic on Q0, Q1).
        # Random distributes the load across all questions.
        #
        # random.randint(a, b) returns a random integer N such that a <= N <= b
        # So randint(0, 49) can return any value from 0 to 49 inclusive.
        #
        pointer = random.randint(0, HARD_POOL_SIZE - 1)
        
        state_collection.insert_one({
            "_id": state_key,
            "hard_pointer": pointer,
            "test_count": 1,
            "last_test_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        # ── SUBSEQUENT TESTS: Advance pointer circularly ─────────────────
        #
        # THE KEY LINE — this is where the magic happens:
        #   pointer = (old_pointer + count) % HARD_POOL_SIZE
        #
        # Examples (with count=2, pool=50):
        #   old=25  → (25+2) % 50 = 27  (normal advance)
        #   old=48  → (48+2) % 50 = 0   (wraps around!)
        #   old=49  → (49+2) % 50 = 1   (wraps around!)
        #
        pointer = (state["hard_pointer"] + count) % HARD_POOL_SIZE
        
        # $set replaces field values, $inc increments by 1
        # We use BOTH in one update to minimize DB roundtrips.
        state_collection.update_one(
            {"_id": state_key},
            {
                "$set": {
                    "hard_pointer": pointer,
                    "last_test_at": datetime.now(timezone.utc).isoformat(),
                },
                "$inc": {"test_count": 1}
            }
        )
    
    # ── Step 2: Calculate which indices to fetch ─────────────────────────
    #
    # We need `count` consecutive indices, wrapping around if necessary.
    #
    # Example: pointer=49, count=2
    #   i=0: (49 + 0) % 50 = 49
    #   i=1: (49 + 1) % 50 = 0   ← wraps!
    #   indices = [49, 0]
    #
    # WHY a list comprehension?
    # Alternative: a for loop with append. List comprehension is more 
    # Pythonic and slightly faster (compiled to bytecode differently).
    #
    indices = [(pointer + i) % HARD_POOL_SIZE for i in range(count)]
    
    # ── Step 3: Fetch questions from MongoDB ─────────────────────────────
    #
    # $in operator: "find documents where 'index' is in this list"
    # This is ONE query that returns all matching documents.
    #
    # WHY NOT query one-by-one in a loop?
    #   Loop: 2 queries × network roundtrip = slow
    #   $in:  1 query = fast
    #   Always batch DB queries when possible!
    #
    questions = list(question_collection.find({
        "skill": skill,
        "index": {"$in": indices}
    }))
    
    # ── Step 4: Sort results in circular order ───────────────────────────
    #
    # MongoDB's find() doesn't guarantee order matching our indices list.
    # If indices = [49, 0], MongoDB might return [Q0, Q49] (sorted by index).
    # We need to reorder to match our circular sequence: [Q49, Q0].
    #
    # HOW: Create a lookup dict {index: position} and sort by position.
    #   {49: 0, 0: 1}  → Q49 goes first (position 0), Q0 goes second (position 1)
    #
    # ALTERNATIVE: Query one at a time in order (guarantees order but 2x queries).
    # ALTERNATIVE: Use MongoDB $sort with a custom expression (complex aggregation).
    # Our approach: Fetch all at once, sort in Python. Simple and fast.
    #
    index_order = {idx: pos for pos, idx in enumerate(indices)}
    questions.sort(key=lambda q: index_order.get(q["index"], 999))
    
    return questions


def get_user_test_count(db: Database, user_id: str, skill: str) -> int:
    """
    Returns how many tests this user has taken for a specific skill.
    
    Useful for the frontend to show "Test #3 for Python" or 
    for analytics like "How many times has this user retested?"
    """
    state = db.user_test_state.find_one(
        {"_id": {"user_id": user_id, "skill": skill}}
    )
    return state["test_count"] if state else 0
