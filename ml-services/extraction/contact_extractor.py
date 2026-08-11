import re
import phonenumbers as ph
from parser.text_extractor import extract_text
import os
import json


def email_extract(text):
    # Handles subdomains (e.g. @mail.company.co.in) and special chars in username (+, _, .)
    email_pattern = r"\b[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b"
    emails = re.findall(email_pattern, text)
    return emails

def phone_extract(text):
    # Primary: phonenumbers library for Indian numbers
    ph_no = [match.raw_string for match in ph.PhoneNumberMatcher(text, "IN")]
    
    # Fallback: Regex to catch international numbers (e.g. +1-800-...) missed by IN matcher
    if not ph_no:
        intl_pattern = r"\+?\d[\d\s\-\.\(\)]{7,14}\d"
        ph_no = re.findall(intl_pattern, text)
    
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for p in ph_no:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique

def extract_links(text):
    l_pattern = r"(?<![@\w.-])(?:https?:\/\/)?(?:www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+(?:\/[^\s]*)?"

    links = re.findall(l_pattern, text)
    clean_links = []
    for link in links:
        # Strip trailing punctuation that might get caught in the regex match
        link = link.rstrip('.,;:)]')
        if not link.lower().endswith(('.js','.c','.cpp','.py')):
            clean_links.append(link)
    return clean_links

def clean_final_links(raw_links):
    valid_links = []

    # Set {} use kiya hai instead of List [] kyunki Sets mein searching super fast hoti hai
    blacklist = {
        # Degrees & Academics
        'b.tech', 'm.tech', 'b.sc', 'm.sc', 'b.com', 'm.com', 'b.a', 'm.a', 
        'b.ed', 'm.ed', 'ph.d', 'b.arch', 'm.arch', 'b.b.a', 'm.b.a', 'b.c.a', 'm.c.a',
        
        # Tech Stacks & Libraries (The JS & NET trap)
        'socket.io', 'next.js', 'react.js', 'node.js', 'vue.js', 'express.js',
        'nuxt.js', 'nest.js', 'chart.js', 'three.js', 'd3.js', 'ember.js', 
        'sails.js', 'meteor.js', 'alpine.js', 'asp.net', 'vb.net', 'ado.net',
        
        # Common English Grammar & Corporate Abbreviations
        'e.g.', 'i.e.', 'etc.', 'vs.', 'mr.', 'ms.', 'dr.', 'prof.', 'inc.', 'co.', 'ltd.', 'no.'
    }

    # 2. EXPANDED FILE EXTENSIONS (Suffix Matches)
    # Yeh Tuple () hona zaroori hai kyunki python ka .endswith() sirf tuple accept karta hai
    bad_extensions = (
        # Code Files
        '.js', '.jsx', '.ts', '.tsx', '.c', '.cpp', '.cs', '.py', '.java', '.rb', '.go', '.php',
        # Data & Config
        '.html', '.css', '.scss', '.json', '.xml', '.yaml', '.yml', '.sql', '.csv',
        # Executables & Documents
        '.sh', '.bat', '.exe', '.apk', '.pdf', '.docx', '.txt', '.md', '.png', '.jpg', '.jpeg'
    )

    # 3. UPGRADED TRUSTED DOMAINS (Developer platforms)
    trusted_domains = [
        'github', 'linkedin', 'hackerrank', 'leetcode', 'portfolio', 
        'vercel', 'app', 'behance', 'dribbble', 'medium', 'hashnode',
        'kaggle', 'codeforces', 'codechef', 'netlify', 'render'
    ]

    for link in raw_links:
        clean_link = link.lower()

        # remove emails from links
        if clean_link.startswith("mailto:"):
            continue

        # Remove Exact Matches (Tech words, Degrees, Grammar)
        if clean_link in blacklist:
            continue

        # Remove File Extensions (e.g. "my_project.py" or "resume.pdf")
        if clean_link.endswith(bad_extensions):
            continue

        # Strict Bare-Domain Check
        # Agar http/www nahi hai aur slash (/) bhi nahi hai, toh tabhi allow karo jab trusted platform ho
        if not clean_link.startswith(('http', 'www')) and '/' not in clean_link:
            if not any(trusted in clean_link for trusted in trusted_domains):
                continue

        valid_links.append(link)

    # set() duplicate links (e.g. hidden aur text same ho) ko hata dega
    return list(set(valid_links))

def contact_info(text,hidden_link=None):
    if hidden_link is None:
        hidden_link=[]
    #to extract emails from links (i.e. if email is in hyperlink format then to extract it)
    hidden_mail=[]
    text_mail= email_extract(text)
    for link in hidden_link:
        # Case-insensitive check — "MAILTO:" would slip through otherwise
        if link.lower().startswith("mailto:"):
            # "mailto:shivansh@gmail.com?subject=Hi" -> "shivansh@gmail.com"
            clean_mail = link[7:].split('?')[0].strip()
            if clean_mail:  # Only add if non-empty
                hidden_mail.append(clean_mail)
    mail=list(set(text_mail+hidden_mail))


    regex_link=extract_links(text)
    link=list(set(regex_link+hidden_link))
    final_link=clean_final_links(link)#calling link cleaner

    contact_data={
        "Phone No.": phone_extract(text),
        "Email": mail,
        "Links": final_link
    }

    return contact_data

if __name__ == "__main__":
    # Tumhare test folder ka path (apne system ke hisab se set kar lena)
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
                    final_data = contact_info(raw_text, hidden_links)
                    
                    # 3. Output ko clean JSON format mein print karo
                    print(json.dumps(final_data, indent=4))
                else:
                    print("❌ FAILED: Could not extract text from this file.")
                
                print("-" * 50)
                
        print("\n✅ Batch Testing Complete!")