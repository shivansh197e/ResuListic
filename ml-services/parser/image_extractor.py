import pytesseract
from PIL import Image, ImageEnhance
import os

pytesseract.pytesseract.tesseract_cmd = os.environ.get(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def img_extract(file_input):
    """
    Extracts text from an image using OCR (Tesseract).
    Accepts either a file path (str) or a PIL Image object.
    Returns: (text: str, links: list) — links is always [] since OCR can't detect hyperlinks.
    On failure: (None, [])
    """
    original_img = None  
    text = ""
    try:
        if isinstance(file_input, str):
            img = Image.open(file_input)
            original_img = img  
        else:
            img = file_input  

        processed = img.convert('L')

        MIN_WIDTH = 1500
        if processed.width < MIN_WIDTH:
            scale = min(2, MIN_WIDTH / processed.width)
            new_w = int(processed.width * scale)
            new_h = int(processed.height * scale)
            processed = processed.resize((new_w, new_h), Image.Resampling.LANCZOS)

        enhancer = ImageEnhance.Contrast(processed)
        processed = enhancer.enhance(2.5)

        text = pytesseract.image_to_string(processed)

        processed.close()
        if original_img is not None:
            original_img.close()

        return text, []

    except Exception as err:
        print(f"OCR Error in img_extract: {err}")
        if original_img is not None:
            try:
                original_img.close()
            except Exception:
                pass
        return None, []