"""
data_generator.py — Dataset generator and loader for the Job Domain Classifier.
Generates realistic candidate profiles (skills, text summaries, and test scores)
mapped to the 5 core job domains, while supporting loading external datasets.
"""
import os
import sys
import random
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

# Ensure ml-services root is in path to import skill_taxonomy
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

# Target domains for the classifier
TARGET_DOMAINS = [
    "Frontend Web Development",
    "Backend Web Development",
    "Data Science & AI/ML",
    "Cloud & DevOps",
    "Mobile App Development",
]

# Map internal taxonomy names to target domains
TAXONOMY_DOMAIN_MAP = {
    "Frontend Web Development": "Frontend Web Development",
    "Backend Web Development": "Backend Web Development",
    "AI, ML & Data Science": "Data Science & AI/ML",
    "Cloud & DevOps": "Cloud & DevOps",
    "Mobile Development": "Mobile App Development",
}

# Domain adjacency / realistic career switch transitions
ADJACENT_DOMAINS = {
    "Frontend Web Development": ["Mobile App Development", "Backend Web Development"],
    "Backend Web Development": ["Cloud & DevOps", "Frontend Web Development"],
    "Data Science & AI/ML": ["Backend Web Development", "Cloud & DevOps"],
    "Cloud & DevOps": ["Backend Web Development", "Data Science & AI/ML"],
    "Mobile App Development": ["Frontend Web Development", "Backend Web Development"],
}

# Summary sentence templates per domain
SUMMARY_TEMPLATES = {
    "Frontend Web Development": [
        "Passionate Frontend Developer specializing in responsive web applications, modern UI/UX workflows, and state management.",
        "Frontend engineer with deep expertise in component lifecycle, SSR, dynamic interfaces, and client performance optimization.",
        "Web developer focusing on single-page applications, interactive user experiences, accessibility, and clean CSS styling.",
        "UI Engineer experienced in crafting scalable design systems, design-to-code pipelines, and fast client-side rendering.",
    ],
    "Backend Web Development": [
        "Backend Software Engineer with expertise in RESTful APIs, relational databases, microservices, and asynchronous architectures.",
        "Experienced backend developer proficient in distributed data pipelines, server-side caching, ORMs, and secure authentication.",
        "Software Engineer building high-throughput services, transaction management, API gateways, and scalable server backends.",
        "API developer specialized in server architectures, database optimization, query tuning, and cloud service integration.",
    ],
    "Data Science & AI/ML": [
        "Data Scientist and Machine Learning engineer experienced in predictive modeling, deep learning architectures, and NLP pipelines.",
        "AI practitioner with strong background in statistical inference, exploratory data analysis, neural networks, and model fine-tuning.",
        "Machine Learning researcher skilled in model training, feature engineering, evaluation metrics, and large language models.",
        "Data Analyst and ML developer specializing in data visualization, hypothesis testing, predictive analytics, and model deployment.",
    ],
    "Cloud & DevOps": [
        "DevOps and Cloud Engineer specializing in container orchestration, infrastructure as code, automated CI/CD, and site reliability.",
        "Cloud Infrastructure Engineer experienced in multi-cloud environments, Kubernetes clusters, Dockerization, and Linux security.",
        "SRE and Platform Engineer focused on scalable deployment strategies, monitoring, automated provisioning, and network topology.",
        "DevOps specialist skilled in continuous delivery pipelines, configuration management, cloud storage, and system monitoring.",
    ],
    "Mobile App Development": [
        "Mobile Application Developer specializing in cross-platform frameworks, native Android/iOS performance, and offline-first mobile apps.",
        "Mobile software engineer skilled in responsive mobile UI, platform channels, state management, and app store deployment.",
        "App developer building native and hybrid mobile solutions with smooth navigation, local caching, and RESTful sync.",
        "Cross-platform mobile engineer experienced in clean architecture, mobile animation, responsive layouts, and device integration.",
    ],
}


def _get_domain_skill_pool(taxonomy_key: str) -> List[str]:
    """Extract flat pool of umbrella skills and subtopics for a domain."""
    pool = []
    domain_dict = SKILL_TAXONOMY.get(taxonomy_key, {})
    for skill_name, subtopics in domain_dict.items():
        pool.append(skill_name)
        pool.extend(subtopics)
    return list(dict.fromkeys(pool))


