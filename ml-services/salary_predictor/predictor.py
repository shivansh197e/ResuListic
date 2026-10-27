"""
predictor.py — Production inference service for Salary Prediction (3.0 LPA to 30.0+ LPA).
Combines candidate assessment score (100-mark scale), domain baseline (x LPA with college tier calibration),
and secondary resume evaluation to output calibrated compensation or Unemployed status.
"""
import os
import re
import sys
import numpy as np
from typing import List, Dict, Optional, Any

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_ML_SERVICES_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, _ML_SERVICES_DIR)

from salary_predictor.data_generator import HIGH_IMPACT_SKILLS, DOMAINS, count_high_impact_skills

# Standard Market Baseline Averages per Domain for Freshers / Early Career (x_std)
DOMAIN_MARKET_AVG = {
    "Frontend Web Development": 6.5,
    "Mobile App Development": 7.0,
    "Backend Web Development": 7.5,
    "Cloud & DevOps": 8.5,
    "Data Science & AI/ML": 9.0,
}


def detect_college_tier(text: Optional[str] = None) -> Dict[str, Any]:
    """
    Scans candidate education and resume text for prestigious institutions:
    - Tier 1: IITs, BITS Pilani, Top IIITs (Hyderabad, Bangalore, Delhi), Top NITs (Trichy, Surathkal, Warangal). Boost: +3.5 LPA.
    - Tier 2: Other NITs, IIITs, DTU, NSUT, BIT Mesra, Jadavpur, Thapar, PEC, VJTI, COEP. Boost: +1.5 LPA.
    - Tier 3: Standard accredited engineering colleges and universities (Default). Boost: +0.0 LPA.
    """
    if not text or not str(text).strip():
        return {"tier": "Tier 3", "boost": 0.0, "name": "Standard Accredited College"}
    t = str(text).lower()

    # Tier 1: IITs, BITS Pilani, Top IIITs, Top NITs
    tier1_patterns = [
        (r"\biit\s+[a-z]+|\bindian\s+institute\s+of\s+technology\b", "IIT"),
        (r"\bbits\s+pilani\b|\bbirla\s+institute\s+of\s+technology\s+and\s+science\b", "BITS Pilani"),
        (r"\biiit[\s-]*(hyderabad|bangalore|delhi)\b", "Top IIIT"),
        (r"\bnit[\s-]*(trichy|tiruchirappalli|surathkal|warangal|calicut|rourkela)\b", "Top NIT"),
        (r"\b(iitk|iitb|iitd|iitm|iitkgp|iitr|iitg|iitbhu)\b", "IIT"),
    ]
    for pat, label in tier1_patterns:
        m = re.search(pat, t)
        if m:
            return {"tier": "Tier 1", "boost": 3.5, "name": label}

    # Tier 2: Other NITs, IIITs, DTU, NSUT, Premier State Tech Colleges
    tier2_patterns = [
        (r"\bnit\s+[a-z]+|\bnational\s+institute\s+of\s+technology\b", "NIT"),
        (r"\biiit\s+[a-z]+|\bindian\s+institute\s+of\s+information\s+technology\b", "IIIT"),
        (r"\bdtu\b|\bdelhi\s+technological\s+university\b", "DTU"),
        (r"\bnsut\b|\bnetaji\s+subhas\b", "NSUT"),
        (r"\bbit\s+mesra\b", "BIT Mesra"),
        (r"\bjadavpur\b", "Jadavpur University"),
        (r"\bthapar\b", "Thapar Institute"),
        (r"\bpec\b|\bpunjab\s+engineering\s+college\b", "PEC Chandigarh"),
        (r"\bvjti\b|\bcoep\b", "COEP / VJTI"),
    ]
    for pat, label in tier2_patterns:
        m = re.search(pat, t)
        if m:
            return {"tier": "Tier 2", "boost": 1.5, "name": label}

    return {"tier": "Tier 3", "boost": 0.0, "name": "General University"}


