"""
data_builder.py — Seeds MongoDB with mock coding questions for testing.
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv
from schema.question_schema import CodingQuestionDoc, SolutionDoc

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def get_db():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    return MongoClient(uri).resulistic_db


def seed_mock_data(skills: list[str]):
    """Generate 100 moderate + 50 hard dummy questions per skill."""
    db = get_db()

    # Clear existing for these skills
    for col in (db.questions_moderate, db.questions_hard, db.solutions):
        col.delete_many({"skill": {"$in": skills}})

    mod_docs, hard_docs, sol_docs = [], [], []

    for skill in skills:
        for i in range(100):
            mod_docs.append(CodingQuestionDoc(
                skill=skill, index=i,
                title=f"Moderate {skill} Task #{i}",
                description=f"Write a {skill} program to solve moderate problem {i}.",
                source="mock",
            ).model_dump())
            sol_docs.append(SolutionDoc(
                skill=skill, index=i, difficulty="moderate",
                reference_solution=f"# Model answer for Moderate {skill} Task {i}\ndef solve(): pass",
            ).model_dump())

        for i in range(50):
            hard_docs.append(CodingQuestionDoc(
                skill=skill, index=i,
                title=f"Hard {skill} Architecture #{i}",
                description=f"Design and implement a scalable {skill} solution for problem {i}.",
                source="mock",
            ).model_dump())
            sol_docs.append(SolutionDoc(
                skill=skill, index=i, difficulty="hard",
                reference_solution=f"# Model answer for Hard {skill} Task {i}\nclass ScalableSystem: pass",
            ).model_dump())

    db.questions_moderate.insert_many(mod_docs)
    db.questions_hard.insert_many(hard_docs)
    db.solutions.insert_many(sol_docs)
    print(f"Seeded {len(skills)*100} moderate + {len(skills)*50} hard questions.")


if __name__ == "__main__":
    seed_mock_data(["Python", "FastAPI", "MongoDB", "React", "Docker"])