def generate_candidate_profile(domain: str, rng: random.Random) -> Dict:
    """Generate a realistic candidate sample for a target domain."""
    # Find matching taxonomy key
    tax_key = None
    for k, v in TAXONOMY_DOMAIN_MAP.items():
        if v == domain:
            tax_key = k
            break
    if not tax_key:
        tax_key = domain

    primary_pool = _get_domain_skill_pool(tax_key)
    if not primary_pool:
        # Fallback pool if taxonomy is unavailable
        primary_pool = [domain, "Coding", "Software", "Debugging"]

    # Pick 4 to 9 primary skills
    k_primary = min(len(primary_pool), rng.randint(4, 9))
    skills = rng.sample(primary_pool, k_primary)

    # 40% probability of picking 1-3 cross-over skills from an adjacent domain
    # This naturally trains the classifier to learn secondary probability distributions for career switching
    if rng.random() < 0.40 and domain in ADJACENT_DOMAINS:
        adj_domain = rng.choice(ADJACENT_DOMAINS[domain])
        adj_tax_key = next((k for k, v in TAXONOMY_DOMAIN_MAP.items() if v == adj_domain), adj_domain)
        adj_pool = _get_domain_skill_pool(adj_tax_key)
        if adj_pool:
            k_adj = min(len(adj_pool), rng.randint(1, 3))
            skills.extend(rng.sample(adj_pool, k_adj))

    # Add general CS foundations with 50% probability
    common_foundations = ["Git", "DSA", "SQL", "OOP", "REST APIs", "Python", "JavaScript"]
    if rng.random() < 0.50:
        k_found = rng.randint(1, 3)
        skills.extend(rng.sample(common_foundations, k_found))

    # Deduplicate preserving order
    skills = list(dict.fromkeys(skills))

    # Text representations
    skills_text = ", ".join(skills)
    template = rng.choice(SUMMARY_TEMPLATES.get(domain, ["Software Engineer."]))
    full_resume_text = f"{template} Key skills and technologies: {skills_text}."

    # Realistic test score distributions (0 to 100)
    # Domain proficiency correlates with test performance, with realistic human variance
    mcq_base = rng.gauss(75, 12)
    code_base = rng.gauss(72, 14)
    mcq_score = float(np.clip(mcq_base, 25.0, 100.0))
    coding_score = float(np.clip(code_base, 20.0, 100.0))
    total_score = round(0.4 * mcq_score + 0.6 * coding_score, 2)

    return {
        "domain": domain,
        "skills_text": skills_text,
        "resume_text": full_resume_text,
        "mcq_score": round(mcq_score, 2),
        "coding_score": round(coding_score, 2),
        "total_score": total_score,
        "num_skills": len(skills),
    }


def generate_synthetic_dataset(
    n_samples_per_domain: int = 500,
    seed: int = 42,
    output_csv_path: Optional[str] = None,
) -> pd.DataFrame:
    """
    Generates a balanced dataset across all 5 target domains.
    Default: 500 samples/domain = 2,500 total samples.
    """
    rng = random.Random(seed)
    np.random.seed(seed)

    rows = []
    for domain in TARGET_DOMAINS:
        for _ in range(n_samples_per_domain):
            rows.append(generate_candidate_profile(domain, rng))

    df = pd.DataFrame(rows)
    # Shuffle dataset
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    if output_csv_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_csv_path)), exist_ok=True)
        df.to_csv(output_csv_path, index=False)
        print(f"[Dataset] Saved {len(df)} samples to {output_csv_path}")

    return df


def load_or_generate_dataset(
    csv_path: Optional[str] = None,
    n_samples_per_domain: int = 500,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Loads dataset from csv_path if it exists; otherwise generates and caches it.
    """
    if csv_path and os.path.exists(csv_path):
        print(f"[Dataset] Loading existing dataset from {csv_path}...")
        df = pd.read_csv(csv_path)
        # Ensure required columns exist
        required_cols = {"domain", "skills_text", "mcq_score", "coding_score", "total_score"}
        if required_cols.issubset(df.columns):
            return df
        print(f"[Dataset] Warning: {csv_path} missing required columns. Regenerating...")

    default_path = csv_path or os.path.join(
        _ML_SERVICES_DIR, "..", "datasets", "job_domain_training_data.csv"
    )
    return generate_synthetic_dataset(
        n_samples_per_domain=n_samples_per_domain,
        seed=seed,
        output_csv_path=default_path,
    )


if __name__ == "__main__":
    df = load_or_generate_dataset()
    print(f"Dataset generated with shape: {df.shape}")
    print("\nClass distribution:\n", df["domain"].value_counts())
    print("\nSample record:\n", df.iloc[0].to_dict())
