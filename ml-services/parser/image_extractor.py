import base64
import io
import os
import shutil
import pytesseract
from PIL import Image, ImageEnhance

_tesseract_cmd = os.environ.get("TESSERACT_CMD")
if _tesseract_cmd and os.path.exists(_tesseract_cmd):
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd
elif not shutil.which("tesseract"):
    for _candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ):
        if os.path.exists(_candidate):
            pytesseract.pytesseract.tesseract_cmd = _candidate
            break


_rapid_ocr_engine = None


def _rapidocr_fallback(img: Image.Image) -> str:
    """Pure-Python ONNX OCR fallback (requires no external Windows Tesseract binary)."""
    global _rapid_ocr_engine
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        if _rapid_ocr_engine is None:
            _rapid_ocr_engine = RapidOCR()
        rgb_arr = np.array(img.convert("RGB"))
        result, _ = _rapid_ocr_engine(rgb_arr)
        if result:
            lines = [item[1] for item in result if len(item) >= 2 and item[1]]
            return "\n".join(lines).strip()
    except Exception as e:
        print(f"[WARN] RapidOCR fallback failed: {e}")
    return ""


def _vision_ocr_fallback(img: Image.Image) -> str:
    """Fallback OCR via Groq Vision when native Tesseract binary is missing."""
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        return ""
    try:
        from groq import Groq
        buf = io.BytesIO()
        rgb_img = img.convert("RGB")
        rgb_img.save(buf, format="JPEG", quality=85)
        b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")
        client = Groq(api_key=groq_key)
        for model_name in (
            "llama-3.2-11b-vision-preview",
            "llama-3.2-90b-vision-preview",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-4-maverick-17b-128e-instruct",
        ):
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "Extract all text verbatim from this resume image. "
                                        "Preserve section headings (e.g. SKILLS, PROJECTS, EXPERIENCE, EDUCATION) "
                                        "on their own lines. Output ONLY the extracted resume text."
                                    ),
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"},
                                },
                            ],
                        }
                    ],
                    temperature=0.0,
                    max_tokens=2048,
                )
                extracted = resp.choices[0].message.content
                if extracted and len(extracted.strip()) > 20:
                    return extracted.strip()
            except Exception:
                continue
    except Exception as e:
        print(f"[WARN] Vision OCR fallback failed: {e}")
    return ""


def img_extract(file_input):
    """
    Extracts text from an image using OCR (Tesseract, with Vision LLM fallback).
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

        try:
            text = pytesseract.image_to_string(processed)
        except Exception as tess_err:
            print(f"[WARN] Local Tesseract unavailable ({tess_err}), using RapidOCR fallback...")
            text = _rapidocr_fallback(img)
            if not text:
                text = _vision_ocr_fallback(img)

        processed.close()
        if original_img is not None:
            original_img.close()

        if not text or not text.strip():
            return None, []
        return text, []

    except Exception as err:
        print(f"OCR Error in img_extract: {err}")
        if original_img is not None:
            try:
                original_img.close()
            except Exception:
                pass
        return None, []