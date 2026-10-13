"""
predictor.py — Production inference service for Salary Prediction (4 LPA to 30+ LPA).
Combines candidate resume skills, domain, and verified test scores to estimate compensation package and salary factors.
"""
import os
import sys
import joblib
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Any

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_ML_SERVICES_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, _ML_SERVICES_DIR)

from salary_predictor.data_generator import HIGH_IMPACT_SKILLS, DOMAINS, count_high_impact_skills

ARTIFACTS_DIR = os.path.join(_CURRENT_DIR, "model_artifacts")
MODEL_PATH = os.path.join(ARTIFACTS_DIR, "salary_model.joblib")

_CACHED_SALARY_MODEL = None


def get_salary_model():
    """Lazily loads and caches the trained salary regression pipeline."""
    global _CACHED_SALARY_MODEL
    if _CACHED_SALARY_MODEL is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Salary model not found at {MODEL_PATH}. Run train_and_evaluate.py first.")
        _CACHED_SALARY_MODEL = joblib.load(MODEL_PATH)
    return _CACHED_SALARY_MODEL


def predict_salary(
    skills: Optional[List[str]] = None,
    domain: Optional[str] = None,
    mcq_score: Optional[float] = None,
    coding_score: Optional[float] = None,
    experience_tier: str = "fresher",
) -> Dict[str, Any]:
    """
    Predicts candidate salary package (4 LPA to 30+ LPA) combining resume skills and test scores.
    """
    model = get_salary_model()
    skills = skills or []
    
    # Resolve domain if missing
    if not domain or domain not in DOMAINS:
        # Default based on skill heuristics or backend default
        skills_lower = " ".join(skills).lower()
        if any(k in skills_lower for k in ["pytorch", "tensorflow", "machine learning", "data science"]):
            domain = "Data Science & AI/ML"
        elif any(k in skills_lower for k in ["docker", "kubernetes", "aws", "devops"]):
            domain = "Cloud & DevOps"
        elif any(k in skills_lower for k in ["react native", "flutter", "android", "ios"]):
            domain = "Mobile App Development"
        elif any(k in skills_lower for k in ["react", "vue", "html", "css", "tailwind"]):
            domain = "Frontend Web Development"
        else:
            domain = "Backend Web Development"

    # Normalize test scores
    norm_mcq = float(np.clip(mcq_score if mcq_score is not None else 70.0, 0.0, 100.0))
    norm_code = float(np.clip(coding_score if coding_score is not None else 70.0, 0.0, 100.0))
    total_score = round(0.4 * norm_mcq + 0.6 * norm_code, 2)
    
    num_skills = len(skills)
    hi_count = count_high_impact_skills(skills)

    input_df = pd.DataFrame([{
        "domain": domain,
        "experience_tier": experience_tier if experience_tier in ["fresher", "early_career", "mid_level"] else "fresher",
        "num_skills": num_skills,
        "high_impact_skills": hi_count,
        "mcq_score": norm_mcq,
        "coding_score": norm_code,
        "total_score": total_score,
    }])

    raw_pred = float(model.predict(input_df)[0])

    # ── Merit-First Calibration & Starting 25%ile Guardrail (< 10 LPA) ─────
    # Skill test score carries 80%+ weight; resume skills only unlock proportionally to test score
    verification_gate = max(0.0, (total_score - 45.0) / 55.0) ** 1.5
    if total_score <= 55.0:
        # Starting 25%ile: Strictly < 10 LPA regardless of resume skill count
        merit_cap = 4.0 + (total_score / 55.0) * 4.2 + min(0.7, hi_count * 0.12)
        blended = 0.35 * raw_pred + 0.65 * merit_cap
        predicted_lpa = round(float(np.clip(min(blended, merit_cap), 4.0, 9.2)), 2)
        min_lpa = round(max(4.0, predicted_lpa - 1.2), 2)
        max_lpa = round(min(9.8, predicted_lpa + 1.2), 2)
    elif total_score < 70.0:
        # 25th - 50th %ile: Moderate test verification
        merit_anchor = 7.8 + ((total_score - 55.0) / 15.0) * 3.8 + (hi_count * 0.45 * verification_gate)
        blended = 0.6 * raw_pred + 0.4 * merit_anchor
        predicted_lpa = round(float(np.clip(blended, 6.5, 13.5)), 2)
        min_lpa = round(max(4.0, predicted_lpa - 1.5), 2)
        max_lpa = round(min(35.0, predicted_lpa + 2.0), 2)
    else:
        predicted_lpa = round(float(np.clip(raw_pred, 4.0, 35.0)), 2)
        min_lpa = round(max(4.0, predicted_lpa - 2.0), 2)
        max_lpa = round(min(35.0, predicted_lpa + 3.0), 2)

    # Classify compensation tier
    if predicted_lpa >= 22.0:
        tier_label = "Top-Tier Product / Unicorn Bracket (22 - 35+ LPA)"
    elif predicted_lpa >= 14.0:
        tier_label = "Tier-1 Product & Growth Startup Bracket (14 - 22 LPA)"
    elif predicted_lpa >= 8.5:
        tier_label = "Established Tech & Mid-Tier Product Bracket (8.5 - 14 LPA)"
    else:
        tier_label = "Entry-Level / Foundation Bracket (4 - 8.5 LPA)"

    # Identify primary salary drivers (Skill Test = Primary 80% Driver)
    factors = []
    if total_score >= 85.0:
        factors.append({"factor": f"Elite Skill Assessment Score ({total_score:.0f}/100 — 80% Weight)", "impact": "+7.5 to +14.0 LPA"})
    elif total_score >= 70.0:
        factors.append({"factor": f"Verified Skill Assessment Score ({total_score:.0f}/100 — 80% Weight)", "impact": "+3.5 to +6.5 LPA"})
    elif total_score > 55.0:
        factors.append({"factor": f"Moderate Assessment Score ({total_score:.0f}/100 — 80% Weight)", "impact": "+1.5 to +3.0 LPA"})
    else:
        factors.append({"factor": f"Low Skill Test Score ({total_score:.0f}/100 — Bottom 25%ile)", "impact": "Capped < 10 LPA (Unverified Resume)"})

    if hi_count > 0:
        matched_hi = [s for s in skills if s.strip().lower() in HIGH_IMPACT_SKILLS]
        hi_preview = ", ".join(matched_hi[:3])
        verified_hi_boost = round(hi_count * 1.25 * verification_gate, 1)
        if total_score <= 55.0:
            factors.append({"factor": f"Resume Skills Discounted by Low Test Score ({hi_preview})", "impact": f"+{verified_hi_boost:.1f} LPA (Gated)"})
        else:
            factors.append({"factor": f"Test-Verified Skill Premium ({hi_preview})", "impact": f"+{verified_hi_boost:.1f} LPA"})

    factors.append({"factor": f"Target Domain Benchmark ({domain})", "impact": "Domain Market Rate"})

    return {
        "predicted_lpa": predicted_lpa,
        "salary_range": {
            "min_lpa": min_lpa,
            "max_lpa": max_lpa,
        },
        "compensation_tier": tier_label,
        "domain": domain,
        "overall_test_score": total_score,
        "factors": factors,
    }


