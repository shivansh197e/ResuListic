"""Stealth Playwright Web Scraper for GeeksForGeeks.

Scrapes interview coding questions and solutions using headless Chromium with
stealth techniques (custom UA, viewport jitter, random delays, webdriver masking).
Extracts Next.js __NEXT_DATA__ and public article solutions.
Drops locked or missing solutions.
Appends validated records to cleaned_dataset.csv.
"""

import argparse
import asyncio
import csv
import json
import os
import random
import re
import sys
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext, async_playwright

FIELDNAMES = ["title", "description", "solution", "skill", "difficulty"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

DEFAULT_TARGET_URLS = [
    ("https://www.geeksforgeeks.org/problems/reverse-a-string/1", "System Design"),
    ("https://www.geeksforgeeks.org/problems/largest-element-in-array4009/1", "System Design"),
    ("https://www.geeksforgeeks.org/problems/missing-number-in-array1416/1", "System Design"),
    ("https://www.geeksforgeeks.org/problems/sort-an-array-of-0s-1s-and-2s4231/1", "System Design"),
    ("https://www.geeksforgeeks.org/problems/palindrome-string0817/1", "System Design"),
]


async def create_stealth_context(browser) -> BrowserContext:
    """Creates a browser context with stealth headers, randomized viewport, and webdriver mask."""
    ua = random.choice(USER_AGENTS)
    width = random.randint(1280, 1440)
    height = random.randint(800, 960)

    context = await browser.new_context(
        user_agent=ua,
        viewport={"width": width, "height": height},
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9", "DNT": "1"},
    )
    # Mask navigator.webdriver
    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return context


def clean_html_to_text(raw_html: str) -> str:
    """Converts HTML to clean, readable plain text without tags."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    # Remove script and style tags
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def extract_problem_from_page(page, url: str, default_skill: str = "System Design") -> Optional[Dict[str, str]]:
    """Loads a GFG problem page and extracts metadata and public solution."""
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(0.8, 1.5))

    # Extract Next.js __NEXT_DATA__
    next_data_json = await page.evaluate("""() => {
        const el = document.getElementById('__NEXT_DATA__');
        return el ? JSON.parse(el.innerText) : null;
    }""")

    prob_data = None
    if next_data_json:
        try:
            prob_data = next_data_json["props"]["pageProps"]["initialState"]["problemData"]["allData"]["probData"]
        except (KeyError, TypeError):
            prob_data = None

    if prob_data:
        title = (prob_data.get("problem_name") or "").strip()
        difficulty = (prob_data.get("problem_level_text") or prob_data.get("difficulty") or "Medium").strip()
        raw_question = prob_data.get("problem_question") or ""
        description = clean_html_to_text(raw_question) or title
        article_list = prob_data.get("article_list") or []
    else:
        # Fallback to DOM extraction
        title_elem = await page.query_selector("h1, .problems_header_content__title__title, .problem-title")
        title = (await title_elem.inner_text()).strip() if title_elem else (await page.title()).strip()
        body_elem = await page.query_selector("#problem-statement, .problems_problem_content__X, .problemDescription")
        raw_question = await body_elem.inner_html() if body_elem else ""
        description = clean_html_to_text(raw_question) or title
        difficulty = "Medium"
        article_list = []

    if not title:
        return None

    # Resolve solution code from public tutorial articles
    solution_code = ""
    for article_url in article_list[:2]:
        try:
            art_page = await page.context.new_page()
            await art_page.goto(article_url, wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(random.uniform(0.5, 1.0))

            # Look for code block in pre tags
            pre_elems = await art_page.query_selector_all("pre, .code-container pre, code")
            for pre in pre_elems:
                code_text = (await pre.inner_text()).strip()
                # Check for substantive code
                if len(code_text.split("\n")) >= 3 and any(kw in code_text for kw in ("def ", "class ", "int ", "public ", "void ", "return ")):
                    solution_code = code_text
                    break
            await art_page.close()
            if solution_code:
                break
        except Exception:
            try:
                await art_page.close()
            except Exception:
                pass

    # If no article solution, check if code is directly on page
    if not solution_code:
        page_pres = await page.query_selector_all("pre, code")
        for pre in page_pres:
            code_text = (await pre.inner_text()).strip()
            if len(code_text.split("\n")) >= 3:
                solution_code = code_text
                break

    # If solution is locked or missing, drop the problem row
    if not solution_code or any(k in solution_code.lower() for k in ("login to access", "unlock editorial", "premium")):
        print(f"[scraper] Dropping '{title}': solution is missing or locked.")
        return None

    return {
        "title": title,
        "description": description,
        "solution": solution_code,
        "skill": default_skill,
        "difficulty": difficulty if difficulty else "Medium",
    }


def append_scraped_to_csv(csv_path: str, rows: List[Dict[str, str]]) -> int:
    """Appends scraped Q&A rows to destination cleaned_dataset.csv, avoiding duplicates."""
    if not rows:
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
    file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    existing_titles = set()
    if file_exists:
        try:
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    if r.get("title"):
                        existing_titles.add(r["title"].strip().lower())
        except Exception:
            pass

    written = 0
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, quoting=csv.QUOTE_MINIMAL)
        if not file_exists:
            writer.writeheader()
        for r in rows:
            t = (r.get("title") or "").strip()
            s = (r.get("solution") or "").strip()
            if t and s and t.lower() not in ("nan", "null", "none") and s.lower() not in ("nan", "null", "none"):
                if t.lower() not in existing_titles:
                    writer.writerow({
                        "title": t,
                        "description": (r.get("description") or t).strip(),
                        "solution": s,
                        "skill": (r.get("skill") or "System Design").strip(),
                        "difficulty": (r.get("difficulty") or "Medium").strip(),
                    })
                    existing_titles.add(t.lower())
                    written += 1
    return written


async def scrape_target_urls(urls_and_skills: List[tuple[str, str]]) -> List[Dict[str, str]]:
    """Runs Playwright stealth scraper across target URLs."""
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await create_stealth_context(browser)
        page = await context.new_page()

        for url, skill in urls_and_skills:
            try:
                print(f"[scraper] Fetching {url}...")
                data = await extract_problem_from_page(page, url, default_skill=skill)
                if data:
                    print(f"  -> Extracted: {data['title']} ({data['difficulty']})")
                    results.append(data)
            except Exception as exc:
                print(f"[scraper] Warning: failed scraping {url}: {exc}", file=sys.stderr)

        await browser.close()
    return results


async def test_live_scraping(
    target_csv: str = "datasets/System design Question/cleaned_dataset.csv",
    min_questions: int = 5,
) -> List[Dict[str, str]]:
    """Live integration test: scrapes >= 5 questions without being blocked."""
    print(f"[TEST] Running test_live_scraping() for >= {min_questions} questions...")
    scraped = await scrape_target_urls(DEFAULT_TARGET_URLS)

    assert len(scraped) >= min_questions, (
        f"Expected to scrape >= {min_questions} questions, successfully scraped {len(scraped)}"
    )

    for item in scraped:
        assert item.get("title"), "Scraped item missing title"
        assert item.get("solution"), "Scraped item missing solution"
        assert item.get("description"), "Scraped item missing description"
        assert item.get("skill"), "Scraped item missing skill"

    # Append to target CSV
    written = append_scraped_to_csv(target_csv, scraped)
    print(f"       PASSED: Successfully scraped {len(scraped)} live questions, wrote {written} rows to {target_csv}.")
    return scraped


def main() -> None:
    parser = argparse.ArgumentParser(description="Stealth Playwright Web Scraper for GFG")
    parser.add_argument("--test", action="store_true", help="Run live integration test for >=5 questions")
    parser.add_argument("--output", default="datasets/System design Question/cleaned_dataset.csv", help="Output CSV path")
    args = parser.parse_args()

    if args.test:
        asyncio.run(test_live_scraping(args.output))
        sys.exit(0)

    scraped = asyncio.run(scrape_target_urls(DEFAULT_TARGET_URLS))
    written = append_scraped_to_csv(args.output, scraped)
    print(f"[scraper] Complete! Scraped {len(scraped)} questions, written {written} to {args.output}")


if __name__ == "__main__":
    main()
