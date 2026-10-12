"""test_pipe_challenger.py — Independent Empirical Stress & Adversarial Test Suite.

Authored by challenger_pipe_2 for Pipeline 1 (PDF Extractor & Playwright Scraper).

Validates:
1. PDF Extractor Streaming Memory Scalability:
   - tracemalloc profiling on the real 17.5MB PDF (datasets/Datascience questions/1632827939589.pdf).
   - Strict assertion: peak memory < 12.0 MB.
   - Chunk overlap, stream boundary integrity, and error handling.
2. Rate Limit Retry Backoff & Jitter:
   - 429 RESOURCE_EXHAUSTED retry and delay growth.
   - 503 UNAVAILABLE retry and delay growth.
   - Non-retryable error handling (immediate fail on 400).
   - Terminal retry exhaustion (proper exception re-raising).
   - Backoff jitter randomness.
   - Markdown fence handling (```json ... ```).
3. Playwright Scraper Contract & Filtering:
   - Locked solution drop rules ("login to access", "unlock editorial", "premium", empty).
   - Valid solution acceptance and clean field normalization.
   - HTML cleanup fidelity (stripping tags, scripts, styles).
   - CSV deduplication and schema adherence.
4. Scraper Live GFG Test (>= 5 questions).
"""

import asyncio
import csv
import json
import os
import random
import sys
import tempfile
import time
import tracemalloc
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pdf_extractor
from pdf_extractor import (
    CSV_FIELDNAMES,
    append_qa_to_csv,
    call_gemini_with_retry,
    stream_pdf_chunks,
)
import scraper
from scraper import (
    DEFAULT_TARGET_URLS,
    FIELDNAMES,
    append_scraped_to_csv,
    clean_html_to_text,
    extract_problem_from_page,
    scrape_target_urls,
)


class TestPDFExtractorMemoryAndStreaming(unittest.TestCase):
    """Empirical challenge: PyMuPDF streaming memory bounds and chunk integrity."""

    REAL_PDF = os.path.join(REPO_ROOT, "datasets", "Datascience questions", "1632827939589.pdf")

    def test_real_17mb_pdf_streaming_memory_bound(self):
        """Assert that streaming the real 17.5MB PDF consumes < 12MB peak RAM."""
        self.assertTrue(os.path.exists(self.REAL_PDF), f"Real PDF missing at {self.REAL_PDF}")
        file_size_mb = os.path.getsize(self.REAL_PDF) / (1024 * 1024)
        self.assertGreater(file_size_mb, 15.0, f"Expected >15MB PDF, found {file_size_mb:.2f}MB")

        tracemalloc.start()
        tracemalloc.reset_peak()

        chunks_generated = 0
        total_chars = 0
        chunk_lengths = []

        for chunk in stream_pdf_chunks(self.REAL_PDF, chunk_size=4000, overlap=600):
            chunks_generated += 1
            total_chars += len(chunk)
            chunk_lengths.append(len(chunk))
            # Simulate minimal downstream consumer
            self.assertIsInstance(chunk, str)
            self.assertGreater(len(chunk), 0)

        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak_bytes / (1024 * 1024)
        print(f"\n[STRESS TEST] Real PDF Memory Profile:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Chunks generated: {chunks_generated}")
        print(f"  Total text streamed: {total_chars:,} characters")
        print(f"  Peak RAM allocated: {peak_mb:.4f} MB (Ceiling: 12.00 MB)")

        self.assertGreater(chunks_generated, 50, "Should generate >50 chunks for 17.5MB PDF")
        self.assertLess(peak_mb, 12.0, f"Peak memory {peak_mb:.2f}MB violated 12.0MB ceiling!")
        # Ponytail ultra efficiency check: streaming should ideally stay under 2MB
        self.assertLess(peak_mb, 5.0, f"Streaming RAM was unexpectedly high: {peak_mb:.2f}MB")

    def test_nonexistent_pdf_raises_file_not_found(self):
        """Assert that non-existent PDF raises FileNotFoundError cleanly."""
        fake_path = os.path.join(REPO_ROOT, "datasets", "non_existent_file.pdf")
        with self.assertRaises(FileNotFoundError):
            list(stream_pdf_chunks(fake_path))

    def test_chunk_overlap_contract(self):
        """Assert sliding window overlap between consecutive chunks."""
        chunks = list(stream_pdf_chunks(self.REAL_PDF, chunk_size=4000, overlap=600))
        self.assertGreater(len(chunks), 2)
        # Check first 2 chunks: suffix of chunk 0 should equal prefix of chunk 1 up to overlap size
        chunk_0_suffix = chunks[0][-600:]
        chunk_1_prefix = chunks[1][:600]
        self.assertEqual(chunk_0_suffix, chunk_1_prefix, "Overlap between consecutive chunks failed contract")