def predict_salary_for_user(db, user_id: str) -> Dict[str, Any]:
    """Auto-resolves candidate resume and test submissions from MongoDB Atlas."""
    if db is None:
        raise ValueError("Database connection required.")

    user_doc = db.resumes.find_one({"_id": user_id})
    if not user_doc:
        raise ValueError(f"User resume not found for user_id: {user_id}")

    # Extract skills
    enrichment = user_doc.get("enrichment", {})
    skills_obj = enrichment.get("skills", {})
    high_skills = skills_obj.get("high", [])
    med_skills = skills_obj.get("medium", [])
    all_skills = list(dict.fromkeys(high_skills + med_skills))

    domain = enrichment.get("predicted_job_domain")

    # Fetch latest test scores
    coding_score = 75.0
    latest_sub = db.submissions.find_one({"user_id": user_id}, sort=[("timestamp", -1)])
    if latest_sub:
        eval_res = latest_sub.get("evaluation_result", {})
        coding_score = float(eval_res.get("score", 75.0))

    mcq_score = 75.0
    latest_test_sub = db.test_submissions.find_one({"user_id": user_id}, sort=[("submitted_at", -1)])
    if latest_test_sub and "score" in latest_test_sub:
        mcq_score = float(latest_test_sub.get("score", 75.0))

    res = predict_salary(
        skills=all_skills,
        domain=domain,
        mcq_score=mcq_score,
        coding_score=coding_score,
    )

    # Persist in MongoDB resumes collection
    db.resumes.update_one(
        {"_id": user_id},
        {
            "$set": {
                "enrichment.predicted_salary_lpa": res["predicted_lpa"],
                "enrichment.salary_range": res["salary_range"],
                "enrichment.compensation_tier": res["compensation_tier"],
            }
        },
    )

    return res


if __name__ == "__main__":
    test_skills = ["React", "JavaScript", "System Design", "Docker", "Node.js"]
    sample_pred = predict_salary(
        skills=test_skills,
        domain="Backend Web Development",
        mcq_score=90,
        coding_score=88,
    )
    import json
    print(json.dumps(sample_pred, indent=2))
