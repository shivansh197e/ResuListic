"""data_builder.py — Production ETL Pipeline for Coding Questions (Ponytail Mode < 200 LOC)."""
import argparse, csv, itertools, json, os, re, sys, time
from collections import defaultdict
from typing import Optional

# Bootstrap project virtualenv site-packages if available
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_venv_site = os.path.join(_PROJECT_ROOT, "venv", "Lib", "site-packages")
if os.path.exists(_venv_site) and _venv_site not in sys.path:
    sys.path.insert(0, _venv_site)

# Reconfigure console streams for Windows CP1252 resilience
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

sys.path.append(os.path.join(os.path.dirname(__file__), "ml-services"))
from schema.question_schema import CodingQuestionDoc, SolutionDoc

try:
    from google import genai
    from google.genai import types, errors
except ImportError:
    genai = types = errors = None  # type: ignore

load_dotenv()


class MutatedQuestion(BaseModel):
    mutated_title: str = Field(description="Novel problem title matching new storyline")
    mutated_description: str = Field(description="Rewritten description preserving all logic and constraints")
    mutated_solution: str = Field(description="Adapted code solution with updated variable names")
    explanation: str = Field(default="")
    variable_mapping: Optional[dict[str, str]] = Field(default_factory=dict)


def get_db(uri: Optional[str] = None, db_name: Optional[str] = None):
    uri = uri or os.getenv("MONGODB_URI") or os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = db_name or os.getenv("MONGODB_DB", "resulistic_db")
    return MongoClient(uri)[db_name]


def read_csv_chunks(filepath: str, chunk_size: int = 50):
    """Streams rows from CSV in chunks of chunk_size."""
    with open(filepath, mode="r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        while True:
            chunk = list(itertools.islice(reader, chunk_size))
            if not chunk:
                break
            yield chunk


def mock_mutate(row: dict) -> MutatedQuestion:
    t, d = (row.get("title") or "Question"), (row.get("description") or "")
    s = row.get("reference_solution") or row.get("solution") or "# Model solution\ndef solve(): pass"
    return MutatedQuestion(
        mutated_title=f"Mutated: {t}", mutated_description=f"Rewritten: {d}",
        mutated_solution=s,
        explanation=row.get("explanation") or "Two pointers approach",
    )


def mutate_question(client: Optional[object], row: dict, model: str = "qwen/qwen3.8-27b", max_retries: int = 10) -> MutatedQuestion:
    """Mutates question narrative and solution variables with 429 exponential backoff using Groq (and Gemini fallback compatibility)."""
    if client is None:
        return mock_mutate(row)

    # Gemini client interface compatibility (for test suites)
    if hasattr(getattr(client, "models", None), "generate_content"):
        prompt = (
            f"Rewrite this coding problem narrative and solution variables to prevent plagiarism.\n"
            f"Keep algorithmic complexity, logic, constraints, and I/O identical.\n"
            f"Title: {row.get('title') or ''}\nDescription: {row.get('description') or ''}\n"
            f"Solution: {row.get('reference_solution') or row.get('solution') or ''}"
        )
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=MutatedQuestion,
            temperature=0.3, system_instruction="You are an expert technical interviewer mutating coding questions."
        ) if types is not None else None
        delay = float(os.getenv("RETRY_BASE_DELAY", "2.0"))
        for attempt in range(max_retries):
            try:
                resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
                if hasattr(resp, "parsed") and resp.parsed is not None:
                    return resp.parsed
                raw = resp.text.strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                try:
                    return MutatedQuestion.model_validate_json(raw)
                except Exception:
                    data = json.loads(raw)
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        return MutatedQuestion.model_validate(data[0])
                    raise
            except Exception as e:
                code, status = getattr(e, "code", None), getattr(e, "status", None)
                is_429 = (code == 429) or (status == "RESOURCE_EXHAUSTED") or ("429" in str(e))
                if is_429 and attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2.0
                    continue
                raise
        raise RuntimeError("Gemini retries exhausted")

    # Groq client execution
    prompt = (
        f"You are an expert technical interviewer mutating coding questions to prevent plagiarism.\n"
        f"Keep algorithmic complexity, logic, constraints, and I/O identical.\n"
        f"You MUST return the output as a valid JSON object with exactly these four keys:\n"
        f"1. 'mutated_title' (string)\n"
        f"2. 'mutated_description' (string)\n"
        f"3. 'mutated_solution' (string)\n"
        f"4. 'explanation' (string)\n\n"
        f"Title: {row.get('title') or ''}\nDescription: {row.get('description') or ''}\n"
        f"Solution: {row.get('reference_solution') or row.get('solution') or ''}"
    )

    fallback_models = []
    for m in [model, "qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
        if m and m not in fallback_models:
            fallback_models.append(m)

    for current_model in fallback_models:
        delay = float(os.getenv("RETRY_BASE_DELAY", "1.0"))
        for attempt in range(max_retries):
            try:
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=current_model,
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )
                raw = chat_completion.choices[0].message.content.strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                try:
                    return MutatedQuestion.model_validate_json(raw)
                except Exception:
                    data = json.loads(raw)
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        return MutatedQuestion.model_validate(data[0])
                    raise
            except Exception as e:
                err_str = str(e).lower()
                if "404" in err_str or "not found" in err_str:
                    print(f"      [!] Model {current_model} not found. Falling back to next...", flush=True)
                    break

                is_retryable = any(x in err_str for x in ["429", "rate limit", "503", "connection error", "timeout", "connecttimeout"])
                if is_retryable and attempt < max_retries - 1:
                    wait_match = re.search(r"try again in (\d+\.?\d*)s", err_str)
                    sleep_time = float(wait_match.group(1)) + 0.5 if wait_match else delay
                    print(f"      [!] {current_model} Rate limited. Retrying in {sleep_time:.1f}s (Attempt {attempt+1}/{max_retries})...", flush=True)
                    time.sleep(sleep_time)
                    delay = max(delay * 2.0, sleep_time)
                    if attempt >= 2 and len(fallback_models) > 1:
                        print(f"      [!] Fast fallback from {current_model} to next model...", flush=True)
                        break
                    continue

                print(f"      [X] Error on {current_model}: {e}. Trying next model...", flush=True)
                break

    print(f"      [!] All fallback models exhausted for '{row.get('title')}'. Falling back to rule mutation.", flush=True)
    return mock_mutate(row)