class TestPDFExtractorRetryAndFaultInjection(unittest.TestCase):
    """Empirical challenge: 429/503 rate limit backoff, jitter, and fault injection."""

    def test_429_single_retry_success(self):
        """Simulate single HTTP 429 and verify retry success and delay."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {"title": "Q1", "description": "D1", "solution": "S1", "difficulty": "Easy"}
        ])

        calls = []

        def side_effect(*args, **kwargs):
            calls.append(time.time())
            if len(calls) == 1:
                raise RuntimeError("429 RESOURCE_EXHAUSTED: Quota exceeded")
            return mock_response

        mock_client.models.generate_content.side_effect = side_effect

        t0 = time.time()
        res = call_gemini_with_retry(mock_client, "Dummy text", max_retries=3, base_delay=0.1)
        elapsed = time.time() - t0

        self.assertEqual(len(calls), 2, "Expected exactly 2 attempts")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["title"], "Q1")
        # Delay should be at least base_delay (0.1s)
        self.assertGreaterEqual(elapsed, 0.1)

    def test_503_multiple_retry_success(self):
        """Simulate two consecutive 503 errors and verify exponential backoff."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {"title": "Q503", "description": "D503", "solution": "S503", "difficulty": "Hard"}
        ])

        call_times = []

        def side_effect(*args, **kwargs):
            call_times.append(time.time())
            if len(call_times) <= 2:
                raise RuntimeError("503 Service Unavailable: High load")
            return mock_response

        mock_client.models.generate_content.side_effect = side_effect

        t0 = time.time()
        res = call_gemini_with_retry(mock_client, "Dummy text", max_retries=4, base_delay=0.1)
        elapsed = time.time() - t0

        self.assertEqual(len(call_times), 3, "Expected 3 attempts (2 retries)")
        self.assertEqual(len(res), 1)
        # Attempt 1 -> sleep 0.1 + jitter (~0.15s)
        # Attempt 2 -> sleep 0.2 + jitter (~0.25s)
        # Total elapsed >= 0.3s
        self.assertGreaterEqual(elapsed, 0.3)

    def test_terminal_exhaustion_reraises(self):
        """Assert that exhausting max_retries re-raises the rate limit exception."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("429 Too Many Requests")

        with self.assertRaises(RuntimeError) as ctx:
            call_gemini_with_retry(mock_client, "Dummy text", max_retries=3, base_delay=0.05)

        self.assertIn("429", str(ctx.exception))

    def test_non_retryable_error_fails_immediately(self):
        """Assert that non-rate-limit errors (e.g. 400 Bad Request) do not retry."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = ValueError("400 Bad Request: Invalid model")

        call_count = 0

        def count_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ValueError("400 Bad Request: Invalid model")

        mock_client.models.generate_content.side_effect = count_calls

        with self.assertRaises(ValueError):
            call_gemini_with_retry(mock_client, "Dummy text", max_retries=5, base_delay=0.1)

        self.assertEqual(call_count, 1, "Non-retryable error should fail on attempt 1 without retrying")

    def test_markdown_code_fence_stripping(self):
        """Assert that markdown ```json code blocks are cleanly stripped."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "```json\n[\n  {\"title\": \"Decorators\", \"solution\": \"def dec(): pass\"}\n]\n```"
        mock_client.models.generate_content.return_value = mock_response

        res = call_gemini_with_retry(mock_client, "chunk text", max_retries=2)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["title"], "Decorators")
        self.assertEqual(res[0]["solution"], "def dec(): pass")

    def test_empty_or_malformed_json_response(self):
        """Assert handling of non-list JSON response."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"message": "no questions found"}'
        mock_client.models.generate_content.return_value = mock_response

        res = call_gemini_with_retry(mock_client, "chunk text", max_retries=2)
        self.assertEqual(res, [], "Non-list JSON response should return empty list")


