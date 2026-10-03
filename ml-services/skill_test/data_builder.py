"""
data_builder.py
───────────────
Populates the MongoDB with Moderate and Hard coding questions.

Supports 3 ingestion methods:
  1. CSV Import (Kaggle datasets)
  2. Web Scraping (GeeksForGeeks)
  3. MOCK Seeder (for testing the API without external dependencies)
"""

import os
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv

from schema.question_schema import CodingQuestionDoc, SolutionDoc

# Load environment variables (MONGODB_URI)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

def get_db():
    uri = os.getenv("MONGODB_URI")
    if not uri:
        # Fallback to localhost if no .env
        uri = "mongodb://localhost:27017"
    client = MongoClient(uri)
    return client.resulistic_db


def seed_mock_data(skills: list[str]):
    """
    Instantly generates 100 moderate and 50 hard dummy questions per skill.
    Used for testing the API logic without needing actual scraped data.
    """
    db = get_db()
    
    # Clear existing to prevent duplicates during testing
    db.questions_moderate.delete_many({"skill": {"$in": skills}})
    db.questions_hard.delete_many({"skill": {"$in": skills}})
    db.solutions.delete_many({"skill": {"$in": skills}})
    
    mod_docs = []
    hard_docs = []
    solution_docs = []
    
    for skill in skills:
        # Generate 100 Moderate
        for i in range(100):
            q = CodingQuestionDoc(
                skill=skill,
                index=i,
                title=f"Moderate {skill} Task #{i}",
                description=f"Write a {skill} program to solve moderate problem {i}.",
                source="mock"
            )
            mod_docs.append(q.model_dump())
            
            s = SolutionDoc(
                skill=skill,
                index=i,
                difficulty="moderate",
                reference_solution=f"# Model answer for Moderate {skill} Task {i}\ndef solve(): pass"
            )
            solution_docs.append(s.model_dump())
            
        # Generate 50 Hard
        for i in range(50):
            q = CodingQuestionDoc(
                skill=skill,
                index=i,
                title=f"Hard {skill} Architecture #{i}",
                description=f"Design and implement a scalable {skill} solution for problem {i}.",
                source="mock"
            )
            hard_docs.append(q.model_dump())
            
            s = SolutionDoc(
                skill=skill,
                index=i,
                difficulty="hard",
                reference_solution=f"# Model answer for Hard {skill} Task {i}\nclass ScalableSystem: pass"
            )
            solution_docs.append(s.model_dump())
            
    # Insert in batches for performance
    if mod_docs:
        db.questions_moderate.insert_many(mod_docs)
    if hard_docs:
        db.questions_hard.insert_many(hard_docs)
    if solution_docs:
        db.solutions.insert_many(solution_docs)
        
    print(f"✅ Successfully seeded {len(skills)*100} moderate and {len(skills)*50} hard questions.")


def scrape_gfg(skill: str):
    """
    TODO: Implement actual BeautifulSoup logic for GeeksForGeeks here.
    """
    pass

def load_from_csv(csv_path: str):
    """
    TODO: Implement pandas logic to read a Kaggle CSV and bulk insert here.
    """
    pass

if __name__ == "__main__":
    print("Seeding mock DB...")
    # Seed with some common skills so we can test the API
    seed_mock_data(["Python", "FastAPI", "MongoDB", "React", "Docker"])
