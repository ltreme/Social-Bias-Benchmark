from peewee import *
import os
import pandas as pd
import locale

# SQLite-Datenbank (Datei im lokalen Verzeichnis)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, '..', 'data', 'personas.db')
db = SqliteDatabase(DB_PATH)


class BaseModel(Model):
    class Meta:
        database = db

class Age(BaseModel):
    id = AutoField()  # Automatischer Primary Key
    age = IntegerField(unique=True)
    male = IntegerField()
    female = IntegerField()
    diverse = IntegerField()
    total = IntegerField()

class MarriageStatus(BaseModel):
    id = AutoField()  # Automatischer Primary Key
    age_from = IntegerField()
    age_to = IntegerField()
    single = IntegerField()
    married = IntegerField()
    widowed = IntegerField()
    divorced = IntegerField()
    class Meta:
        indexes = (
            (('age_from', 'age_to'), True),  # True = unique
        )

class MigrationStatus(BaseModel):
    id = AutoField()  # Automatischer Primary Key
    age_from = IntegerField()
    age_to = IntegerField()
    gender = CharField()
    with_migration = IntegerField()
    without_migration = IntegerField()
    class Meta:
        indexes = (
            (('age_from', 'age_to', 'gender'), True),  # True = unique
        )

class Country(BaseModel):
    id = AutoField()  # Automatischer Primary Key
    country_en = CharField(unique=True)
    country_de = CharField()
    region = CharField()
    subregion = CharField()
    population = IntegerField()
    country_code_alpha2 = CharField(unique=True)
    country_code_numeric = IntegerField(unique=True)

class ForeignersPerCountry(BaseModel):
    id = AutoField()  # Automatischer Primary Key
    country = ForeignKeyField(Country, backref='foreigners_per_country')
    total = IntegerField()

class ReligionPerCountry(BaseModel):
    id = AutoField()  # Automatischer Primary Key
    country = ForeignKeyField(Country, backref='religion_per_country')
    religion = CharField()
    total = IntegerField()

class Education(BaseModel):
    id = AutoField()  # Automatischer Primary Key
    age_from = IntegerField()
    age_to = IntegerField()
    gender = CharField()
    education_level = CharField()
    value = IntegerField()

class Occupation(BaseModel):
    id = AutoField()  # Automatischer Primary Key
    age_from = IntegerField()
    age_to = IntegerField()
    category = CharField()
    job_de = CharField()
    job_en = CharField()

class Persona(BaseModel):
    id = AutoField()  # Automatischer Primary Key
    age = IntegerField()
    gender = CharField()
    origin = CharField()
    migration_status = CharField()
    religion = CharField()
    occupation = CharField()
    sexuality = CharField()
    marriage_status = CharField()
    education = CharField()


# class Persona(BaseModel):
#     uuid = CharField(primary_key=True)
#     age = ForeignKeyField(Age, backref='personas')
#     appearance = ForeignKeyField(Appearance, backref='personas')
#     gender = ForeignKeyField(Gender, backref='personas')
#     profession = ForeignKeyField(Profession, backref='personas')
#     origin = ForeignKeyField(Origin, backref='personas')
#     religion = ForeignKeyField(Religion, backref='personas')
#     ses = ForeignKeyField(SES, backref='personas')

def read_csv(file_path, sep=';'):
    """
    Reads a CSV file and returns a DataFrame.
    """
    return pd.read_csv(f"{file_path}", sep=sep)

def parse_number_locale(s):
    # Set locale to US (works for "1,234,567")
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    return locale.atoi(s)


