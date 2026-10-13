"""
data_generator.py — Compensation dataset generator for Indian tech market salaries (4 LPA to 30+ LPA).
Simulates realistic salary compensation bands combining candidate resume attributes with test assessment scores.
"""
import os
import random
import numpy as np
import pandas as pd
from typing import Optional, List

HIGH_IMPACT_SKILLS = {
    "system design", "microservices", "kubernetes", "docker", "aws", "gcp", "azure",
    "pytorch", "tensorflow", "deep learning", "large language models", "rag",
    "redis", "kafka", "graphql", "distributed systems", "ci/cd", "terraform"
}

DOMAINS = [
    "Frontend Web Development",
    "Backend Web Development",
    "Data Science & AI/ML",
    "Cloud & DevOps",
    "Mobile App Development",
]

DOMAIN_BASE_LPA = {
    "Frontend Web Development": 5.0,
    "Mobile App Development": 5.5,
    "Backend Web Development": 6.0,
    "Cloud & DevOps": 7.0,
    "Data Science & AI/ML": 7.5,
}

EXPERIENCE_TIERS = ["fresher", "early_career", "mid_level"]
EXP_TIER_BOOST = {
    "fresher": 0.0,
    "early_career": 3.5,
    "mid_level": 7.5,
}


def count_high_impact_skills(skills: List[str]) -> int:
    """Counts occurrence of tier-1 high-demand skills."""
    return sum(1 for s in skills if s.strip().lower() in HIGH_IMPACT_SKILLS)


def generate_salary_sample(rng: random.Random) -> dict:
    """Generates a single candidate profile with an industry-realistic salary in LPA heavily weighted by skill test score."""
    domain = rng.choice(DOMAINS)
    exp_tier = rng.choices(EXPERIENCE_TIERS, weights=[0.55, 0.35, 0.10], k=1)[0]
    
    num_skills = rng.randint(2, 16)
    max_hi = min(num_skills, 6)
    hi_count = rng.randint(0, max_hi)
    
    # Sample test scores across full spectrum (15 to 100) so model learns low-score penalties accurately
    tier_roll = rng.random()
    if tier_roll < 0.28:
        # Starting 25%ile: low test scores (15 to 55) regardless of resume inflation
        mcq = float(np.clip(rng.uniform(15.0, 56.0), 10.0, 100.0))
        code = float(np.clip(rng.uniform(10.0, 55.0), 10.0, 100.0))
    elif tier_roll < 0.65:
        # Mid bracket (50 to 80)
        mcq = float(np.clip(rng.gauss(68.0, 10.0), 45.0, 100.0))
        code = float(np.clip(rng.gauss(66.0, 11.0), 40.0, 100.0))
    else:
        # High / Top bracket (78 to 100)
        mcq = float(np.clip(rng.gauss(88.0, 7.0), 72.0, 100.0))
        code = float(np.clip(rng.gauss(87.0, 8.0), 70.0, 100.0))

    total_score = round(0.4 * mcq + 0.6 * code, 2)

    # ── Merit-First Salary Calculation (Skill Test = 80%+ Weight) ──────────
    # Resume skills are GATED by test performance: unverified skills on a resume
    # yield almost zero bonus if the candidate scores poorly on the assessment.
    verification_gate = max(0.0, (total_score - 45.0) / 55.0) ** 1.5
    raw_resume_boost = max(0, num_skills - 3) * 0.25 + (hi_count * 1.25)
    gated_resume_boost = raw_resume_boost * verification_gate
    domain_diff = DOMAIN_BASE_LPA[domain] - 5.0  # 0.0 to 2.5 LPA

    if total_score <= 55.0:
        # Starting 25%ile: Strictly < 10 LPA (4.0 to 8.8 LPA)
        # Test score drives almost the entire variation here
        base_package = 4.0 + (total_score / 55.0) * 3.6
        exp_component = EXP_TIER_BOOST[exp_tier] * 0.15 * (total_score / 55.0)
        salary = base_package + (domain_diff * 0.25) + (gated_resume_boost * 0.35) + exp_component + rng.gauss(0, 0.25)
        salary_lpa = float(np.clip(salary, 4.0, 9.2))
    elif total_score < 70.0:
        # 25th to 50th %ile: 7.8 to 12.0 LPA
        progress = (total_score - 55.0) / 15.0
        base_package = 7.6 + progress * 3.2
        exp_component = EXP_TIER_BOOST[exp_tier] * (0.35 + 0.30 * progress)
        salary = base_package + (domain_diff * 0.5) + gated_resume_boost + exp_component + rng.gauss(0, 0.4)
        salary_lpa = float(np.clip(salary, 7.2, 13.5))
    elif total_score < 85.0:
        # 50th to 80th %ile: 11.0 to 19.5 LPA
        progress = (total_score - 70.0) / 15.0
        base_package = 10.8 + progress * 4.5
        exp_component = EXP_TIER_BOOST[exp_tier] * (0.65 + 0.25 * progress)
        salary = base_package + (domain_diff * 0.75) + gated_resume_boost + exp_component + rng.gauss(0, 0.5)
        salary_lpa = float(np.clip(salary, 10.2, 21.5))
    else:
        # Top 20%ile (85+): Unlocks Tier-1 Product & Unicorn packages (15 to 35 LPA)
        progress = (total_score - 85.0) / 15.0
        base_package = 15.3 + progress * 7.5
        exp_component = EXP_TIER_BOOST[exp_tier]
        salary = base_package + domain_diff + gated_resume_boost + exp_component + rng.gauss(0, 0.6)
        salary_lpa = float(np.clip(salary, 14.2, 35.0))

    return {
        "domain": domain,
        "experience_tier": exp_tier,
        "num_skills": num_skills,
        "high_impact_skills": hi_count,
        "mcq_score": round(mcq, 2),
        "coding_score": round(code, 2),
        "total_score": total_score,
        "salary_lpa": round(salary_lpa, 2),
    }


def generate_salary_dataset(n_samples: int = 3000, seed: int = 42, output_csv: Optional[str] = None) -> pd.DataFrame:
    """Generates a dataset of candidate salary records."""
    rng = random.Random(seed)
    np.random.seed(seed)
    rows = [generate_salary_sample(rng) for _ in range(n_samples)]
    df = pd.DataFrame(rows)
    
    if output_csv:
        os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
        df.to_csv(output_csv, index=False)
        print(f"[Salary Dataset] Saved {len(df)} samples to {output_csv}")
    
    return df


if __name__ == "__main__":
    df = generate_salary_dataset(n_samples=2500)
    print(df.describe())
    print("\nSample records:")
    print(df.head())
