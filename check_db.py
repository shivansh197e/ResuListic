import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv('MONGODB_URI')
client = MongoClient(uri)
db = client['resulistic_db']  

print('=== Database Status ===')
print(f'Moderate Questions: {db.questions_moderate.count_documents({})}')
print(f'Hard Questions:     {db.questions_hard.count_documents({})}')
print(f'Solutions:          {db.solutions.count_documents({})}')
print('\n=== Sample Moderate Question ===')
sample = db.questions_moderate.find_one()
if sample:
    print(f"Title: {sample.get('title')}")
    print(f"Skill: {sample.get('skill')}")
    print(f"Description snippet: {sample.get('description', '')[:100]}...")
else:
    print('No data found yet.')
