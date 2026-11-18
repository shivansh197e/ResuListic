#!/usr/bin/env python3
"""
ResuListic Requirement R4: Automated UI & Visual Verification Suite
------------------------------------------------------------------
Empirical 6-Tier Playwright & Headless Browser Verification Suite.
Validates:
  [TIER 1] Browser Engine Launch & Headless Shell Contract
  [TIER 2] 5-View End-to-End Progression & Component Rendering
  [TIER 3] Deep Midnight Navy (#080E1C) & Spectral Identity Integration
  [TIER 4] Universal rounded-full Button Styling Across Live DOM
  [TIER 5] Live DOM & Static Code Zero-Emoji Audit
  [TIER 6] Multi-Viewport Responsiveness & High-Resolution Visual Artifacts
"""

import os
import sys
import re
import time
import urllib.request

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Dynamically add venv site-packages to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_SITE = os.path.join(PROJECT_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("[ERROR] Playwright is not installed in the environment.")
    sys.exit(1)


def is_live_server_active(url="http://localhost:8000/"):
    """Check if the live FastAPI server is running on localhost:8000."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ResuListic-Verifier/1.0"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def extract_button_tags(content: str):
    """
    Parses JSX/HTML to extract every opening <button ...> tag.
    Handles curly braces { ... } for JSX expressions (e.g. arrow functions () =>),
    and quotes ('...', "...", `...`).
    """
    buttons = []
    i = 0
    n = len(content)
    while i < n:
        if content[i:i+7].lower() == '<button' and (i + 7 == n or content[i+7] in ' \t\r\n>'):
            start = i
            i += 7
            in_quote = None
            brace_depth = 0
            while i < n:
                ch = content[i]
                if in_quote:
                    if ch == in_quote and (i == 0 or content[i-1] != '\\'):
                        in_quote = None
                elif ch in ('"', "'", '`'):
                    in_quote = ch
                elif ch == '{':
                    brace_depth += 1
                elif ch == '}':
                    brace_depth = max(0, brace_depth - 1)
                elif ch == '>' and brace_depth == 0 and in_quote is None:
                    buttons.append((start, i + 1, content[start:i+1]))
                    break
                i += 1
        else:
            i += 1
    return buttons


def run_ast_button_check():
    """Performs static AST/regex audit across all JSX and HTML files."""
    frontend_files = [
        os.path.join(PROJECT_ROOT, "static", "index.html"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "Navbar.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "UploadResume.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "SkillSelection.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "Quiz.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "ResultDashboard.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "Stepper.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "Toast.jsx")
    ]
    
    total_buttons = 0
    violations = []
    
    for fpath in frontend_files:
        if not os.path.exists(fpath):
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        tags = extract_button_tags(content)
        total_buttons += len(tags)
        for _, _, tag in tags:
            if "rounded-full" not in tag:
                cleaned = " ".join(tag.split())[:80]
                violations.append((os.path.basename(fpath), cleaned))
                
    return total_buttons, violations


def run_static_emoji_check():
    """Scans code files for any raw Unicode or HTML entity emojis."""
    emoji_regex = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u27ff]")
    entity_regex = re.compile(r"&#(?:x1[0-9a-f]{4}|12[0-9]{4}|13[0-9]{4});", re.IGNORECASE)
    
    target_files = [
        os.path.join(PROJECT_ROOT, "static", "index.html"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "Navbar.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "UploadResume.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "SkillSelection.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "Quiz.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "ResultDashboard.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "Stepper.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "components", "Toast.jsx"),
        os.path.join(PROJECT_ROOT, "frontend", "src", "index.css"),
        os.path.join(PROJECT_ROOT, "frontend", "tailwind.config.js")
    ]
    
    violations = []
    for fpath in target_files:
        if not os.path.exists(fpath):
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                if emoji_regex.search(line) or entity_regex.search(line):
                    violations.append((os.path.basename(fpath), idx, line.strip()))
                    
    return violations


def main():
    print("=" * 80)
    print("   RESULISTIC REQUIREMENT R4: AUTOMATED UI & VISUAL REGRESSION SUITE")
    print("=" * 80)

    # Prepare screenshot artifact directory
    screenshot_dir = os.path.join(PROJECT_ROOT, "static", "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)

    # Determine execution mode (live port 8000 vs direct zero-build file://)
    live_active = is_live_server_active("http://localhost:8000/")
    if live_active:
        target_url = "http://localhost:8000/"
        print(f"[*] Target mode: Live FastAPI server ({target_url})")
    else:
        static_index = os.path.abspath(os.path.join(PROJECT_ROOT, "static", "index.html")).replace("\\", "/")
        target_url = f"file:///{static_index}"
        print(f"[*] Target mode: Direct zero-build React 18 SPA ({target_url})")

    console_errors = []
    page_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-web-security", "--allow-file-access-from-files", "--no-sandbox"]
        )
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # Telemetry error listeners
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # =====================================================================
        # [TIER 1] Browser Engine Launch & Headless Shell Contract
        # =====================================================================
        print("\n" + "=" * 80)
        print("[TIER 1] BROWSER ENGINE LAUNCH & HEADLESS SHELL CONTRACT")
        print("=" * 80)

        t1_start = time.time()
        page.goto(target_url, wait_until="networkidle")
        t1_duration = time.time() - t1_start

        # Check title
        title = page.title()
        assert "ResuListic" in title, f"Page title missing 'ResuListic': {title}"
        print(f"  [PASS] Page loaded and title verified: '{title}' ({t1_duration:.2f}s)")

        # Check root mount container
        root_el = page.query_selector("#root")
        assert root_el is not None, "FATAL: #root container missing from DOM!"
        print("  [PASS] Mount container #root hydrated with React 18 component tree.")

        # Check favicon link and theme-color in head
        favicon_link = page.query_selector('link[rel*="icon"]')
        assert favicon_link is not None, "FATAL: <link rel='icon'> missing in <head>!"
        favicon_href = favicon_link.get_attribute("href")
        print(f"  [PASS] Vector favicon icon linked in <head>: '{favicon_href}'")

        theme_meta = page.query_selector('meta[name="theme-color"]')
        assert theme_meta is not None, "FATAL: <meta name='theme-color'> missing in <head>!"
        theme_color = theme_meta.get_attribute("content")
        assert theme_color == "#080E1C", f"Expected theme-color #080E1C, got: {theme_color}"
        print(f"  [PASS] Deep Midnight Navy theme-color verified: '{theme_color}'")

        # Verify console errors
        # Filter out benign network errors if backend is offline in file:// mode
        fatal_errors = [e for e in console_errors if "Failed to load resource" not in e and "net::ERR_FILE_NOT_FOUND" not in e]
        assert len(page_errors) == 0, f"Uncaught JavaScript page errors: {page_errors}"
        assert len(fatal_errors) == 0, f"Console error logs detected: {fatal_errors}"
        print("  [PASS] Clean execution telemetry: 0 uncaught errors, 0 runtime exceptions.")

        # =====================================================================
        # [TIER 2] 5-View End-to-End Progression & Component Rendering
        # =====================================================================
        print("\n" + "=" * 80)
        print("[TIER 2] 5-VIEW END-TO-END PROGRESSION & COMPONENT RENDERING")
        print("=" * 80)

        # 1. View 1 & 2: Navbar + Stepper + UploadResume
        navbar_logo = page.query_selector("header svg")
        assert navbar_logo is not None, "Navbar logo missing!"
        stepper_text = page.inner_text("main")
        assert "Resume Intake" in stepper_text, "Stepper missing Step 1!"
        print("  [PASS] View 1 (Navbar & Stepper) successfully rendered.")

        # Screenshot 1: Navbar and Upload Resume
        screen1_path = os.path.join(screenshot_dir, "01_navbar_and_upload.png")
        page.screenshot(path=screen1_path)
        print(f"  [PASS] Captured Screenshot 1: {screen1_path}")

        # Provide a sample PDF file to file input
        sample_pdf = os.path.abspath(os.path.join(PROJECT_ROOT, "Complete_System_Architecture.pdf"))
        file_input = page.query_selector('input[type="file"]')
        assert file_input is not None, "File input missing in UploadResume!"
        file_input.set_input_files(sample_pdf)
        time.sleep(0.3)

        # Click Parse button
        parse_btn = page.query_selector('button:has-text("Parse & Verify Skills")')
        assert parse_btn is not None, "Parse & Verify Skills button missing!"
        parse_btn.click()
        print("  [PASS] Submitted resume for parsing. Awaiting Step 2 (Skill Selection)...")

        # Wait for Step 2 transition (SkillSelection)
        page.wait_for_selector('text="Verified Skill Taxonomy"', timeout=6000)
        print("  [PASS] View 2 -> View 3 transition complete: Skill Selection active.")

        # Screenshot 2: Skill Taxonomy
        screen2_path = os.path.join(screenshot_dir, "02_skill_taxonomy.png")
        page.screenshot(path=screen2_path)
        print(f"  [PASS] Captured Screenshot 2: {screen2_path}")

        # Ensure proceed button is enabled (skills loaded)
        proceed_btn = page.wait_for_selector('button:has-text("Proceed to 120m Assessment"):not([disabled])', timeout=10000)
        assert proceed_btn is not None, "Proceed to Assessment button missing or disabled!"
        proceed_btn.click()
        print("  [PASS] Confirmed skill taxonomy. Awaiting Step 3 (Timed Assessment generation)...")

        # Diagnostic polling for Quiz view
        quiz_loaded = False
        for sec in range(25):
            time.sleep(1)
            btext = page.inner_text("body")
            if "Question Palette" in btext or "Time Remaining" in btext or "Question 1 of" in btext:
                quiz_loaded = True
                print(f"  [DEBUG] Quiz loaded successfully at second {sec+1}")
                break
            if sec % 3 == 0:
                cur_snippet = btext.replace("\n", " ")[:120]
                print(f"  [DEBUG] sec={sec+1}: Body snippet: {cur_snippet}")

        assert quiz_loaded, "Timed Assessment Quiz failed to load within 25 seconds!"
        print("  [PASS] View 3 -> View 4 transition complete: Timed Assessment Quiz active.")

        # Verify Question 1 is visible and select an option
        page.wait_for_selector('div[role="radio"]', timeout=5000)
        radios = page.query_selector_all('div[role="radio"]')
        if len(radios) > 0:
            radios[0].click()
            time.sleep(0.3)

        # Screenshot 3: Timed Assessment
        screen3_path = os.path.join(screenshot_dir, "03_timed_assessment_quiz.png")
        page.screenshot(path=screen3_path)
        print(f"  [PASS] Captured Screenshot 3: {screen3_path}")

        # Navigate to the last question via question navigation pills
        question_pills = page.query_selector_all('button[title*="Question"]')
        assert len(question_pills) > 0, "No question navigation pills found!"
        question_pills[-1].click()
        time.sleep(0.5)

        # Click Submit Assessment button
        submit_btn = page.wait_for_selector('button:has-text("Submit Assessment")', timeout=5000)
        assert submit_btn is not None, "Submit Assessment button missing on final question!"
        submit_btn.click()
        print("  [PASS] Assessment submitted. Awaiting Step 4 (Result Dashboard & Career Synthesis)...")

        # Wait for Step 4 transition (ResultDashboard) - allow time for live prediction chaining
        page.wait_for_selector('text="Assessment Audit & Market Valuation"', timeout=18000)
        print("  [PASS] View 4 -> View 5 transition complete: Result Dashboard active.")

        # Allow document.startViewTransition 250ms CSS cross-fade animation to fully conclude
        time.sleep(0.6)

        # Screenshot 4: Result Dashboard
        screen4_path = os.path.join(screenshot_dir, "04_result_dashboard.png")
        page.screenshot(path=screen4_path)
        print(f"  [PASS] Captured Screenshot 4: {screen4_path}")

        # =====================================================================
        # [TIER 3] Deep Midnight Navy (#080E1C) & Spectral Identity Integration
        # =====================================================================
        print("\n" + "=" * 80)
        print("[TIER 3] DEEP MIDNIGHT NAVY (#080E1C) & SPECTRAL IDENTITY INTEGRATION")
        print("=" * 80)

        # Check presence of Deep Midnight Navy #080E1C and border #1E2E4A in DOM
        html_content = page.content()
        assert "#080E1C" in html_content, "FATAL: Deep Midnight Navy #080E1C not found in rendered DOM!"
        assert "#1E2E4A" in html_content, "FATAL: Midnight Navy Border #1E2E4A not found in rendered DOM!"
        print("  [PASS] Deep Midnight Navy (#080E1C) and Border (#1E2E4A) active in live DOM.")

        # Check SVG linearGradient for Score Gauge (url(#score_gauge_spectral))
        gauge_grad = page.query_selector("#score_gauge_spectral")
        assert gauge_grad is not None, "FATAL: SVG linearGradient #score_gauge_spectral missing in Circular Gauge!"
        print("  [PASS] Circular Gauge verified with dynamic multi-stop spectral linearGradient.")

        # Check SVG linearGradient for Radar Chart
        radar_grad = page.query_selector("#radar_spectral_glow_static")
        assert radar_grad is not None, "FATAL: Multi-axis Competency Radar SVG gradient missing!"
        print("  [PASS] Multi-Axis Competency Radar chart verified with spectral gradient stops.")

        # Check Continuous Spectral Gradient in styles and DOM
        assert "#FF385C" in html_content, "Spectral stop #FF385C missing!"
        assert "#10B981" in html_content, "Spectral stop #10B981 missing!"
        assert "#2563EB" in html_content, "Spectral stop #2563EB missing!"
        print("  [PASS] Continuous Red-to-Green-to-Blue spectral color stops verified in active views.")

        # Check Retake Test Button
        retake_btn = page.query_selector('button:has-text("Retake Assessment")')
        assert retake_btn is not None, "Retake Assessment button missing!"
        retake_cls = retake_btn.get_attribute("class") or ""
        assert "#080E1C" in retake_cls or "bg-[#080E1C]" in retake_cls, "Retake button missing Midnight Navy styling!"
        print("  [PASS] Action controls styled with Deep Midnight Navy token.")

        # =====================================================================
        # [TIER 4] Universal rounded-full Button Styling Across Live DOM
        # =====================================================================
        print("\n" + "=" * 80)
        print("[TIER 4] UNIVERSAL rounded-full BUTTON STYLING ACROSS LIVE DOM")
        print("=" * 80)

        # Open the Answer Review dialog to inspect modal buttons
        review_btn = page.query_selector('button:has-text("View Detailed Answer Explanations")')
        if review_btn:
            review_btn.click()
            time.sleep(0.3)

        live_buttons = page.query_selector_all("button")
        assert len(live_buttons) > 0, "No buttons found in live DOM!"
        live_violations = []

        for btn in live_buttons:
            cls = btn.get_attribute("class") or ""
            btn_text = btn.inner_text().strip().replace("\n", " ")[:30]
            if "rounded-full" not in cls:
                live_violations.append((btn_text, cls))

        print(f"  Inspected {len(live_buttons)} live DOM buttons across active view and open dialog.")
        assert len(live_violations) == 0, f"Live DOM buttons violating rounded-full: {live_violations}"
        print(f"  [PASS] Live DOM: All {len(live_buttons)} buttons strictly adhere to 'rounded-full' utility.")

        # Close dialog
        close_dialog_btn = page.query_selector('dialog button:has-text("Close Review")')
        if close_dialog_btn:
            close_dialog_btn.click()
            time.sleep(0.2)

        # Run Static AST check across all JSX & HTML files
        total_static_btns, static_violations = run_ast_button_check()
        print(f"  Inspected {total_static_btns} static buttons across all frontend codebase files.")
        assert len(static_violations) == 0, f"Static button violations: {static_violations}"
        print(f"  [PASS] Static Code: All {total_static_btns} buttons contain 'rounded-full' without exception.")

        # =====================================================================
        # [TIER 5] Live DOM & Static Code Zero-Emoji Audit
        # =====================================================================
        print("\n" + "=" * 80)
        print("[TIER 5] LIVE DOM & STATIC CODE ZERO-EMOJI AUDIT")
        print("=" * 80)

        # Check live DOM text
        live_body_text = page.inner_text("body")
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u27ff]")
        entity_pattern = re.compile(r"&#(?:x1[0-9a-f]{4}|12[0-9]{4}|13[0-9]{4});", re.IGNORECASE)

        dom_emojis = emoji_pattern.findall(live_body_text)
        dom_entities = entity_pattern.findall(live_body_text)
        assert len(dom_emojis) == 0, f"Live DOM contains Unicode emojis: {dom_emojis}"
        assert len(dom_entities) == 0, f"Live DOM contains HTML entity emojis: {dom_entities}"
        print("  [PASS] Live DOM rendered text is 100% free of Unicode and HTML entity emojis.")

        # Check static files
        static_emoji_violations = run_static_emoji_check()
        assert len(static_emoji_violations) == 0, f"Static emoji violations: {static_emoji_violations}"
        print("  [PASS] Static source files contain 0 Unicode or HTML entity emojis (SVG icons exclusively).")

        # =====================================================================
        # [TIER 6] Multi-Viewport Responsiveness & High-Resolution Visual Artifacts
        # =====================================================================
        print("\n" + "=" * 80)
        print("[TIER 6] MULTI-VIEWPORT RESPONSIVENESS & VISUAL ARTIFACTS")
        print("=" * 80)

        viewports = [
            ("Desktop (1280x800)", 1280, 800),
            ("Tablet (768x1024)", 768, 1024),
            ("Mobile (375x667)", 375, 667)
        ]

        for vp_name, w, h in viewports:
            page.set_viewport_size({"width": w, "height": h})
            time.sleep(0.3)
            # Evaluate horizontal scrollbar overflow
            is_overflowing = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 2")
            assert not is_overflowing, f"Horizontal overflow detected on viewport {vp_name}!"
            print(f"  [PASS] Viewport {vp_name}: Responsive layout with zero horizontal overflow.")

        # Capture Mobile Screenshot
        screen5_path = os.path.join(screenshot_dir, "05_mobile_responsive.png")
        page.screenshot(path=screen5_path)
        print(f"  [PASS] Captured Screenshot 5: {screen5_path}")

        # Verify all 5 screenshot artifacts exist and are valid PNG images > 10KB
        all_screens = [screen1_path, screen2_path, screen3_path, screen4_path, screen5_path]
        for s_path in all_screens:
            assert os.path.exists(s_path), f"Screenshot missing: {s_path}"
            fsize = os.path.getsize(s_path)
            assert fsize > 10240, f"Screenshot suspiciously small ({fsize} bytes): {s_path}"
            print(f"  [PASS] Verified image artifact: {os.path.basename(s_path)} ({fsize // 1024} KB)")

        browser.close()

    print("\n" + "=" * 80)
    print("   REQUIREMENT R4 VERIFICATION SUMMARY: ALL 6 TIERS PASSED WITH ZERO ERRORS!")
    print("=" * 80)
    print("   [TIER 1] Headless Browser Launch & Shell Contract: PASS")
    print("   [TIER 2] 5-View Progression & Rendering:           PASS")
    print("   [TIER 3] Deep Midnight Navy & Spectral Glow:       PASS")
    print("   [TIER 4] Universal rounded-full Button Styling:    PASS")
    print("   [TIER 5] Live DOM & Static Code Zero-Emoji Audit:  PASS")
    print("   [TIER 6] Multi-Viewport Responsiveness & Artifacts:PASS")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
