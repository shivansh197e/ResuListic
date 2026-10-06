"""LLM-Powered Streaming PDF Extractor.

Extracts interview questions and answers from multi-megabyte PDFs using
PyMuPDF page streaming (O(1) RAM footprint) and Google GenAI with
exponential backoff retry for HTTP 429/503.
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
import tracemalloc
from typing import Any, Dict, Iterator, List, Optional
from unittest.mock import MagicMock

import pymupdf as fitz
from dotenv import load_dotenv

load_dotenv()

CSV_FIELDNAMES = ["title", "description", "solution", "skill", "difficulty"]


def stream_pdf_chunks(
    pdf_path: str,
    chunk_size: int = 4000,
    overlap: int = 600,
) -> Iterator[str]:
    """Streams text page-by-page from PDF, maintaining O(1) RAM via sliding window."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    buffer = ""
    try:
        for page in doc:
            text = page.get_text() or ""
            if not text.strip():
                continue
            buffer += "\n" + text
            while len(buffer) >= chunk_size:
                yield buffer[:chunk_size]
                buffer = buffer[chunk_size - overlap :]
        if buffer.strip():
            yield buffer
    finally:
        doc.close()


def call_gemini_with_retry(
    client: Any,
    text_chunk: str,
    model: str = "gemini-flash-latest",
    max_retries: int = 5,
    base_delay: float = 0.5,
) -> List[Dict[str, str]]:
    """Calls Gemini API to extract structured Q&A pairs with exponential backoff on 429/503."""
    prompt = (
        "Extract all technical interview questions and answers from this text.\n"
        "Return ONLY a JSON array of objects. Each object must have keys:\n"
        "- title: concise question name\n"
        "- description: full question setup/premise\n"
        "- solution: detailed answer or code\n"
        "- difficulty: Easy, Medium, or Hard\n"
        "If no technical questions exist in the text, return [].\n\n"
        f"Text:\n{text_chunk}"
    )

    delay = base_delay
    for attempt in range(max_retries):
        try:
            # Check if using real client or mock
            if hasattr(client, "models") and hasattr(client.models, "generate_content"):
                from google.genai import types

                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )
            else:
                response = client.generate_content(prompt)

            raw_text = (getattr(response, "text", "") or "").strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", raw_text).strip()

            parsed = json.loads(raw_text)
            if isinstance(parsed, list):
                valid = []
                for item in parsed:
                    if isinstance(item, dict) and item.get("title") and item.get("solution"):
                        valid.append({
                            "title": str(item["title"]).strip(),
                            "description": str(item.get("description") or item["title"]).strip(),
                            "solution": str(item["solution"]).strip(),
                            "difficulty": str(item.get("difficulty") or "Medium").strip(),
                        })
                return valid
            return []
        except Exception as exc:
            err_msg = str(exc).lower()
            is_rate_limit = any(k in err_msg for k in ("429", "503", "resource_exhausted", "unavailable", "rate limit"))
            if is_rate_limit and attempt < max_retries - 1:
                jitter = random.uniform(0.05, 0.2)
                time.sleep(delay + jitter)
                delay *= 2.0
                continue
            raise


def append_qa_to_csv(
    csv_path: str,
    qa_pairs: List[Dict[str, str]],
    skill: str = "Data Science",
) -> int:
    """Appends validated Q&A pairs to target cleaned_dataset.csv."""
    if not qa_pairs:
        return 0

    file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    written = 0

    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, quoting=csv.QUOTE_MINIMAL)
        if not file_exists:
            writer.writeheader()

        for qa in qa_pairs:
            t = (qa.get("title") or "").strip()
            s = (qa.get("solution") or "").strip()
            if t and s and t.lower() not in ("nan", "null", "none") and s.lower() not in ("nan", "null", "none"):
                writer.writerow({
                    "title": t,
                    "description": (qa.get("description") or t).strip(),
                    "solution": s,
                    "skill": skill,
                    "difficulty": (qa.get("difficulty") or "Medium").strip(),
                })
                written += 1
    return written


