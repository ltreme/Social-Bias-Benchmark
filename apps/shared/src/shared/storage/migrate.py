import argparse
from typing import List

import peewee as pw

from .db import init_database, get_db
from .models import create_tables, Dataset, DatasetPersona, CounterfactualLink


def ensure_new_tables(verbose: bool = True) -> List[str]:
    db = get_db()
    before = set(db.get_tables())
    create_tables()
    after = set(db.get_tables())
    created = sorted(list(after - before))
    if verbose:
        if created:
            print("Created tables:", ", ".join(created))
        else:
            print("No new tables needed.")
    return created


def main():
    parser = argparse.ArgumentParser(description="Apply DB schema updates without dropping data")
    parser.add_argument("--db_url", type=str, default=None, help="Optional DB URL (fallback to env DB_URL or SQLite path)")
    args = parser.parse_args()

    init_database(args.db_url)
    ensure_new_tables(verbose=True)


if __name__ == "__main__":
    main()