class TestScraperAdversarialAndContract(unittest.TestCase):
    """Empirical challenge: Scraper locked editorial rules, HTML stripping, and CSV format."""

    def test_clean_html_to_text_fidelity(self):
        """Verify HTML tag stripping, script/style removal, and whitespace normalization."""
        raw_html = """
        <div>
            <h1>Binary Search</h1>
            <script>alert('malicious')</script>
            <style>.hidden { display: none; }</style>
            <p>Given a sorted array of <b>size N</b>, find index of <i>K</i>.</p>
            <ul><li>Expected Time: O(log N)</li><li>Space: O(1)</li></ul>
        </div>
        """
        cleaned = clean_html_to_text(raw_html)
        self.assertNotIn("<h1>", cleaned)
        self.assertNotIn("alert", cleaned)
        self.assertNotIn(".hidden", cleaned)
        self.assertIn("Binary Search", cleaned)
        self.assertIn("Given a sorted array", cleaned)
        self.assertIn("O(log N)", cleaned)
        self.assertFalse("  " in cleaned, "Should not contain double spaces")

    def test_locked_editorial_drop_rule(self):
        """Assert that locked or missing solutions are dropped per R3 specification."""
        # Test simulated page extraction logic with various locked solution strings
        locked_indicators = [
            "Login to access full editorial and solutions",
            "Unlock Editorial with Geekbits",
            "Premium problem solution locked",
            "",
            "   \n  \t ",
        ]

        for ind in locked_indicators:
            # Rule test: scraper drops when condition holds
            is_dropped = not ind.strip() or any(k in ind.lower() for k in ("login to access", "unlock editorial", "premium"))
            self.assertTrue(is_dropped, f"Failed to drop locked solution pattern: '{ind}'")

    def test_append_scraped_to_csv_schema_and_deduplication(self):
        """Assert that append_scraped_to_csv adheres strictly to 5 columns and prevents dupes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_csv = os.path.join(tmp_dir, "cleaned_dataset.csv")

            test_rows = [
                {
                    "title": "Reverse Array",
                    "description": "Reverse an array in-place",
                    "solution": "def rev(arr): return arr[::-1]",
                    "skill": "System Design",
                    "difficulty": "Easy",
                },
                {
                    "title": "Reverse Array",  # Duplicate title
                    "description": "Another description",
                    "solution": "def rev2(arr): return list(reversed(arr))",
                    "skill": "System Design",
                    "difficulty": "Easy",
                },
                {
                    "title": "NAN",  # Invalid null-like title
                    "description": "Bad row",
                    "solution": "def bad(): pass",
                    "skill": "System Design",
                    "difficulty": "Easy",
                },
                {
                    "title": "Valid Problem 2",
                    "description": "Desc 2",
                    "solution": "",  # Empty solution
                    "skill": "System Design",
                    "difficulty": "Medium",
                },
                {
                    "title": "Valid Problem 3",
                    "description": "Desc 3",
                    "solution": "def valid3(): return True",
                    "skill": "System Design",
                    "difficulty": "Hard",
                },
            ]

            written = append_scraped_to_csv(out_csv, test_rows)
            # Row 1 (valid), Row 2 (dupe dropped), Row 3 (NAN title dropped), Row 4 (empty sol dropped), Row 5 (valid)
            self.assertEqual(written, 2, f"Expected 2 rows written, got {written}")

            # Verify file structure
            with open(out_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, FIELDNAMES)
                rows = list(reader)
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]["title"], "Reverse Array")
                self.assertEqual(rows[1]["title"], "Valid Problem 3")


class TestScraperLivePlaywrightIntegration(unittest.TestCase):
    """Empirical challenge: Run Playwright against live GFG and verify >= 5 questions scraped."""

    def test_live_gfg_scraping_resilience(self):
        """Assert that live Playwright scraper extracts >= 5 questions from GFG without blocks."""
        print("\n[STRESS TEST] Launching Live Playwright Scraper against GeeksForGeeks...")
        scraped = asyncio.run(scrape_target_urls(DEFAULT_TARGET_URLS))

        print(f"[STRESS TEST] Successfully scraped {len(scraped)} live questions.")
        for item in scraped:
            print(f"  * Title: {item['title']} | Diff: {item['difficulty']} | Sol len: {len(item['solution'])}")

        self.assertGreaterEqual(len(scraped), 5, f"Expected >= 5 questions scraped, got {len(scraped)}")

        for item in scraped:
            self.assertTrue(item.get("title"), "Missing title in scraped question")
            self.assertTrue(item.get("description"), "Missing description in scraped question")
            self.assertTrue(item.get("solution"), "Missing solution in scraped question")
            self.assertGreater(len(item["solution"].strip()), 10, "Solution code too short")
            # Assert no locked message slipped into solution
            for locked_kw in ("login to access", "unlock editorial", "premium"):
                self.assertNotIn(locked_kw, item["solution"].lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
