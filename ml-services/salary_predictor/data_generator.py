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
    """Generates a single candidate profile with an industry-realistic salary in LPA."""
    domain = rng.choice(DOMAINS)
    exp_tier = rng.choices(EXPERIENCE_TIERS, weights=[0.55, 0.35, 0.10], k=1)[0]
    
    num_skills = rng.randint(4, 16)
    # High impact skill count depends partly on experience & skill count
    max_hi = min(num_skills, 6)
    hi_count = rng.randint(0, max_hi)
    
    # Test scores (0 to 100)
    # Realistic correlation: candidates with high impact skills tend to have slightly higher scores
    score_mu = 65 + (hi_count * 3) + (2 if exp_tier != "fresher" else 0)
    mcq = float(np.clip(rng.gauss(score_mu, 12), 25.0, 100.0))
    code = float(np.clip(rng.gauss(score_mu - 2, 14), 20.0, 100.0))
    total_score = round(0.4 * mcq + 0.6 * code, 2)

    # ── Industry Salary Calculation Formula ────────────────────────────────
    # Base floor in Indian tech industry starts at ~4.0 LPA
    base = DOMAIN_BASE_LPA[domain]
    exp_boost = EXP_TIER_BOOST[exp_tier]
    
    # Skill volume contribution: +0.25 LPA per skill beyond 4
    skill_boost = max(0, num_skills - 4) * 0.30
    
    # High impact skill premium: +1.2 LPA per specialized skill
    hi_boost = hi_count * 1.35
    
    # Test performance multiplier:
    # Top tier coders (85+) unlock product-company tier salaries (Amazon/Microsoft/startup bracket)
    if total_score >= 85:
        test_boost = (total_score - 85) * 0.50 + 6.0  # +6.0 to +13.5 LPA
    elif total_score >= 70:
        test_boost = (total_score - 70) * 0.25 + 2.0  # +2.0 to +5.75 LPA
    elif total_score >= 50:
        test_boost = (total_score - 50) * 0.10        # 0 to +2.0 LPA
    else:
        test_boost = -1.5                             # Sub-par test penalty

    # Noise factor (individual negotiation, pedigree)
    noise = rng.gauss(0, 0.8)

    salary = base + exp_boost + skill_boost + hi_boost + test_boost + noise
    
    # Bound salary strictly between 4.0 LPA and 35.0 LPA
    salary_lpa = float(np.clip(salary, 4.0, 35.0))

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
