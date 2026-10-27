"""
predictor.py — Production inference service for Job Domain Prediction & Career Switching.
Combines candidate resume skills/text with test scores, queries the trained Scikit-Learn pipeline,
and computes actionable Career Switch recommendations with hierarchical Skill Gap Analysis.
"""
import os
import sys
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
import joblib

# Ensure ml-services root is in path
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_ML_SERVICES_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, _ML_SERVICES_DIR)

try:
    from extraction.skill_taxonomy import SKILL_TAXONOMY
except ImportError:
    try:
        from skill_taxonomy import SKILL_TAXONOMY
    except ImportError:
        SKILL_TAXONOMY = {}

from job_predictor.data_generator import TAXONOMY_DOMAIN_MAP

ARTIFACTS_DIR = os.path.join(_CURRENT_DIR, "model_artifacts")
MODEL_PATH = os.path.join(ARTIFACTS_DIR, "job_classifier.joblib")
ENCODER_PATH = os.path.join(ARTIFACTS_DIR, "label_encoder.joblib")

_CACHED_MODEL = None
_CACHED_ENCODER = None


def get_model():
    """Lazily loads and caches the trained pipeline and label encoder."""
    global _CACHED_MODEL, _CACHED_ENCODER
    if _CACHED_MODEL is None:
        if not os.path.exists(MODEL_PATH) or not os.path.exists(ENCODER_PATH):
            raise FileNotFoundError(
                f"Trained model artifacts not found in {ARTIFACTS_DIR}. Run train_and_evaluate.py first."
            )
        _CACHED_MODEL = joblib.load(MODEL_PATH)
        _CACHED_ENCODER = joblib.load(ENCODER_PATH)
    return _CACHED_MODEL, _CACHED_ENCODER


def _get_domain_skills(domain: str) -> List[str]:
    """Retrieves all canonical umbrella skills for a target domain from skill_taxonomy."""
    tax_key = None
    for k, v in TAXONOMY_DOMAIN_MAP.items():
        if v == domain or k == domain:
            tax_key = k
            break
    if not tax_key:
        tax_key = domain

    domain_dict = SKILL_TAXONOMY.get(tax_key, {})
    return list(domain_dict.keys())


def analyze_skill_gap(candidate_skills: List[str], target_domain: str) -> Dict[str, Any]:
    """
    Computes skill overlap and identifies missing domain-critical skills.
    """
    domain_skills = _get_domain_skills(target_domain)
    candidate_skills_lower = {s.strip().lower() for s in candidate_skills}

    overlap = []
    missing = []

    for d_skill in domain_skills:
        # Check umbrella skill match or partial match
        if d_skill.lower() in candidate_skills_lower:
            overlap.append(d_skill)
        else:
            missing.append(d_skill)

    overlap_ratio = len(overlap) / max(1, len(domain_skills))
    if overlap_ratio >= 0.4:
        feasibility = "High"
    elif overlap_ratio >= 0.15:
        feasibility = "Moderate"
    else:
        feasibility = "Low"

    return {
        "overlap_skills": overlap,
        "missing_skills": missing[:6],  # Top 6 priority skills to learn
        "feasibility": feasibility,
        "overlap_count": len(overlap),
        "target_domain_skills_count": len(domain_skills),
    }


