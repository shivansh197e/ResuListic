"""
verify_salary_predictor.py — Master 4-Tier Verification Suite for Salary Predictor (4 LPA to 30+ LPA).
Covers dataset generation, model artifacts, multi-tier inference accuracy, and FastAPI HTTP 200 endpoint integration.
"""

import os
import sys
import json
import unittest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ML_SERVICES_DIR = os.path.join(PROJECT_ROOT, "ml-services")
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

from dotenv import load_dotenv
load_dotenv()

from starlette.testclient import TestClient

from salary_predictor.data_generator import generate_salary_dataset
from salary_predictor.predictor import predict_salary, get_salary_model
from schema.question_schema import PredictSalaryRequest, PredictSalaryResponse
import main

test_client = TestClient(main.app)


class TestSalaryPredictorE2E(unittest.TestCase):

    def test_tier1_dataset_contract(self):
        """Tier 1: Verify dataset generation covers 4 LPA to 30+ LPA with required schema."""
        print("\n[Running Tier 1: Salary Dataset Generation Contract]")
        df = generate_salary_dataset(n_samples=50, seed=42)
        self.assertEqual(len(df), 50)
        self.assertGreaterEqual(df["salary_lpa"].min(), 4.0)
        self.assertLessEqual(df["salary_lpa"].max(), 35.0)
        for col in ["domain", "experience_tier", "num_skills", "high_impact_skills", "mcq_score", "coding_score", "total_score", "salary_lpa"]:
            self.assertIn(col, df.columns)
        print("  -> Passed Tier 1: Dataset contracts and 4-35 LPA range verified.")

    def test_tier2_model_artifacts_and_metrics(self):
        """Tier 2: Verify trained pipeline, regression metrics, and diagnostic plot."""
        print("\n[Running Tier 2: Model Artifacts & Regression Metrics]")
        model = get_salary_model()
        self.assertIsNotNone(model)

        metrics_file = os.path.join(ML_SERVICES_DIR, "salary_predictor", "model_artifacts", "salary_metrics.json")
        self.assertTrue(os.path.exists(metrics_file), f"Metrics file missing at {metrics_file}")
        with open(metrics_file, "r") as f:
            metrics = json.load(f)

        best = metrics.get("best_model", "")
        self.assertIn(best, metrics)
        best_stats = metrics[best]
        self.assertGreaterEqual(best_stats["test_r2"], 0.90)
        self.assertLessEqual(best_stats["test_mae_lpa"], 1.5)

        plot_file = os.path.join(ML_SERVICES_DIR, "salary_predictor", "evaluation_plots", "predicted_vs_actual_salary.png")
        self.assertTrue(os.path.exists(plot_file))
        print(f"  -> Passed Tier 2: Model {best} achieves R2={best_stats['test_r2']:.3f}, MAE={best_stats['test_mae_lpa']:.2f} LPA. Plot verified.")

    def test_tier3_multi_tier_inference(self):
        """Tier 3: Test compensation predictions across Entry, Mid, and Top-Tier brackets."""
        print("\n[Running Tier 3: Multi-Tier Compensation Inference (4 - 30+ LPA)]")

        # Case A: Entry-level / fresher with low scores -> expects ~4 to 7 LPA
        entry_res = predict_salary(
            skills=["HTML", "CSS"],
            domain="Frontend Web Development",
            mcq_score=40.0,
            coding_score=35.0,
            experience_tier="fresher",
        )
        self.assertGreaterEqual(entry_res["predicted_lpa"], 4.0)
        self.assertLessEqual(entry_res["predicted_lpa"], 8.5)
        self.assertIn("Entry-Level", entry_res["compensation_tier"])

        # Case B: Solid Mid-level profile -> expects ~10 to 18 LPA
        mid_res = predict_salary(
            skills=["React", "JavaScript", "Node.js", "MongoDB", "REST APIs"],
            domain="Backend Web Development",
            mcq_score=75.0,
            coding_score=75.0,
            experience_tier="early_career",
        )
        self.assertGreaterEqual(mid_res["predicted_lpa"], 10.0)
        self.assertLessEqual(mid_res["predicted_lpa"], 22.0)

        # Case C: High-impact skills + top coding (95/100) -> expects 22 - 35 LPA
        top_res = predict_salary(
            skills=["System Design", "Microservices", "Kubernetes", "Docker", "AWS", "PyTorch", "Python", "Kafka"],
            domain="Data Science & AI/ML",
            mcq_score=95.0,
            coding_score=95.0,
            experience_tier="mid_level",
        )
        self.assertGreaterEqual(top_res["predicted_lpa"], 22.0)
        self.assertIn("Top-Tier Product", top_res["compensation_tier"])
        self.assertTrue(len(top_res["factors"]) > 0)
        print("  -> Passed Tier 3: Entry, Mid, and 30+ LPA Top-Tier brackets accurately differentiated.")

    def test_tier4_fastapi_endpoint(self):
        """Tier 4: Verify FastAPI POST /api/predict-salary integration."""
        print("\n[Running Tier 4: FastAPI Endpoint Integration]")
        payload = {
            "skills": ["React", "JavaScript", "System Design", "Docker", "Node.js"],
            "domain": "Backend Web Development",
            "mcq_score": 88.0,
            "coding_score": 90.0,
        }
        response = test_client.post("/api/predict-salary", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["predicted_lpa"], 14.0)
        self.assertIn("salary_range", data)
        self.assertIn("compensation_tier", data)
        self.assertIn("factors", data)

        # Validate with Pydantic model
        validated = PredictSalaryResponse(**data)
        self.assertEqual(validated.domain, "Backend Web Development")
        print("  -> Passed Tier 4: HTTP 200 returned with valid PredictSalaryResponse schema.")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSalaryPredictorE2E)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
