import os
import sys
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables early so dependent modules have API keys
load_dotenv()

# Ensure the ml-services module is accessible
sys.path.append(os.path.join(os.path.dirname(__file__), 'ml-services'))

try:
    from builder.resume_builder import build_resume_document
except Exception:
    build_resume_document = None

from schema.question_schema import (
    StartTestRequest,
    AnswerSubmission,
    EvaluateRequest,
    EvaluateResponse,
)

try:
    from skill_test.question_selector import generate_test_session
except Exception:
    generate_test_session = None

from skill_test.code_evaluator import (
    evaluate_code,
    get_question_and_solution,
    save_submission,
)

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
test_sessions_collection = db.test_sessions
test_submissions_collection = db.test_submissions
submissions_collection = db.submissions

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


@app.get("/api/user-skills/{user_id}")
async def get_user_skills(user_id: str):
    """
    Fetches the skills extracted from the user's resume so the frontend
    can display them for test selection.
    """
    user_doc = resumes_collection.find_one({"_id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User resume not found.")
    
    # Extract skills safely
    skills = user_doc.get("enrichment", {}).get("skills", {})
    
    return {
        "high_confidence": skills.get("high", []),
        "medium_confidence": skills.get("medium", [])
    }

@app.post("/api/start-test")
async def start_test(request: StartTestRequest):
    """
    Generates a 10-question dynamic test session based on the selected skills.
    If no skills are selected, it defaults to the user's top high-confidence skills.
    """
    # 1. Fetch user doc to ensure they exist and get fallback skills if needed
    user_doc = resumes_collection.find_one({"_id": request.user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User resume not found. Cannot start test.")

    skills_to_test = request.selected_skills
    
    # If the frontend sent null or an empty list, auto-pick up to 5 high-confidence skills
    if not skills_to_test:
        high_skills = user_doc.get("enrichment", {}).get("skills", {}).get("high", [])
        if not high_skills:
            raise HTTPException(status_code=400, detail="No high-confidence skills found to auto-pick. Please select skills manually.")
        skills_to_test = high_skills[:5]

    try:
        # 2. Generate the test session using our Orchestrator
        # Note: This calls Gemini (AI) and MongoDB (Circular Tracker)
        session_data = generate_test_session(db, request.user_id, skills_to_test)
        
        # 3. Save the full session (including evaluation keys/answers) to the database securely
        test_sessions_collection.insert_one(session_data)
        
        # 4. Return ONLY the frontend-safe payload (which has answers stripped out)
        return session_data["frontend_payload"]
        
    except Exception as e:
        print(f"[ERROR] generating test: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/submit-test")
async def submit_test(submission: AnswerSubmission):
    """
    Receives the user's answers. In Phase 5, this will trigger the AI Evaluator.
    For now, it saves the raw answers to the database.
    """
    # 1. Verify the session exists
    session = test_sessions_collection.find_one({"frontend_payload.session_id": submission.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Test session not found.")
        
    # 2. Save the submission
    submission_doc = submission.model_dump()
    submission_doc["status"] = "pending_evaluation"
    
    test_submissions_collection.insert_one(submission_doc)
    
    return {
        "status": "submitted",
        "session_id": submission.session_id,
        "message": "Test submitted successfully. Evaluation pending Phase 5."
    }


@app.post("/api/evaluate", response_model=EvaluateResponse)
async def evaluate_submission(request: EvaluateRequest):
    """
    Evaluates candidate's Python code against problem description and reference solution
    using Groq LLM-as-a-Judge, saves submission to MongoDB, and returns the grade.
    """
    try:
        problem_desc = request.problem_description
        ref_sol = request.reference_solution

        # Resolve from database if problem description or reference solution not supplied
        if not problem_desc or not ref_sol:
            q_doc, sol_doc = get_question_and_solution(db, request.question_id)
            if not q_doc and not problem_desc:
                raise HTTPException(status_code=404, detail="Question not found")
            problem_desc = problem_desc or q_doc.get("description", "")
            ref_sol = ref_sol or sol_doc.get("reference_solution", "")

        # Execute evaluation (falls back to mock if requested, offline, or key missing)
        eval_result = evaluate_code(
            code=request.code,
            problem_description=problem_desc or "No description provided.",
            reference_solution=ref_sol or "No reference solution provided.",
            mock=bool(request.mock),
        )

        # Save submission record to MongoDB submissions collection
        submission_id = save_submission(
            db=db,
            user_id=request.user_id,
            question_id=request.question_id,
            submitted_code=request.code,
            evaluation_result=eval_result,
        )

        return EvaluateResponse(
            passed=eval_result["passed"],
            score=eval_result["score"],
            feedback=eval_result["feedback"],
            time_complexity=eval_result["time_complexity"],
            submission_id=submission_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Evaluation failed: {str(e)}")

