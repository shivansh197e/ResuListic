import re
import json
import os
from datetime import datetime, timezone

from parser.text_extractor import extract_text
from extraction.contact_extractor import contact_info
from extraction.section_splitter import splitter
from extraction.skills_extractor import extract_skill

# Placeholders for future modules
# from skill_test.evaluator import evaluate_skills
# from job_matcher.predictor import predict_job_id


# ── Section Key Mapping ─────────────────────────────────────────────────────
# Maps a clean output key → list of possible heading names from the splitter.
# The first match wins. This replaces the long "or" chains and makes it easy
# to add new heading variations in one place.
SECTION_MAP = {
    "summary":        ["SUMMARY", "PROFESSIONAL SUMMARY", "OBJECTIVE", "CAREER OBJECTIVE", "PROFILE", "ABOUT ME"],
    "education":      ["EDUCATION", "ACADEMIC BACKGROUND", "EDUCATIONAL QUALIFICATION", "ACADEMICS", "SCHOLASTIC RECORD"],
    "experience":     ["EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE", "WORK HISTORY", "CAREER HISTORY", "EMPLOYMENT", "INTERNSHIPS", "RELEVANT EXPERIENCE"],
    "projects":       ["PROJECTS", "ACADEMIC PROJECTS", "PERSONAL PROJECTS", "KEY PROJECTS", "OPEN SOURCE CONTRIBUTIONS"],
    "certifications": ["CERTIFICATIONS", "COURSES", "TRAININGS"],
    "achievements":   ["ACHIEVEMENTS", "AWARDS", "AWARDS & ACHIEVEMENTS", "HONORS", "PATENTS"],
    "publications":   ["PUBLICATIONS", "RESEARCH"],
    "languages":      ["LANGUAGES"],
    "extracurricular":["EXTRACURRICULAR ACTIVITIES", "CO-CURRICULAR ACTIVITIES", "POSITIONS OF RESPONSIBILITY", "POR", "LEADERSHIP", "VOLUNTEER EXPERIENCE"],
}

# Keys to search for raw skill text (used as input to skill_extractor)
SKILL_SECTION_KEYS = ["SKILLS", "TECHNICAL SKILLS", "TECHNOLOGIES", "EXPERTISE", "CORE COMPETENCIES", "IT SKILLS", "SOFTWARE SKILLS", "TECHNICAL PROFICIENCY"]


def _resolve_section(sections: dict, keys: list) -> str:
    """Returns the first non-empty match from a list of possible heading keys."""
    for key in keys:
        value = sections.get(key, "")
        if value and value.strip():
            return value
    return ""


def _classify_links(links: list) -> dict:
    """Separates links into linkedin, github, portfolio, and others."""
    classified = {
        "linkedin": [],
        "github": [],
        "portfolio": [],
        "other": [],
    }
    for link in links:
        lower = link.lower()
        if "linkedin" in lower:
            classified["linkedin"].append(link)
        elif "github" in lower:
            classified["github"].append(link)
        elif any(kw in lower for kw in ["portfolio", "vercel", "netlify", "render", "heroku"]):
            classified["portfolio"].append(link)
        else:
            classified["other"].append(link)
    return classified


def _extract_name_and_headline(raw_text: str, summary_text: str) -> dict:
    """
    Extracts the candidate's name (first line of resume) and their 
    professional headline/title from the top few lines.
    
    Name → Almost always the very first non-empty line of any resume.
    Headline → Common job titles or descriptors found in the first 5 lines.
    """
    name = ""
    headline = ""

    # ── Name: First non-empty line of the raw resume text ────────────────
    lines = raw_text.strip().split('\n')
    for line in lines:
        cleaned = line.strip()
        # A name line is short, has no '@' (email), no '/' (links), no digits (phone)
        if cleaned and len(cleaned) < 60 and '@' not in cleaned and '/' not in cleaned and not re.search(r'\d{3,}', cleaned):
            name = cleaned
            break

    # ── Headline: Look in first 5 lines for common job title keywords ────
    headline_keywords = [
        # Engineering & Development
        'software engineer', 'software developer', 'web developer', 'frontend', 'front-end',
        'backend', 'back-end', 'full stack', 'fullstack', 'devops', 'sre', 'mobile developer',
        'android developer', 'ios developer', 'app developer', 'cloud engineer',
        # Data & AI
        'data scientist', 'data analyst', 'data engineer', 'ml engineer', 'machine learning',
        'ai engineer', 'deep learning', 'nlp engineer', 'computer vision',
        'ml aspirant', 'ai aspirant', 'data science aspirant',
        # Design & Product
        'ui/ux', 'ux designer', 'ui designer', 'product designer', 'graphic designer',
        'product manager', 'project manager',
        # Cybersecurity & Infra
        'cybersecurity', 'security analyst', 'penetration tester', 'network engineer',
        'system administrator',
        # Intern & Student
        'intern', 'fresher', 'student', 'graduate', 'undergraduate',
        'b.tech', 'btech', 'm.tech', 'mtech',
    ]

    # Search in the first 5 lines of the resume (headline is always near the top)
    search_block = '\n'.join(lines[:5]).lower()
    for kw in headline_keywords:
        if kw in search_block:
            # Find the actual line that contains this keyword and use it as headline
            for line in lines[:5]:
                if kw in line.lower() and line.strip() != name:
                    headline = line.strip()
                    break
            if headline:
                break

    return {"name": name, "headline": headline}


