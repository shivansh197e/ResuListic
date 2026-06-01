import pdfplumber
from pdf2image import convert_from_path
from image_extractor import img_extract
from pdf_extractor import pdf_extract
from docx_extractor import docx_extract

POPPLER_PATH=r"C:\poppler-26.02.0\Library\bin"

def extract_text(file_path):
    
    try:
        text=""
        if file_path.lower().endswith('.png') or file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
            text+= img_extract(file_path)
        elif file_path.lower().endswith('.docx'):
            text+= docx_extract(file_path)
        elif file_path.lower().endswith('.pdf'):
            with pdfplumber.open(file_path) as pdf:
                page=pdf.pages[0]
                txt=page.extract_text()
                if txt and len(txt.strip())>10:
                    text+=pdf_extract(file_path)
                else:
                    try:
                        pages = convert_from_path(file_path, poppler_path=POPPLER_PATH)
                    except Exception as e:
                        print(f"Error converting PDF to image: {e}")
                        return None
                    for page_number, page_image in enumerate(pages):
                        print(f"Running OCR on page {page_number+1}...")

                        page_text=img_extract(page_image)

                        if page_text:
                            text+=page_text+"\n"
        return text
    
    except Exception as err:
        print(f"Error:{err}")
        return None

if __name__ == "__main__":
    print(extract_text(r"C:\Users\Asus\Downloads\resume_sample_student8ea47e04a8fe67e6b7acff0000376a3b.pdf"))
    print(extract_text(r"C:\Users\Asus\Downloads\clean-modern-resume-portfolio-cv-template\CV-Template-01.jpg"))
    print(extract_text(r"C:\onedrive files\OneDrive\Desktop\Moving Target Defense for Adversarial Robustness in Deep Learning Systems (AutoRecovered).docx"))