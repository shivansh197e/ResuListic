import os
import sys
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from dotenv import load_dotenv

from datetime import datetime, timezone

# Load environment variables early so dependent modules have API keys
load_dotenv()

# Bootstrap project virtualenv site-packages if available
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_venv_site = os.path.join(_PROJECT_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(_venv_site) and _venv_site not in sys.path:
    sys.path.insert(0, _venv_site)

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
    PredictDomainRequest,
    PredictDomainResponse,
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
from job_predictor.predictor import (
    predict_job_domain,
    predict_for_user,
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
    Receives user test answers, enforces the 90-minute session deadline,
    grades completed MCQ answers against secret keys, and persists submission records.
    """
    # 1. Verify the session exists
    session = test_sessions_collection.find_one({"frontend_payload.session_id": submission.session_id})
    if not session:
        session = test_sessions_collection.find_one({"session_id": submission.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Test session not found.")

    # 2. Enforce session deadline
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    expires_at_val = session.get("expires_at") or session.get("frontend_payload", {}).get("expires_at")
    started_at_val = session.get("started_at") or session.get("frontend_payload", {}).get("started_at") or session.get("frontend_payload", {}).get("created_at")

    is_expired = False
    duration_seconds = None

    time_limit_val = (
        session.get("time_limit_minutes")
        or session.get("frontend_payload", {}).get("time_limit_minutes")
        or 90
    )
    try:
        time_limit_minutes = float(time_limit_val)
    except (ValueError, TypeError):
        time_limit_minutes = 90.0

    if started_at_val:
        try:
            if isinstance(started_at_val, datetime):
                started_dt = started_at_val if started_at_val.tzinfo else started_at_val.replace(tzinfo=timezone.utc)
            else:
                started_dt = datetime.fromisoformat(str(started_at_val).replace("Z", "+00:00"))
                if started_dt.tzinfo is None:
                    started_dt = started_dt.replace(tzinfo=timezone.utc)
            duration_seconds = max(0.0, (now_dt - started_dt).total_seconds())
        except Exception as parse_err:
            print(f"[WARNING] Could not parse started_at '{started_at_val}': {parse_err}")

    if expires_at_val:
        try:
            if isinstance(expires_at_val, datetime):
                expires_dt = expires_at_val if expires_at_val.tzinfo else expires_at_val.replace(tzinfo=timezone.utc)
            else:
                expires_dt = datetime.fromisoformat(str(expires_at_val).replace("Z", "+00:00"))
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if now_dt >= expires_dt:
                is_expired = True
        except Exception as parse_err:
            print(f"[WARNING] Could not parse expires_at '{expires_at_val}': {parse_err}")

    # Fallback: if expires_at was absent or unparseable, check against started_at + time limit
    if not is_expired and duration_seconds is not None:
        if duration_seconds >= (time_limit_minutes * 60.0):
            is_expired = True

    if is_expired:
        status = "submitted_expired"
        dur_msg = f"{duration_seconds:.1f}s" if duration_seconds is not None else "unknown duration"
        print(f"[WARNING] Session {submission.session_id} submitted after 90m expiration. Duration taken: {dur_msg}.")
    else:
        status = "submitted"

    # 3. Grade completed questions against session evaluation key
    eval_key = session.get("evaluation_key", {})
    mcq_correct = 0
    mcq_total = 0
    graded_answers = []

    for ans in submission.answers:
        q_idx = str(ans.get("q_index", ""))
        raw_user_ans = ans.get("user_answer")
        user_ans = str(raw_user_ans).strip().upper() if raw_user_ans is not None else ""
        ev = eval_key.get(q_idx) or eval_key.get(int(q_idx) if q_idx.isdigit() else -1)
        if ev and ev.get("question_type") == "mcq":
            mcq_total += 1
            corr = str(ev.get("correct_answer", "")).strip().upper()
            is_corr = bool(user_ans and user_ans == corr)
            if is_corr:
                mcq_correct += 1
            graded_answers.append({
                "q_index": ans.get("q_index"),
                "user_answer": raw_user_ans,
                "correct_answer": corr,
                "is_correct": is_corr,
            })
        else:
            graded_answers.append(ans)

    # 4. Save the submission document
    submission_doc = submission.model_dump()
    submission_doc["status"] = status
    submission_doc["is_expired"] = is_expired
    submission_doc["submitted_at"] = now_iso
    if duration_seconds is not None:
        submission_doc["duration_seconds"] = duration_seconds
    if mcq_total > 0:
        score_val = round((mcq_correct / mcq_total) * 100.0, 1)
        submission_doc["score"] = score_val
        submission_doc["mcq_score"] = score_val
        submission_doc["mcq_correct"] = mcq_correct
        submission_doc["mcq_total"] = mcq_total
    submission_doc["graded_answers"] = graded_answers

    test_submissions_collection.insert_one(submission_doc)

    return {
        "status": status,
        "session_id": submission.session_id,
        "is_expired": is_expired,
        "score": submission_doc.get("score"),
        "mcq_score": submission_doc.get("mcq_score"),
        "message": (
            "Test submitted after deadline. Completed answers evaluated."
            if is_expired
            else "Test submitted successfully."
        ),
        "duration_seconds": duration_seconds,
        "questions_answered": len(submission.answers),
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


@app.post("/api/predict-domain", response_model=PredictDomainResponse)
async def predict_domain_endpoint(request: PredictDomainRequest):
    """
    Evaluates candidate resume skills and test performance to predict their primary job domain,
    class probabilities, and actionable career switch recommendations with skill gap analysis.
    """
    try:
        # Case A: user_id provided without direct skills -> resolve from MongoDB
        if request.user_id and not request.skills and request.mcq_score is None and request.coding_score is None:
            res = predict_for_user(db, request.user_id)
            res["user_id"] = request.user_id
            return PredictDomainResponse(**res)

        # Case B: Direct skills / test scores passed in payload (or hybrid)
        res = predict_job_domain(
            skills=request.skills or [],
            resume_text=request.resume_text,
            mcq_score=request.mcq_score,
            coding_score=request.coding_score,
        )
        res["user_id"] = request.user_id
        return PredictDomainResponse(**res)

    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Domain prediction failed: {str(e)}")

