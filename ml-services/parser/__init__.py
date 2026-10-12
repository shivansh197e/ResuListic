# This file makes the parser folder a Python module.

from .pdf_extractor import pdf_extract
from .docx_extractor import docx_extract
from .image_extractor import img_extract
from .text_extractor import extract_text

__all__ = ["pdf_extract", "docx_extract", "img_extract", "extract_text"]