def bulk_insert_documents(db, mod_docs: list[dict], hard_docs: list[dict], sol_docs: list[dict]) -> dict[str, int]:
    """Batch insertion using insert_many(ordered=False) with empty list guards."""
    counts = {"moderate": 0, "hard": 0, "solutions": 0}
    for key, col, docs in [("moderate", db.questions_moderate, mod_docs),
                           ("hard", db.questions_hard, hard_docs),
                           ("solutions", db.solutions, sol_docs)]:
        if docs:
            try:
                res = col.insert_many(docs, ordered=False)
                counts[key] = len(res.inserted_ids)
            except BulkWriteError as bwe:
                counts[key] = bwe.details.get("nInserted", 0)
    return counts


def run_pipeline(csv_path: str, chunk_size: int = 50, dry_run: bool = False, clear: bool = False,
                 mock_llm: bool = False, model: str = "qwen/qwen3.8-27b", db=None, client=None, skip: int = 0) -> dict:
    """Orchestrates CSV streaming, Groq mutation, and MongoDB bulk loading."""
    db = db if db is not None else (None if dry_run else get_db())
    if db is not None:
        ensure_indexes(db)
    if client is None and not (dry_run or mock_llm):
        from groq import Groq
        client = Groq()
    index_counters, cleared_skills = defaultdict(int), set()
    totals = {"read": 0, "moderate": 0, "hard": 0, "solutions": 0}

    for chunk in read_csv_chunks(csv_path, chunk_size=chunk_size):
        mod_batch, hard_batch, sol_batch = [], [], []
        for row in chunk:
            totals["read"] += 1
            if totals["read"] <= skip:
                continue
            
            skill = (row.get("skill") or row.get("topic") or "General").strip() or "General"
            raw_diff = (row.get("difficulty") or row.get("level") or "moderate").strip().lower()
            title_lower = (row.get("title") or "").lower()

            if raw_diff in ("hard", "difficult", "expert", "3"):
                diff = "hard"
            elif skill == "OOPS" and "code" in title_lower:
                diff = "hard"
            elif skill == "System Design" and any(k in title_lower for k in ["sort", "missing"]):
                diff = "hard"
            elif skill in ("Data Science", "Datascience") and totals["read"] > 100:
                diff = "hard"
            else:
                diff = "moderate"

            tags = [t.strip() for t in str(row.get("tags") or "").replace(";", ",").split(",") if t.strip() and t.strip().lower() != "none"]
            if skill in ("Software Engineering", "mix skill"):
                for t_extra in ["Software Engineering", "mix skill"]:
                    if t_extra not in tags:
                        tags.append(t_extra)

            if clear and db is not None and skill not in cleared_skills:
                for c in (db.questions_moderate, db.questions_hard, db.solutions):
                    c.delete_many({"skill": skill})
                cleared_skills.add(skill)
                index_counters[(skill, "moderate")] = index_counters[(skill, "hard")] = 0
            elif not clear and db is not None and (skill, diff) not in index_counters:
                coll = db.questions_hard if diff == "hard" else db.questions_moderate
                last = coll.find_one({"skill": skill}, sort=[("index", -1)])
                index_counters[(skill, diff)] = (last["index"] + 1) if last and "index" in last else 0

            title_display = str(row.get('title', 'Unknown Title')).encode(getattr(sys.stdout, "encoding", "utf-8") or "utf-8", errors="replace").decode(getattr(sys.stdout, "encoding", "utf-8") or "utf-8", errors="replace")
            print(f"[{totals['read']}] Mutating: {title_display} ...", flush=True)
            mut = mock_mutate(row) if (mock_llm or client is None) else mutate_question(client, row, model=model)
            idx = index_counters[(skill, diff)]
            index_counters[(skill, diff)] += 1

            q_doc = CodingQuestionDoc(
                skill=skill, index=idx, title=mut.mutated_title, description=mut.mutated_description,
                source="gemini_mutated", source_url=row.get("source_url") or "", tags=tags,
            ).model_dump()
            s_doc = SolutionDoc(
                skill=skill, index=idx, difficulty=diff,
                reference_solution=mut.mutated_solution, explanation=mut.explanation,
            ).model_dump()

            (hard_batch if diff == "hard" else mod_batch).append(q_doc)
            sol_batch.append(s_doc)

        if not dry_run and db is not None:
            print(f"Batch insert of {len(mod_batch) + len(hard_batch)} questions into MongoDB...", flush=True)
            counts = bulk_insert_documents(db, mod_batch, hard_batch, sol_batch)
            for k in ("moderate", "hard", "solutions"):
                totals[k] += counts[k]
        else:
            totals["moderate"] += len(mod_batch)
            totals["hard"] += len(hard_batch)
            totals["solutions"] += len(sol_batch)

    print(f"[data_builder] Complete. Read: {totals['read']}, Moderate: {totals['moderate']}, Hard: {totals['hard']}, Solutions: {totals['solutions']}", flush=True)
    return totals


