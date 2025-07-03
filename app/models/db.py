from peewee import *

# SQLite-Datenbank (Datei im lokalen Verzeichnis)
db = SqliteDatabase('personas.db')


class BaseModel(Model):
    class Meta:
        database = db

class AgeGroup(BaseModel):
    id = AutoField()
    from_age = IntegerField()
    to_age = IntegerField()
    label = CharField(unique=True)
    weight = FloatField()

class Appearance(BaseModel):
    id = AutoField()
    appearance = CharField(unique=True)
    weight = FloatField()

class Gender(BaseModel):
    id = AutoField()
    gender = CharField(unique=True)
    weight = FloatField()

class SES(BaseModel):
    id = AutoField()
    ses = CharField(unique=True)
    weight = FloatField()

class Religion(BaseModel):
    id = AutoField()
    religion = CharField(unique=True)
    weight = FloatField()

class Country(BaseModel):
    id = AutoField()
    name = CharField(unique=True)
    continent = CharField()
    region = CharField()
    cultural_group = CharField()

class Origin(BaseModel):
    id = AutoField()
    origin = ForeignKeyField(Country, backref='origins')

class Profession(BaseModel):
    id = AutoField()
    profession = CharField(unique=True)
    min_age = IntegerField()
    max_age = IntegerField()
    ses_status = CharField()
    education_level = CharField()
    category = CharField()

class Persona(BaseModel):
    uuid = CharField(primary_key=True)
    age_group = ForeignKeyField(AgeGroup, backref='personas')
    appearance = ForeignKeyField(Appearance, backref='personas')
    gender = ForeignKeyField(Gender, backref='personas')
    profession = ForeignKeyField(Profession, backref='personas')
    origin = ForeignKeyField(Origin, backref='personas')
    religion = ForeignKeyField(Religion, backref='personas')
    ses = ForeignKeyField(SES, backref='personas')

def init_db():
    """Create all tables if they do not already exist."""
    db.connect()
    db.create_tables([
        AgeGroup, Appearance, Gender, SES, Religion, Country, Origin, Profession, Persona
    ])
    db.close()

if __name__ == "__main__":
    init_db()
    print("Datenbank und Tabellen erfolgreich angelegt.")

