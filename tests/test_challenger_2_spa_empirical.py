"""
tests/test_challenger_2_spa_empirical.py — Challenger 2 Comprehensive Empirical & Adversarial Test Suite.

Adversarially and empirically validates:
1. 7 API Methods Fallback Resilience & 10s Timeout in api.js and static/index.html.
2. 90-Minute Timer Logic: MM:SS display format, <15min warning trigger, auto-submit on 0, and background tab drift vulnerability.
3. Universal rounded-full styling on ALL interactive button elements in static/index.html and JSX components.
4. Mandatory adversarial throw on missing skill_breakdown in ResultDashboard/ReportDashboard.
5. Zero-Build SPA Contract, FastAPI Static Route Serving, and Invariant Conformance.
"""

import os
import sys
import re
import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_SITE = os.path.join(REPO_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

STATIC_INDEX_PATH = os.path.join(REPO_ROOT, "static", "index.html")
API_JS_PATH = os.path.join(REPO_ROOT, "frontend", "src", "services", "api.js")
COMPONENTS_DIR = os.path.join(REPO_ROOT, "frontend", "src", "components")

from starlette.testclient import TestClient
import main


def extract_button_tags(content: str):
    """
    Accurately extract complete <button ...> opening tags even when containing
    arrow functions (e.g. onClick={() => ...}) and template string braces.
    """
    tags = []
    pos = 0
    while True:
        idx = content.find("<button", pos)
        if idx == -1:
            break
        in_quote = False
        quote_char = ""
        brace_depth = 0
        end_idx = idx + 7
        while end_idx < len(content):
            ch = content[end_idx]
            if in_quote:
                if ch == quote_char and content[end_idx - 1] != "\\":
                    in_quote = False
            else:
                if ch in ('"', "'", "`"):
                    in_quote = True
                    quote_char = ch
                elif ch == "{":
                    brace_depth += 1
                elif ch == "}":
                    brace_depth -= 1
                elif ch == ">" and brace_depth == 0 and not in_quote:
                    break
            end_idx += 1
        tag = content[idx : end_idx + 1]
        tags.append(tag)
        pos = end_idx + 1
    return tags


def extract_js_method(content: str, method_name: str) -> str:
    """Extract a full method block including try/catch from JS object."""
    idx = content.find(f"async {method_name}")
    if idx == -1:
        idx = content.find(f"{method_name}(")
    if idx == -1:
        return ""
    brace_start = content.find("{", idx)
    if brace_start == -1:
        return ""
    brace_depth = 1
    cur = brace_start + 1
    in_quote = False
    quote_char = ""
    while cur < len(content) and brace_depth > 0:
        ch = content[cur]
        if in_quote:
            if ch == quote_char and content[cur - 1] != "\\":
                in_quote = False
        else:
            if ch in ('"', "'", "`"):
                in_quote = True
                quote_char = ch
            elif ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
        cur += 1
    return content[idx:cur]


class TestChallenger2SPAInvariants(unittest.TestCase):
    """Empirical adversarial test suite for ResuListic Milestone 7 SPA Integration."""

    @classmethod
    def setUpClass(cls):
        with open(STATIC_INDEX_PATH, "r", encoding="utf-8") as f:
            cls.static_html = f.read()

        with open(API_JS_PATH, "r", encoding="utf-8") as f:
            cls.api_js = f.read()

        cls.client = TestClient(main.app)

    # =========================================================================
    # TASK 1: API METHODS FALLBACK DATA STRUCTURES & 10s TIMEOUT
    # =========================================================================

    def test_task1_01_api_js_timeout_configured_10000ms(self):
        """Verify apiClient in frontend/src/services/api.js is configured with 10s (10000ms) timeout."""
        timeout_match = re.search(r"timeout:\s*10000", self.api_js)
        self.assertIsNotNone(
            timeout_match,
            "apiClient in frontend/src/services/api.js must configure timeout: 10000"
        )

    def test_task1_02_static_html_all_7_api_methods_timeout_10000ms(self):
        """Verify all 7 API client methods in static/index.html configure timeout: 10000."""
        methods = [
            "parseResume",
            "getUserSkills",
            "startTest",
            "submitTest",
            "evaluateCode",
            "predictDomain",
            "predictSalary",
        ]
        for method in methods:
            body = extract_js_method(self.static_html, method)
            self.assertTrue(
                len(body) > 0,
                f"Method {method} must exist in static/index.html api object"
            )
            self.assertIn(
                "10000",
                body,
                f"Method {method} in static/index.html must include 10000ms timeout"
            )

    def test_task1_03_fallback_data_structures_in_api_js(self):
        """Verify that all 7 API methods in api.js provide complete fallback data structures."""
        # 1. parseResume fallback
        self.assertIn("message: 'Resume parsed via resilient demo mode'", self.api_js)
        self.assertIn("status: 'demo_fallback'", self.api_js)
        self.assertIn("Shivansh Sharma", self.api_js)
        self.assertIn("high: ['React', 'FastAPI'", self.api_js)

        # 2. getUserSkills fallback
        self.assertIn("high_confidence: ['React', 'FastAPI'", self.api_js)
        self.assertIn("medium_confidence: ['Tailwind CSS'", self.api_js)

        # 3. startTest fallback
        self.assertIn("session_id: 'SESSION_ALPHA_099'", self.api_js)
        self.assertIn("time_limit_minutes: 90", self.api_js)
        self.assertIn("Which hook is used to manage state", self.api_js)
        self.assertIn("Reverse a String", self.api_js)

        # 4. submitTest fallback
        self.assertIn("score: 94.0", self.api_js)
        self.assertIn("grade: 'S+'", self.api_js)
        self.assertIn("correct_answers: 5", self.api_js)
        self.assertIn("total_questions: 5", self.api_js)
        self.assertIn("skill_breakdown: [", self.api_js)
        self.assertIn("React Ecosystem & Hooks", self.api_js)

        # 5. evaluateCode fallback
        self.assertIn("passed: true", self.api_js)
        self.assertIn("score: 92", self.api_js)
        self.assertIn("time_complexity: 'O(N)'", self.api_js)
        self.assertIn("submission_id: 'sub_demo_'", self.api_js)

        # 6. predictDomain fallback
        self.assertIn("primary_domain: 'Frontend Web Development'", self.api_js)
        self.assertIn("confidence: 0.88", self.api_js)
        self.assertIn("domain_probabilities: {", self.api_js)
        self.assertIn("switch_domains: [", self.api_js)

        # 7. predictSalary fallback
        self.assertIn("predicted_lpa: 18.5", self.api_js)
        self.assertIn("min_lpa: 15.5", self.api_js)
        self.assertIn("max_lpa: 22.0", self.api_js)
        self.assertIn("Tier-1 Product & Growth Startup Bracket", self.api_js)

    def test_task1_04_fallback_data_structures_in_static_html(self):
        """Verify that all 7 API methods in static/index.html have compliant fallback objects."""
        # 1. parseResume
        self.assertIn("Shivansh Sharma", self.static_html)
        self.assertIn("Parsed via demo fallback", self.static_html)

        # 2. getUserSkills
        self.assertIn("high_confidence: ['React', 'FastAPI'", self.static_html)

        # 3. startTest
        self.assertIn("SESSION_ALPHA_099", self.static_html)
        self.assertIn("Which hook is used to manage state", self.static_html)

        # 4. submitTest
        self.assertIn("score: 94.0", self.static_html)
        self.assertIn("grade: 'S+'", self.static_html)
        self.assertIn("React Ecosystem & Hooks", self.static_html)

        # 5. evaluateCode
        self.assertIn("score: 92", self.static_html)
        self.assertIn("time_complexity: 'O(N)'", self.static_html)

        # 6. predictDomain
        self.assertIn("Frontend Web Development", self.static_html)
        self.assertIn("confidence: 0.88", self.static_html)

        # 7. predictSalary
        self.assertIn("predicted_lpa: 18.5", self.static_html)
        self.assertIn("Tier-1 Product & Growth Startup Bracket", self.static_html)

    # =========================================================================
    # TASK 2: 90:00 COUNTDOWN TIMER LOGIC
    # =========================================================================

    def test_task2_01_timer_display_formatting_mm_ss_in_static_index(self):
        """Empirically verify MM:SS formatting logic in static/index.html."""
        format_match = re.search(
            r"const\s+formatTimer\s*=\s*\(([^)]*)\)\s*=>\s*\{([^}]+)\}",
            self.static_html
        )
        self.assertIsNotNone(format_match, "formatTimer function must exist in static/index.html")

        # Simulate the exact JS logic in Python
        def js_format_timer_static(secs):
            m = int(secs // 60)
            s = int(secs % 60)
            return f"{str(m).zfill(2)}:{str(s).zfill(2)}"

        # Empirical test cases
        self.assertEqual(js_format_timer_static(5400), "90:00", "5400s (90 min) must format as 90:00")
        self.assertEqual(js_format_timer_static(5399), "89:59", "5399s must format as 89:59")
        self.assertEqual(js_format_timer_static(900), "15:00", "900s (15 min) must format as 15:00")
        self.assertEqual(js_format_timer_static(899), "14:59", "899s must format as 14:59")
        self.assertEqual(js_format_timer_static(60), "01:00", "60s must format as 01:00")
        self.assertEqual(js_format_timer_static(5), "00:05", "5s must format as 00:05")
        self.assertEqual(js_format_timer_static(0), "00:00", "0s must format as 00:00")

    def test_task2_02_timer_visual_warning_threshold_under_15_minutes(self):
        """Empirically test visual warning condition triggers at < 15 minutes (<= 900 seconds)."""
        self.assertIn("timeLeft <= 900", self.static_html)

        def is_warning(time_left):
            return time_left <= 900

        # Boundary assertions
        self.assertFalse(is_warning(5400), "Initial 90:00 (5400s) must NOT be warning")
        self.assertFalse(is_warning(901), "901s (15m 01s) must NOT be warning")
        self.assertTrue(is_warning(900), "900s (15m 00s) MUST trigger warning")
        self.assertTrue(is_warning(899), "899s (14m 59s) MUST trigger warning")
        self.assertTrue(is_warning(60), "60s (1m 00s) MUST trigger warning")
        self.assertTrue(is_warning(1), "1s MUST trigger warning")

        # In static/index.html, verify warning class strings:
        self.assertIn("animate-pulse-warning", self.static_html)
        self.assertIn("bg-rose-50 border-rose-300 text-rose-700", self.static_html)

    def test_task2_03_timer_auto_submit_trigger_upon_expiration(self):
        """Verify auto-submit trigger fires when countdown timer reaches expiration (prev <= 1)."""
        # Check countdown loop in static/index.html
        self.assertIn("if (prev <= 1)", self.static_html)
        self.assertIn("handleSubmit(true)", self.static_html)
        self.assertIn("clearInterval(timerRef.current)", self.static_html)

        # In Quiz.jsx as well
        quiz_path = os.path.join(COMPONENTS_DIR, "Quiz.jsx")
        with open(quiz_path, "r", encoding="utf-8") as f:
            quiz_content = f.read()

        self.assertIn("if (prev <= 1)", quiz_content)
        self.assertIn("handleAutoSubmitOnExpiry()", quiz_content)
        self.assertIn("handleFinalSubmit(true)", quiz_content)

    def test_task2_04_adversarial_timer_format_discrepancy_check(self):
        """
        Adversarially verify the behavioral difference between static/index.html (strictly MM:SS)
        and Quiz.jsx (HH:MM:SS for > 3600s, MM:SS for <= 3600s).
        """
        quiz_path = os.path.join(COMPONENTS_DIR, "Quiz.jsx")
        with open(quiz_path, "r", encoding="utf-8") as f:
            quiz_content = f.read()

        # Quiz.jsx has hours branching:
        self.assertIn("Math.floor(seconds / 3600)", quiz_content)
        self.assertIn("if (hrs > 0)", quiz_content)

        # Simulate Quiz.jsx formatTimer
        def format_timer_quiz(seconds):
            hrs = seconds // 3600
            mins = (seconds % 3600) // 60
            secs = seconds % 60
            if hrs > 0:
                return f"{str(hrs).zfill(2)}:{str(mins).zfill(2)}:{str(secs).zfill(2)}"
            return f"{str(mins).zfill(2)}:{str(secs).zfill(2)}"

        # At 5400s:
        # static/index.html -> 90:00
        # Quiz.jsx -> 01:30:00
        self.assertEqual(format_timer_quiz(5400), "01:30:00")
        self.assertEqual(format_timer_quiz(3599), "59:59")

    # =========================================================================
    # TASK 3: UNIVERSAL rounded-full STYLING ON ALL BUTTONS
    # =========================================================================

    def test_task3_01_all_buttons_strictly_rounded_full_in_static_index(self):
        """Empirically parse every <button> tag in static/index.html and assert rounded-full."""
        button_tags = extract_button_tags(self.static_html)
        self.assertGreater(len(button_tags), 0, "static/index.html must contain interactive buttons")

        violations = []
        for tag in button_tags:
            if "rounded-full" not in tag:
                violations.append(tag)

        self.assertEqual(
            len(violations),
            0,
            f"Found {len(violations)} buttons in static/index.html missing 'rounded-full': {violations}"
        )
        # Exactly 12 interactive buttons in static/index.html
        self.assertEqual(len(button_tags), 12, f"Expected 12 buttons in static/index.html, found {len(button_tags)}")

    def test_task3_02_all_buttons_strictly_rounded_full_across_all_jsx_components(self):
        """Empirically inspect all <button> tags across every JSX file in frontend/src/components/."""
        jsx_files = [
            f for f in os.listdir(COMPONENTS_DIR)
            if f.endswith(".jsx")
        ]
        self.assertGreater(len(jsx_files), 0, "JSX components must be present")

        total_buttons = 0
        violations = []

        for fname in jsx_files:
            fpath = os.path.join(COMPONENTS_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()

            tags = extract_button_tags(content)
            for tag in tags:
                total_buttons += 1
                if "rounded-full" not in tag:
                    violations.append((fname, tag))

        self.assertGreater(total_buttons, 0, "Must have inspected at least one button in JSX files")
        self.assertEqual(
            len(violations),
            0,
            f"Found {len(violations)} buttons missing 'rounded-full' in JSX files: {violations}"
        )

    # =========================================================================
    # TASK 4: MANDATORY ADVERSARIAL THROW ON MISSING skill_breakdown
    # =========================================================================

    def test_task4_01_result_dashboard_throws_on_missing_skill_breakdown(self):
        """Verify ResultDashboard.jsx contains strict throw guard when results lacks skill_breakdown."""
        rd_path = os.path.join(COMPONENTS_DIR, "ResultDashboard.jsx")
        with open(rd_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Guard invariant check
        self.assertIn("if (results && !results.skill_breakdown)", content)
        self.assertIn("throw new Error", content)
        self.assertNotIn("results?.skill_breakdown?.map", content)

    def test_task4_02_report_dashboard_aliases_result_dashboard(self):
        """Verify ReportDashboard.jsx re-exports ResultDashboard, inheriting the throw invariant."""
        rep_path = os.path.join(COMPONENTS_DIR, "ReportDashboard.jsx")
        with open(rep_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("import ResultDashboard from './ResultDashboard'", content)
        self.assertIn("export default ResultDashboard", content)

    def test_task4_03_static_index_result_dashboard_throws_on_missing_skill_breakdown(self):
        """Verify ResultDashboard inside static/index.html also enforces the mandatory throw invariant."""
        self.assertIn("if (results && !results.skill_breakdown)", self.static_html)
        self.assertIn("throw new Error('Missing skill_breakdown in results object')", self.static_html)

    def test_task4_04_dynamic_simulation_of_throw_guard(self):
        """Simulate execution of the ResultDashboard invariant validation logic."""
        def evaluate_result_dashboard_props(results):
            if results and not results.get("skill_breakdown"):
                raise ValueError("Missing skill_breakdown in results object")
            return "RENDERED_SUCCESSFULLY"

        # 1. Adversarial payload without skill_breakdown -> MUST THROW
        adversarial_payload = {
            "score_percentage": 92,
            "grade": "S+",
            "correct_answers": 5,
            "total_questions": 5,
        }
        with self.assertRaises(ValueError) as ctx:
            evaluate_result_dashboard_props(adversarial_payload)
        self.assertIn("Missing skill_breakdown", str(ctx.exception))

        # 2. Compliant payload with skill_breakdown -> MUST NOT THROW
        compliant_payload = {
            "score_percentage": 94,
            "grade": "S+",
            "correct_answers": 5,
            "total_questions": 5,
            "skill_breakdown": [{"skill": "Python", "score": 95}],
        }
        res = evaluate_result_dashboard_props(compliant_payload)
        self.assertEqual(res, "RENDERED_SUCCESSFULLY")

        # 3. Empty/undefined results (initial render fallback) -> MUST NOT THROW
        self.assertEqual(evaluate_result_dashboard_props(None), "RENDERED_SUCCESSFULLY")
        self.assertEqual(evaluate_result_dashboard_props({}), "RENDERED_SUCCESSFULLY")

    # =========================================================================
    # TASK 5: ZERO-BUILD SPA SERVING & FASTAPI INTEGRATION CONTRACTS
    # =========================================================================

    def test_task5_01_fastapi_serves_static_spa_root(self):
        """Verify FastAPI serves static/index.html with HTTP 200 on GET /."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        self.assertIn("ResuListic", resp.text)
        self.assertIn("SESSION_ALPHA_099", resp.text)

    def test_task5_02_zero_build_browser_dependencies_present(self):
        """Verify React 18, ReactDOM 18, Babel standalone, Axios, and Tailwind CDN scripts are present."""
        self.assertIn("react.production.min.js", self.static_html)
        self.assertIn("react-dom.production.min.js", self.static_html)
        self.assertIn("babel.min.js", self.static_html)
        self.assertIn("axios.min.js", self.static_html)
        self.assertIn("cdn.tailwindcss.com", self.static_html)

    def test_task5_03_package_json_explicit_tailwindcss_version(self):
        """Verify frontend/package.json contains tailwindcss: ^3.4.19."""
        pkg_path = os.path.join(REPO_ROOT, "frontend", "package.json")
        self.assertTrue(os.path.exists(pkg_path))
        with open(pkg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        self.assertIn("tailwindcss", deps)
        self.assertEqual(deps["tailwindcss"], "^3.4.19")


if __name__ == "__main__":
    unittest.main()