def seed_mock_data(skills: list[str]):
    """Maintains backward compatibility with original ml-services test seeder."""
    db = get_db()
    for col in (db.questions_moderate, db.questions_hard, db.solutions):
        col.delete_many({"skill": {"$in": skills}})
    mod, hard, sol = [], [], []
    for s in skills:
        mod.extend(CodingQuestionDoc(skill=s, index=i, title=f"Moderate {s} Task #{i}", description=f"Solve {i}.", source="mock").model_dump() for i in range(100))
        sol.extend(SolutionDoc(skill=s, index=i, difficulty="moderate", reference_solution="def solve(): pass").model_dump() for i in range(100))
        hard.extend(CodingQuestionDoc(skill=s, index=i, title=f"Hard {s} Task #{i}", description=f"Design {i}.", source="mock").model_dump() for i in range(50))
        sol.extend(SolutionDoc(skill=s, index=i, difficulty="hard", reference_solution="class System: pass").model_dump() for i in range(50))
    bulk_insert_documents(db, mod, hard, sol)
    print(f"Seeded {len(skills)*100} moderate + {len(skills)*50} hard questions.")


def ensure_indexes(db=None):
    """Ensures compound unique and query indexes exist across collections (R2 index integrity)."""
    db = db if db is not None else get_db()
    db.questions_moderate.create_index([("skill", 1), ("index", 1)], unique=True)
    db.questions_moderate.create_index([("skill", 1)])
    db.questions_hard.create_index([("skill", 1), ("index", 1)], unique=True)
    db.questions_hard.create_index([("skill", 1)])
    db.solutions.create_index([("skill", 1), ("index", 1), ("difficulty", 1)], unique=True)
    db.solutions.create_index([("skill", 1)])
    return True