def predict_salary(
    skills: Optional[List[str]] = None,
    domain: Optional[str] = None,
    mcq_score: Optional[float] = None,
    coding_score: Optional[float] = None,
    total_score: Optional[float] = None,
    overall_score: Optional[float] = None,
    experience_tier: str = "fresher",
    resume_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Predicts candidate salary package (3.0 LPA to 30.0+ LPA) or Unemployed status.
    Implements piecewise formula based on role average x LPA with college tier calibration.
    """
    skills = skills or []

    # Resolve domain if missing
    if not domain or domain not in DOMAINS:
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

    # Compute total score if not passed directly
    candidate_score = overall_score if overall_score is not None else total_score
    if candidate_score is not None:
        score = float(np.clip(candidate_score, 0.0, 100.0))
    else:
        norm_mcq = float(np.clip(mcq_score if mcq_score is not None else 70.0, 0.0, 100.0))
        norm_code = float(np.clip(coding_score if coding_score is not None else 70.0, 0.0, 100.0))
        # 100-mark scale: MCQs 20%, Coding 80% (Moderate 30% + Hard 50%)
        score = round(0.20 * norm_mcq + 0.80 * norm_code, 2)

    # 1. Detect College Tier from resume text
    college_info = detect_college_tier(resume_text)
    base_x = DOMAIN_MARKET_AVG.get(domain, 7.5) + college_info["boost"]
    experience_boost = {"fresher": 0.0, "early_career": 2.5, "mid_level": 5.0}.get(str(experience_tier).lower(), 0.0)
    base_x += experience_boost

    # 2. Piecewise Formula based on Candidate Score S:
    if score >= 90.0:
        # x + (6 to 10) LPA
        offset = 6.0 + ((score - 90.0) / 10.0) * 4.0
    elif score >= 80.0:
        # x + (2 to 6) LPA
        offset = 2.0 + ((score - 80.0) / 10.0) * 4.0
    elif score >= 70.0:
        # x to x+2 LPA
        offset = 0.0 + ((score - 70.0) / 10.0) * 2.0
    elif score >= 60.0:
        # x-2 to x LPA
        offset = -2.0 + ((score - 60.0) / 10.0) * 2.0
    elif score >= 50.0:
        # x-4 to x-2 LPA
        offset = -4.0 + ((score - 50.0) / 10.0) * 2.0
    elif score >= 40.0:
        # x-5 to x-4 LPA
        offset = -5.0 + ((score - 40.0) / 10.0) * 1.0
    elif score >= 30.0:
        # x-7 to x-5 LPA
        offset = -7.0 + ((score - 30.0) / 10.0) * 2.0
    elif score >= 20.0:
        # x-10 to x-7 LPA
        offset = -10.0 + ((score - 20.0) / 10.0) * 3.0
    elif score >= 10.0:
        # x-12 to x-10 LPA
        offset = -12.0 + ((score - 10.0) / 10.0) * 2.0
    else:
        # Score < 10: Strictly Unemployed
        offset = -999.0

    raw_salary = base_x + offset

    # 3. Secondary Resume Evaluation (subtle adjustment: -0.2 to +1.2 LPA)
    hi_count = count_high_impact_skills(skills)
    skill_count = len(skills)
    resume_adj = min(1.0, hi_count * 0.25) + min(0.4, max(-0.2, (skill_count - 5) * 0.05))
    final_salary = round(raw_salary + resume_adj, 2)

    # 4. Check Unemployed threshold: score < 10 or final_salary < 3.0 LPA
    if score < 10.0 or final_salary < 3.0:
        return {
            "is_unemployed": True,
            "status": "Unemployed",
            "predicted_lpa": 0.0,
            "salary_range": {"min_lpa": 0.0, "max_lpa": 0.0},
            "compensation_tier": "Unemployed / Re-skilling Recommended (< 3.0 LPA Threshold)",
            "domain": domain,
            "overall_test_score": score,
            "college_tier": college_info["tier"],
            "college_name": college_info["name"],
            "domain_baseline_lpa": base_x,
            "factors": [
                {
                    "factor": f"Technical Assessment Score ({score:.1f}/100)",
                    "impact": "Below Employability Threshold (< 3.0 LPA)",
                },
                {
                    "factor": f"Institution Tier Benchmark ({college_info['tier']}: {college_info['name']})",
                    "impact": f"+{college_info['boost']:.1f} LPA Base",
                },
                {
                    "factor": f"Role Baseline Benchmark ({domain})",
                    "impact": f"₹{base_x:.1f} LPA ({college_info['tier']})",
                },
            ],
        }

    # 5. Clamped strictly between 3.0 LPA and 30.0 LPA
    clamped_lpa = round(float(np.clip(final_salary, 3.0, 30.0)), 2)
    min_lpa = round(max(3.0, clamped_lpa - 1.5), 2)
    max_lpa = round(min(30.0, clamped_lpa + 2.0), 2)

    if clamped_lpa >= 20.0:
        tier_label = "Top-Tier Product / Unicorn Bracket (20 - 30+ LPA)"
    elif clamped_lpa >= 14.0:
        tier_label = "Tier-1 Product & Growth Startup Bracket (14 - 20 LPA)"
    elif clamped_lpa >= 8.5:
        tier_label = "Established Tech & Mid-Tier Product Bracket (8.5 - 14 LPA)"
    else:
        tier_label = "Entry-Level / Foundation Bracket (3.0 - 8.5 LPA)"

    factors = [
        {
            "factor": f"Assessment Performance ({score:.1f}/100 Marks)",
            "impact": f"{offset:+.1f} LPA Offset",
        },
        {
            "factor": f"Institution Tier Benchmark ({college_info['tier']}: {college_info['name']})",
            "impact": f"+{college_info['boost']:.1f} LPA Base",
        },
        {
            "factor": f"Role Market Baseline ({domain})",
            "impact": f"₹{base_x:.1f} LPA",
        },
        {
            "factor": f"Experience Tier ({experience_tier})",
            "impact": f"+{experience_boost:.1f} LPA Base",
        },
    ]
    if hi_count > 0:
        factors.append({
            "factor": f"Resume Skill Equity ({hi_count} High-Impact Skills)",
            "impact": f"{resume_adj:+.2f} LPA",
        })

    return {
        "is_unemployed": False,
        "status": "Employed",
        "predicted_lpa": clamped_lpa,
        "salary_range": {"min_lpa": min_lpa, "max_lpa": max_lpa},
        "compensation_tier": tier_label,
        "domain": domain,
        "overall_test_score": score,
        "college_tier": college_info["tier"],
        "college_name": college_info["name"],
        "domain_baseline_lpa": base_x,
        "factors": factors,
    }


def predict_salary_for_user(db, user_id: str) -> Dict[str, Any]:
    """Auto-resolves candidate resume, college details, and test submissions from MongoDB Atlas."""
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

    # Combine resume text and education for college detection
    edu_text = user_doc.get("sections", {}).get("education", "")
    raw_text = user_doc.get("raw_text", "")
    combined_resume_text = f"{edu_text}\n{raw_text[:2000]}"

    # Fetch latest test submission score
    total_score = 70.0
    latest_sub = db.test_submissions.find_one({"user_id": user_id}, sort=[("submitted_at", -1)])
    if latest_sub and "score" in latest_sub:
        total_score = float(latest_sub.get("score", 70.0))

    res = predict_salary(
        skills=all_skills,
        domain=domain,
        total_score=total_score,
        resume_text=combined_resume_text,
    )

    # Persist in MongoDB resumes collection
    db.resumes.update_one(
        {"_id": user_id},
        {
            "$set": {
                "enrichment.predicted_salary_lpa": res["predicted_lpa"],
                "enrichment.salary_range": res["salary_range"],
                "enrichment.compensation_tier": res["compensation_tier"],
                "enrichment.is_unemployed": res["is_unemployed"],
                "enrichment.employment_status": res["status"],
            }
        },
    )

    return res


if __name__ == "__main__":
    # Quick sanity tests
    print("--- Test 1: Tier 1 IIT Candidate, Score 95 ---")
    print(predict_salary(skills=["Python", "Docker", "Kubernetes", "System Design"], domain="Backend Web Development", total_score=95, resume_text="B.Tech from IIT Bombay"))

    print("\n--- Test 2: Tier 3 Candidate, Score 55 ---")
    print(predict_salary(skills=["React", "HTML", "CSS"], domain="Frontend Web Development", total_score=55, resume_text="B.Tech from ABC Engineering College"))

    print("\n--- Test 3: Candidate with Score < 10 (Unemployed) ---")
    print(predict_salary(skills=["Java"], domain="Backend Web Development", total_score=8, resume_text="College of Engineering"))

    print("\n--- Test 4: Candidate with calculated salary < 3 LPA (Unemployed) ---")
    print(predict_salary(skills=["HTML"], domain="Frontend Web Development", total_score=15, resume_text="Local College"))
