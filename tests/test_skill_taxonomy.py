"""
test_skill_taxonomy.py — Comprehensive Automated Test Suite for 3-Level Skill Taxonomy.

Verifies All Milestone 4 Acceptance Criteria:
- Tier 1: 9 Core Domains and >50 Resume Skills in SKILL_TAXONOMY
- Tier 2: get_subtopics("DSA") returns algorithmic topics including "Array" and "Dynamic Programming"
- Tier 3: Case-insensitive lookups & alias resolution (e.g. "dsa", "Data Structures and Algorithms", "OOPS", "K8s")
- Tier 4: get_domain resolution for canonical skills, aliases, and subtopics
- Tier 5: get_all_skills_flat deduplication, ordering, and edge cases
- Tier 6: skills_extractor acceptance (extracting DSA, OOPS, Python, Docker into high/medium/by_domain)
- Tier 7: Pipeline cross-module contracts and MongoDB tag compatibility
"""

import os
import sys
import unittest

# Ensure project root and ml-services are in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_SITE = os.path.join(PROJECT_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ML_SERVICES_DIR = os.path.join(PROJECT_ROOT, "ml-services")
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


class TestSkillTaxonomyStructure(unittest.TestCase):
    """Tier 1: Taxonomy Structure & Mathematical Invariants"""

    EXPECTED_DOMAINS = {
        "Core CS & Foundations",
        "Programming Languages",
        "Frontend Web Development",
        "Backend Web Development",
        "Databases & Storage",
        "Cloud & DevOps",
        "AI, ML & Data Science",
        "Mobile Development",
        "Software Engineering & Practices",
    }

    def test_taxonomy_has_exactly_9_core_domains(self):
        self.assertEqual(
            len(SKILL_TAXONOMY), 9,
            f"Expected exactly 9 core domains, found {len(SKILL_TAXONOMY)}"
        )
        self.assertEqual(
            set(SKILL_TAXONOMY.keys()), self.EXPECTED_DOMAINS,
            "Domains in SKILL_TAXONOMY do not match expected 9 core domains."
        )

    def test_taxonomy_has_over_50_resume_skills(self):
        total_skills = sum(len(skills) for skills in SKILL_TAXONOMY.values())
        self.assertGreater(
            total_skills, 50,
            f"Expected >50 resume skills across taxonomy, found {total_skills}"
        )

    def test_each_domain_has_multiple_skills(self):
        for domain, skills in SKILL_TAXONOMY.items():
            self.assertGreaterEqual(
                len(skills), 3,
                f"Domain '{domain}' has fewer than 3 skills ({len(skills)})"
            )

    def test_all_skills_have_non_empty_subtopics(self):
        for domain, skills in SKILL_TAXONOMY.items():
            for skill, subtopics in skills.items():
                self.assertIsInstance(
                    subtopics, list,
                    f"Subtopics for {skill} in {domain} must be a list"
                )
                self.assertGreater(
                    len(subtopics), 0,
                    f"Skill '{skill}' in domain '{domain}' has empty subtopics list"
                )
                for topic in subtopics:
                    self.assertIsInstance(topic, str)
                    self.assertTrue(topic.strip(), f"Subtopic in {skill} is empty string")

    def test_skill_names_are_unique_across_domains(self):
        seen_skills = set()
        for domain, skills in SKILL_TAXONOMY.items():
            for skill in skills.keys():
                self.assertNotIn(
                    skill.lower(), seen_skills,
                    f"Skill '{skill}' in domain '{domain}' is duplicated across taxonomy"
                )
                seen_skills.add(skill.lower())


