from .db_filler import DBFiller
from .models import (
    Age,
    Country,
    Education,
    ForeignersPerCountry,
    MarriageStatus,
    MigrationStatus,
    Occupation,
    Persona,
    ReligionPerCountry,
    db,
)


def init_db():
    """Create all tables if they do not already exist."""
    db.connect()
    db.create_tables(
        [
            Age,
            MarriageStatus,
            MigrationStatus,
            Education,
            Country,
            ForeignersPerCountry,
            ReligionPerCountry,
            Occupation,
            Persona,
        ]
    )
    db_filler = DBFiller()
    db_filler.fill_all()  # Fill the database with initial data

    db.close()


if __name__ == "__main__":
    init_db()
    print("Datenbank und Tabellen erfolgreich angelegt.")