def test_mock_pdf_extraction_and_retry() -> bool:
    """Hermetic unit test: verifies structured JSON extraction & 429 retry logic."""
    print("[TEST] Running test_mock_pdf_extraction_and_retry()...")

    mock_chunk = (
        "Question: Explain Bias-Variance Tradeoff.\n"
        "Answer: Bias is error due to overly simplistic assumptions in the model. "
        "Variance is error due to too much complexity in the learning algorithm."
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps([
        {
            "title": "Explain Bias-Variance Tradeoff",
            "description": "What is bias and variance in machine learning?",
            "solution": "Bias is error due to overly simplistic assumptions. Variance is error due to model complexity.",
            "difficulty": "Medium",
        }
    ])

    call_count = 0

    def mock_generate_content(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED: Rate limit exceeded")
        return mock_response

    mock_client.models.generate_content.side_effect = mock_generate_content

    start_time = time.time()
    results = call_gemini_with_retry(
        mock_client,
        mock_chunk,
        max_retries=3,
        base_delay=0.1,
    )
    elapsed = time.time() - start_time

    assert call_count == 2, f"Expected 2 attempts (1 retry), got {call_count}"
    assert len(results) == 1, f"Expected 1 extracted question, got {len(results)}"
    assert results[0]["title"] == "Explain Bias-Variance Tradeoff"
    assert "Bias is error" in results[0]["solution"]
    assert elapsed >= 0.1, "Exponential backoff delay was not applied"

    print("       PASSED: 429 retry triggered and structured JSON extracted successfully.")
    return True


def test_streaming_memory_footprint(
    pdf_path: str = "datasets/Datascience questions/1632827939589.pdf",
    max_peak_mb: float = 12.0,
) -> float:
    """Profiles memory usage during streaming chunk generation to assert O(1) RAM."""
    print(f"[TEST] Running test_streaming_memory_footprint() on {pdf_path}...")
    if not os.path.exists(pdf_path):
        # Look in workspace root
        for candidate in [
            os.path.join("datasets", "Datascience questions", "1632827939589.pdf"),
            os.path.join("..", "datasets", "Datascience questions", "1632827939589.pdf"),
        ]:
            if os.path.exists(candidate):
                pdf_path = candidate
                break

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Target PDF not found for profiling: {pdf_path}")

    tracemalloc.start()
    chunk_count = 0
    total_chars = 0

    # Stream through chunks and measure memory
    for chunk in stream_pdf_chunks(pdf_path, chunk_size=4000, overlap=600):
        chunk_count += 1
        total_chars += len(chunk)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak / (1024 * 1024)
    print(
        f"       Chunks generated: {chunk_count}, Total chars: {total_chars:,}, "
        f"Peak memory: {peak_mb:.2f} MB (Limit: {max_peak_mb:.2f} MB)"
    )

    assert chunk_count > 0, "No chunks generated from PDF"
    assert peak_mb < max_peak_mb, (
        f"Peak memory {peak_mb:.2f} MB exceeded O(1) bound of {max_peak_mb:.2f} MB"
    )
    print("       PASSED: Memory footprint strictly bounded within O(1) limit.")
    return peak_mb


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-Powered Streaming PDF Extractor")
    parser.add_argument("--test", action="store_true", help="Run hermetic unit tests and memory profiling")
    parser.add_argument("--pdf", default="datasets/Datascience questions/1632827939589.pdf", help="Path to PDF")
    parser.add_argument("--output", default="datasets/Datascience questions/cleaned_dataset.csv", help="Output CSV")
    parser.add_argument("--limit", type=int, default=3, help="Max chunks to extract via LLM")
    args = parser.parse_args()

    if args.test:
        test_mock_pdf_extraction_and_retry()
        test_streaming_memory_footprint(args.pdf)
        print("All PDF Extractor tests passed successfully.")
        sys.exit(0)

    # Real extraction execution if API key is present
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[pdf_extractor] GEMINI_API_KEY not configured. Running in test mode.")
        test_mock_pdf_extraction_and_retry()
        test_streaming_memory_footprint(args.pdf)
        sys.exit(0)

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        print(f"[pdf_extractor] Extracting Q&A from {args.pdf}...")
        extracted_total = 0
        for idx, chunk in enumerate(stream_pdf_chunks(args.pdf)):
            if idx >= args.limit:
                break
            print(f"  Processing chunk {idx + 1}/{args.limit} ({len(chunk)} chars)...")
            qa_list = call_gemini_with_retry(client, chunk)
            written = append_qa_to_csv(args.output, qa_list, skill="Data Science")
            extracted_total += written
            print(f"  Chunk {idx + 1}: extracted {len(qa_list)} Q&A pairs, wrote {written} to {args.output}")

        print(f"[pdf_extractor] Completed! Total extracted and appended: {extracted_total} rows.")
    except Exception as exc:
        print(f"[pdf_extractor] Error during extraction: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