class TestGetSubtopics(unittest.TestCase):
    """Tier 2: get_subtopics Behavior and Verification"""

    def test_dsa_returns_core_algorithmic_topics(self):
        subtopics = get_subtopics("DSA")
        self.assertIn("Array", subtopics)
        self.assertIn("Dynamic Programming", subtopics)
        self.assertIn("Tree", subtopics)
        self.assertIn("Graph", subtopics)
        self.assertIn("String", subtopics)
        self.assertIn("Linked List", subtopics)
        self.assertIn("Binary Search", subtopics)
        self.assertIn("Sorting", subtopics)
        self.assertIn("Stack", subtopics)
        self.assertIn("Queue", subtopics)

    def test_oop_returns_core_principles(self):
        subtopics = get_subtopics("OOP")
        self.assertIn("Inheritance", subtopics)
        self.assertIn("Polymorphism", subtopics)
        self.assertIn("Encapsulation", subtopics)
        self.assertIn("Abstraction", subtopics)
        self.assertIn("SOLID Principles", subtopics)
        self.assertIn("Design Patterns", subtopics)

    def test_system_design_returns_architectural_topics(self):
        subtopics = get_subtopics("System Design")
        self.assertIn("High-Level Design", subtopics)
        self.assertIn("Microservices", subtopics)
        self.assertIn("Load Balancing", subtopics)
        self.assertIn("Caching", subtopics)
        self.assertIn("Sharding", subtopics)
        self.assertIn("CAP Theorem", subtopics)

    def test_subtopics_returns_new_list_copy(self):
        subtopics1 = get_subtopics("DSA")
        subtopics1.append("TestMutationTopic")
        subtopics2 = get_subtopics("DSA")
        self.assertNotIn("TestMutationTopic", subtopics2, "get_subtopics must return a shallow copy")


class TestSkillAliasesAndCaseInsensitivity(unittest.TestCase):
    """Tier 3: Case-Insensitivity & Alias Resolution"""

    def test_case_insensitive_lookups(self):
        expected_dsa = get_subtopics("DSA")
        self.assertEqual(get_subtopics("dsa"), expected_dsa)
        self.assertEqual(get_subtopics("Dsa"), expected_dsa)
        self.assertEqual(get_subtopics("DSA "), expected_dsa)
        self.assertEqual(get_subtopics("  dsa  "), expected_dsa)

        expected_python = get_subtopics("Python")
        self.assertEqual(get_subtopics("python"), expected_python)
        self.assertEqual(get_subtopics("PYTHON"), expected_python)

        expected_fastapi = get_subtopics("FastAPI")
        self.assertEqual(get_subtopics("fastapi"), expected_fastapi)
        self.assertEqual(get_subtopics("FASTAPI"), expected_fastapi)

        expected_docker = get_subtopics("Docker")
        self.assertEqual(get_subtopics("docker"), expected_docker)
        self.assertEqual(get_subtopics("DOCKER"), expected_docker)

    def test_alias_resolution_core_cs(self):
        expected_dsa = get_subtopics("DSA")
        self.assertEqual(get_subtopics("Data Structures and Algorithms"), expected_dsa)
        self.assertEqual(get_subtopics("Data Structures & Algorithms"), expected_dsa)
        self.assertEqual(get_subtopics("data structures and algorithms"), expected_dsa)
        self.assertEqual(get_subtopics("Algorithms"), expected_dsa)

        expected_oop = get_subtopics("OOP")
        self.assertEqual(get_subtopics("OOPS"), expected_oop)
        self.assertEqual(get_subtopics("oops"), expected_oop)
        self.assertEqual(get_subtopics("Object-Oriented Programming"), expected_oop)

        expected_sd = get_subtopics("System Design")
        self.assertEqual(get_subtopics("system design"), expected_sd)
        self.assertEqual(get_subtopics("sys design"), expected_sd)

        expected_os = get_subtopics("Operating Systems")
        self.assertEqual(get_subtopics("OS"), expected_os)
        self.assertEqual(get_subtopics("os"), expected_os)

        expected_cn = get_subtopics("Computer Networks")
        self.assertEqual(get_subtopics("CN"), expected_cn)
        self.assertEqual(get_subtopics("cn"), expected_cn)

    def test_alias_resolution_cloud_devops_and_ai(self):
        expected_k8s = get_subtopics("Kubernetes")
        self.assertEqual(get_subtopics("K8s"), expected_k8s)
        self.assertEqual(get_subtopics("k8s"), expected_k8s)
        self.assertEqual(get_subtopics("kube"), expected_k8s)

        expected_ml = get_subtopics("Machine Learning")
        self.assertEqual(get_subtopics("ML"), expected_ml)
        self.assertEqual(get_subtopics("ml"), expected_ml)

        expected_dl = get_subtopics("Deep Learning")
        self.assertEqual(get_subtopics("DL"), expected_dl)

        expected_nlp = get_subtopics("Natural Language Processing")
        self.assertEqual(get_subtopics("NLP"), expected_nlp)

        expected_llm = get_subtopics("Large Language Models")
        self.assertEqual(get_subtopics("LLM"), expected_llm)
        self.assertEqual(get_subtopics("GenAI"), expected_llm)

    def test_unknown_and_invalid_inputs(self):
        self.assertEqual(get_subtopics("NonExistentSkillFooBar"), [])
        self.assertEqual(get_subtopics(""), [])
        self.assertEqual(get_subtopics("   "), [])
        self.assertEqual(get_subtopics(None), [])
        self.assertEqual(get_subtopics(12345), [])  # Non-string input safety


