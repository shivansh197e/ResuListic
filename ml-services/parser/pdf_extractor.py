import pdfplumber


def pdf_extract(file_path):
    
    text=""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text+= page.extract_text()+"\n"
            return text
    except Exception as err:
        print(f"Error: {err}")
        return None
    

