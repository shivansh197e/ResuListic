import re



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
    
    text = clean_noisy_text(text) #taking already cleaned text
    
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
        
        # 4. Remove leftover link text labels (e.g., "LinkedIn", "GitHub" that remain after URL removal)
        link_labels = ['linkedin', 'github', 'portfolio', 'hackerrank', 'leetcode', 
                       'codeforces', 'codechef', 'kaggle', 'behance', 'dribbble', 
                       'medium', 'hashnode', 'website', 'blog']
        for label in link_labels:
            summary_text = re.sub(r'\b' + label + r'\b', '', summary_text, flags=re.IGNORECASE)

        # 5. Remove leftover visual separators: pipes (|), bullets (•), em-dashes (—/–), and empty lines
        summary_text = re.sub(r'[•|\\-–—]', '', summary_text)
        summary_text = re.sub(r'\n\s*\n', '\n', summary_text)
        
        # 6. Remove garbage summary (OCR artifacts) if it lacks enough real words (e.g. less than 4 alphabetic words)
        words = re.findall(r'[a-zA-Z]{2,}', summary_text)
        if len(words) < 4:
            summary_text = ""

        # 7. Update the cleaned summary back, OR delete the key if it became empty
        cleaned = summary_text.strip()
        if cleaned:
            section["SUMMARY"] = cleaned
        else:
            del section["SUMMARY"]  # Don't pollute the dict with an empty key

    return section


