import pdfplumber


def pdf_extract(file_path):
    
    text=""
    hyper_link=[]
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text+= page.extract_text()+"\n"
                if page.hyperlinks:
                    for link in page.hyperlinks:
                        if 'uri' in link:
                            hyper_link.append(link['uri'])
            return text, hyper_link
    except Exception as err:
        print(f"Error: {err}")
        return None,[]