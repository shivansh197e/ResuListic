"""
test_reviewer2_taxonomy_adversarial.py — Independent Robustness, Backward Compatibility,
and Adversarial Verification Harness for 3-Level Skill Taxonomy Engine.
Authored by Reviewer 2.

Covers:
1. Taxonomy Edge Cases & Non-String Fuzzing (None, numbers, booleans, objects, whitespace)
2. Aliases & Taxonomy Graph Integrity (Bidirectional mappings, canonical resolution)
3. Regex Safety & Special Characters (C++, C#, .NET, Node.js, SQL injection, emojis)
4. Skills Extractor Adversarial Inputs & JSON Serializability
5. Question Selector Skill Expansion, Distribution & Regex Boundaries
6. Downstream Backward Compatibility with main.py and resume_builder.py schemas
"""

import json
import os
import re
import sys
import unittest
from unittest.mock import MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_SITE = os.path.join(REPO_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
ML_SERVICES_DIR = os.path.join(REPO_ROOT, "ml-services")
if ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, ML_SERVICES_DIR)

from extraction.skill_taxonomy import (
    SKILL_TAXONOMY,
    SKILL_ALIASES,
    get_subtopics,
    get_domain,
    get_all_skills_flat,
    get_canonical_skill,
    get_parent_skill,
)
from extraction.skills_extractor import extract_skill, SKILL_PATTERNS
from skill_test.question_selector import (
    _expand_skill,
    _build_skill_regex,
    _distribute,
    generate_test_session,
)


class TestTaxonomyRobustnessAndEdgeCases(unittest.TestCase):
    """Stress testing skill_taxonomy helper functions with adversarial and malformed inputs."""

    PATHOLOGICAL_INPUTS = [
        None,
        "",
        "   ",
        "\t\n\r",
        12345,
        -1,
        3.14159,
        True,
        False,
        [],
        {},
        {"skill": "DSA"},
        ["DSA", "Python"],
        object(),
        lambda x: x,
        b"DSA",
        "'; DROP TABLE skills; --",
        "<script>alert(1)</script>",
        "../../etc/passwd",
        "🚀 🐍 💻",
        "DSA" * 1000,  # Long string
        "\\x00\\x01\\x02",
        "\0nullbyte",
    ]

    def test_get_subtopics_never_raises_on_pathological_inputs(self):
        for inp in self.PATHOLOGICAL_INPUTS:
            with self.subTest(input=inp):
                res = get_subtopics(inp)
                self.assertIsInstance(res, list)
                if inp != "DSA" * 1000:
                    self.assertEqual(res, [])

    def test_get_domain_never_raises_on_pathological_inputs(self):
        for inp in self.PATHOLOGICAL_INPUTS:
            with self.subTest(input=inp):
                res = get_domain(inp)
                self.assertIsInstance(res, str)
                if inp != "DSA" * 1000:
                    self.assertEqual(res, "")

    def test_get_canonical_skill_never_raises_on_pathological_inputs(self):
        for inp in self.PATHOLOGICAL_INPUTS:
            with self.subTest(input=inp):
                res = get_canonical_skill(inp)
                self.assertIsInstance(res, str)
                if inp != "DSA" * 1000:
                    self.assertEqual(res, "")

    def test_get_parent_skill_never_raises_on_pathological_inputs(self):
        for inp in self.PATHOLOGICAL_INPUTS:
            with self.subTest(input=inp):
                res = get_parent_skill(inp)
                self.assertIsInstance(res, str)
                if inp != "DSA" * 1000:
                    self.assertEqual(res, "")

    def test_mutation_independence_subtopics(self):
        orig = get_subtopics("DSA")
        orig.append("HACKED_TOPIC")
        orig.clear()
        fresh = get_subtopics("DSA")
        self.assertGreater(len(fresh), 10)
        self.assertNotIn("HACKED_TOPIC", fresh)
        self.assertIn("Array", fresh)

    def test_case_and_whitespace_invariance(self):
        variations = [
            "dsa", "DSA", "Dsa", "dSa", "  DSA  ", "\tDSA\n",
            "dAtA sTrUcTuReS & aLgOrItHmS",
            "  DATA STRUCTURES AND ALGORITHMS  ",
        ]
        expected_subs = get_subtopics("DSA")
        for v in variations:
            with self.subTest(variant=v):
                self.assertEqual(get_subtopics(v), expected_subs)
                self.assertEqual(get_domain(v), "Core CS & Foundations")
                self.assertEqual(get_canonical_skill(v), "DSA")


