"""Check an existing khatians.db for required search tables and columns."""
import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "khatian_details": {"khatian_id", "jl_number_id", "survey_name", "detail_json"},
    "khatian_index": {"khatian_id", "survey_name"},
}


def validate(path: Path):
    errors = []
    if not path.is_file():
        return [f"No SQLite database at {path}"]
    try:
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                errors.append("SQLite quick_check failed")
            for table, needed in REQUIRED.items():
                columns = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
                if needed - columns:
                    errors.append(f"{table} missing columns: {', '.join(sorted(needed - columns))}")
                else:
                    print(f"{table}: {db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:,} rows")
    except sqlite3.Error as exc:
        errors.append(str(exc))
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, nargs="?", default=ROOT / "data" / "khatians.db")
    args = parser.parse_args()
    problems = validate(args.path)
    if problems:
        for problem in problems:
            print("ERROR:", problem)
        raise SystemExit(1)
    print("Database structure is compatible with the core RAG search engine.")
