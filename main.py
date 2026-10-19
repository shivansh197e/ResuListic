import os
import sys
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
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
    PredictSalaryRequest,
    PredictSalaryResponse,
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
from salary_predictor.predictor import (
    predict_salary,
    predict_salary_for_user,
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

# Mount static directory for Frontend SPA
_static_dir = os.path.join(_PROJECT_ROOT, "static")
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

@app.get("/")
def read_root():
    index_path = os.path.join(_PROJECT_ROOT, "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"status": "online", "message": "Welcome to the ResuListic API!"}

@app.get("/api/health")
def health_check():
    return {"status": "online", "message": "ResuListic backend operational"}

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
    # 1. Fetch user doc to get fallback skills if needed
    user_doc = resumes_collection.find_one({"_id": request.user_id})
    skills_to_test = request.selected_skills

    if not skills_to_test:
        if not user_doc:
            raise HTTPException(status_code=404, detail="User resume not found. Cannot start test.")
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
    clean_session_id = str(submission.session_id).strip()
    session = (
        test_sessions_collection.find_one({"frontend_payload.session_id": submission.session_id})
        or test_sessions_collection.find_one({"session_id": submission.session_id})
        or test_sessions_collection.find_one({"frontend_payload.session_id": clean_session_id})
        or test_sessions_collection.find_one({"session_id": clean_session_id})
    )
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
    session_questions = session.get("frontend_payload", {}).get("questions") or session.get("questions") or []
    pub_q_map = {str(q.get("q_index")): q for q in session_questions if isinstance(q, dict)}

    mcq_correct = 0
    mcq_total = 0
    mod_total = 0
    mod_passed = 0
    mod_score_sum = 0.0
    hard_total = 0
    hard_passed = 0
    hard_score_sum = 0.0
    graded_answers = []
    skill_stats = {}

    for ans in submission.answers:
        q_idx = str(ans.get("q_index", ""))
        raw_user_ans = ans.get("user_answer")
        user_ans = str(raw_user_ans).strip().upper() if raw_user_ans is not None else ""
        ev = eval_key.get(q_idx) or eval_key.get(int(q_idx) if q_idx.isdigit() else -1) or {}
        pub_q = pub_q_map.get(q_idx, {})

        is_mcq = ev.get("question_type") == "mcq" or "correct_answer" in ev or pub_q.get("question_type") == "mcq"
        difficulty = str(ev.get("difficulty") or pub_q.get("difficulty") or "").lower()

        if is_mcq:
            mcq_total += 1
            corr = str(ev.get("correct_answer", "")).strip().upper()
            is_corr = bool(user_ans and user_ans == corr)
            q_marks = 1.0 if is_corr else 0.0
            if is_corr:
                mcq_correct += 1
            graded_answers.append({
                "q_index": ans.get("q_index"),
                "user_answer": raw_user_ans,
                "correct_answer": corr,
                "is_correct": is_corr,
                "marks_obtained": q_marks,
                "max_marks": 1.0,
                "difficulty": "easy",
            })
            q_skill = ev.get("skill") or pub_q.get("skill")
            if q_skill:
                if q_skill not in skill_stats:
                    skill_stats[q_skill] = {"correct": 0.0, "total": 0}
                skill_stats[q_skill]["total"] += 1
                if is_corr:
                    skill_stats[q_skill]["correct"] += 1.0
        else:
            code_str = str(raw_user_ans or "").strip()
            is_subj = pub_q.get("question_type") in ("subjective", "text")
            # Filter out comments and blank lines to detect untouched starter code
            meaningful_lines = [
                ln.strip() for ln in code_str.splitlines()
                if ln.strip() and not ln.strip().startswith("#") and not ln.strip().startswith("//")
            ]
            if is_subj:
                is_untouched_starter = len(code_str) < 5
            else:
                is_untouched_starter = (
                    len(meaningful_lines) == 0
                    or (len(meaningful_lines) == 2 and meaningful_lines[0].startswith("def ") and meaningful_lines[1] == "pass")
                    or code_str == (pub_q.get("starter_code") or "").strip()
                )
            if is_untouched_starter:
                c_score = 0.0
                c_passed = False
            elif ans.get("eval_score") is not None:
                c_score = float(ans.get("eval_score"))
                c_passed = c_score >= 50.0
            else:
                from skill_test.code_evaluator import mock_evaluate_code
                m_res = mock_evaluate_code(code_str)
                c_score = float(m_res.get("score", 0.0))
                c_passed = bool(m_res.get("passed", False))

            is_hard = difficulty == "hard" or float(ev.get("max_marks", 0.0)) >= 20.0
            if is_hard:
                hard_total += 1
                q_max_marks = 25.0
                earned_marks = round((c_score / 100.0) * q_max_marks, 2)
                hard_score_sum += earned_marks
                if c_passed:
                    hard_passed += 1
            else:
                mod_total += 1
                q_max_marks = 10.0
                earned_marks = round((c_score / 100.0) * q_max_marks, 2)
                mod_score_sum += earned_marks
                if c_passed:
                    mod_passed += 1

            graded_answers.append({
                "q_index": ans.get("q_index"),
                "user_answer": raw_user_ans,
                "score": c_score,
                "marks_obtained": earned_marks,
                "max_marks": q_max_marks,
                "difficulty": "hard" if is_hard else "moderate",
                "is_correct": c_passed,
            })
            q_skill = ev.get("skill") or pub_q.get("skill")
            if q_skill:
                if q_skill not in skill_stats:
                    skill_stats[q_skill] = {"correct": 0.0, "total": 0}
                skill_stats[q_skill]["total"] += 1
                skill_stats[q_skill]["correct"] += (c_score / 100.0)

    # 100-Mark System: MCQs = 20 marks, Moderate = 30 marks, Hard = 50 marks
    if mcq_total == 20:
        mcq_marks_val = round(mcq_correct * 1.0, 1)
    elif mcq_total > 0:
        mcq_marks_val = round((mcq_correct / mcq_total) * 20.0, 1)
    else:
        mcq_marks_val = 0.0

    if mod_total == 3:
        moderate_marks_val = round(mod_score_sum, 1)
    elif mod_total > 0:
        moderate_marks_val = round((mod_score_sum / (mod_total * 10.0)) * 30.0, 1)
    else:
        moderate_marks_val = 0.0

    if hard_total == 2:
        hard_marks_val = round(hard_score_sum, 1)
    elif hard_total > 0:
        hard_marks_val = round((hard_score_sum / (hard_total * 25.0)) * 50.0, 1)
    else:
        hard_marks_val = 0.0

    coding_total = mod_total + hard_total
    coding_passed = mod_passed + hard_passed

    if coding_total > 0:
        score_val = round(min(100.0, max(0.0, mcq_marks_val + moderate_marks_val + hard_marks_val)), 1)
        mcq_score_val = round((mcq_correct / mcq_total) * 100.0, 1) if mcq_total > 0 else 0.0
        coding_score_val = round(((moderate_marks_val + hard_marks_val) / 80.0) * 100.0, 1)
        total_questions_out = mcq_total + coding_total
        correct_answers_out = mcq_correct + coding_passed
    else:
        mcq_score_val = round((mcq_correct / mcq_total) * 100.0, 1) if mcq_total > 0 else 0.0
        score_val = mcq_score_val
        coding_score_val = 0.0
        total_questions_out = mcq_total
        correct_answers_out = mcq_correct

    # Calculate letter grade
    if score_val >= 90.0:
        grade = "S+"
    elif score_val >= 80.0:
        grade = "A"
    elif score_val >= 70.0:
        grade = "B"
    elif score_val >= 60.0:
        grade = "C"
    elif score_val >= 50.0:
        grade = "D"
    elif score_val >= 40.0:
        grade = "E"
    else:
        grade = "F"

    # Synthesize dynamic skill breakdown from tested skills
    session_skills = (
        session.get("skills_tested")
        or session.get("frontend_payload", {}).get("skills_tested")
        or []
    )
    if not session_skills:
        extracted = [q.get("skill") for q in session_questions if isinstance(q, dict) and q.get("skill")]
        if not extracted and eval_key:
            extracted = [ev.get("skill") for ev in eval_key.values() if isinstance(ev, dict) and ev.get("skill")]
        session_skills = list(dict.fromkeys(extracted))

    if not session_skills:
        session_skills = ["Problem Solving", "Technical Foundations"]

    skill_breakdown = []
    for s_idx, skill_name in enumerate(session_skills):
        if skill_name in skill_stats and skill_stats[skill_name]["total"] > 0:
            st = skill_stats[skill_name]
            s_score = round((st["correct"] / st["total"]) * 100.0, 1)
        else:
            s_score = round(min(100.0, max(0.0, score_val + ((s_idx % 3) - 1) * 2.0)), 1)
        skill_breakdown.append({
            "skill": skill_name,
            "score": s_score
        })

    # 4. Save the submission document
    submission_doc = submission.model_dump()
    submission_doc["status"] = status
    submission_doc["is_expired"] = is_expired
    submission_doc["submitted_at"] = now_iso
    if duration_seconds is not None:
        submission_doc["duration_seconds"] = duration_seconds
    submission_doc["score"] = score_val
    submission_doc["mcq_score"] = mcq_score_val
    submission_doc["coding_score"] = coding_score_val
    submission_doc["mcq_marks"] = mcq_marks_val
    submission_doc["moderate_marks"] = moderate_marks_val
    submission_doc["hard_marks"] = hard_marks_val
    submission_doc["score_percentage"] = score_val
    submission_doc["mcq_correct"] = mcq_correct
    submission_doc["mcq_total"] = mcq_total
    submission_doc["correct_answers"] = correct_answers_out
    submission_doc["total_questions"] = total_questions_out
    submission_doc["grade"] = grade
    submission_doc["skill_breakdown"] = skill_breakdown
    submission_doc["graded_answers"] = graded_answers

    test_submissions_collection.insert_one(submission_doc)

    return {
        "status": status,
        "session_id": submission.session_id,
        "is_expired": is_expired,
        "score": score_val,
        "mcq_score": mcq_score_val,
        "coding_score": coding_score_val,
        "mcq_marks": mcq_marks_val,
        "moderate_marks": moderate_marks_val,
        "hard_marks": hard_marks_val,
        "score_percentage": score_val,
        "correct_answers": correct_answers_out,
        "total_questions": total_questions_out,
        "grade": grade,
        "skill_breakdown": skill_breakdown,
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


@app.post("/api/predict-salary", response_model=PredictSalaryResponse)
async def predict_salary_endpoint(request: PredictSalaryRequest):
    """
    Evaluates candidate resume skills and assessment performance to predict compensation
    (ranging from 3.0 LPA to 30.0 LPA, or Unemployed) with college tier detection and factors.
    """
    try:
        resume_text = request.resume_text
        target_skills = list(request.skills) if request.skills else []

        # If user_id provided and resume_text / skills are missing, resolve from MongoDB
        if request.user_id and db is not None:
            user_doc = db.resumes.find_one({"_id": request.user_id})
            if user_doc:
                if not resume_text:
                    edu_text = user_doc.get("sections", {}).get("education", "")
                    raw_text = user_doc.get("raw_text", "")
                    resume_text = f"{edu_text}\n{raw_text[:2000]}"
                if not target_skills:
                    enrichment = user_doc.get("enrichment", {})
                    skills_obj = enrichment.get("skills", {})
                    high_skills = skills_obj.get("high", [])
                    med_skills = skills_obj.get("medium", [])
                    target_skills = list(dict.fromkeys(high_skills + med_skills))

        # Case A: user_id provided without direct skills or scores -> resolve from MongoDB
        if request.user_id and not target_skills and request.mcq_score is None and request.coding_score is None and request.overall_score is None:
            res = predict_salary_for_user(db, request.user_id)
            res["user_id"] = request.user_id
            return PredictSalaryResponse(**res)

        # Case B: Direct skills / test scores passed in payload (with DB resume enrichment)
        res = predict_salary(
            skills=target_skills,
            domain=request.domain,
            mcq_score=request.mcq_score,
            coding_score=request.coding_score,
            overall_score=request.overall_score,
            resume_text=resume_text,
            experience_tier=request.experience_tier or "fresher",
        )
        res["user_id"] = request.user_id
        return PredictSalaryResponse(**res)

    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Salary prediction failed: {str(e)}")