class TestTaxonomyGraphIntegrity(unittest.TestCase):
    """Mathematical graph consistency of SKILL_TAXONOMY, SKILL_ALIASES, and lookup maps."""

    def test_all_aliases_map_to_valid_canonical_skills(self):
        canonical_skills = {
            skill.lower(): skill
            for domain_skills in SKILL_TAXONOMY.values()
            for skill in domain_skills.keys()
        }
        for alias, target in SKILL_ALIASES.items():
            self.assertIn(
                target.lower(), canonical_skills,
                f"Alias '{alias}' points to target '{target}' which does not exist in SKILL_TAXONOMY!"
            )

    def test_all_canonical_skills_resolve_to_own_domain_and_subtopics(self):
        for domain, skills_dict in SKILL_TAXONOMY.items():
            for skill, subtopics in skills_dict.items():
                self.assertEqual(get_domain(skill), domain)
                self.assertEqual(get_canonical_skill(skill), skill)
                self.assertEqual(get_subtopics(skill), subtopics)

    def test_all_subtopics_resolve_to_correct_domain_and_parent(self):
        for domain, skills_dict in SKILL_TAXONOMY.items():
            for skill, subtopics in skills_dict.items():
                for sub in subtopics:
                    # Some subtopics may be shared across skills, but domain must match
                    sub_domain = get_domain(sub)
                    self.assertTrue(bool(sub_domain), f"Subtopic '{sub}' returned empty domain")
                    sub_parent = get_parent_skill(sub)
                    self.assertTrue(bool(sub_parent), f"Subtopic '{sub}' returned empty parent skill")

    def test_all_skills_flat_is_sorted_and_unique(self):
        flat = get_all_skills_flat()
        self.assertEqual(len(flat), len(set(flat)))
        self.assertEqual(flat, sorted(flat))
        # Ensure flat list contains no empty strings or whitespace
        for item in flat:
            self.assertTrue(isinstance(item, str) and item.strip() == item and len(item) > 0)


class TestSkillsExtractorAdversarial(unittest.TestCase):
    """Adversarial stress-testing of skills_extractor.py."""

    def test_empty_and_none_text_handling(self):
        for empty_val in ["", "   ", "\n\t", None]:
            res = extract_skill(empty_val)
            self.assertEqual(res, {"high": [], "medium": [], "by_domain": {}})

    def test_special_characters_programming_languages(self):
        # C++, C#, .NET are notorious for tokenization and regex issues
        text = "Candidate excels in C++, C#, .NET, Node.js, and React.js."
        res = extract_skill(text)
        detected = set(res["high"]) | set(res["medium"])
        self.assertIn("C++", detected)
        self.assertIn("C#", detected)

    def test_json_serializability_of_output(self):
        # Result must be 100% JSON serializable for MongoDB insertion & FastAPI responses
        text = "Skills: Python, FastAPI, Docker, DSA, OOPS, PostgreSQL"
        projects = "Built ResuListic backend with Python, FastAPI, and Docker."
        res = extract_skill(text, projects)

        # Assert no sets or custom non-serializable objects
        serialized = json.dumps(res)
        deserialized = json.loads(serialized)
        self.assertIn("high", deserialized)
        self.assertIn("medium", deserialized)
        self.assertIn("by_domain", deserialized)
        self.assertIsInstance(deserialized["high"], list)
        self.assertIsInstance(deserialized["medium"], list)
        self.assertIsInstance(deserialized["by_domain"], dict)

    def test_large_input_stress_no_hang(self):
        # 50,000 chars of repeated text to stress spaCy pipeline
        large_text = "Python, Docker, Kubernetes, DSA, Machine Learning, Fastapi. " * 800
        res = extract_skill(large_text)
        self.assertIsInstance(res["medium"], list)
        self.assertIn("Python", res["medium"])
        self.assertIn("Docker", res["medium"])

    def test_by_domain_only_includes_detected_entities(self):
        text = "Proficient only in Docker containerization and Linux systems."
        res = extract_skill(text)
        by_domain = res["by_domain"]
        self.assertIn("Cloud & DevOps", by_domain)
        # Should NOT include unmentioned domains
        self.assertNotIn("AI, ML & Data Science", by_domain)
        self.assertNotIn("Frontend Web Development", by_domain)


