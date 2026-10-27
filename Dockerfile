# ═══════════════════════════════════════════════════════════════
# ResuListic — Full-Stack AI & OCR Dockerfile
# Includes: Python 3.12, Tesseract OCR, Poppler Utils, spaCy NLP
# ═══════════════════════════════════════════════════════════════
FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

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

# Serve the compiled React application through FastAPI's existing static mount.
RUN rm -rf /app/static/*
COPY --from=frontend-build /frontend/build/ /app/static/

# Create temporary upload directory
RUN mkdir -p /app/temp_uploads

EXPOSE 8000

# 4. Launch FastAPI server (uses $PORT injected by Render/Railway/Cloud Run, or defaults to 8000)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