class TestGetDomain(unittest.TestCase):
    """Tier 4: get_domain Resolution for Skills, Aliases, and Subtopics"""

    def test_canonical_skill_domains(self):
        self.assertEqual(get_domain("DSA"), "Core CS & Foundations")
        self.assertEqual(get_domain("OOP"), "Core CS & Foundations")
        self.assertEqual(get_domain("Python"), "Programming Languages")
        self.assertEqual(get_domain("React"), "Frontend Web Development")
        self.assertEqual(get_domain("FastAPI"), "Backend Web Development")
        self.assertEqual(get_domain("PostgreSQL"), "Databases & Storage")
        self.assertEqual(get_domain("Docker"), "Cloud & DevOps")
        self.assertEqual(get_domain("Machine Learning"), "AI, ML & Data Science")
        self.assertEqual(get_domain("Flutter"), "Mobile Development")
        self.assertEqual(get_domain("Git"), "Software Engineering & Practices")

    def test_alias_domains(self):
        self.assertEqual(get_domain("dsa"), "Core CS & Foundations")
        self.assertEqual(get_domain("Data Structures & Algorithms"), "Core CS & Foundations")
        self.assertEqual(get_domain("OOPS"), "Core CS & Foundations")
        self.assertEqual(get_domain("k8s"), "Cloud & DevOps")
        self.assertEqual(get_domain("ML"), "AI, ML & Data Science")
        self.assertEqual(get_domain("Postgres"), "Databases & Storage")
        self.assertEqual(get_domain("NodeJS"), "Backend Web Development")

    def test_subtopic_domains(self):
        self.assertEqual(get_domain("Array"), "Core CS & Foundations")
        self.assertEqual(get_domain("Dynamic Programming"), "Core CS & Foundations")
        self.assertEqual(get_domain("JSX"), "Frontend Web Development")
        self.assertEqual(get_domain("Pydantic Models"), "Backend Web Development")
        self.assertEqual(get_domain("ACID Compliance"), "Databases & Storage")
        self.assertEqual(get_domain("Pods"), "Cloud & DevOps")
        self.assertEqual(get_domain("Transformers"), "AI, ML & Data Science")
        self.assertEqual(get_domain("Widgets (Stateless & Stateful)"), "Mobile Development")
        self.assertEqual(get_domain("TDD (Test-Driven Development)"), "Software Engineering & Practices")

    def test_unknown_and_invalid_domains(self):
        self.assertEqual(get_domain("NonExistentSkill"), "")
        self.assertEqual(get_domain(""), "")
        self.assertEqual(get_domain("   "), "")
        self.assertEqual(get_domain(None), "")
        self.assertEqual(get_domain(999), "")


class TestGetAllSkillsFlat(unittest.TestCase):
    """Tier 5: get_all_skills_flat Completeness, Ordering & Canonical Helpers"""

    def test_flat_list_properties(self):
        flat = get_all_skills_flat()
        self.assertIsInstance(flat, list)
        self.assertGreater(len(flat), 100)
        self.assertEqual(len(flat), len(set(flat)), "Flat list contains duplicate entries")
        self.assertEqual(flat, sorted(flat), "Flat list is not sorted alphabetically")

    def test_contains_core_skills_and_aliases(self):
        flat_set = set(get_all_skills_flat())
        for required in [
            "DSA", "OOP", "OOPS", "Data Structures & Algorithms",
            "Python", "FastAPI", "React", "Docker", "Kubernetes", "K8s",
            "Array", "Dynamic Programming", "Tree", "PostgreSQL"
        ]:
            self.assertIn(required, flat_set, f"Expected '{required}' in flat skills list")

    def test_canonical_and_parent_helpers(self):
        self.assertEqual(get_canonical_skill("OOPS"), "OOP")
        self.assertEqual(get_canonical_skill("k8s"), "Kubernetes")
        self.assertEqual(get_canonical_skill("DSA"), "DSA")
        self.assertEqual(get_canonical_skill("nonexistent"), "")
        self.assertEqual(get_canonical_skill(None), "")

        self.assertEqual(get_parent_skill("Array"), "DSA")
        self.assertEqual(get_parent_skill("Inheritance"), "OOP")
        self.assertEqual(get_parent_skill("Pydantic Models"), "FastAPI")
        self.assertEqual(get_parent_skill("nonexistent"), "")
        self.assertEqual(get_parent_skill(None), "")


