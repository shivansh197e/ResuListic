"""
test_challenger_2_r_empirical.py — Dedicated Empirical Adversarial Verification Suite
for question_selector.py, take_test.py, and circular_tracker.py.

Authored by Challenger 2 (Replacement).
"""

import os
import sys
import re
import subprocess
import unittest
from datetime import datetime

# 1. Bootstrap virtualenv site-packages to ensure resilient import of dependencies
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_SITE = os.path.join(PROJECT_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

# 2. Add project root and ml-services to sys.path
ML_SERVICES_DIR = os.path.join(PROJECT_ROOT, "ml-services")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

# 3. Propagate PYTHONPATH to os.environ for child subprocesses
existing_pp = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = os.pathsep.join(
    [p for p in [VENV_SITE, PROJECT_ROOT, ML_SERVICES_DIR, existing_pp] if p]
)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
from pymongo import MongoClient

from extraction.skill_taxonomy import (
    SKILL_TAXONOMY,
    SKILL_ALIASES,
    get_subtopics,
    get_domain,
)
from skill_test.question_selector import (
    _expand_skill,
    _build_skill_regex,
    _distribute,
    generate_test_session,
)
from skill_test.circular_tracker import (
    get_hard_questions,
    get_user_test_count,
)


class TestUmbrellaSkillExpansion(unittest.TestCase):
    """Tier 1: Umbrella Skill Expansion & Algorithmic Subtopic Verification"""

    def test_expand_skill_dsa(self):
        cands = _expand_skill("DSA")
        self.assertIn("DSA", cands)
        for expected in ["Array", "Dynamic Programming", "Tree", "Graph", "Linked List"]:
            self.assertIn(expected, cands)

    def test_expand_skill_case_insensitive_dsa(self):
        cands = _expand_skill("dsa")
        self.assertIn("dsa", cands)
        self.assertIn("Array", cands)
        self.assertIn("String", cands)

    def test_expand_skill_oop_and_oops(self):
        cands_oop = _expand_skill("OOP")
        self.assertIn("OOP", cands_oop)
        self.assertIn("Inheritance", cands_oop)
        self.assertIn("Polymorphism", cands_oop)

        cands_oops = _expand_skill("OOPS")
        self.assertIn("OOPS", cands_oops)
        self.assertIn("Inheritance", cands_oops)

    def test_expand_skill_system_design(self):
        cands = _expand_skill("System Design")
        self.assertIn("System Design", cands)
        self.assertIn("Microservices", cands)
        self.assertIn("Load Balancing", cands)
        self.assertIn("Caching", cands)

    def test_build_regex_escapes_and_matches(self):
        cands = ["C++", "DSA", "Array"]
        pat = _build_skill_regex(cands)
        self.assertTrue(re.match(pat, "c++", re.IGNORECASE))
        self.assertTrue(re.match(pat, "DSA", re.IGNORECASE))
        self.assertTrue(re.match(pat, "ARRAY", re.IGNORECASE))
        self.assertFalse(re.match(pat, "Python", re.IGNORECASE))


class TestLiveDBQuestionSelection(unittest.TestCase):
    """Tier 2: Live Database Session Generation Across Diverse Umbrella Skills"""

    @classmethod
    def setUpClass(cls):
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise unittest.SkipTest("MONGODB_URI not set")
        cls.client = MongoClient(uri)
        cls.db = cls.client.resulistic_db
        cls.test_users = []

    @classmethod
    def tearDownClass(cls):
        if cls.test_users:
            cls.db.user_test_state.delete_many({
                "_id.user_id": {"$in": cls.test_users}
            })
        cls.client.close()

    def _verify_session(self, skill_input, user_id):
        self.test_users.append(user_id)
        session = generate_test_session(self.db, user_id, skill_input)

        payload = session["frontend_payload"]
        eval_key = session["evaluation_key"]

        self.assertEqual(payload["user_id"], user_id)
        self.assertEqual(payload["skills_tested"], skill_input)
        self.assertEqual(payload["total_questions"], 10)
        self.assertEqual(len(payload["questions"]), 10)
        self.assertEqual(len(eval_key), 10)

        # First 5 are MCQs
        for idx in range(5):
            q = payload["questions"][idx]
            self.assertEqual(q["question_type"], "mcq")
            self.assertEqual(q["difficulty"], "easy")
            self.assertEqual(len(q["options"]), 4)
            self.assertIn("correct_answer", eval_key[str(idx)])

        # Next 3 are moderate coding
        for idx in range(5, 8):
            q = payload["questions"][idx]
            self.assertEqual(q["question_type"], "coding")
            self.assertEqual(q["difficulty"], "moderate")
            self.assertTrue(q["title"])
            self.assertTrue(q["description"])
            self.assertIn("question_index", eval_key[str(idx)])

        # Last 2 are hard coding
        for idx in range(8, 10):
            q = payload["questions"][idx]
            self.assertEqual(q["question_type"], "coding")
            self.assertEqual(q["difficulty"], "hard")
            self.assertTrue(q["title"])
            self.assertTrue(q["description"])
            self.assertIn("question_index", eval_key[str(idx)])

        return payload, eval_key

    def test_selection_dsa_umbrella_subtopic_verification(self):
        """Verify coding questions selected for DSA are actual algorithmic subtopics."""
        payload, eval_key = self._verify_session(["DSA"], "challenger_r_dsa")
        dsa_subtopics = set(s.lower() for s in get_subtopics("DSA"))

        coding_questions = [q for q in payload["questions"] if q["question_type"] == "coding"]
        self.assertEqual(len(coding_questions), 5)

        for q in coding_questions:
            skill = q["skill"].lower()
            # Must be either 'dsa' or an algorithmic subtopic
            is_valid = (skill == "dsa") or (skill in dsa_subtopics)
            self.assertTrue(
                is_valid,
                f"Selected question skill '{q['skill']}' is neither 'DSA' nor an algorithmic subtopic"
            )

    def test_selection_dsa_lowercase(self):
        self._verify_session(["dsa"], "challenger_r_dsa_lower")

    def test_selection_oop(self):
        self._verify_session(["OOP"], "challenger_r_oop")

    def test_selection_oops(self):
        self._verify_session(["OOPS"], "challenger_r_oops")

    def test_selection_system_design(self):
        self._verify_session(["System Design"], "challenger_r_sysdes")


class TestReferenceSolutionLookup(unittest.TestCase):
    """Tier 3: Reference Solution Lookups in db.solutions for Selected Questions"""

    @classmethod
    def setUpClass(cls):
        uri = os.getenv("MONGODB_URI")
        cls.client = MongoClient(uri)
        cls.db = cls.client.resulistic_db
        cls.test_users = []

    @classmethod
    def tearDownClass(cls):
        if cls.test_users:
            cls.db.user_test_state.delete_many({
                "_id.user_id": {"$in": cls.test_users}
            })
        cls.client.close()

    def test_solution_lookups_for_selected_questions(self):
        user_id = "challenger_r_sol_lookup"
        self.test_users.append(user_id)
        test_skills = ["DSA", "dsa", "OOP", "OOPS", "System Design"]

        for skill in test_skills:
            session = generate_test_session(self.db, user_id, [skill])
            questions = session["frontend_payload"]["questions"]
            eval_key = session["evaluation_key"]

            coding_qs = [q for q in questions if q.get("question_type") == "coding"]
            self.assertEqual(len(coding_qs), 5)

            for cq in coding_qs:
                idx = cq["q_index"]
                ev = eval_key[str(idx)]
                target_skill = ev.get("skill")
                target_index = ev.get("question_index")
                target_diff = ev.get("difficulty")

                sol_doc = self.db.solutions.find_one({
                    "skill": target_skill,
                    "index": target_index,
                    "difficulty": target_diff,
                })

                self.assertIsNotNone(
                    sol_doc,
                    f"Solution missing for skill='{target_skill}', index={target_index}, diff='{target_diff}'"
                )
                self.assertIn("reference_solution", sol_doc)
                self.assertGreater(len(sol_doc["reference_solution"].strip()), 0)


class TestCircularTrackerStatePersistence(unittest.TestCase):
    """Tier 4: Circular Tracker State Persistence in MongoDB Atlas"""

    @classmethod
    def setUpClass(cls):
        uri = os.getenv("MONGODB_URI")
        cls.client = MongoClient(uri)
        cls.db = cls.client.resulistic_db
        cls.user_id = "challenger_r_circ_user"

    @classmethod
    def tearDownClass(cls):
        cls.db.user_test_state.delete_many({
            "_id.user_id": {"$regex": "^challenger_r_circ_"}
        })
        cls.client.close()

    def test_circular_pointer_persistence_and_advancement(self):
        skill = "Array"
        pool_size = self.db.questions_hard.count_documents({"skill": skill})
        self.assertGreater(pool_size, 0)

        state_key = {"user_id": self.user_id, "skill": skill}
        self.db.user_test_state.delete_one({"_id": state_key})

        # Test 1
        q1 = get_hard_questions(self.db, self.user_id, skill, count=2)
        self.assertEqual(len(q1), 2)
        s1 = self.db.user_test_state.find_one({"_id": state_key})
        self.assertIsNotNone(s1)
        self.assertEqual(s1["test_count"], 1)
        ptr1 = s1["hard_pointer"]

        # Test 2
        q2 = get_hard_questions(self.db, self.user_id, skill, count=2)
        self.assertEqual(len(q2), 2)
        s2 = self.db.user_test_state.find_one({"_id": state_key})
        self.assertEqual(s2["test_count"], 2)
        expected_ptr2 = (ptr1 + 2) % pool_size
        self.assertEqual(s2["hard_pointer"], expected_ptr2)

        # Test 3
        q3 = get_hard_questions(self.db, self.user_id, skill, count=2)
        self.assertEqual(len(q3), 2)
        s3 = self.db.user_test_state.find_one({"_id": state_key})
        self.assertEqual(s3["test_count"], 3)
        expected_ptr3 = (expected_ptr2 + 2) % pool_size
        self.assertEqual(s3["hard_pointer"], expected_ptr3)

    def test_wrap_around_boundary(self):
        skill = "Array"
        pool_size = self.db.questions_hard.count_documents({"skill": skill})
        wrap_user = "challenger_r_circ_wrap"
        state_key = {"user_id": wrap_user, "skill": skill}

        # Force pointer to pool_size - 1
        self.db.user_test_state.update_one(
            {"_id": state_key},
            {"$set": {"hard_pointer": pool_size - 1, "test_count": 10}},
            upsert=True
        )

        # Advancing by 2 should wrap around
        get_hard_questions(self.db, wrap_user, skill, count=2)
        s = self.db.user_test_state.find_one({"_id": state_key})
        expected_ptr = (pool_size - 1 + 2) % pool_size  # 1
        self.assertEqual(s["hard_pointer"], expected_ptr)
        self.assertEqual(s["test_count"], 11)


class TestTakeTestCLIExecution(unittest.TestCase):
    """Tier 5: CLI Execution Modes of take_test.py"""

    @classmethod
    def setUpClass(cls):
        cls.python_exe = sys.executable
        cls.take_test_path = os.path.join(PROJECT_ROOT, "take_test.py")

    def _run(self, args, input_data=None, timeout=75):
        cmd = [self.python_exe, self.take_test_path] + args
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            cmd,
            input=input_data,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            cwd=PROJECT_ROOT,
            timeout=timeout,
            env=env,
        )
        return proc

    def test_generate_only_dsa(self):
        proc = self._run(["--skill", "DSA", "--user-id", "cli_test_dsa", "--generate-only"])
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("[GENERATE-ONLY] Questions preview:", proc.stdout)
        self.assertIn("[SUCCESS] Test session generated successfully.", proc.stdout)
        self.assertIn("Generated 10 questions successfully!", proc.stdout)

    def test_generate_only_lowercase_dsa(self):
        proc = self._run(["--skill", "dsa", "--generate-only"])
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("[SUCCESS] Test session generated successfully.", proc.stdout)

    def test_piped_interactive_execution(self):
        """Test piped execution answering MCQs then gracefully exiting on EOF."""
        piped_input = "cli_pipe_user\nDSA\nA\nB\n"
        proc = self._run([], input_data=piped_input, timeout=75)
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("WELCOME TO RESULISTIC SKILL TEST SIMULATOR", proc.stdout)
        self.assertIn("TEST COMPLETE!", proc.stdout)


if __name__ == "__main__":
    unittest.main()
