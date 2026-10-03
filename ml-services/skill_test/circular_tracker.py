"""
circular_tracker.py — Circular question pointer via modulo arithmetic.
Serves consecutive hard questions per user per skill, advancing on each test.
"""

import random
from datetime import datetime, timezone
from pymongo.database import Database

HARD_POOL_SIZE = 50  # ponytail: bump if 25 unique tests per skill isn't enough


def get_hard_questions(db: Database, user_id: str, skill: str, count: int = 2) -> list[dict]:
    """Fetch `count` consecutive hard questions using circular pointer logic."""
    state_key = {"user_id": user_id, "skill": skill}
    state = db.user_test_state.find_one({"_id": state_key})

    if state is None:
        pointer = random.randint(0, HARD_POOL_SIZE - 1)
        db.user_test_state.insert_one({
            "_id": state_key,
            "hard_pointer": pointer,
            "test_count": 1,
            "last_test_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        pointer = (state["hard_pointer"] + count) % HARD_POOL_SIZE
        db.user_test_state.update_one(
            {"_id": state_key},
            {
                "$set": {"hard_pointer": pointer, "last_test_at": datetime.now(timezone.utc).isoformat()},
                "$inc": {"test_count": 1}
            }
        )

    indices = [(pointer + i) % HARD_POOL_SIZE for i in range(count)]

    questions = list(db.questions_hard.find({"skill": skill, "index": {"$in": indices}}))

    # Re-sort to match circular order (MongoDB doesn't guarantee $in order)
    index_order = {idx: pos for pos, idx in enumerate(indices)}
    questions.sort(key=lambda q: index_order.get(q["index"], 999))

    return questions


def get_user_test_count(db: Database, user_id: str, skill: str) -> int:
    state = db.user_test_state.find_one({"_id": {"user_id": user_id, "skill": skill}})
    return state["test_count"] if state else 0
