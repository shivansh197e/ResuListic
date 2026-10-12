"""
test_job_predictor.py — Test suite for ResuListic Job Domain Classifier & Career Switch Engine.
Covers data generation, model artifact validity, multi-domain inference,
career switch logic, skill gap analysis, and FastAPI endpoint integration.
"""
import os
import sys
import pytest
from fastapi.testclient import TestClient

# Bootstrap path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_ML_SERVICES_DIR = os.path.join(_PROJECT_ROOT, "ml-services")
if _ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, _ML_SERVICES_DIR)

from job_predictor.data_generator import (
    TARGET_DOMAINS,
    generate_candidate_profile,
    load_or_generate_dataset,
)
from job_predictor.predictor import (
    predict_job_domain,
    analyze_skill_gap,
    get_model,
)
from main import app

client = TestClient(app)


def test_data_generation_contract():
    """Verify generated dataset meets structural and class balance requirements."""
    df = load_or_generate_dataset(n_samples_per_domain=20, seed=123)
    assert df is not None
    assert len(df) == 20 * len(TARGET_DOMAINS)
    assert set(df["domain"].unique()) == set(TARGET_DOMAINS)
    for col in ["resume_text", "skills_text", "mcq_score", "coding_score", "total_score", "num_skills"]:
        assert col in df.columns


def test_model_artifacts_and_loading():
    """Verify trained pipeline and label encoder load successfully."""
    model, encoder = get_model()
    assert model is not None
    assert encoder is not None
    assert len(encoder.classes_) == 5
    for domain in TARGET_DOMAINS:
        assert domain in encoder.classes_


def test_frontend_profile_prediction():
    """Verify frontend candidate is classified into Frontend Web Development."""
    skills = ["React", "JavaScript", "HTML/CSS", "Tailwind CSS", "Redux"]
    result = predict_job_domain(
        skills=skills,
        mcq_score=85.0,
        coding_score=80.0,
    )
    assert result["primary_domain"] == "Frontend Web Development"
    assert result["confidence"] > 0.40
    assert result["overall_test_score"] == 82.0
    assert "Frontend Web Development" in result["domain_probabilities"]
    assert len(result["switch_domains"]) >= 1

    # Verify switch recommendation structure
    first_switch = result["switch_domains"][0]
    assert "domain" in first_switch
    assert "missing_skills" in first_switch
    assert "feasibility" in first_switch
    assert isinstance(first_switch["missing_skills"], list)


def test_datascience_profile_prediction():
    """Verify AI/ML candidate is classified into Data Science & AI/ML."""
    skills = ["Machine Learning", "Deep Learning", "PyTorch", "Natural Language Processing", "Pandas", "Python"]
    result = predict_job_domain(
        skills=skills,
        mcq_score=90.0,
        coding_score=85.0,
    )
    assert result["primary_domain"] == "Data Science & AI/ML"
    assert result["confidence"] > 0.40


def test_cloud_devops_profile_prediction():
    """Verify Cloud/DevOps candidate is classified into Cloud & DevOps."""
    skills = ["Docker", "Kubernetes", "AWS", "Terraform", "CI/CD", "Linux"]
    result = predict_job_domain(
        skills=skills,
        mcq_score=88.0,
        coding_score=78.0,
    )
    assert result["primary_domain"] == "Cloud & DevOps"
    assert result["confidence"] > 0.40


def test_skill_gap_analysis():
    """Verify skill gap analysis detects missing and overlapping skills."""
    candidate_skills = ["React", "JavaScript", "Docker"]
    # Check gap against Mobile App Development
    gap = analyze_skill_gap(candidate_skills, "Mobile App Development")
    assert "missing_skills" in gap
    assert "feasibility" in gap
    assert len(gap["missing_skills"]) > 0


def test_fastapi_predict_domain_endpoint_direct():
    """Verify POST /api/predict-domain works with direct payload."""
    payload = {
        "skills": ["FastAPI", "Django", "PostgreSQL", "Redis", "REST APIs"],
        "mcq_score": 85.0,
        "coding_score": 90.0,
    }
    response = client.post("/api/predict-domain", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["primary_domain"] == "Backend Web Development"
    assert data["confidence"] > 0.40
    assert "switch_domains" in data
    assert len(data["switch_domains"]) > 0
    assert "overall_test_score" in data


def test_fastapi_predict_domain_not_found():
    """Verify non-existent user_id returns 404."""
    payload = {"user_id": "non_existent_user_99999"}
    response = client.post("/api/predict-domain", json=payload)
    assert response.status_code == 404