def fill_countries_religion_foreigner():
    df = read_csv('data/processed/countries_religion_foreigner.csv')
    for index, row in df.iterrows():
        country = Country(
            country_en=row['country'],
            country_de=row['country_de'],
            region=row['region_y'],
            subregion=row['sub-region'],
            population=row['population'],
            country_code_alpha2=row['country_code_alpha2'],
            country_code_numeric=row['country-code']
        )
        try:
            country.save()
        except Exception as e:
            print(f"Error saving country {row['country']}: {e}")
            return
        if not pd.isna(row['foreigners']):
            foreign_country = ForeignersPerCountry(
                country=country,
                total=int(row['foreigners'])
            )
        try:
            foreign_country.save()
        except Exception as e:
            print(f"Error saving foreigners for country {row['country']}: {e}")
            return
        religion_columns = ['Christians', 'Muslims', 'Religiously_unaffiliated', 'Buddhists', 'Hindus', 'Jews', 'Other_religions']
        for religion in religion_columns:
            religion = ReligionPerCountry(
                country=country,
                religion=religion,
                total=parse_number_locale(row[religion])
            )
            try:
                religion.save()
            except Exception as e:
                print(f"Error saving religion {religion} for country {row['country']}: {e}")
                return

def fill_db_tables():
    # fill ages
    df_ages = read_csv('data/processed/altersaufbau-bevoelkerung-deutschland-zensus-2022-adjusted.csv')
    for row in df_ages.itertuples():
        age = Age(
            age=row.age,
            male=row.male_adjusted,
            female=row.female_adjusted,
            diverse=row.diverse,
            total=row.total
        )
        try:
            age.save()
        except Exception as e:
            print(f"Error saving age {row.age}: {e}")
    print("Ages have been saved to the database.")

    # fill family status
    df_family_status = read_csv('data/processed/familienstand-altersgruppen.csv')
    for index, row in df_family_status.iterrows():
        ms = MarriageStatus(
            age_from=row['from'],
            age_to=row['to'],
            single=row['single'],
            married=row['married'],
            widowed=row['widowed'],
            divorced=row['divorced']
        )
        try:
            ms.save()
        except Exception as e:
            print(f"Error saving marriage status {row['from']}-{row['to']}: {e}")
    print("Marriage statuses have been saved to the database.")
    
    # fill migration status
    df_migration_status = read_csv('data/processed/migration_population_distribution.csv')
    def map_gender(gender: str) -> str:
        if gender.lower() == "männlich":
            return "male"
        elif gender.lower() == "weiblich":
            return "female"
        else:
            return "all"

    for index, row in df_migration_status.iterrows():
        migration_status = MigrationStatus(
            age_from=row['age_from'],
            age_to=row['age_to'],
            gender=map_gender(row['gender']),
            with_migration=row['with_migration'],
            without_migration=row['without_migration']
        )
        try:
            migration_status.save()
        except Exception as e:
            print(f"Error saving migration status {row['age_from']}-{row['age_to']}: {e}")
    print("Migration statuses have been saved to the database.")

    # fill countries, religion, and foreigners
    fill_countries_religion_foreigner()
    print("Countries, religions, and foreigners have been saved to the database.")

    # fill education
    df_education = read_csv('data/processed/education_population_distribution_2024.csv')
    for index, row in df_education.iterrows():
        education = Education(
            age_from=row['age_from'],
            age_to=row['age_to'],
            gender=map_gender(row['Geschlecht']),
            education_level=row['Schulabschluss'],
            value=row['Anzahl']
        )
        try:
            education.save()
        except Exception as e:
            print(f"Error saving education {row['age_from']}-{row['age_to']} {row['Geschlecht']} {row['Schulabschluss']}: {e}")
    print("Education levels have been saved to the database.")

    # fill jobs
    df_jobs = read_csv('data/raw/occupation.csv', sep=',')
    for index, row in df_jobs.iterrows():
        occupation = Occupation(
            age_from=row['from_age'],
            age_to=row['to_age'],
            category=row['category'],
            job_de=row['job_de'],
            job_en=row['job_en']
        )
        try:
            occupation.save()
        except Exception as e:
            print(f"Error saving occupation {row['age_from']}-{row['age_to']} {row['category']} {row['job_de']}: {e}")
    print("Occupations have been saved to the database.")

def init_db():
    """Create all tables if they do not already exist."""
    db.connect()
    db.create_tables([
        Age,
        MarriageStatus,
        MigrationStatus,
        Education,
        Country,
        ForeignersPerCountry,
        ReligionPerCountry,
        Occupation,
        Persona
    ])

    fill_db_tables()

    db.close()

if __name__ == "__main__":
    init_db()
    print("Datenbank und Tabellen erfolgreich angelegt.")

