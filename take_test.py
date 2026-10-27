"""
take_test.py — Interactive CLI simulator for taking a ResuListic test.
Tests the entire pipeline: Groq AI MCQs, MongoDB Coding Questions, and Live Groq Code Grading.
"""
import argparse
import copy
import os
import sys
import time
from datetime import datetime, timezone
# Standard library UTF-8 console streams reconfiguration for Windows CP1252 resilience
for _stream in (sys.stdout, sys.stderr, sys.stdin):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# Bootstrap project virtualenv site-packages if available
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_venv_site = os.path.join(_PROJECT_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(_venv_site) and _venv_site not in sys.path:
    sys.path.insert(0, _venv_site)

_ml_services_dir = os.path.join(_PROJECT_ROOT, "ml-services")
if _ml_services_dir not in sys.path:
    sys.path.insert(0, _ml_services_dir)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pymongo import MongoClient
from skill_test.question_selector import generate_test_session
from skill_test.code_evaluator import evaluate_code

def main():
    parser = argparse.ArgumentParser(description="ResuListic Skill Test Simulator")
    parser.add_argument("--skill", "-s", dest="skills", help="Skills to test (e.g. DSA or Array,String)")
    parser.add_argument("--user-id", "-u", default=None, help="Candidate Name or ID")
    parser.add_argument("--generate-only", action="store_true", help="Generate questions without taking test")
    parser.add_argument("--time-limit-minutes", type=int, default=None, help="Time limit in minutes (default: 90)")

    args, unknown = parser.parse_known_args()

    # Determine skills and user_id: CLI flags override interactive input
    if args.skills:
        selected_skills = [s.strip() for s in args.skills.split(",") if s.strip()]
        user_id = args.user_id or "test_user"
    elif len(unknown) > 0 and not unknown[0].startswith("-"):
        selected_skills = [unknown[0].strip()]
        user_id = args.user_id or "test_user"
    else:
        print("=" * 60)
        print("   WELCOME TO RESULISTIC SKILL TEST SIMULATOR")
        print("=" * 60)
        try:
            prompt_user = input("\nEnter your Candidate Name or ID (e.g. test_user): ").strip()
            user_id = args.user_id or prompt_user or "test_user"
            skill_input = input("Enter skills to test separated by comma (e.g. Array, String) [default: Array]: ").strip()
            if skill_input:
                selected_skills = [s.strip() for s in skill_input.split(",") if s.strip()]
            else:
                selected_skills = ["Array"]
        except (EOFError, KeyboardInterrupt):
            user_id = args.user_id or "test_user"
            selected_skills = ["Array"]

    uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
    client = MongoClient(uri)
    db = client.resulistic_db

    print(f"\n[1/3] Generating test for {user_id} on {selected_skills}...")
    try:
        limit_arg = args.time_limit_minutes if args.time_limit_minutes is not None else 120
        session = generate_test_session(db, user_id, selected_skills, time_limit_minutes=limit_arg)
    except Exception as e:
        print(f"Error generating test: {e}", file=sys.stderr)
        sys.exit(1)

    payload = session["frontend_payload"]
    eval_key = session.get("evaluation_key", {})
    secret_answers = {int(k): v for k, v in eval_key.items()}
    
    questions = payload["questions"]
    print(f"[2/3] Generated {len(questions)} questions successfully!")
    print("=" * 60)

    # Persist session to MongoDB test_sessions
    try:
        db.test_sessions.insert_one(copy.deepcopy(session))
    except Exception:
        pass
    
    if args.generate_only:
        print("[GENERATE-ONLY] Questions preview:")
        for idx, q in enumerate(questions):
            q_type = q.get("question_type", "mcq")
            diff = q.get("difficulty", "easy").upper()
            skill = q.get("skill", "")
            title = q.get("title") or q.get("question", "")[:60]
            print(f"  [{idx}] Type: {q_type:<6} | Difficulty: {diff:<8} | Skill: {skill:<20} | {title}")
        print("=" * 60)
        print("[SUCCESS] Test session generated successfully.")
        return

    def format_time_remaining(rem_secs: float) -> str:
        rem_secs = max(0, int(rem_secs))
        h = rem_secs // 3600
        m = (rem_secs % 3600) // 60
        s = rem_secs % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    session_time_limit = payload.get("time_limit_minutes", 120)
    time_limit_minutes = args.time_limit_minutes if args.time_limit_minutes is not None else session_time_limit
    time_limit_seconds = time_limit_minutes * 60

    score = 0
    total_eval = 0
    coding_scores = []
    answered_submissions = []
    time_expired = False
    start_time = time.time()

    for idx, q in enumerate(questions):
        elapsed = time.time() - start_time
        remaining = time_limit_seconds - elapsed
        if remaining <= 0:
            print("\n" + "=" * 60)
            print(f"[Time Expired: 00:00:00] The {time_limit_minutes}-minute test time limit has been reached.")
            print("[Auto-submitting completed answers so far...]")
            print("=" * 60)
            time_expired = True
            break

        print(f"\n[Time Remaining: {format_time_remaining(remaining)}]")
        print(f"--- Question {idx + 1} of {len(questions)} ---")
        q_type = q.get("question_type", "mcq")
        diff = q.get("difficulty", "easy").upper()
        skill = q.get("skill", "")

        if q_type == "mcq":
            print(f"Type: MCQ | Difficulty: {diff} | Topic: {skill}")
            print(f"\n{q.get('question')}\n")
            for opt in q.get("options", []):
                print(f"  {opt}")
            
            try:
                user_ans = input("\nYour answer (A, B, C, or D): ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                print("\n[Input closed / interrupted — terminating test gracefully]")
                break

            answered_submissions.append({"q_index": idx, "user_answer": user_ans})

            correct_obj = secret_answers.get(idx, {})
            correct_ans = correct_obj.get("correct_answer", "").strip().upper()
            explanation = correct_obj.get("explanation", "")

            total_eval += 1
            if user_ans == correct_ans:
                print(f"-> CORRECT! (+1)")
                score += 1
            else:
                print(f"-> INCORRECT. Correct answer was {correct_ans}.")
            if explanation:
                print(f"   Explanation: {explanation}")

            if time.time() - start_time >= time_limit_seconds:
                print("\n" + "=" * 60)
                print(f"[Time Expired: 00:00:00] The {time_limit_minutes}-minute test time limit has been reached.")
                print("[Auto-submitting completed answers so far...]")
                print("=" * 60)
                time_expired = True
                break

        elif q_type == "coding":
            title = q.get("title", "")
            desc = q.get("description", "")
            q_id = q.get("question_id")
            
            # Resolve actual reference solution from DB
            ref_sol = "def solution(): pass"
            ev_data = secret_answers.get(idx, {})
            sol_doc = db.solutions.find_one({
                "skill": ev_data.get("skill", skill),
                "index": ev_data.get("question_index"),
                "difficulty": ev_data.get("difficulty", diff.lower())
            })
            if sol_doc:
                ref_sol = sol_doc.get("reference_solution", ref_sol)

            print(f"Type: CODING CHALLENGE | Difficulty: {diff} | Topic: {skill}")
            print(f"Title: {title}")
            print(f"\nProblem Description:\n{desc}\n")
            print("Write your Python solution below. When finished, type 'DONE' on a new line:")
            
            lines = []
            interrupted = False
            while True:
                try:
                    line = input()
                except (EOFError, KeyboardInterrupt):
                    interrupted = True
                    break
                if line.strip() == "DONE":
                    break
                lines.append(line)
            code_submission = "\n".join(lines).strip()

            if interrupted and not code_submission:
                print("\n[Input closed / interrupted — terminating test gracefully]")
                break

            if not code_submission:
                print("Skipped / empty solution.")
                continue

            answered_submissions.append({"q_index": idx, "user_answer": code_submission})

            print("\nEvaluating your code with Groq LLM-as-a-Judge...")
            try:
                res = evaluate_code(
                    code=code_submission,
                    problem_description=desc,
                    reference_solution=ref_sol,
                )
            except Exception as e:
                print(f"[!] Live LLM evaluation unavailable ({e}). Falling back to local syntax evaluator...")
                from skill_test.code_evaluator import mock_evaluate_code
                res = mock_evaluate_code(code_submission, desc, ref_sol)

            code_score = res.get("score", 0)
            coding_scores.append(code_score)

            print(f"-> Passed: {res.get('passed')}")
            print(f"-> Score: {code_score}/100")
            print(f"-> Time Complexity: {res.get('time_complexity')}")
            print(f"-> Feedback: {res.get('feedback')}")

            if time.time() - start_time >= time_limit_seconds:
                print("\n" + "=" * 60)
                print(f"[Time Expired: 00:00:00] The {time_limit_minutes}-minute test time limit has been reached.")
                print("[Auto-submitting completed answers so far...]")
                print("=" * 60)
                time_expired = True
                break

    # Post-loop deadline enforcement check (handles EOF, interruptions, or post-question evaluation overages)
    elapsed_total = time.time() - start_time
    if not time_expired and (elapsed_total >= time_limit_seconds):
        time_expired = True
        print("\n" + "=" * 60)
        print(f"[Time Expired: 00:00:00] The {time_limit_minutes}-minute test time limit has been reached.")
        print("[Auto-submitting completed answers so far...]")
        print("=" * 60)

    # Auto-submit answered questions to test_submissions collection
    submission_status = "submitted_expired" if time_expired else "submitted"
    mcq_score_val = round((score / total_eval) * 100.0, 1) if total_eval > 0 else 0.0
    avg_code_score = round(sum(coding_scores) / len(coding_scores), 1) if coding_scores else None
    overall_score = (
        round(0.4 * mcq_score_val + 0.6 * avg_code_score, 1)
        if avg_code_score is not None and total_eval > 0
        else (mcq_score_val if total_eval > 0 else (avg_code_score or 0.0))
    )
    try:
        sub_doc = {
            "session_id": payload.get("session_id") or session.get("session_id"),
            "user_id": user_id,
            "answers": answered_submissions,
            "status": submission_status,
            "is_expired": time_expired,
            "time_expired": time_expired,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": elapsed_total,
            "score": overall_score,
            "mcq_score": mcq_score_val,
            "mcq_correct": score,
            "mcq_total": total_eval,
            "coding_scores": coding_scores,
        }
        if avg_code_score is not None:
            sub_doc["coding_score"] = avg_code_score
        db.test_submissions.insert_one(sub_doc)
    except Exception:
        pass

    print("\n" + "=" * 60)
    print(f"TEST COMPLETE! MCQ Score: {score}/{total_eval}")
    print("=" * 60)

    # ── Job Domain Prediction & Career Switch Report ────────────────────────
    try:
        from job_predictor.predictor import predict_job_domain
        if len(answered_submissions) == 0:
            mcq_pct = 0.0
            avg_code = 0.0
        else:
            mcq_pct = (score / max(1, total_eval)) * 100.0 if total_eval > 0 else (avg_code_score if avg_code_score is not None else 0.0)
            avg_code = avg_code_score if avg_code_score is not None else (mcq_pct if total_eval > 0 else 0.0)
        
        pred = predict_job_domain(
            skills=selected_skills,
            mcq_score=mcq_pct,
            coding_score=avg_code,
        )

        print("\n" + "=" * 60)
        print("   AI EVALUATION & JOB DOMAIN PREDICTION REPORT")
        print("=" * 60)
        print(f"Primary Predicted Domain:   {pred['primary_domain']}")
        print(f"Domain Match Confidence:    {pred['confidence'] * 100:.1f}%")
        print(f"Overall Competency Score:   {pred['overall_test_score']}/100")
        
        print("\nPotential Career Switch Domains:")
        for sw in pred.get("switch_domains", []):
            missing = ", ".join(sw.get("missing_skills", [])[:4])
            print(f"  • {sw['domain']:<28} (Confidence: {sw['confidence']*100:.1f}%, Feasibility: {sw['feasibility']})")
            if missing:
                print(f"    Required skills to switch:  {missing}")
        print("=" * 60 + "\n")

        # ── Compensation Estimation & Salary Prediction ─────────────────────
        try:
            from salary_predictor.predictor import predict_salary
            sal = predict_salary(
                skills=selected_skills,
                domain=pred.get("primary_domain"),
                mcq_score=mcq_pct,
                coding_score=avg_code,
            )
            print("=" * 60)
            print("   COMPENSATION ESTIMATION & SALARY PREDICTION")
            print("=" * 60)
            print(f"Estimated Salary Package:   {sal['predicted_lpa']} LPA")
            print(f"Expected Compensation Range: {sal['salary_range']['min_lpa']} LPA - {sal['salary_range']['max_lpa']} LPA")
            print(f"Market Compensation Bracket: {sal['compensation_tier']}")
            print("\nKey Compensation Drivers:")
            for fac in sal.get("factors", []):
                print(f"  • {fac['factor']:<42} [{fac['impact']}]")
            print("=" * 60 + "\n")
        except Exception as se:
            print(f"[Notice] Salary prediction report skipped: {se}")

    except Exception as e:
        print(f"[Notice] Domain prediction report skipped: {e}")

if __name__ == "__main__":
    main()
