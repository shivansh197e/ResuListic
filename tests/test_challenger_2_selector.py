"""
test_challenger_2_selector.py — Empirical Adversarial Verification Suite
for question_selector.py, take_test.py, and circular_tracker.py.

Authored by Challenger 2.
Covers:
1. Umbrella skill and alias expansion (_expand_skill, _build_skill_regex)
2. Question distribution arithmetic (_distribute)
3. End-to-end question selection on live MongoDB (DSA, dsa, OOP, OOPS, System Design, Python, multi-skill)
4. Reference solution lookup matching in db.solutions for selected coding questions
5. Circular tracker modulo arithmetic, state persistence, and pointer wrap-around
6. CLI execution modes of take_test.py (--generate-only, positional args, EOF pipe, invalid inputs)
7. Security and edge cases (empty skills, injection strings, DB state cleanup)
"""

import os
import sys
import re
import subprocess
# Setup paths and bootstrap venv site-packages
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_SITE = os.path.join(PROJECT_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

ML_SERVICES_DIR = os.path.join(PROJECT_ROOT, "ml-services")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

existing_pp = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = os.pathsep.join(
    [p for p in [VENV_SITE, PROJECT_ROOT, ML_SERVICES_DIR, existing_pp] if p]
)

import unittest
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

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


class TestSkillExpansionAndDistribution(unittest.TestCase):
    """Tier 1: Taxonomy Expansion & Distribution Unit Mechanics"""

    def test_expand_skill_dsa(self):
        cands = _expand_skill("DSA")
        self.assertIn("DSA", cands)
        self.assertIn("Array", cands)
        self.assertIn("Dynamic Programming", cands)
        self.assertIn("Graph", cands)
        self.assertGreater(len(cands), 10)

    def test_expand_skill_case_insensitive_dsa(self):
        cands = _expand_skill("dsa")
        self.assertIn("dsa", cands)
        # Should resolve subtopics despite lowercase
        self.assertIn("Array", cands)
        self.assertIn("String", cands)

    def test_expand_skill_oops_alias(self):
        cands = _expand_skill("OOPS")
        self.assertIn("OOPS", cands)
        self.assertIn("Inheritance", cands)
        self.assertIn("Polymorphism", cands)

    def test_expand_skill_system_design(self):
        cands = _expand_skill("System Design")
        self.assertIn("System Design", cands)
        self.assertIn("Microservices", cands)
        self.assertIn("Caching", cands)

    def test_expand_skill_unknown_fallback(self):
        cands = _expand_skill("NonExistentSkillXYZ")
        self.assertEqual(cands, ["NonExistentSkillXYZ"])

    def test_expand_skill_empty(self):
        self.assertEqual(_expand_skill(""), [])
        self.assertEqual(_expand_skill(None), [])

    def test_build_skill_regex(self):
        cands = ["DSA", "Array", "C++"]
        pattern = _build_skill_regex(cands)
        self.assertTrue(re.match(pattern, "dsa", re.IGNORECASE))
        self.assertTrue(re.match(pattern, "ARRAY", re.IGNORECASE))
        self.assertTrue(re.match(pattern, "C++", re.IGNORECASE))
        self.assertFalse(re.match(pattern, "Java", re.IGNORECASE))
        self.assertEqual(_build_skill_regex([]), "^$")

    def test_distribute_arithmetic(self):
        # 3 questions across 1 skill
        self.assertEqual(_distribute(["DSA"], 3), {"DSA": 3})
        # 3 questions across 2 skills -> 2 and 1
        d2 = _distribute(["DSA", "Python"], 3)
        self.assertEqual(sum(d2.values()), 3)
        self.assertEqual(d2["DSA"], 2)
        self.assertEqual(d2["Python"], 1)
        # 2 questions across 3 skills -> 1, 1, 0
        d3 = _distribute(["A", "B", "C"], 2)
        self.assertEqual(sum(d3.values()), 2)
        self.assertEqual(d3, {"A": 1, "B": 1, "C": 0})
        # empty skills
        self.assertEqual(_distribute([], 5), {})


class TestLiveDBQuestionSelection(unittest.TestCase):
    """Tier 2: Live Database Session Generation Across Diverse Skills"""

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
        # Clean up any test states created in user_test_state
        if cls.test_users:
            cls.db.user_test_state.delete_many({
                "_id.user_id": {"$in": cls.test_users}
            })
        cls.client.close()

    def _generate_and_validate(self, skill_input, user_id):
        self.test_users.append(user_id)
        session = generate_test_session(self.db, user_id, skill_input)

        self.assertIn("frontend_payload", session)
        self.assertIn("evaluation_key", session)

        payload = session["frontend_payload"]
        eval_key = session["evaluation_key"]

        # Contract checks
        self.assertEqual(payload["user_id"], user_id)
        self.assertEqual(payload["skills_tested"], skill_input)
        self.assertEqual(payload["total_questions"], 10)
        self.assertEqual(len(payload["questions"]), 10)
        self.assertEqual(len(eval_key), 10)

        # Structure of 10 questions: 5 MCQs, 3 Moderate coding, 2 Hard coding
        for idx in range(5):
            q = payload["questions"][idx]
            self.assertEqual(q["question_type"], "mcq", f"Index {idx} should be mcq")
            self.assertEqual(q["difficulty"], "easy", f"Index {idx} should be easy")
            self.assertIn("options", q)
            self.assertEqual(len(q["options"]), 4)
            self.assertIn(str(idx), eval_key)
            self.assertIn("correct_answer", eval_key[str(idx)])

        for idx in range(5, 8):
            q = payload["questions"][idx]
            self.assertEqual(q["question_type"], "coding", f"Index {idx} should be coding")
            self.assertEqual(q["difficulty"], "moderate", f"Index {idx} should be moderate")
            self.assertIn("title", q)
            self.assertIn("description", q)
            self.assertIn(str(idx), eval_key)
            self.assertIn("question_index", eval_key[str(idx)])

        for idx in range(8, 10):
            q = payload["questions"][idx]
            self.assertEqual(q["question_type"], "coding", f"Index {idx} should be coding")
            self.assertEqual(q["difficulty"], "hard", f"Index {idx} should be hard")
            self.assertIn("title", q)
            self.assertIn("description", q)
            self.assertIn(str(idx), eval_key)
            self.assertIn("question_index", eval_key[str(idx)])

        return payload, eval_key

    def test_session_umbrella_dsa(self):
        self._generate_and_validate(["DSA"], "emp_challenger_dsa")

    def test_session_umbrella_lowercase_dsa(self):
        self._generate_and_validate(["dsa"], "emp_challenger_dsa_lower")

    def test_session_umbrella_oop(self):
        self._generate_and_validate(["OOP"], "emp_challenger_oop")

    def test_session_umbrella_oops_alias(self):
        self._generate_and_validate(["OOPS"], "emp_challenger_oops")

    def test_session_umbrella_system_design(self):
        self._generate_and_validate(["System Design"], "emp_challenger_sysdes")

    def test_session_umbrella_python(self):
        self._generate_and_validate(["Python"], "emp_challenger_python")

    def test_session_multi_skills(self):
        self._generate_and_validate(["DSA", "Python"], "emp_challenger_multi")

    def test_session_unknown_skill_backfills_gracefully(self):
        """Unknown skill has 0 DB questions, but backfill fulfills 10 questions total."""
        payload, eval_key = self._generate_and_validate(["SkillXYZNonExistent"], "emp_challenger_fallback")
        self.assertEqual(payload["total_questions"], 10)

    def test_session_empty_skills_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_test_session(self.db, "emp_challenger_empty", [])


class TestReferenceSolutionLookup(unittest.TestCase):
    """Tier 3: Verification of Reference Solution Pairing in db.solutions"""

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

    def test_take_test_reference_solution_lookup_fidelity(self):
        """
        Verify that for every coding question returned in take_test.py,
        the exact solution lookup logic in take_test.py (lines 120-125):
            db.solutions.find_one({
                'skill': ev_data.get('skill', skill),
                'index': ev_data.get('question_index'),
                'difficulty': ev_data.get('difficulty', diff.lower())
            })
        successfully finds a non-empty reference solution in db.solutions.
        """
        user_id = "emp_challenger_ref_sol"
        self.test_users.append(user_id)
        skills_to_test = ["DSA", "dsa", "OOP", "OOPS", "System Design", "Python"]

        for skill in skills_to_test:
            session = generate_test_session(self.db, user_id, [skill])
            questions = session["frontend_payload"]["questions"]
            eval_key = session["evaluation_key"]

            coding_questions = [q for q in questions if q.get("question_type") == "coding"]
            self.assertEqual(len(coding_questions), 5, f"Skill {skill} should have 5 coding questions")

            for cq in coding_questions:
                q_idx = cq["q_index"]
                ev_data = eval_key[str(q_idx)]
                target_skill = ev_data.get("skill")
                target_index = ev_data.get("question_index")
                target_diff = ev_data.get("difficulty")

                sol_doc = self.db.solutions.find_one({
                    "skill": target_skill,
                    "index": target_index,
                    "difficulty": target_diff,
                })

                self.assertIsNotNone(
                    sol_doc,
                    f"Missing solution in db.solutions for skill={target_skill}, "
                    f"index={target_index}, difficulty={target_diff}"
                )
                self.assertIn("reference_solution", sol_doc)
                ref_sol = sol_doc["reference_solution"]
                self.assertIsInstance(ref_sol, str)
                self.assertGreater(len(ref_sol.strip()), 5)

    def test_database_wide_solutions_coverage(self):
        """Spot-check 100 questions from questions_moderate and questions_hard."""
        moderate_sample = list(self.db.questions_moderate.find().limit(50))
        for doc in moderate_sample:
            sol = self.db.solutions.find_one({
                "skill": doc["skill"],
                "index": doc["index"],
                "difficulty": "moderate",
            })
            self.assertIsNotNone(
                sol,
                f"Moderate question index {doc.get('index')} ({doc.get('skill')}) has no solution."
            )

        hard_sample = list(self.db.questions_hard.find().limit(50))
        for doc in hard_sample:
            sol = self.db.solutions.find_one({
                "skill": doc["skill"],
                "index": doc["index"],
                "difficulty": "hard",
            })
            self.assertIsNotNone(
                sol,
                f"Hard question index {doc.get('index')} ({doc.get('skill')}) has no solution."
            )


class TestCircularTrackerModulo(unittest.TestCase):
    """Tier 4: Empirical Circular Pointer Modulo Mechanics & Persistence"""

    @classmethod
    def setUpClass(cls):
        uri = os.getenv("MONGODB_URI")
        cls.client = MongoClient(uri)
        cls.db = cls.client.resulistic_db
        cls.test_user = "emp_challenger_circular_tester"

    @classmethod
    def tearDownClass(cls):
        cls.db.user_test_state.delete_many({
            "_id.user_id": {"$regex": "^emp_challenger_circular_"}
        })
        cls.client.close()

    def test_circular_progression_across_sequential_tests(self):
        skill = "Array"
        pool_size = self.db.questions_hard.count_documents({"skill": skill})
        self.assertGreater(pool_size, 0, "Pool size for Array must be > 0")

        # Initial clean
        state_key = {"user_id": self.test_user, "skill": skill}
        self.db.user_test_state.delete_one({"_id": state_key})

        # Test 1: First test
        q1 = get_hard_questions(self.db, self.test_user, skill, count=2)
        self.assertEqual(len(q1), 2)
        state1 = self.db.user_test_state.find_one({"_id": state_key})
        self.assertIsNotNone(state1)
        self.assertEqual(state1["test_count"], 1)
        ptr1 = state1["hard_pointer"]

        # Test 2: Second test
        q2 = get_hard_questions(self.db, self.test_user, skill, count=2)
        self.assertEqual(len(q2), 2)
        state2 = self.db.user_test_state.find_one({"_id": state_key})
        self.assertEqual(state2["test_count"], 2)
        expected_ptr2 = (ptr1 + 2) % pool_size
        self.assertEqual(state2["hard_pointer"], expected_ptr2)

        # Test 3: Third test
        q3 = get_hard_questions(self.db, self.test_user, skill, count=2)
        self.assertEqual(len(q3), 2)
        state3 = self.db.user_test_state.find_one({"_id": state_key})
        self.assertEqual(state3["test_count"], 3)
        expected_ptr3 = (expected_ptr2 + 2) % pool_size
        self.assertEqual(state3["hard_pointer"], expected_ptr3)

    def test_modulo_wrap_around_boundary(self):
        """Simulate wrap-around when pointer reaches the end of pool."""
        skill = "Array"
        pool_size = self.db.questions_hard.count_documents({"skill": skill})
        user_id = "emp_challenger_circular_wrap"
        state_key = {"user_id": user_id, "skill": skill}

        # Set pointer to pool_size - 1
        self.db.user_test_state.update_one(
            {"_id": state_key},
            {
                "$set": {
                    "hard_pointer": pool_size - 1,
                    "test_count": 5,
                    "last_test_at": datetime.now().isoformat()
                }
            },
            upsert=True
        )

        # Request count=2: pointer advances to (pool_size - 1 + 2) % pool_size = 1
        qs = get_hard_questions(self.db, user_id, skill, count=2)
        self.assertEqual(len(qs), 2)

        updated_state = self.db.user_test_state.find_one({"_id": state_key})
        expected_pointer = 1
        self.assertEqual(updated_state["hard_pointer"], expected_pointer)
        self.assertEqual(updated_state["test_count"], 6)

        # Questions returned should have indices: [1, (1+1)%pool_size]
        indices = [q["index"] for q in qs]
        self.assertEqual(indices, [1, (1 + 1) % pool_size])

    def test_multi_user_isolation(self):
        """Ensure distinct users maintain independent pointers and test counts."""
        u1 = "emp_challenger_circular_u1"
        u2 = "emp_challenger_circular_u2"
        skill = "Array"

        self.db.user_test_state.delete_many({"_id.user_id": {"$in": [u1, u2]}})

        get_hard_questions(self.db, u1, skill, count=2)
        get_hard_questions(self.db, u1, skill, count=2)
        get_hard_questions(self.db, u2, skill, count=2)

        self.assertEqual(get_user_test_count(self.db, u1, skill), 2)
        self.assertEqual(get_user_test_count(self.db, u2, skill), 1)


class TestTakeTestCLIExecution(unittest.TestCase):
    """Tier 5: CLI Subprocess Execution and Pipe Ingestion Testing"""

    @classmethod
    def setUpClass(cls):
        cls.python_exe = sys.executable
        cls.take_test_path = os.path.join(PROJECT_ROOT, "take_test.py")

    def _run_cli(self, args, input_data=None, timeout=75):
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
            env=env,
            timeout=timeout,
        )
        return proc

    def test_cli_generate_only_dsa(self):
        proc = self._run_cli(["--skill", "DSA", "--user-id", "cli_test_1", "--generate-only"])
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("[GENERATE-ONLY] Questions preview:", proc.stdout)
        self.assertIn("[SUCCESS] Test session generated successfully.", proc.stdout)
        self.assertIn("Generated 10 questions successfully!", proc.stdout)

    def test_cli_generate_only_lowercase_dsa(self):
        proc = self._run_cli(["--skill", "dsa", "--user-id", "cli_test_2", "--generate-only"])
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("[SUCCESS] Test session generated successfully.", proc.stdout)

    def test_cli_positional_skill_argument(self):
        proc = self._run_cli(["DSA", "--generate-only"])
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("[SUCCESS] Test session generated successfully.", proc.stdout)

    def test_cli_multiple_skills_flag(self):
        proc = self._run_cli(["--skill", "DSA,Python", "--generate-only"])
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("[SUCCESS] Test session generated successfully.", proc.stdout)

    def test_cli_eof_graceful_handling_interactive_prompt(self):
        """Simulate immediate pipe close (EOF) during interactive user prompt."""
        proc = self._run_cli([], input_data="")
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        # Should gracefully default to test_user and Array, then terminate cleanly when questions arrive
        self.assertIn("WELCOME TO RESULISTIC SKILL TEST SIMULATOR", proc.stdout)

    def test_cli_eof_graceful_handling_during_test(self):
        """Simulate piping answers then immediate EOF."""
        pipe_input = "A\nB\n"  # Answer 2 MCQs then EOF
        proc = self._run_cli(["--skill", "DSA"], input_data=pipe_input, timeout=75)
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("[Input closed / interrupted", proc.stdout)
        self.assertIn("terminating test gracefully]", proc.stdout)
        self.assertIn("TEST COMPLETE!", proc.stdout)

    def test_cli_invalid_answers_piped(self):
        """Simulate piping invalid MCQ answers ('Z', '?', empty) then skipping coding with empty lines."""
        pipe_input = "Z\n?\n\nA\nB\nDONE\nDONE\nDONE\nDONE\nDONE\n"
        proc = self._run_cli(["--skill", "DSA"], input_data=pipe_input, timeout=75)
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("TEST COMPLETE!", proc.stdout)


if __name__ == "__main__":
    unittest.main()
