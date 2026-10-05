import os
import sys
from dotenv import load_dotenv
load_dotenv()  # LOAD BEFORE EVERYTHING ELSE

import json
from pymongo import MongoClient

# Add ml-services to path
sys.path.append(os.path.join(os.path.dirname(__file__), "ml-services"))

from skill_test.question_selector import generate_test_session

def run_test():
    uri = os.getenv("MONGODB_URI")
    client = MongoClient(uri)
    db = client.resulistic_db
    
    user_id = "manual_test_user"
    selected_skills = ["Array", "Dynamic Programming"]
    
    print(f"Generating test session for user: {user_id}")
    print(f"Selected skills: {selected_skills}")
    print("-" * 50)
    
    try:
        session_data = generate_test_session(db, user_id, selected_skills)
        frontend_payload = session_data["frontend_payload"]
        
        print(f"Session ID: {frontend_payload['session_id']}")
        print(f"Total Questions: {frontend_payload['total_questions']}")
        print("\n--- Questions ---")
        
        for idx, q in enumerate(frontend_payload['questions']):
            q_type = q.get('question_type', 'mcq')
            diff = q.get('difficulty', 'easy')
            title = q.get('title', 'MCQ Question')
            print(f"Q{idx+1}. [{q_type.upper()}] ({diff.upper()}) {title}")
            
        print("\n[SUCCESS] Test generation completed successfully!")
        
    except Exception as e:
        print(f"[ERROR] Failed to generate test: {e}")

if __name__ == "__main__":
    run_test()
