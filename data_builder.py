"""data_builder.py — Production ETL Pipeline for Coding Questions (Ponytail Mode < 200 LOC)."""
import argparse, csv, itertools, os, sys, time
from collections import defaultdict
from typing import Optional
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
    """Mutates question narrative and solution variables with 429 exponential backoff using Groq."""
    if client is None:
        return mock_mutate(row)
    
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

    fallback_models = [model, "qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    
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
                raw = chat_completion.choices[0].message.content
                return MutatedQuestion.model_validate_json(raw)
            except Exception as e:
                err_str = str(e).lower()
                if "404" in err_str or "not found" in err_str:
                    print(f"      [!] Model {current_model} not found. Falling back to next...")
                    break
                    
                is_retryable = any(x in err_str for x in ["429", "rate limit", "503", "connection error", "timeout", "connecttimeout"])
                if is_retryable and attempt < max_retries - 1:
                    print(f"      [!] {current_model} Busy/Timeout. Retrying in {delay}s (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(delay)
                    delay *= 2.0
                    continue
                    
                print(f"      [X] Fatal Error on {current_model}: {e}. Trying next model...")
                break
                
    raise RuntimeError(f"All fallback models failed for question: {row.get('title')}")


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
            diff = "hard" if raw_diff in ("hard", "difficult", "expert", "3") else "moderate"
            tags = [t.strip() for t in str(row.get("tags") or "").replace(";", ",").split(",") if t.strip() and t.strip().lower() != "none"]

            if clear and db is not None and skill not in cleared_skills:
                for c in (db.questions_moderate, db.questions_hard, db.solutions):
                    c.delete_many({"skill": skill})
                cleared_skills.add(skill)
                index_counters[(skill, "moderate")] = index_counters[(skill, "hard")] = 0
            elif not clear and db is not None and (skill, diff) not in index_counters:
                coll = db.questions_hard if diff == "hard" else db.questions_moderate
                last = coll.find_one({"skill": skill}, sort=[("index", -1)])
                index_counters[(skill, diff)] = (last["index"] + 1) if last and "index" in last else 0

            print(f"[{totals['read']}] Mutating: {row.get('title', 'Unknown Title')} ...")
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
            print(f"Batch insert of {len(mod_batch) + len(hard_batch)} questions into MongoDB...")
            counts = bulk_insert_documents(db, mod_batch, hard_batch, sol_batch)
            for k in ("moderate", "hard", "solutions"):
                totals[k] += counts[k]
        else:
            totals["moderate"] += len(mod_batch)
            totals["hard"] += len(hard_batch)
            totals["solutions"] += len(sol_batch)

    print(f"[data_builder] Complete. Read: {totals['read']}, Moderate: {totals['moderate']}, Hard: {totals['hard']}, Solutions: {totals['solutions']}")
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


def main():
    p = argparse.ArgumentParser(description="ResuListic ETL Pipeline for Coding Questions")
    p.add_argument("--csv", required=True, help="Path to input CSV dataset")
    p.add_argument("--chunk-size", type=int, default=50, help="Row chunk size (default: 50)")
    p.add_argument("--dry-run", action="store_true", help="Process without inserting into MongoDB")
    p.add_argument("--clear", action="store_true", help="Clear existing documents for skills before inserting")
    p.add_argument("--mock-llm", action="store_true", help="Use mock mutation (no Gemini API calls)")
    p.add_argument("--model", default=os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"), help="Groq model name")
    p.add_argument("--db-name", default=os.getenv("MONGODB_DB", "resulistic_db"), help="Target database name")
    p.add_argument("--skip", type=int, default=0, help="Number of rows to skip (useful for resuming after a crash)")
    args = p.parse_args()
    if not os.path.exists(args.csv):
        print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
        sys.exit(1)
    run_pipeline(csv_path=args.csv, chunk_size=args.chunk_size, dry_run=args.dry_run,
                 clear=args.clear, mock_llm=args.mock_llm, model=args.model, skip=args.skip)

if __name__ == "__main__":
    main()
