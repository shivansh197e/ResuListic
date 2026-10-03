import os
import sys
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from dotenv import load_dotenv

# Ensure the ml-services module is accessible
sys.path.append(os.path.join(os.path.dirname(__file__), 'ml-services'))

from builder.resume_builder import build_resume_document

# Load environment variables
load_dotenv()

# Initialize FastAPI App
app = FastAPI(title="ResuListic API", version="1.0", description="API for Resume Parsing and Skill Testing")

# Allow Frontend to communicate with this Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to MongoDB Atlas
MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.resulistic_db         # Creates/Accesses 'resulistic_db' database
resumes_collection = db.resumes   # Creates/Accesses 'resumes' collection

@app.get("/")
def read_root():
    return {"status": "online", "message": "Welcome to the ResuListic API!"}

@app.post("/api/parse-resume")
async def parse_resume(user_id: str = Form(...), file: UploadFile = File(...)):
    """
    Endpoint to upload a resume file, process it through the NLP pipeline, 
    and save the extracted JSON to MongoDB Atlas.
    """
    # 1. Validate file extension
    valid_extensions = ('.pdf', '.docx', '.png', '.jpg', '.jpeg')
    if not file.filename.lower().endswith(valid_extensions):
        raise HTTPException(status_code=400, detail="Unsupported file format.")

    # 2. Save the uploaded file temporarily so our parser can read it
    temp_dir = os.path.join(os.getcwd(), "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, file.filename)

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 3. Process the file through our ML/NLP pipeline
        print(f"Processing {file.filename} for user {user_id}...")
        parsed_data = build_resume_document(temp_file_path, user_id)

        if not parsed_data:
            raise HTTPException(status_code=500, detail="Failed to parse resume.")

        # 4. Save the result to MongoDB
        # We use update_one with upsert=True so if the user re-uploads a resume, 
        # it updates their existing document instead of creating a duplicate.
        resumes_collection.update_one(
            {"_id": parsed_data["_id"]},
            {"$set": parsed_data},
            upsert=True
        )

        return {
            "message": "Resume parsed and saved to database successfully!",
            "data": parsed_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 5. Clean up the temporary file to save space
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
