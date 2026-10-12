"""
data_builder.py — Backward-compatible module entry in ml-services.
Re-exports the core production ETL pipeline and seeder from repository root data_builder.py.
"""

import os, sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from data_builder import (
    MutatedQuestion,
    get_db,
    read_csv_chunks,
    mock_mutate,
    mutate_question,
    bulk_insert_documents,
    run_pipeline,
    seed_mock_data,
    main,
)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        seed_mock_data(["Python", "FastAPI", "MongoDB", "React", "Docker"])
