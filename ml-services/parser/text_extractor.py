import pdfplumber
from pdf2image import convert_from_path
from parser.image_extractor import img_extract
from parser.pdf_extractor import pdf_extract
from parser.docx_extractor import docx_extract

POPPLER_PATH=r"C:\poppler-26.02.0\Library\bin"

def extract_text(file_path):
    
    try:
        text=""
        hidden_links=[]
        if file_path.lower().endswith('.png') or file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):#image
            extracted_text,link= img_extract(file_path)
            if extracted_text:  # Yeh check karega ki kya value None, khali string "", ya False toh nahi hai?
                text += extracted_text
        elif file_path.lower().endswith('.docx'):#word document
            extracted_text,link= docx_extract(file_path)
            if extracted_text:  # Yeh check karega ki kya value None, khali string "", ya False toh nahi hai?
                text += extracted_text
            if link:
                hidden_links.extend(link)
        elif file_path.lower().endswith('.pdf'):#simple pdf
            with pdfplumber.open(file_path) as pdf:
                page=pdf.pages[0]
                txt=page.extract_text()
                if txt and len(txt.strip())>10:
                    extracted_text,link=pdf_extract(file_path)
                    if extracted_text:  # Yeh check karega ki kya value None, khali string "", ya False toh nahi hai?
                        text += extracted_text
                    if link:
                        hidden_links.extend(link)
                else:#scanned pdf
                    try:
                        pages = convert_from_path(file_path, poppler_path=POPPLER_PATH)#conversion of pdf to image, pages will be a list of image objects
                    except Exception as e:
                        print(f"Error converting PDF to image: {e}")
                        return None,[]
                    for page_number, page_image in enumerate(pages): #after conversion, we'll get a list of image object, we'll send them to image_extractor using for loop on list
                        print(f"Running OCR on page {page_number+1}...")

                        page_text,link=img_extract(page_image)

                        if page_text:
                            text+=page_text+"\n"
        return text,hidden_links
    
    except Exception as err:
        print(f"Error:{err}")
        return None,[]

