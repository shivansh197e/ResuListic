import json
import os
import uuid
from datetime import datetime, timezone

from parser.text_extractor import extract_text
from extraction.contact_extractor import contact_info
from extraction.section_splitter import splitter
from extraction.skills_extractor import extract_skill # Assuming this returns a list of skills

# Placeholders for future modules
# from skill_test.evaluator import evaluate_skills
# from job_matcher.predictor import predict_job_id


def build_resume_document(file_path: str) -> dict | None:
    """
    Master pipeline function.
    Takes a resume file path, runs it through the full extraction pipeline,
    and returns a single, clean JSON-ready document for direct DB insertion.

    Returns None if the file could not be parsed.
    """

    # ── Step 1: Parse the raw file ──────────────────────────────────────────
    result = extract_text(file_path)
    if result is None or result[0] is None:
        print(f"❌ Could not extract text from: {file_path}")
        return None

    raw_text, hidden_links = result

    if not raw_text or not raw_text.strip():
        print(f"❌ Empty text extracted from: {file_path}")
        return None

    # ── Step 2: Run both extractors ─────────────────────────────────────────
    contact_data = contact_info(raw_text, hidden_links)
    sections     = splitter(raw_text)

    # ── Step 3: Smartly separate LinkedIn vs GitHub vs other links ──────────
    linkedin_urls = []
    github_urls   = []
    other_links   = []

    for link in contact_data.get("Links", []):
        lower = link.lower()
        if "linkedin" in lower:
            linkedin_urls.append(link)
        elif "github" in lower:
            github_urls.append(link)
        else:
            other_links.append(link)
            
    # ── Step 4: Extract Skills (Placeholder until implemented) ──────────────
    skills_raw = sections.get("SKILLS", "") \
                or sections.get("TECHNICAL SKILLS", "") \
                or sections.get("TECHNOLOGIES", "")
    
    # Extract skills using the NLP pipeline (once you build it!)
    skills_extracted = extract_skill(skills_raw)
    
    # ── Step 5: External Module Calls (Placeholders) ────────────────────────
    # skill_test_result = evaluate_skills(skills_extracted)
    # predicted_job_id = predict_job_id(skills_extracted, sections)
    skill_test_result = None
    predicted_job_id = None

    # ── Step 6: Build the final document ────────────────────────────────────
    document = {
        # ── Metadata (for DB housekeeping) ───────────────────────────────────
        "_id":          str(uuid.uuid4()),        # Unique document ID
        "source_file":  os.path.basename(file_path),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "status":       "raw",                    # raw → enriched → scored

        # ── Contact Information ───────────────────────────────────────────────
        "contact": {
            "emails":    contact_data.get("Email", []),
            "phones":    contact_data.get("Phone No.", []),
            "linkedin":  linkedin_urls,
            "github":    github_urls,
            "other_links": other_links,
        },

        # ── Resume Sections (raw text, for next pipeline stages) ─────────────
        "sections": {
            "summary":          sections.get("SUMMARY", ""),
            "education":        sections.get("EDUCATION", "")
                                or sections.get("ACADEMIC BACKGROUND", "")
                                or sections.get("ACADEMICS", ""),

            "experience":       sections.get("EXPERIENCE", "")
                                or sections.get("WORK EXPERIENCE", "")
                                or sections.get("PROFESSIONAL EXPERIENCE", "")
                                or sections.get("INTERNSHIPS", ""),

            "projects":         sections.get("PROJECTS", "")
                                or sections.get("ACADEMIC PROJECTS", "")
                                or sections.get("PERSONAL PROJECTS", ""),

            # skills_raw is removed as requested!

            "certifications":   sections.get("CERTIFICATIONS", ""),
            "achievements":     sections.get("ACHIEVEMENTS", "")
                                or sections.get("AWARDS", "")
                                or sections.get("AWARDS & ACHIEVEMENTS", ""),

            "languages":        sections.get("LANGUAGES", ""),
            "courses":          sections.get("COURSES", "")
                                or sections.get("TRAININGS", ""),

            "extracurricular":  sections.get("EXTRACURRICULAR ACTIVITIES", "")
                                or sections.get("CO-CURRICULAR ACTIVITIES", "")
                                or sections.get("POSITIONS OF RESPONSIBILITY", ""),
        },

        # ── Enriched fields (to be filled by skill_extractor & AI later) ─────
        "skills_extracted": skills_extracted, # Filled by skill_extractor.py
        "skill_test_result": skill_test_result, # Placeholder for skill test module
        "score":            None, 
        "matched_job_id":   predicted_job_id, # Placeholder for job matching module
    }

    return document


# ── Quick Batch Test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_folder = r"D:\ResuMate\ml-services\data\test_resumes"

    print(f"🚀 Starting Pipeline Test in: {test_folder}\n")
    print("-" * 60)

    if not os.path.exists(test_folder):
        print(f"❌ Error: Folder '{test_folder}' not found.")
    else:
        for filename in os.listdir(test_folder):
            file_path = os.path.join(test_folder, filename)

            if os.path.isfile(file_path):
                print(f"📄 Processing: {filename}...")

                doc = build_resume_document(file_path)

                if doc:
                    print(json.dumps(doc, indent=4, ensure_ascii=False))
                else:
                    print("❌ FAILED: Pipeline returned None.")

                print("-" * 60)

        print("\n✅ Batch Pipeline Test Complete!")
