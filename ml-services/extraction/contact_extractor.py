import re
import phonenumbers as ph



def email_extract(text):
    email_pattern = r"\b[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b"
    emails = re.findall(email_pattern, text)
    return emails

def phone_extract(text):
    ph_no = [match.raw_string for match in ph.PhoneNumberMatcher(text, "IN")]
    
    if not ph_no:
        intl_pattern = r"\+?\d[\d\s\-\.\(\)]{7,14}\d"
        ph_no = re.findall(intl_pattern, text)
    
    return list(dict.fromkeys(ph_no))

def extract_links(text):
    l_pattern = r"(?<![@\w.-])(?:https?:\/\/)?(?:www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+(?:\/[^\s]*)?"

    links = re.findall(l_pattern, text)
    clean_links = []
    for link in links:
        link = link.rstrip('.,;:)]')
        if not link.lower().endswith(('.js','.c','.cpp','.py')):
            clean_links.append(link)
    return clean_links

def clean_final_links(raw_links):
    valid_links = []

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

    bad_extensions = (
        # Code Files
        '.js', '.jsx', '.ts', '.tsx', '.c', '.cpp', '.cs', '.py', '.java', '.rb', '.go', '.php',
        # Data & Config
        '.html', '.css', '.scss', '.json', '.xml', '.yaml', '.yml', '.sql', '.csv',
        # Executables & Documents
        '.sh', '.bat', '.exe', '.apk', '.pdf', '.docx', '.txt', '.md', '.png', '.jpg', '.jpeg'
    )

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

