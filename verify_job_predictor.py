"""
verify_job_predictor.py — Master Verification Suite for Job Predictor & Career Switch Engine.

Executes and verifies:
- Tier 1: Dataset Generation & Feature Union Contracts
- Tier 2: Model Artifacts, Serialization & Benchmark Metrics (ROC-AUC & Macro F1)
- Tier 3: Multi-Domain Inference, Transition Feasibility & Skill Gap Analysis
- Tier 4: FastAPI HTTP Endpoint integration (/api/predict-domain)

Exit code: 0 on success, non-zero on any failure.
"""

import os
import sys
import json
import unittest

# Ensure project root and ml-services are in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ML_SERVICES_DIR = os.path.join(PROJECT_ROOT, "ml-services")
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

from dotenv import load_dotenv
load_dotenv()

from starlette.testclient import TestClient

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
from schema.question_schema import (
    PredictDomainRequest,
    PredictDomainResponse,
    SwitchDomainRecommendation,
)
import main

test_client = TestClient(main.app)


class TestJobPredictorE2E(unittest.TestCase):

    def test_tier1_dataset_contract(self):
        """Tier 1: Verify data generator produces balanced datasets with required schema."""
        print("\n[Running Tier 1: Dataset Generation Contract]")
        df = load_or_generate_dataset(n_samples_per_domain=30, seed=42)
        self.assertEqual(len(df), 30 * len(TARGET_DOMAINS))
        self.assertEqual(set(df["domain"].unique()), set(TARGET_DOMAINS))
        required_cols = ["resume_text", "skills_text", "mcq_score", "coding_score", "total_score", "num_skills"]
        for col in required_cols:
            self.assertIn(col, df.columns)
        print("  -> Passed Tier 1: Dataset structure and class balance confirmed.")

    def test_tier2_model_artifacts_and_metrics(self):
        """Tier 2: Verify trained model artifacts, label encoder, and benchmark scores."""
        print("\n[Running Tier 2: Model Artifacts & Benchmark Metrics]")
        model, encoder = get_model()
        self.assertIsNotNone(model)
        self.assertIsNotNone(encoder)
        self.assertEqual(len(encoder.classes_), 5)

        metrics_file = os.path.join(ML_SERVICES_DIR, "job_predictor", "model_artifacts", "benchmark_metrics.json")
        self.assertTrue(os.path.exists(metrics_file), f"Metrics file missing at {metrics_file}")
        with open(metrics_file, "r") as f:
            metrics = json.load(f)
        
        self.assertIn("best_model", metrics)
        best = metrics["best_model"]
        self.assertIn(best, metrics)
        best_stats = metrics[best]
        self.assertGreaterEqual(best_stats["test_roc_auc_macro"], 0.85)
        self.assertGreaterEqual(best_stats["test_f1_macro"], 0.85)

        # Check visual plots exist
        plots_dir = os.path.join(ML_SERVICES_DIR, "job_predictor", "evaluation_plots")
        for plot_name in ["roc_curves.png", "precision_recall_curves.png", "confusion_matrix.png"]:
            p = os.path.join(plots_dir, plot_name)
            self.assertTrue(os.path.exists(p), f"Plot {plot_name} missing at {p}")
            self.assertGreater(os.path.getsize(p), 1000)

        print(f"  -> Passed Tier 2: Best Model: {best} (ROC-AUC={best_stats['test_roc_auc_macro']}, F1={best_stats['test_f1_macro']}). Plots verified.")

    def test_tier3_multi_domain_inference_and_switching(self):
        """Tier 3: Test multi-domain inference accuracy and career switch recommendations."""
        print("\n[Running Tier 3: Multi-Domain Inference & Career Switch Engine]")
        test_cases = [
            {
                "skills": ["React", "JavaScript", "HTML/CSS", "Next.js", "Redux", "Tailwind CSS"],
                "expected": "Frontend Web Development",
                "mcq": 85.0,
                "code": 80.0,
            },
            {
                "skills": ["Machine Learning", "Deep Learning", "PyTorch", "NLP", "Pandas", "Computer Vision"],
                "expected": "Data Science & AI/ML",
                "mcq": 90.0,
                "code": 85.0,
            },
            {
                "skills": ["Docker", "Kubernetes", "AWS", "Terraform", "CI/CD", "Linux"],
                "expected": "Cloud & DevOps",
                "mcq": 80.0,
                "code": 80.0,
            },
            {
                "skills": ["FastAPI", "Django", "PostgreSQL", "Redis", "REST APIs", "Node.js"],
                "expected": "Backend Web Development",
                "mcq": 85.0,
                "code": 85.0,
            },
            {
                "skills": ["Flutter", "React Native", "Android", "iOS", "Dart", "Swift"],
                "expected": "Mobile App Development",
                "mcq": 82.0,
                "code": 78.0,
            },
        ]

        for tc in test_cases:
            res = predict_job_domain(
                skills=tc["skills"],
                mcq_score=tc["mcq"],
                coding_score=tc["code"],
            )
            self.assertEqual(res["primary_domain"], tc["expected"])
            self.assertGreaterEqual(res["confidence"], 0.40)
            self.assertTrue(len(res["switch_domains"]) >= 1)

            # Test switch domains have missing skills
            for sw in res["switch_domains"]:
                self.assertNotEqual(sw["domain"], tc["expected"])
                self.assertIn("missing_skills", sw)
                self.assertIsInstance(sw["missing_skills"], list)
                self.assertIn(sw["feasibility"], ["High", "Moderate", "Low"])

        print("  -> Passed Tier 3: All 5 target domains predicted accurately with valid switch recommendations.")

    def test_tier4_fastapi_endpoint(self):
        """Tier 4: Verify FastAPI POST /api/predict-domain integration."""
        print("\n[Running Tier 4: FastAPI Endpoint Integration]")
        payload = {
            "skills": ["FastAPI", "Django", "PostgreSQL", "Redis", "REST APIs"],
            "mcq_score": 85.0,
            "coding_score": 90.0,
        }
        response = test_client.post("/api/predict-domain", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["primary_domain"], "Backend Web Development")
        self.assertGreaterEqual(data["confidence"], 0.40)
        self.assertEqual(data["overall_test_score"], 88.0)
        self.assertIn("switch_domains", data)
        self.assertTrue(len(data["switch_domains"]) > 0)

        # Verify response matches Pydantic schema
        validated_resp = PredictDomainResponse(**data)
        self.assertEqual(validated_resp.primary_domain, "Backend Web Development")

        print("  -> Passed Tier 4: HTTP 200 received with valid PredictDomainResponse schema.")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestJobPredictorE2E)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
