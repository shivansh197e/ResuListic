import unittest
import sys
import os

# Set working directory to project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
ML_SERVICES_DIR = os.path.join(ROOT_DIR, "ml-services")
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

from salary_predictor.predictor import predict_salary, detect_college_tier
from schema.question_schema import PredictSalaryRequest, TestSubmissionResponse


class TestRedesignPipeline(unittest.TestCase):
    def test_college_tier_detection(self):
        # Tier 1: IIT Bombay
        t1 = detect_college_tier("B.Tech in Computer Science from IIT Bombay (Indian Institute of Technology)")
        self.assertEqual(t1["tier"], "Tier 1")
        self.assertEqual(t1["boost"], 3.5)

        # Tier 1: Top NIT (Trichy, Surathkal, Warangal)
        t1_nit = detect_college_tier("Bachelor of Technology from NIT Trichy")
        self.assertEqual(t1_nit["tier"], "Tier 1")
        self.assertEqual(t1_nit["boost"], 3.5)

        # Tier 2: Other NITs / DTU / NSUT
        t2 = detect_college_tier("Bachelor of Engineering from NIT Bhopal")
        self.assertEqual(t2["tier"], "Tier 2")
        self.assertEqual(t2["boost"], 1.5)

        # Tier 3 / Standard
        t3 = detect_college_tier("B.Tech from State Technical University")
        self.assertEqual(t3["tier"], "Tier 3")
        self.assertEqual(t3["boost"], 0.0)

    def test_salary_piecewise_bands(self):
        # 1. Exceptional Score (> 90) Tier 1 IIT: Base x = 7.5 + 3.5 = 11.0 LPA.
        # Score 95 -> offset in [6..10], e.g. 8.0 -> raw = 19.0 + resume -> ~20 LPA
        res_top = predict_salary(
            skills=["Python", "FastAPI", "React", "Docker", "System Design"],
            domain="Backend Web Development",
            overall_score=95.0,
            resume_text="IIT Delhi graduate, Software Engineer",
        )
        self.assertFalse(res_top["is_unemployed"])
        self.assertEqual(res_top["status"], "Employed")
        self.assertGreaterEqual(res_top["predicted_lpa"], 17.0)
        self.assertLessEqual(res_top["predicted_lpa"], 30.0)
        self.assertEqual(res_top["college_tier"], "Tier 1")

        # 2. Mid-High Score (80 to 90): Base x = 7.0 (Frontend). Offset in [2..6].
        res_mid_high = predict_salary(
            skills=["React", "JavaScript", "HTML"],
            domain="Frontend Web Development",
            overall_score=85.0,
            resume_text="Graduated from XYZ College",
        )
        self.assertFalse(res_mid_high["is_unemployed"])
        self.assertGreaterEqual(res_mid_high["predicted_lpa"], 9.0)
        self.assertLessEqual(res_mid_high["predicted_lpa"], 15.0)

        # 3. Average Score (60 to 70): Base x = 7.0. Offset in [-2..0].
        res_avg = predict_salary(
            skills=["Python", "SQL"],
            domain="Data Science & AI/ML",
            overall_score=65.0,
        )
        self.assertFalse(res_avg["is_unemployed"])
        self.assertGreaterEqual(res_avg["predicted_lpa"], 6.0)

        # 4. Low Score (20 to 30): Offset in [-10..-7]. If salary < 3.0 -> Unemployed
        res_low = predict_salary(
            skills=["HTML"],
            domain="Frontend Web Development", # Base x = 7.0
            overall_score=22.0,
        )
        # raw_salary = 7.0 - 9.4 = -2.4 -> < 3.0 -> Unemployed
        self.assertTrue(res_low["is_unemployed"])
        self.assertEqual(res_low["status"], "Unemployed")
        self.assertEqual(res_low["predicted_lpa"], 0.0)

        # 5. Score < 10 -> Strictly Unemployed
        res_fail = predict_salary(
            skills=["Python", "React"],
            overall_score=6.0,
        )
        self.assertTrue(res_fail["is_unemployed"])
        self.assertEqual(res_fail["status"], "Unemployed")
        self.assertEqual(res_fail["predicted_lpa"], 0.0)

    def test_schema_parsing(self):
        req = PredictSalaryRequest.model_validate({
            "userId": "user_abc",
            "skills": ["Python", "Docker"],
            "overallScore": 88.5,
            "resumeText": "B.Tech BITS Pilani"
        })
        self.assertEqual(req.user_id, "user_abc")
        self.assertEqual(req.overall_score, 88.5)
        self.assertEqual(req.resume_text, "B.Tech BITS Pilani")

        sub_resp = TestSubmissionResponse(
            status="submitted",
            session_id="sess_123",
            is_expired=False,
            score=92.5,
            mcq_marks=19.0,
            moderate_marks=28.5,
            hard_marks=45.0,
            correct_answers=23,
            total_questions=25,
            message="Submitted",
            questions_answered=25
        )
        self.assertEqual(sub_resp.score, 92.5)
        self.assertEqual(sub_resp.mcq_marks, 19.0)
        self.assertEqual(sub_resp.moderate_marks, 28.5)
        self.assertEqual(sub_resp.hard_marks, 45.0)


    def test_mcq_no_skill_leak(self):
        from skill_test.ai_question_generator import generate_mcq_questions
        # Test generation with fast mock flag to test fallback templates
        os.environ["FAST_MOCK_MCQ"] = "1"
        test_skills = ["Python", "React", "Docker", "FastAPI"]
        mcqs = generate_mcq_questions(test_skills, count=20)
        self.assertEqual(len(mcqs), 20)
        for item in mcqs:
            pub = item["public_data"]
            q_text = pub["question"].lower()
            # Verify no skill name is leaked into the question text
            for s in test_skills:
                self.assertNotIn(f" {s.lower()} ", f" {q_text} ", f"Skill {s} leaked in question: {pub['question']}")
            # Verify exactly 4 options
            self.assertEqual(len(pub["options"]), 4)

    def test_strict_code_evaluator(self):
        from skill_test.code_evaluator import mock_evaluate_code
        # 1. Empty code -> 0 marks
        res_empty = mock_evaluate_code("")
        self.assertFalse(res_empty["passed"])
        self.assertEqual(res_empty["score"], 0)

        # 2. Trivial starter code / stubs -> <= 15 marks
        res_starter = mock_evaluate_code("def solution(*args):\n    pass\n")
        self.assertFalse(res_starter["passed"])
        self.assertLessEqual(res_starter["score"], 15)

        res_stub = mock_evaluate_code("def solution(nums):\n    return 0\n")
        self.assertFalse(res_stub["passed"])
        self.assertLessEqual(res_stub["score"], 15)

        # 3. Syntax error -> <= 15 marks with syntax error feedback
        res_syn = mock_evaluate_code("def foo(: return")
        self.assertFalse(res_syn["passed"])
        self.assertLessEqual(res_syn["score"], 15)
        self.assertIn("syntax error:", res_syn["feedback"].lower())

        # 4. Valid algorithmic implementation -> >= 70 marks, passed: True
        good_code = "def two_sum(nums, target):\n    lookup = {}\n    for i, n in enumerate(nums):\n        if target - n in lookup:\n            return [lookup[target - n], i]\n        lookup[n] = i\n    return []\n"
        res_good = mock_evaluate_code(good_code)
        self.assertTrue(res_good["passed"])
        self.assertGreaterEqual(res_good["score"], 70)

    def test_clean_title_and_description_enrichment(self):
        from skill_test.question_selector import _clean_title, _clean_and_enrich_description
        # Clean title strips Mutated: and Rewritten:
        self.assertEqual(_clean_title("Mutated: Binary Tree Traversal"), "Binary Tree Traversal")
        self.assertEqual(_clean_title("Rewritten: Two Sum"), "Two Sum")

        # Description without examples receives formatted examples and constraints
        enriched = _clean_and_enrich_description("Rewritten: <p>Find the maximum subarray sum.</p>", "Maximum Subarray")
        self.assertNotIn("Rewritten:", enriched)
        self.assertIn("Example 1:", enriched)
        self.assertIn("Constraints:", enriched)


if __name__ == "__main__":
    unittest.main()
