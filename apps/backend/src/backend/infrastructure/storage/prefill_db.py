import os
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd
from peewee import IntegrityError

from .models import (
    Age,
    Country,
    Education,
    ForeignersPerCountry,
    MarriageStatus,
    MigrationStatus,
    Occupation,
    ReligionPerCountry,
    Trait,
)


def _find_repo_root() -> Path:
    """Find the repository root by looking for the data/ directory."""
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        # The true repo root has a data/ directory with persona subdirectory
        if (parent / "data" / "persona").exists():
            return parent
    # Fallback: go up 7 levels from this file
    # prefill_db.py -> storage -> infrastructure -> backend -> src -> backend -> apps -> (repo root)
    return Path(__file__).parent.parent.parent.parent.parent.parent.parent


def processed_path(filename: str) -> Path:
    """Returns the full path to a processed CSV file."""
    repo_root = _find_repo_root()
    return repo_root / "data" / "persona" / "processed" / filename


def raw_path(filename: str) -> Path:
    """Returns the full path to a raw CSV file."""
    repo_root = _find_repo_root()
    return repo_root / "data" / "persona" / "raw" / filename


def traits_path(filename: str) -> Path:
    """Returns the full path to a traits CSV file."""
    repo_root = _find_repo_root()
    return repo_root / "data" / "cases" / filename


class CSVFiles:
    AGES = processed_path(
        "altersaufbau-bevoelkerung-deutschland-zensus-2022-adjusted.csv"
    )
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
    def parse_int_robust(s):
        """Parse integers from common formatted strings without relying on locales.

        Handles: '36,134,864' -> 36134864, '1 234' -> 1234, '1234.0' -> 1234,
        plain ints/floats, or returns 0 on failure.
        """
        if s is None:
            return 0
        try:
            if isinstance(s, int):
                return s
            if isinstance(s, float):
                return int(s)
            txt = str(s).strip()
            if txt == "" or txt.lower() in {"nan", "none"}:
                return 0
            # Remove common thousand separators (commas, spaces, NBSP)
            txt = txt.replace(",", "").replace(" ", "").replace("\u00a0", "")
            # If there's a decimal part, drop it
            if "." in txt:
                txt = txt.split(".", 1)[0]
            # Keep optional leading minus
            m = re.match(r"^-?\d+", txt)
            if not m:
                return 0
            return int(m.group(0))
        except Exception:
            return 0

    @staticmethod
    def to_int_or_none(v):
        """Convert value to int using parse_int_robust, but return None for empty/NaN."""
        try:
            if v is None:
                return None
            # Handle pandas NaN
            if isinstance(v, float) and pd.isna(v):
                return None
            if isinstance(v, str) and v.strip() == "":
                return None
            x = DBFiller.parse_int_robust(v)
            # If parsing yields 0 but original looked empty-ish, still return None
            return x
        except Exception:
            return None

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
                    age=self.parse_int_robust(row.age),
                    male=self.parse_int_robust(row.male_adjusted),
                    female=self.parse_int_robust(row.female_adjusted),
                    diverse=self.parse_int_robust(row.diverse),
                    total=self.parse_int_robust(row.total),
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
            alpha2_raw = row.get("country_code_alpha2")
            alpha2 = None
            if isinstance(alpha2_raw, str):
                a = alpha2_raw.strip()
                if a and a.lower() != "nan" and len(a) == 2:
                    alpha2 = a
            country_rows.append(
                dict(
                    country_en=row["country"],
                    country_de=row.get("country_de"),
                    region=row.get("region_y"),
                    subregion=row.get("sub-region"),
                    population=self.to_int_or_none(row.get("population")),
                    country_code_alpha2=alpha2,
                    country_code_numeric=self.to_int_or_none(row.get("country-code")),
                )
            )
        n_c = self._bulk_insert_ignore(Country, country_rows)
        print(f"Country inserted: {n_c} (duplicates ignored).")

        # Build mapping from unique key -> Country.id to attach FKs efficiently
        code_to_country = {
            c.country_code_alpha2: c
            for c in Country.select()
            if getattr(c, "country_code_alpha2", None)
        }

        # 2) ForeignersPerCountry (optional per row)
        foreign_rows = []
        for _, row in df.iterrows():
            alpha2 = row.get("country_code_alpha2")
            if pd.isna(row.get("foreigners")) or alpha2 not in code_to_country:
                continue
            foreign_rows.append(
                dict(
                    country=code_to_country[alpha2],
                    total=self.parse_int_robust(row["foreigners"]),
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
                        total=self.parse_int_robust(val),
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

    def fill_traits(self):
        # Read traits from CSV file
        trait_csv_path = traits_path("simple_likert.csv")
        df = self.read_csv(trait_csv_path, sep=",")
        rows = []
        for _, row in df.iterrows():
            rows.append(
                dict(
                    id=str(row["id"]).strip(),
                    adjective=row["adjective"].strip(),
                    case_template=None,
                )
            )
        n = self._bulk_insert_ignore(Trait, rows)
        print(f"Traits inserted: {n} (duplicates ignored).")

    def fill_all(self):
        self.fill_ages()
        self.fill_family_status()
        self.fill_migration_status()
        self.fill_countries_religion_foreigner()
        self.fill_education()
        self.fill_jobs()
        self.fill_traits()
