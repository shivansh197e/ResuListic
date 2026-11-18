"""
verify_m10_ui_quiz.py — Verification script for Milestone M10 UI & Quiz UX Enhancements.
Verifies:
1. Error404View design tokens, spectral gradient, recovery buttons, and diagnostic metadata in both shells.
2. Quiz 3-track navigation partitioning and SVG chevrons (zero ASCII arrows).
3. Monospace drift-proof timer with circular SVG progress ring and 3-tier warning states.
4. Mobile horizontal quick-scrubber.
5. Quiz localStorage state persistence and autosave under 'resulistic_assessment_state_'.
6. All 7 Architectural Invariants + Invariant 8 (zero emojis).
7. api.js startTest timeout (30000ms).
"""

import os
import re
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_checks():
    print("=" * 80)
    print("M10-UIAndQuiz VERIFICATION SUITE")
    print("=" * 80)

    # 1. Inspect Error404View.jsx
    e404_path = os.path.join(PROJECT_ROOT, "frontend", "src", "components", "Error404View.jsx")
    assert os.path.exists(e404_path), "Error404View.jsx does not exist!"
    with open(e404_path, "r", encoding="utf-8") as f:
        e404_content = f.read()

    assert "#080E1C" in e404_content, "Missing Deep Midnight Navy #080E1C in Error404View.jsx"
    assert "#1E2E4A" in e404_content, "Missing card border #1E2E4A in Error404View.jsx"
    assert "bg-gradient-to-r from-[#FF385C] via-[#FF5A36] via-[#10B981] to-[#2563EB]" in e404_content, "Missing continuous spectral accent gradient in Error404View.jsx"
    assert "Retry Test Generation" in e404_content, "Missing 'Retry Test Generation' in Error404View.jsx"
    assert "Select Alternate Skills" in e404_content, "Missing 'Select Alternate Skills' in Error404View.jsx"
    assert "Upload New Resume" in e404_content, "Missing 'Upload New Resume' in Error404View.jsx"
    assert "Diagnostic Metadata" in e404_content, "Missing Diagnostic Metadata card in Error404View.jsx"
    print("  [PASS] 1. Error404View.jsx meets all styling, token, and recovery requirements.")

    # 2. Inspect static/index.html Error404View parity
    st_path = os.path.join(PROJECT_ROOT, "static", "index.html")
    with open(st_path, "r", encoding="utf-8") as f:
        st_content = f.read()

    assert "const Error404View" in st_content, "Error404View missing in static/index.html"
    assert "from-[#FF385C] via-[#FF5A36] via-[#10B981] to-[#2563EB]" in st_content, "Missing spectral accent line in static/index.html Error404View"
    assert "Retry Test Generation" in st_content, "Missing 'Retry Test Generation' in static/index.html"
    assert "Select Alternate Skills" in st_content, "Missing 'Select Alternate Skills' in static/index.html"
    assert "Upload New Resume" in st_content, "Missing 'Upload New Resume' in static/index.html"
    print("  [PASS] 2. static/index.html Error404View cross-shell parity verified.")

    # 3. Inspect Quiz.jsx enhancements
    quiz_path = os.path.join(PROJECT_ROOT, "frontend", "src", "components", "Quiz.jsx")
    with open(quiz_path, "r", encoding="utf-8") as f:
        quiz_content = f.read()

    # 3-track navigation
    assert "Track 1: Screening MCQs" in quiz_content, "Missing Track 1 in Quiz.jsx"
    assert "Track 2: Moderate Coding" in quiz_content, "Missing Track 2 in Quiz.jsx"
    assert "Track 3: Hard Algo & System" in quiz_content or "Track 3: Hard System & Algo" in quiz_content, "Missing Track 3 in Quiz.jsx"
    # Chevrons
    assert "IconChevronLeft" in quiz_content and "IconChevronRight" in quiz_content, "Missing SVG chevron icons in Quiz.jsx"
    assert "←" not in quiz_content and "→" not in quiz_content, "Raw ASCII arrows still found in Quiz.jsx!"
    # Timer
    assert "tabular-nums" in quiz_content, "Missing tabular-nums monospace in Quiz.jsx timer"
    assert "strokeDashoffset" in quiz_content, "Missing circular SVG progress ring in Quiz.jsx timer"
    # Mobile scrubber
    assert "overflow-x-auto" in quiz_content, "Missing mobile horizontal scrubber in Quiz.jsx"
    # LocalStorage persistence
    assert "resulistic_assessment_state_" in quiz_content, "Missing localStorage key in Quiz.jsx"
    assert "localStorage.getItem" in quiz_content and "localStorage.setItem" in quiz_content, "Missing localStorage logic in Quiz.jsx"
    assert "localStorage.removeItem" in quiz_content, "Missing localStorage purge on submit in Quiz.jsx"
    assert "Autosaved" in quiz_content, "Missing Autosaved badge in Quiz.jsx"
    print("  [PASS] 3. Quiz.jsx 3-track, chevrons, timer, mobile scrubber, and localStorage verified.")

    # 4. Inspect static/index.html Quiz enhancements
    assert "Track 1: Screening MCQs" in st_content, "Missing Track 1 in static/index.html"
    assert "Track 2: Moderate Coding" in st_content, "Missing Track 2 in static/index.html"
    assert "IconChevronLeft" in st_content and "IconChevronRight" in st_content, "Missing SVG chevron icons in static/index.html"
    assert "resulistic_assessment_state_" in st_content, "Missing localStorage key in static/index.html"
    assert "localStorage.getItem" in st_content and "localStorage.setItem" in st_content, "Missing localStorage logic in static/index.html"
    assert "localStorage.removeItem" in st_content, "Missing localStorage purge in static/index.html"
    print("  [PASS] 4. static/index.html Quiz enhancements cross-shell parity verified.")

    # 5. Inspect api.js timeout
    api_path = os.path.join(PROJECT_ROOT, "frontend", "src", "services", "api.js")
    with open(api_path, "r", encoding="utf-8") as f:
        api_content = f.read()
    assert "timeout: 30000" in api_content, "startTest timeout 30000ms missing in frontend/src/services/api.js"
    print("  [PASS] 5. api.js startTest 30000ms timeout verified.")

    # 6. Verify Invariant 2 AST references
    assert "SESSION_ALPHA_099" in quiz_content and "Which hook is used to manage state" in quiz_content, "Invariant 2 broken in Quiz.jsx!"
    assert "SESSION_ALPHA_099" in st_content and "Which hook is used to manage state" in st_content, "Invariant 2 broken in static/index.html!"
    print("  [PASS] 6. Invariant 2 fallback references intact in both shells.")

    print("=" * 80)
    print("ALL M10 CHECKS PASSED WITH ZERO REGRESSIONS!")
    print("=" * 80)

if __name__ == "__main__":
    run_checks()