class TestSkillsExtractorIntegration(unittest.TestCase):
    """Tier 6: skills_extractor Integration & R2 Acceptance Checks"""

    def test_extract_skill_four_core_skills(self):
        """Validates extraction of DSA, OOPS, Python, Docker with high/medium/by_domain."""
        text = "DSA, OOPS, Python, Docker"
        res = extract_skill(text)

        # Check return structure contract
        self.assertIn("high", res)
        self.assertIn("medium", res)
        self.assertIn("by_domain", res)

        all_detected = set(res["high"]) | set(res["medium"])
        self.assertIn("DSA", all_detected)
        self.assertIn("OOPS", all_detected)
        self.assertIn("Python", all_detected)
        self.assertIn("Docker", all_detected)

        # Check by_domain contains only detected domains
        by_domain = res["by_domain"]
        expected_detected_domains = {
            "Core CS & Foundations",
            "Programming Languages",
            "Cloud & DevOps",
        }
        self.assertEqual(
            set(by_domain.keys()), expected_detected_domains,
            f"Expected only detected domains {expected_detected_domains}, got {set(by_domain.keys())}"
        )

        # Check that DSA subtopics are populated
        self.assertIn("DSA", by_domain["Core CS & Foundations"])
        dsa_subs = by_domain["Core CS & Foundations"]["DSA"]
        self.assertIn("Array", dsa_subs)
        self.assertIn("Dynamic Programming", dsa_subs)

        # Check that OOPS resolves to canonical OOP in by_domain
        self.assertIn("OOP", by_domain["Core CS & Foundations"])
        oop_subs = by_domain["Core CS & Foundations"]["OOP"]
        self.assertIn("Inheritance", oop_subs)
        self.assertIn("Polymorphism", oop_subs)

        # Check Python in Programming Languages
        self.assertIn("Python", by_domain["Programming Languages"])
        self.assertIn("Generators", by_domain["Programming Languages"]["Python"])

        # Check Docker in Cloud & DevOps
        self.assertIn("Docker", by_domain["Cloud & DevOps"])
        self.assertIn("Containerization", by_domain["Cloud & DevOps"]["Docker"])

    def test_extract_skill_cross_section_priority(self):
        """Validates cross-section ranking: items in both sections are 'high' priority."""
        skills_text = "DSA, Python, Docker"
        projects_text = "Engineered ResuListic using Python and Docker containerization."

        res = extract_skill(skills_text, projects_text)

        # Python and Docker are in both sections
        self.assertIn("Python", res["high"])
        self.assertIn("Docker", res["high"])

        # DSA is only in skills section
        self.assertIn("DSA", res["medium"])
        self.assertNotIn("DSA", res["high"])

    def test_extract_skill_empty_and_noise(self):
        res_empty = extract_skill("")
        self.assertEqual(res_empty, {"high": [], "medium": [], "by_domain": {}})

        res_noise = extract_skill("This is a simple narrative sentence without any technical words.")
        self.assertEqual(res_noise["high"], [])
        self.assertEqual(res_noise["medium"], [])
        self.assertEqual(res_noise["by_domain"], {})


class TestPipelineCrossIntegration(unittest.TestCase):
    """Tier 7: Cross-Module Invariants & Compatibility with Test Runner"""

    def test_dsa_subtopics_match_database_tags(self):
        dsa_topics = set(get_subtopics("DSA"))
        # Known question tags present in MongoDB questions_moderate & questions_hard
        mongo_tags = {
            "Array", "String", "Linked List", "Tree",
            "Dynamic Programming", "Binary Search", "Backtracking", "Hash Table"
        }
        intersection = dsa_topics.intersection(mongo_tags)
        self.assertGreaterEqual(
            len(intersection), 5,
            f"DSA subtopics must match at least 5 MongoDB tags. Intersected: {intersection}"
        )

    def test_skill_patterns_contains_taxonomy_flat_skills(self):
        skill_patterns_set = {p.lower() for p in SKILL_PATTERNS}
        for sample in ["dsa", "oops", "dynamic programming", "fastapi", "docker"]:
            self.assertIn(
                sample, skill_patterns_set,
                f"Expected '{sample}' to be present in merged SKILL_PATTERNS"
            )


if __name__ == "__main__":
    unittest.main()