def predict_job_domain(
    skills: Optional[List[str]] = None,
    resume_text: Optional[str] = None,
    mcq_score: Optional[float] = None,
    coding_score: Optional[float] = None,
    switch_threshold: float = 0.05,
) -> Dict[str, Any]:
    """
    Analyzes resume skills and test scores to predict the candidate's primary job domain
    and identify career switch paths with missing skills.
    """
    model, encoder = get_model()

    skills = skills or []
    # Normalize MCQ score if on a 0-5 scale
    if mcq_score is not None and mcq_score <= 5.0 and mcq_score > 0.0:
        norm_mcq = float(mcq_score * 20.0)
    elif mcq_score is not None:
        norm_mcq = float(np.clip(mcq_score, 0.0, 100.0))
    else:
        norm_mcq = 70.0  # neutral prior

    if coding_score is not None:
        norm_code = float(np.clip(coding_score, 0.0, 100.0))
    else:
        norm_code = 70.0

    total_score = round(0.4 * norm_mcq + 0.6 * norm_code, 2)
    skills_str = ", ".join(skills)
    full_text = resume_text or f"Candidate profile with technical skills: {skills_str}."
    num_skills = len(skills)

    # Build single-row DataFrame
    input_df = pd.DataFrame([{
        "resume_text": full_text,
        "mcq_score": norm_mcq,
        "coding_score": norm_code,
        "total_score": total_score,
        "num_skills": num_skills,
    }])

    # Predict probabilities across all classes
    probs = model.predict_proba(input_df)[0]
    classes = list(encoder.classes_)

    # Sort classes by probability descending
    class_prob_pairs = sorted(zip(classes, probs), key=lambda x: x[1], reverse=True)
    primary_domain, primary_prob = class_prob_pairs[0]

    domain_probabilities = {c: round(float(p), 4) for c, p in class_prob_pairs}

    # Evaluate Switch Domains (alternatives with probability >= threshold)
    switch_domains = []
    for domain, prob in class_prob_pairs[1:]:
        if float(prob) < switch_threshold:
            continue
        gap_info = analyze_skill_gap(skills, domain)
        # Even if probability is modest, adjacent domains provide high value
        switch_domains.append({
            "domain": domain,
            "confidence": round(float(prob), 4),
            "feasibility": gap_info["feasibility"],
            "overlap_skills": gap_info["overlap_skills"],
            "missing_skills": gap_info["missing_skills"],
        })

    return {
        "primary_domain": primary_domain,
        "confidence": round(float(primary_prob), 4),
        "overall_test_score": total_score,
        "domain_probabilities": domain_probabilities,
        "switch_domains": switch_domains[:3],  # Top 3 viable transition paths
    }


def predict_for_user(db, user_id: str) -> Dict[str, Any]:
    """
    End-to-end user resolver: Fetches candidate resume & submissions from MongoDB,
    computes domain prediction, and saves results to candidate profile.
    """
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

    # Extract resume summary/text if available
    sections = user_doc.get("sections", {})
    summary = sections.get("summary", "")
    full_text = f"{summary} Skills: {', '.join(all_skills)}"

    # Fetch latest test scores from submissions or test_submissions
    latest_sub = db.submissions.find_one({"user_id": user_id}, sort=[("timestamp", -1)])
    coding_score = 75.0
    if latest_sub:
        eval_res = latest_sub.get("evaluation") or latest_sub.get("evaluation_result", {})
        coding_score = float(eval_res.get("score", 75.0))

    mcq_score = 75.0
    latest_test_sub = db.test_submissions.find_one({"user_id": user_id}, sort=[("submitted_at", -1)])
    if latest_test_sub and "score" in latest_test_sub:
        mcq_score = float(latest_test_sub.get("score", 75.0))

    # Run inference
    result = predict_job_domain(
        skills=all_skills,
        resume_text=full_text,
        mcq_score=mcq_score,
        coding_score=coding_score,
    )

    # Persist prediction in MongoDB resumes collection
    db.resumes.update_one(
        {"_id": user_id},
        {
            "$set": {
                "enrichment.predicted_job_domain": result["primary_domain"],
                "enrichment.domain_confidence": result["confidence"],
                "enrichment.switch_recommendations": result["switch_domains"],
                "status": "matched",
            }
        },
    )

    return result


if __name__ == "__main__":
    # Test sample: Frontend Developer wanting to know their domain and switch potential
    sample_skills = ["React", "JavaScript", "HTML/CSS", "Tailwind CSS", "Redux"]
    res = predict_job_domain(
        skills=sample_skills,
        mcq_score=85,
        coding_score=80,
    )
    import json
    print("\n--- SAMPLE INFERENCE RESULT ---")
    print(json.dumps(res, indent=2))
