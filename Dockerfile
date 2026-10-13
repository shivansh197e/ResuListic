# ═══════════════════════════════════════════════════════════════
# ResuListic — Full-Stack AI & OCR Dockerfile
# Includes: Python 3.12, Tesseract OCR, Poppler Utils, spaCy NLP
# ═══════════════════════════════════════════════════════════════
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TESSERACT_CMD=/usr/bin/tesseract

# 1. Install system-level dependencies:
#    - tesseract-ocr & tesseract-ocr-eng: OCR engine for .png/.jpg/.jpeg resumes
#    - poppler-utils: PDF-to-image converter (pdftoppm/pdfinfo) for scanned PDFs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install Python dependencies first (cached Docker layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_md

# 3. Copy application code
COPY . .

# Create temporary upload directory
RUN mkdir -p /app/temp_uploads

EXPOSE 8000

# 4. Launch FastAPI server (serves both React SPA at / and API at /api/*)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
