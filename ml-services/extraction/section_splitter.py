import re
from parser.text_extractor import extract_text
import os

import json


def clean_noisy_text(text):
    # 1. Remove zero-width spaces and other invisible unicode characters
    text = text.replace('\u200b', '').replace('\u00a0', ' ')
    
    # 2. Fix spaced-out headings like "S K I L L S" -> "SKILLS"
    # Requires at LEAST 4 uppercase letters to avoid collapsing real 2-letter words (e.g. names)
    def de_space(match):
        return match.group(0).replace(' ', '')
    text = re.sub(r'(?m)^\s*(?:[A-Z]\s+){4,}[A-Z]\s*$', de_space, text)
    
    # 3. Handle inline headings like "SKILLS: Python, React" — insert a newline before content
    # So it becomes "SKILLS\nPython, React" for the splitter to catch
    text = re.sub(r'(?m)^([A-Z][A-Z\s&/]{2,}):\s*(.+)$',
                  lambda m: m.group(1).strip() + '\n' + m.group(2).strip(), text)
    
    # 4. Normalize newlines (replace 3 or more newlines with just 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

def splitter(text):
    # general headings of specific sections in resume
    headings = [
        "SUMMARY", "PROFESSIONAL SUMMARY", "OBJECTIVE", "CAREER OBJECTIVE", "PROFILE", "ABOUT ME",
        "EDUCATION", "ACADEMIC BACKGROUND", "EDUCATIONAL QUALIFICATION", "ACADEMICS", "SCHOLASTIC RECORD",
        "EXPERIENCE", "WORK EXPERIENCE", "EMPLOYMENT", "PROFESSIONAL EXPERIENCE", "WORK HISTORY", "CAREER HISTORY", "INTERNSHIPS", "RELEVANT EXPERIENCE",
        "PROJECTS", "PERSONAL PROJECTS", "ACADEMIC PROJECTS", "KEY PROJECTS", "OPEN SOURCE CONTRIBUTIONS",
        "SKILLS", "TECHNICAL SKILLS", "EXPERTISE", "CORE COMPETENCIES", "TECHNOLOGIES", "IT SKILLS", "SOFTWARE SKILLS", "TECHNICAL PROFICIENCY",
        "CERTIFICATIONS", "PUBLICATIONS", "RESEARCH", "AWARDS", "ACHIEVEMENTS", "HONORS", "AWARDS & ACHIEVEMENTS", "PATENTS",
        "POSITIONS OF RESPONSIBILITY", "POR", "EXTRACURRICULAR ACTIVITIES", "CO-CURRICULAR ACTIVITIES", "LEADERSHIP", "VOLUNTEER EXPERIENCE",
        "LANGUAGES", "COURSES", "TRAININGS"
    ]

    heading_pattern = r'\n\s*(' + '|'.join(headings) + r')\s*\n'
    
    # Apply noise cleaning to the raw text first
    text = clean_noisy_text(text)
    
    splits = re.split(heading_pattern,"\n"+ text +"\n", flags=re.IGNORECASE)#splitter for regex
    section= {}

    current_heading = "SUMMARY"# we'll make it first heading


    


    #list to dict
    for i in range(len(splits)):
        part = splits[i].strip() # we're removing whitespaces from every index and storing them into part variable(i.e. storing them as parts)
        if not part:
            continue #for empty strings

        if part.upper() in headings:
            current_heading=part.upper()

        else: #means we're dealing with raw text because splits contains both text and headings and we've made parts using splits
            if current_heading in section:
                section[current_heading]+="\n"+ part
            else:
                section[current_heading] = part

    # --- 🧹 SUMMARY CLEANUP: Remove Contact Info ---
    if "SUMMARY" in section:
        summary_text = section["SUMMARY"]
        
        # 1. Remove Emails (e.g., nikhilanand...@gmail.com)
        summary_text = re.sub(r'\S+@\S+', '', summary_text)
        
        # 2. Remove Links (e.g., https://, www., linkedin, github)
        summary_text = re.sub(r'(https?://\S+|www\.\S+|linkedin\.com\S+|github\.com\S+)', '', summary_text, flags=re.IGNORECASE)
        
        # 3. Remove Phone Numbers (e.g., +91-844..., 98765...)
        summary_text = re.sub(r'\+?\d[\d \-\(\)]{8,14}\d', '', summary_text)
        
        # 4. Remove leftover visual separators: pipes (|), bullets (•), em-dashes (—/–), and empty lines
        summary_text = re.sub(r'[•|\-–—]', '', summary_text)
        summary_text = re.sub(r'\n\s*\n', '\n', summary_text)
        
        # 5. Update the cleaned summary back, OR delete the key if it became empty
        cleaned = summary_text.strip()
        if cleaned:
            section["SUMMARY"] = cleaned
        else:
            del section["SUMMARY"]  # Don't pollute the dict with an empty key

    return section


# --- Quick Test ---
if __name__ == "__main__":
    
    test_folder = r"D:\ResuMate\ml-services\data\test_resumes"
    
    print(f"🚀 Starting Batch Test in: {test_folder}\n")
    print("-" * 50)
    
    if not os.path.exists(test_folder):
        print(f"❌ Error: Folder '{test_folder}' not found. Path check karo.")
    else:
        # Folder ke andar ki har file par loop chalega
        for filename in os.listdir(test_folder):
            file_path = os.path.join(test_folder, filename)
            
            # Sirf files ko process karega (folders ya hidden items ko ignore karega)
            if os.path.isfile(file_path):
                print(f"📄 Processing: {filename}...")
                
                # 1. Pipeline ke through pass karo (Tuple Unpacking for text & hidden links)
                raw_text, hidden_links = extract_text(file_path)
                
                if raw_text:
                    # 2. Dono inputs contact_info ko bhejo
                    final_data = splitter(raw_text)
                    
                    # 3. Output ko clean JSON format mein print karo
                    print(json.dumps(final_data, indent=4))
                else:
                    print("❌ FAILED: Could not extract text from this file.")
                
                print("-" * 50)
                
        print("\n✅ Batch Testing Complete!")