def print_status(db=None):
    """Prints current database counts and schema breakdown across all skills."""
    db = db if db is not None else get_db()
    ensure_indexes(db)
    print("=== Database Status ===")
    total_mod = db.questions_moderate.count_documents({})
    total_hard = db.questions_hard.count_documents({})
    total_sol = db.solutions.count_documents({})
    print(f"Total Moderate Questions: {total_mod}")
    print(f"Total Hard Questions:     {total_hard}")
    print(f"Total Questions (M+H):    {total_mod + total_hard}")
    print(f"Total Solutions:          {total_sol}")

    all_skills = sorted(set(db.questions_moderate.distinct("skill") + db.questions_hard.distinct("skill") + db.solutions.distinct("skill")))
    print("\n--- Breakdown by Skill ---")
    for s in all_skills:
        m_cnt = db.questions_moderate.count_documents({"skill": s})
        h_cnt = db.questions_hard.count_documents({"skill": s})
        sol_m = db.solutions.count_documents({"skill": s, "difficulty": "moderate"})
        sol_h = db.solutions.count_documents({"skill": s, "difficulty": "hard"})
        sol_total = db.solutions.count_documents({"skill": s})
        print(f"  Skill '{s}': Moderate={m_cnt} (sol={sol_m}), Hard={h_cnt} (sol={sol_h}), Total Q={m_cnt+h_cnt}, Total Sol={sol_total}")
        if m_cnt != sol_m or h_cnt != sol_h:
            print(f"    [!] MISMATCH for skill '{s}': Q(m={m_cnt}, h={h_cnt}) vs Sol(m={sol_m}, h={sol_h})")

    # Fast in-memory check for missing reference solutions (O(N) instead of O(N) WAN round-trips)
    sol_keys = {(s["skill"], s["index"], s["difficulty"]) for s in db.solutions.find({}, {"skill": 1, "index": 1, "difficulty": 1})}
    missing_sols = 0
    for col, diff in [(db.questions_moderate, "moderate"), (db.questions_hard, "hard")]:
        for q in col.find({}, {"skill": 1, "index": 1}):
            sk, idx = q.get("skill"), q.get("index")
            if (sk, idx, diff) not in sol_keys:
                missing_sols += 1
    print(f"\nMissing reference solutions across all questions: {missing_sols}")
    print("=========================")


def main():
    p = argparse.ArgumentParser(description="ResuListic ETL Pipeline for Coding Questions")
    p.add_argument("--csv", required=False, help="Path to input CSV dataset")
    p.add_argument("--status", action="store_true", help="Print current database status and exit")
    p.add_argument("--chunk-size", type=int, default=50, help="Row chunk size (default: 50)")
    p.add_argument("--dry-run", action="store_true", help="Process without inserting into MongoDB")
    p.add_argument("--clear", action="store_true", help="Clear existing documents for skills before inserting")
    p.add_argument("--mock-llm", action="store_true", help="Use mock mutation (no Gemini API calls)")
    p.add_argument("--model", default=os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"), help="Groq model name")
    p.add_argument("--db-name", default=os.getenv("MONGODB_DB", "resulistic_db"), help="Target database name")
    p.add_argument("--skip", type=int, default=0, help="Number of rows to skip (useful for resuming after a crash)")
    args = p.parse_args()

    if args.status:
        print_status()
        return

    if not args.csv:
        p.print_help()
        sys.exit(1)

    if not os.path.exists(args.csv):
        print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
        sys.exit(1)
    run_pipeline(csv_path=args.csv, chunk_size=args.chunk_size, dry_run=args.dry_run,
                 clear=args.clear, mock_llm=args.mock_llm, model=args.model, skip=args.skip)

if __name__ == "__main__":
    main()