def build_resume_document(file_path: str, user_id: str) -> dict | None:
    """
    Master pipeline function.
    Takes a resume file path + authenticated user ID, runs it through
    the full extraction pipeline, and returns a single, clean JSON-ready
    document for direct DB insertion.

    Args:
        file_path: Path to the resume file.
        user_id:   Authenticated user's ID (from Firebase/Auth system).
                   This ensures the same user always maps to the same document.

    Returns None if the file could not be parsed.
    """
    if not user_id or not user_id.strip():
        print("[ERROR] user_id is required. Cannot create a document without authentication.")
        return None

    # ── Step 1: Parse the raw file ──────────────────────────────────────────
    result = extract_text(file_path)
    if result is None or result[0] is None:
        print(f"[ERROR] Could not extract text from: {file_path}")
        return None

    raw_text, hidden_links = result

    if not raw_text or not raw_text.strip():
        print(f"[ERROR] Empty text extracted from: {file_path}")
        return None

    # ── Step 2: Run extractors ──────────────────────────────────────────────
    contact_data = contact_info(raw_text, hidden_links)
    sections     = splitter(raw_text)

    # ── Step 3: Extract name & headline from top of resume ──────────────────
    summary_text = _resolve_section(sections, SECTION_MAP["summary"])
    identity = _extract_name_and_headline(raw_text, summary_text)

    # ── Step 4: Clean summary — remove the name line from it ────────────────
    if identity["name"] and summary_text:
        # Remove the name from summary so it doesn't appear twice
        summary_text = summary_text.replace(identity["name"], "").strip()
        # Clean leftover empty lines
        summary_text = re.sub(r'\n\s*\n', '\n', summary_text).strip()

    # ── Step 5: Classify links ──────────────────────────────────────────────
    classified_links = _classify_links(contact_data.get("Links", []))

    # ── Step 6: Resolve sections using the mapping ──────────────────────────
    resolved_sections = {}
    for output_key, heading_variants in SECTION_MAP.items():
        resolved_sections[output_key] = _resolve_section(sections, heading_variants)
    # Override summary with the cleaned version (name removed)
    resolved_sections["summary"] = summary_text if summary_text else "N/A"

    # ── Step 7: Extract Skills ──────────────────────────────────────────────
    skills_raw = _resolve_section(sections, SKILL_SECTION_KEYS)
    projects_raw = _resolve_section(sections, SECTION_MAP["projects"])
    experience_raw = _resolve_section(sections, SECTION_MAP["experience"])
    skills_extracted = extract_skill(skills_raw, projects_raw)

    total_extracted = len(skills_extracted.get("high", [])) + len(skills_extracted.get("medium", []))
    if total_extracted < 3:
        # Fallback for table-based DOCX or OCR images where headings didn't split cleanly
        secondary_text = "\n".join(filter(None, [projects_raw, experience_raw]))
        skills_extracted = extract_skill(raw_text, secondary_text if secondary_text else raw_text)

    if not skills_extracted.get("high") and skills_extracted.get("medium"):
        skills_extracted["high"] = skills_extracted["medium"][:6]
        skills_extracted["medium"] = skills_extracted["medium"][6:]

    # ── Step 8: External Module Calls (Placeholders) ────────────────────────
    # skill_test_result = evaluate_skills(skills_extracted)
    # predicted_job_id  = predict_job_id(skills_extracted, sections)

    # ── Step 9: Build the final document ────────────────────────────────────
    document = {

        # ── Identity ─────────────────────────────────────────────────────────
        "_id":     user_id,
        "status":  "raw",  # Pipeline state: raw → enriched → scored → matched

        # ── Metadata ─────────────────────────────────────────────────────────
        "meta": {
            "source_file":  os.path.basename(file_path),
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "pipeline_version": "1.0",
        },

        # ── Candidate Profile ────────────────────────────────────────────────
        "profile": {
            "name":     identity["name"],
            "headline": identity["headline"],  # e.g., "Software Engineer", "ML Aspirant"
        },

        # ── Contact Information ──────────────────────────────────────────────
        "contact": {
            "emails":    contact_data.get("Email", []),
            "phones":    contact_data.get("Phone No.", []),
            "links":     classified_links,
        },

        # ── Resume Sections (raw text for downstream processing) ─────────────
        "sections": resolved_sections,

        # ── AI Enrichment (filled by downstream pipeline stages) ─────────────
        "enrichment": {
            "skills":           skills_extracted,   # ← skill_extractor.py
            "skill_test_result": None,              # ← skill_test module (future)
            "predicted_job_id":  None,              # ← job_matcher module (future)
            "match_score":       None,              # ← scoring engine (future)
        },
    }

    return document


# ── Quick Batch Test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_folder = os.path.join(os.path.dirname(__file__), "..", "data", "test_resumes")
    test_user_id = "test_user_001"  # Dummy user ID for testing

    print(f"Starting Pipeline Test in: {test_folder}\n")
    print("-" * 60)

    if not os.path.exists(test_folder):
        print(f"[ERROR] Folder '{test_folder}' not found.")
    else:
        for filename in os.listdir(test_folder):
            file_path = os.path.join(test_folder, filename)

            if os.path.isfile(file_path):
                print(f"Processing: {filename}...")

                doc = build_resume_document(file_path, test_user_id)

                if doc:
                    print(json.dumps(doc, indent=4, ensure_ascii=False))
                else:
                    print("[FAILED] Pipeline returned None.")

                print("-" * 60)

        print("\nBatch Pipeline Test Complete!")
