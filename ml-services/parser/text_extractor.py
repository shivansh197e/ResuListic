import os
import pdfplumber
from pdf2image import convert_from_path
from parser.image_extractor import img_extract
from parser.docx_extractor import docx_extract

POPPLER_PATH = os.environ.get("POPPLER_PATH")  # None = use system PATH

SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.pdf', '.docx')


def extract_text(file_path):
    """
    Master router: takes any supported resume file and extracts text + hidden links.
    Supports: PDF (text-based & scanned), DOCX, PNG, JPG, JPEG.
    Returns: (text: str, hidden_links: list[str])
    On failure: (None, [])
    """

    if not os.path.isfile(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return None, []
 
    if not file_path.lower().endswith(SUPPORTED_EXTENSIONS):
        print(f"[WARN] Unsupported file type: {file_path}")
        print(f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
        return None, []

    try:
        text = ""
        hidden_links = []
 
        if file_path.lower().endswith(('.png', '.jpg', '.jpeg')): #file is image type, hence send it to image_extractor.py
            extracted_text, link = img_extract(file_path)
            if extracted_text:
                text += extracted_text
            if link:  
                hidden_links.extend(link)
 
        elif file_path.lower().endswith('.docx'): #file is word document, send it to docx_extractor.py
            extracted_text, link = docx_extract(file_path)
            if extracted_text:
                text += extracted_text
            if link:
                hidden_links.extend(link)
 
        elif file_path.lower().endswith('.pdf'): #file is pdf type, first of all check if it is image only pdf or is text pdf
            text, hidden_links = _handle_pdf(file_path) # sent to _handle_pdf function for checking

        return text, hidden_links

    except Exception as err:
        print(f"Error in extract_text: {err}")
        return None, []


def _handle_pdf(file_path):
    """
    Handles PDF extraction with smart detection:
    Checks if the PDF is text-based or scanned (image-based) and routes accordingly.
    """
    text = ""
    hidden_links = []

    with pdfplumber.open(file_path) as pdf: 
        if not pdf.pages:
            print(f"[WARN] PDF has no pages: {file_path}")
            return "", []
 
        first_page_text = pdf.pages[0].extract_text()#check if there's any text in 1st page(i.e. in the page which is at idx 0)

        if first_page_text and len(first_page_text.strip()) > 10:
            
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

                
                if page.hyperlinks:
                    for link in page.hyperlinks:
                        if 'uri' in link:
                            hidden_links.append(link['uri'])
 
            hidden_links = list(dict.fromkeys(hidden_links))

        else:
            pages = []
            try:
                pages = convert_from_path(file_path, poppler_path=POPPLER_PATH)
            except Exception as e:
                print(f"[WARN] Poppler unavailable ({e}), falling back to PyMuPDF page rendering...")
                try:
                    import pymupdf as fitz
                    from PIL import Image
                    import io
                    doc = fitz.open(file_path)
                    for page in doc:
                        pix = page.get_pixmap(dpi=200)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        pages.append(img)
                    doc.close()
                except Exception as fitz_err:
                    print(f"[ERROR] converting PDF to image: {fitz_err}")
                    return "", []

            for page_number, page_image in enumerate(pages):
                print(f"Running OCR on page {page_number + 1}...")
                page_text, link = img_extract(page_image)
                if page_text:
                    text += page_text + "\n"
                if link:
                    hidden_links.extend(link)

    return text, hidden_links
