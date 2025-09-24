import locale
import os
from typing import List, Dict

import pandas as pd
from peewee import IntegrityError
from pathlib import Path
from .models import (
    Age,
    Case,
    Country,
    Education,
    ForeignersPerCountry,
    MarriageStatus,
    MigrationStatus,
    Occupation,
    ReligionPerCountry,
)


def processed_path(filename: str) -> str:
    """Returns the full path to a processed CSV file."""
    # Get the repository root by going up from this file's location
    repo_root = Path(__file__).parent.parent.parent.parent.parent.parent
    return repo_root / "data" / "persona" / "processed" / filename



def raw_path(filename: str) -> str:
    """Returns the full path to a raw CSV file."""
    # Get the repository root by going up from this file's location
    repo_root = Path(__file__).parent.parent.parent.parent.parent.parent
    return repo_root / "data" / "persona" / "raw" / filename


def cases_path(filename: str) -> str:
    """Returns the full path to a cases CSV file."""
    # Get the repository root by going up from this file's location
    repo_root = Path(__file__).parent.parent.parent.parent.parent.parent
    return repo_root / "data" / "cases" / filename


class CSVFiles:
    AGES = processed_path("altersaufbau-bevoelkerung-deutschland-zensus-2022-adjusted.csv")
    FAMILY_STATUS = processed_path("familienstand-altersgruppen.csv")
    MIGRATION_STATUS = processed_path("migration_population_distribution.csv")
    COUNTRIES_RELIGION_FOREIGNER = processed_path("countries_religion_foreigner.csv")
    EDUCATION = processed_path("education_population_distribution_2024.csv")
    JOBS = raw_path("occupation.csv")


