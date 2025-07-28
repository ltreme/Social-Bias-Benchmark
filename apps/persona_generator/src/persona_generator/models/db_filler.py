import locale

import pandas as pd

from .models import (
    Age,
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
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "data", "processed", filename)


def raw_path(filename: str) -> str:
    """Returns the full path to a raw CSV file."""
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "data", "raw", filename)


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
    def parse_number_locale(s):
        locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
        return locale.atoi(s)

    def fill_ages(self):
        df = self.read_csv(CSVFiles.AGES)
        for row in df.itertuples():
            age = Age(
                age=row.age,
                male=row.male_adjusted,
                female=row.female_adjusted,
                diverse=row.diverse,
                total=row.total,
            )
            try:
                age.save()
            except Exception as e:
                print(f"Error saving age {row.age}: {e}")
        print("Ages have been saved to the database.")

    def fill_family_status(self):
        df = self.read_csv(CSVFiles.FAMILY_STATUS)
        for _, row in df.iterrows():
            ms = MarriageStatus(
                age_from=row["from"],
                age_to=row["to"],
                single=row["single"],
                married=row["married"],
                widowed=row["widowed"],
                divorced=row["divorced"],
            )
            try:
                ms.save()
            except Exception as e:
                print(f"Error saving marriage status {row['from']}-{row['to']}: {e}")
        print("Marriage statuses have been saved to the database.")

    def fill_migration_status(self):
        df = self.read_csv(CSVFiles.MIGRATION_STATUS)

        def map_gender(gender: str) -> str:
            if gender.lower() == "männlich":
                return "male"
            elif gender.lower() == "weiblich":
                return "female"
            else:
                return "all"

        for _, row in df.iterrows():
            migration_status = MigrationStatus(
                age_from=row["age_from"],
                age_to=row["age_to"],
                gender=map_gender(row["gender"]),
                with_migration=row["with_migration"],
                without_migration=row["without_migration"],
            )
            try:
                migration_status.save()
            except Exception as e:
                print(
                    f"Error saving migration status {row['age_from']}-{row['age_to']}: {e}"
                )
        print("Migration statuses have been saved to the database.")

    def fill_countries_religion_foreigner(self):
        df = self.read_csv(CSVFiles.COUNTRIES_RELIGION_FOREIGNER)
        for _, row in df.iterrows():
            country = Country(
                country_en=row["country"],
                country_de=row["country_de"],
                region=row["region_y"],
                subregion=row["sub-region"],
                population=row["population"],
                country_code_alpha2=row["country_code_alpha2"],
                country_code_numeric=row["country-code"],
            )
            try:
                country.save()
            except Exception as e:
                print(f"Error saving country {row['country']}: {e}")
                return
            if not pd.isna(row["foreigners"]):
                foreign_country = ForeignersPerCountry(
                    country=country, total=int(row["foreigners"])
                )
                try:
                    foreign_country.save()
                except Exception as e:
                    print(f"Error saving foreigners for country {row['country']}: {e}")
                    return
            religion_columns = [
                "Christians",
                "Muslims",
                "Religiously_unaffiliated",
                "Buddhists",
                "Hindus",
                "Jews",
                "Other_religions",
            ]
            for religion in religion_columns:
                religion_obj = ReligionPerCountry(
                    country=country,
                    religion=religion,
                    total=self.parse_number_locale(row[religion]),
                )
                try:
                    religion_obj.save()
                except Exception as e:
                    print(
                        f"Error saving religion {religion} for country {row['country']}: {e}"
                    )
                    return
        print("Countries, religions, and foreigners have been saved to the database.")

    def fill_education(self):
        df = self.read_csv(CSVFiles.EDUCATION)

        def map_gender(gender: str) -> str:
            if gender.lower() == "männlich":
                return "male"
            elif gender.lower() == "weiblich":
                return "female"
            else:
                return "all"

        for _, row in df.iterrows():
            education = Education(
                age_from=row["age_from"],
                age_to=row["age_to"],
                gender=map_gender(row["Geschlecht"]),
                education_level=row["Schulabschluss"],
                value=row["Anzahl"],
            )
            try:
                education.save()
            except Exception as e:
                print(
                    f"Error saving education {row['age_from']}-{row['age_to']} {row['Geschlecht']} {row['Schulabschluss']}: {e}"
                )
        print("Education levels have been saved to the database.")

    def fill_jobs(self):
        df = self.read_csv(CSVFiles.JOBS, sep=",")
        for _, row in df.iterrows():
            occupation = Occupation(
                age_from=row["from_age"],
                age_to=row["to_age"],
                category=row["category"],
                job_de=row["job_de"],
                job_en=row["job_en"],
            )
            try:
                occupation.save()
            except Exception as e:
                print(
                    f"Error saving occupation {row['age_from']}-{row['to_age']} {row['category']} {row['job_de']}: {e}"
                )
        print("Occupations have been saved to the database.")

    def fill_all(self):
        self.fill_ages()
        self.fill_family_status()
        self.fill_migration_status()
        self.fill_countries_religion_foreigner()
        self.fill_education()
        self.fill_jobs()
