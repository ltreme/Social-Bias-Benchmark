from backend.infrastructure.storage.db import create_tables, get_db, init_database
from backend.infrastructure.storage.prefill_db import DBFiller


def main():
    init_database()
    db = get_db()
    create_tables()
    filler = DBFiller()
    filler.fill_all()
    tables = db.get_tables()
    for table in tables:
        print("### Tabelle: " + table + " ###")
        columns = db.get_columns(table)
        for column in columns:
            print("- " + column.name)
        print()
    print("Datenbank und Tabellen wurden erfolgreich initialisiert.")


if __name__ == "__main__":
    main()
