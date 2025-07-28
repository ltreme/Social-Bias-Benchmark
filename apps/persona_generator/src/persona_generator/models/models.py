import os

from peewee import *


def find_project_root_for_data(start_path, target_rel_path="data/persona/personas.db"):
    current = os.path.abspath(start_path)
    while True:
        candidate = os.path.join(current, target_rel_path)
        if os.path.exists(candidate):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise FileNotFoundError(f"{target_rel_path} nicht gefunden!")
        current = parent


PROJECT_ROOT = find_project_root_for_data(__file__)
DB_PATH = os.path.join(PROJECT_ROOT, "data", "persona", "personas.db")
db = SqliteDatabase(DB_PATH)


class BaseModel(Model):
    class Meta:
        database = db


class Age(BaseModel):
    id = AutoField()
    age = IntegerField(unique=True)
    male = IntegerField()
    female = IntegerField()
    diverse = IntegerField()
    total = IntegerField()


class MarriageStatus(BaseModel):
    id = AutoField()
    age_from = IntegerField()
    age_to = IntegerField()
    single = IntegerField()
    married = IntegerField()
    widowed = IntegerField()
    divorced = IntegerField()

    class Meta:
        indexes = ((("age_from", "age_to"), True),)


class MigrationStatus(BaseModel):
    id = AutoField()
    age_from = IntegerField()
    age_to = IntegerField()
    gender = CharField()
    with_migration = IntegerField()
    without_migration = IntegerField()

    class Meta:
        indexes = ((("age_from", "age_to", "gender"), True),)


class Country(BaseModel):
    id = AutoField()
    country_en = CharField(unique=True)
    country_de = CharField()
    region = CharField()
    subregion = CharField()
    population = IntegerField()
    country_code_alpha2 = CharField(unique=True)
    country_code_numeric = IntegerField(unique=True)


class ForeignersPerCountry(BaseModel):
    id = AutoField()
    country = ForeignKeyField(Country, backref="foreigners_per_country")
    total = IntegerField()


class ReligionPerCountry(BaseModel):
    id = AutoField()
    country = ForeignKeyField(Country, backref="religion_per_country")
    religion = CharField()
    total = IntegerField()


class Education(BaseModel):
    id = AutoField()
    age_from = IntegerField()
    age_to = IntegerField()
    gender = CharField()
    education_level = CharField()
    value = IntegerField()


class Occupation(BaseModel):
    id = AutoField()
    age_from = IntegerField()
    age_to = IntegerField()
    category = CharField()
    job_de = CharField()
    job_en = CharField()


class Persona(BaseModel):
    id = AutoField()
    age = IntegerField()
    gender = CharField()
    origin = CharField()
    migration_status = CharField()
    religion = CharField()
    occupation = CharField()
    sexuality = CharField()
    marriage_status = CharField()
    education = CharField()