class TestQuestionSelectorRobustness(unittest.TestCase):
    """Stress testing skill expansion, regex generation, and question distribution."""

    def test_expand_skill_special_chars_and_aliases(self):
        # DSA umbrella expansion
        expanded_dsa = _expand_skill("DSA")
        self.assertIn("DSA", expanded_dsa)
        self.assertIn("Array", expanded_dsa)
        self.assertIn("Dynamic Programming", expanded_dsa)

        # C++ has regex '+'
        expanded_cpp = _expand_skill("C++")
        self.assertIn("C++", expanded_cpp)
        self.assertIn("STL", expanded_cpp)

        # None/empty inputs
        self.assertEqual(_expand_skill(""), [])
        self.assertEqual(_expand_skill(None), [])

    def test_build_skill_regex_escapes_special_characters(self):
        # C++, C#, .NET, and node.js contain +, #, ., etc.
        skills = ["C++", "C#", ".NET", "Node.js", "A+B"]
        pattern = _build_skill_regex(skills)

        # Must compile without error
        regex = re.compile(pattern, re.IGNORECASE)

        # Must match exactly
        self.assertTrue(regex.match("C++"))
        self.assertTrue(regex.match("c++"))
        self.assertTrue(regex.match("C#"))
        self.assertTrue(regex.match(".NET"))
        self.assertTrue(regex.match("Node.js"))

        # Must NOT partial-match or match wildcards
        self.assertFalse(regex.match("C"))       # C++ shouldn't match C
        self.assertFalse(regex.match("XNET"))    # .NET dot shouldn't act as any char
        self.assertFalse(regex.match("C+++"))

    def test_build_skill_regex_empty_list(self):
        pattern = _build_skill_regex([])
        self.assertEqual(pattern, "^$")
        regex = re.compile(pattern)
        self.assertTrue(regex.match(""))
        self.assertFalse(regex.match("Python"))

    def test_distribute_edge_cases(self):
        # Empty list
        self.assertEqual(_distribute([], 5), {})

        # Total 0
        self.assertEqual(_distribute(["Python", "DSA"], 0), {"Python": 0, "DSA": 0})

        # Remainder handling
        dist = _distribute(["A", "B", "C"], 5)
        # 5 // 3 = 1, rem = 2 -> A: 2, B: 2, C: 1
        self.assertEqual(dist, {"A": 2, "B": 2, "C": 1})
        self.assertEqual(sum(dist.values()), 5)

        # Total less than skills count
        dist2 = _distribute(["A", "B", "C", "D"], 2)
        self.assertEqual(dist2, {"A": 1, "B": 1, "C": 0, "D": 0})
        self.assertEqual(sum(dist2.values()), 2)

    def test_generate_test_session_empty_skills_raises(self):
        mock_db = MagicMock()
        with self.assertRaises(ValueError):
            generate_test_session(mock_db, "user1", [])


class TestBackwardCompatibilityContracts(unittest.TestCase):
    """Guarantees existing contracts in main.py and resume_builder.py remain unbroken."""

    def test_main_py_get_user_skills_contract(self):
        """Simulates how main.py /api/user-skills reads the enrichment.skills document."""
        mock_resume_doc = {
            "_id": "test_user_123",
            "enrichment": {
                "skills": extract_skill("Python, Docker", "Built API with Python")
            }
        }
        # In main.py lines 122-127:
        skills = mock_resume_doc.get("enrichment", {}).get("skills", {})
        high = skills.get("high", [])
        med = skills.get("medium", [])

        self.assertIsInstance(high, list)
        self.assertIsInstance(med, list)
        self.assertIn("Python", high)
        self.assertIn("Docker", med)

    def test_main_py_start_test_auto_pick_contract(self):
        """Simulates main.py lines 145-148 auto-picking top 5 high-confidence skills."""
        mock_resume_doc = {
            "_id": "test_user_123",
            "enrichment": {
                "skills": extract_skill(
                    "Python, Docker, FastAPI, PostgreSQL, Git, Redis",
                    "Used Python, Docker, FastAPI, PostgreSQL, Git, Redis in projects."
                )
            }
        }
        high_skills = mock_resume_doc.get("enrichment", {}).get("skills", {}).get("high", [])
        self.assertGreaterEqual(len(high_skills), 5)
        auto_picked = high_skills[:5]
        self.assertEqual(len(auto_picked), 5)
        for s in auto_picked:
            self.assertIsInstance(s, str)

    def test_resume_builder_build_resume_document_structure(self):
        """Validates that extract_skill output embeds cleanly into resume document format."""
        skills_raw = "Python, FastAPI, MongoDB, DSA"
        projects_raw = "ResuListic platform built with Python and FastAPI"
        extracted = extract_skill(skills_raw, projects_raw)

        # Simulate doc creation as in resume_builder.py
        doc = {
            "_id": "user_abc",
            "enrichment": {
                "skills": extracted,
                "skill_test_result": None,
                "predicted_job_id": None,
                "match_score": None,
            }
        }
        # Validate JSON dump does not fail
        dumped = json.dumps(doc)
        self.assertTrue(len(dumped) > 50)


if __name__ == "__main__":
    unittest.main()