class DBFiller:
    def __init__(self):
        pass

    @staticmethod
    def read_csv(file_path, sep=";"):
        return pd.read_csv(file_path, sep=sep)

    @staticmethod
    def parse_number_locale(s):
        """Parse locale-formatted integer strings (e.g., '1,234')."""
        locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
        return locale.atoi(s)

    @staticmethod
    def _bulk_insert_ignore(model, rows: List[Dict]) -> int:
        """
        Try a bulk insert that ignores duplicates based on the model's UNIQUE constraints.
        Falls back to row-wise insert with IntegrityError swallow if bulk ignore not supported.
        Returns number of successfully inserted rows (best-effort).
        """
        if not rows:
            return 0

        inserted = 0
        try:
            query = model.insert_many(rows)
            # Peewee 3.x provides on_conflict_ignore(); older API is on_conflict('IGNORE')
            if hasattr(query, "on_conflict_ignore"):
                query = query.on_conflict_ignore()
            else:
                query = query.on_conflict("IGNORE")  # type: ignore
            res = query.execute()
            # SQLite returns number of rows inserted; Postgres may differ – treat as best-effort
            if isinstance(res, int):
                inserted = res
            else:
                # When driver doesn't return count, approximate as len(rows).
                inserted = len(rows)
        except Exception:
            # Fallback: row-wise create with IntegrityError handling
            for data in rows:
                try:
                    model.create(**data)
                    inserted += 1
                except IntegrityError:
                    # Duplicate – ignore
                    pass
                except Exception as e:
                    print(f"[{model.__name__}] Error on create: {e}")
        return inserted

    def fill_ages(self):
        df = self.read_csv(CSVFiles.AGES)
        rows = []
        for row in df.itertuples():
            rows.append(
                dict(
                    age=row.age,
                    male=row.male_adjusted,
                    female=row.female_adjusted,
                    diverse=row.diverse,
                    total=row.total,
                )
            )
        n = self._bulk_insert_ignore(Age, rows)
        print(f"Ages inserted: {n} (duplicates ignored).")

    def fill_family_status(self):
        df = self.read_csv(CSVFiles.FAMILY_STATUS)
        rows = []
        for _, row in df.iterrows():
            rows.append(
                dict(
                    age_from=row["from"],
                    age_to=row["to"],
                    single=row["single"],
                    married=row["married"],
                    widowed=row["widowed"],
                    divorced=row["divorced"],
                )
            )
        n = self._bulk_insert_ignore(MarriageStatus, rows)
        print(f"MarriageStatus inserted: {n} (duplicates ignored).")

    def fill_migration_status(self):
        df = self.read_csv(CSVFiles.MIGRATION_STATUS)

        def map_gender(g: str) -> str:
            gl = (g or "").strip().lower()
            if gl == "männlich":
                return "male"
            if gl == "weiblich":
                return "female"
            return "all"

        rows = []
        for _, row in df.iterrows():
            rows.append(
                dict(
                    age_from=row["age_from"],
                    age_to=row["age_to"],
                    gender=map_gender(row["gender"]),
                    with_migration=row["with_migration"],
                    without_migration=row["without_migration"],
                )
            )
        n = self._bulk_insert_ignore(MigrationStatus, rows)
        print(f"MigrationStatus inserted: {n} (duplicates ignored).")

    def fill_countries_religion_foreigner(self):
        df = self.read_csv(CSVFiles.COUNTRIES_RELIGION_FOREIGNER)

        # 1) Countries
        country_rows = []
        for _, row in df.iterrows():
            country_rows.append(
                dict(
                    country_en=row["country"],
                    country_de=row.get("country_de"),
                    region=row.get("region_y"),
                    subregion=row.get("sub-region"),
                    population=row.get("population"),
                    country_code_alpha2=row.get("country_code_alpha2"),
                    country_code_numeric=row.get("country-code"),
                )
            )
        n_c = self._bulk_insert_ignore(Country, country_rows)
        print(f"Country inserted: {n_c} (duplicates ignored).")

        # Build mapping from unique key -> Country.id to attach FKs efficiently
        code_to_country = {c.country_code_alpha2: c for c in Country.select()}

        # 2) ForeignersPerCountry (optional per row)
        foreign_rows = []
        for _, row in df.iterrows():
            alpha2 = row.get("country_code_alpha2")
            if pd.isna(row.get("foreigners")) or alpha2 not in code_to_country:
                continue
            foreign_rows.append(
                dict(
                    country=code_to_country[alpha2],
                    total=int(row["foreigners"]),
                )
            )
        n_f = self._bulk_insert_ignore(ForeignersPerCountry, foreign_rows)
        print(f"ForeignersPerCountry inserted: {n_f} (duplicates ignored).")

        # 3) ReligionPerCountry (multiple per row)
        religion_cols = [
            "Christians",
            "Muslims",
            "Religiously_unaffiliated",
            "Buddhists",
            "Hindus",
            "Jews",
            "Other_religions",
        ]
        religion_rows = []
        for _, row in df.iterrows():
            alpha2 = row.get("country_code_alpha2")
            country = code_to_country.get(alpha2)
            if not country:
                continue
            for rel in religion_cols:
                val = row.get(rel)
                if pd.isna(val):
                    continue
                religion_rows.append(
                    dict(
                        country=country,
                        religion=rel,
                        total=self.parse_number_locale(val),
                    )
                )
        n_r = self._bulk_insert_ignore(ReligionPerCountry, religion_rows)
        print(f"ReligionPerCountry inserted: {n_r} (duplicates ignored).")

    def fill_education(self):
        df = self.read_csv(CSVFiles.EDUCATION)

        def map_gender(g: str) -> str:
            gl = (g or "").strip().lower()
            if gl == "männlich":
                return "male"
            if gl == "weiblich":
                return "female"
            return "all"

        rows = []
        for _, row in df.iterrows():
            rows.append(
                dict(
                    age_from=row["age_from"],
                    age_to=row["age_to"],
                    gender=map_gender(row["Geschlecht"]),
                    education_level=row["Schulabschluss"],
                    value=row["Anzahl"],
                )
            )
        n = self._bulk_insert_ignore(Education, rows)
        print(f"Education inserted: {n} (duplicates ignored).")

    def fill_jobs(self):
        df = self.read_csv(CSVFiles.JOBS, sep=",")
        rows = []
        for _, row in df.iterrows():
            rows.append(
                dict(
                    age_from=row["from_age"],
                    age_to=row["to_age"],
                    category=row["category"],
                    job_de=row["job_de"],
                    job_en=row["job_en"],
                )
            )
        n = self._bulk_insert_ignore(Occupation, rows)
        print(f"Occupation inserted: {n} (duplicates ignored).")

    def fill_cases(self):
        # Read cases from CSV file
        case_csv_path = cases_path("simple_likert.csv")
        df = self.read_csv(case_csv_path, sep=",")
        rows = []
        for _, row in df.iterrows():
            rows.append(
                dict(
                    id=str(row["id"]).strip(),
                    adjective=row["adjective"].strip(),
                    case_template=None,
                )
            )
        n = self._bulk_insert_ignore(Case, rows)
        print(f"Cases inserted: {n} (duplicates ignored).")

    def fill_all(self):
        self.fill_ages()
        self.fill_family_status()
        self.fill_migration_status()
        self.fill_countries_religion_foreigner()
        self.fill_education()
        self.fill_jobs()
        self.fill_cases()
