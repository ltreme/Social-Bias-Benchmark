import os
import uuid
from datetime import datetime

import peewee as pw
from .db import db_proxy


# --- Base model with shared DB ---
class BaseModel(pw.Model):
    class Meta:
        database = db_proxy

# --- Helpers ---
def utcnow() -> datetime:
    # Store timestamps in UTC. SQLite has no timezone type, so use ISO without tzinfo.
    return datetime.now()

def uuid_default() -> uuid.UUID:
    # Peewee's UUIDField will store as TEXT on SQLite; native on Postgres.
    return uuid.uuid4()

# =========================
# == Main domain tables  ==
# =========================

class PersonaGeneratorRun(BaseModel):
    gen_id = pw.AutoField(primary_key=True)  # incremental run id
    created_at = pw.DateTimeField(default=utcnow, null=False)

    age_min = pw.IntegerField(null=True)
    age_max = pw.IntegerField(null=True)
    age_temperature = pw.FloatField(null=True)

    education_exclude = pw.TextField(null=True)
    education_temperature = pw.FloatField(null=True)

    gender_exclude = pw.TextField(null=True)
    gender_temperature = pw.FloatField(null=True)

    marriage_status_exclude = pw.TextField(null=True)
    marriage_status_temperature = pw.FloatField(null=True)

    origin_exclude = pw.TextField(null=True)

    religion_exclude = pw.TextField(null=True)
    religion_temperature = pw.FloatField(null=True)

    sexuality_exclude = pw.TextField(null=True)
    sexuality_temperature = pw.FloatField(null=True)


class Country(BaseModel):
    id = pw.AutoField()
    country_en = pw.CharField(unique=True, null=False)
    country_de = pw.CharField(null=False)
    region = pw.CharField(null=True)
    subregion = pw.CharField(null=True)
    population = pw.IntegerField(null=True)
    country_code_alpha2 = pw.CharField(max_length=2, unique=True, null=True)
    country_code_numeric = pw.IntegerField(unique=True, null=True)


class Persona(BaseModel):
    # UUID primary key, stable across DBs
    uuid = pw.UUIDField(primary_key=True, default=uuid_default)
    # FK to generation run (explicitly referencing its PK field)
    gen_id = pw.ForeignKeyField(PersonaGeneratorRun, field=PersonaGeneratorRun.gen_id, backref="personas", on_delete="CASCADE")
    created_at = pw.DateTimeField(default=utcnow, null=False)

    # RawPersonaDto-like attributes
    age = pw.IntegerField(null=True)
    gender = pw.CharField(null=True)
    origin = pw.ForeignKeyField(Country, field=Country.id, backref="personas", null=True, on_delete="SET NULL")
    education = pw.CharField(null=True)
    occupation = pw.CharField(null=True)
    marriage_status = pw.CharField(null=True)
    migration_status = pw.CharField(null=True)
    religion = pw.CharField(null=True)
    sexuality = pw.CharField(null=True)

    class Meta:
        # Optional: index a few frequent filters
        indexes = (
            (("age", "gender"), False),
        )

class AdditionalPersonaAttributes(BaseModel):
    id = pw.AutoField()
    persona_uuid = pw.ForeignKeyField(
        Persona, field=Persona.uuid, backref="extra_attributes", on_delete="CASCADE"
    )
    model_name = pw.CharField(null=False)

    # rename: gen_time_seconds -> gen_time_ms  (präziser, passt zum DTO)
    gen_time_ms = pw.IntegerField(null=False)

    # neu: attempt (für Nachverfolgung von Retries)
    attempt = pw.IntegerField(null=False, default=1)

    attribute_key = pw.CharField(null=False)
    value = pw.TextField(null=False)
    created_at = pw.DateTimeField(default=utcnow, null=False)

    class Meta:
        indexes = (
            # Unique per attribute per model to allow multiple model-specific enrichments
            (("persona_uuid", "attribute_key", "model_name"), True),
        )

class FailLog(BaseModel):
    id = pw.AutoField()
    persona_uuid = pw.ForeignKeyField(Persona, field=Persona.uuid, on_delete="CASCADE", null=True)
    model_name = pw.CharField(null=True)
    attempt = pw.IntegerField(null=True)
    error_kind = pw.CharField(null=False)
    raw_text_snippet = pw.TextField(null=True)
    prompt_snippet = pw.TextField(null=True)
    created_at = pw.DateTimeField(default=utcnow, null=False)

# ==============================
# == Run tracking (new)       ==
# ==============================

class BenchmarkRun(BaseModel):
    id = pw.AutoField()
    created_at = pw.DateTimeField(default=utcnow, null=False)

    # Link to the persona generation batch the run used
    gen_id = pw.ForeignKeyField(PersonaGeneratorRun, field=PersonaGeneratorRun.gen_id, backref="benchmark_runs", on_delete="CASCADE")

    # Core parameters captured from CLI
    llm_kind = pw.CharField(null=False)              # e.g., 'hf' | 'fake'
    model_name = pw.CharField(null=False)            # HF model or identifier
    batch_size = pw.IntegerField(null=True)
    max_new_tokens = pw.IntegerField(null=True)
    max_attempts = pw.IntegerField(null=True)
    template_version = pw.CharField(null=False, default="v1")
    include_rationale = pw.BooleanField(null=False, default=True)
    system_prompt = pw.TextField(null=True)
    question_file = pw.TextField(null=True)
    persist_kind = pw.CharField(null=True)           # 'print' | 'peewee'

    class Meta:
        indexes = (
            (("gen_id", "created_at"), False),
        )


class AttrGenerationRun(BaseModel):
    id = pw.AutoField()
    created_at = pw.DateTimeField(default=utcnow, null=False)

    gen_id = pw.ForeignKeyField(PersonaGeneratorRun, field=PersonaGeneratorRun.gen_id, backref="attrgen_runs", on_delete="CASCADE")

    # Parameters for attribute generation CLI
    llm_kind = pw.CharField(null=False)
    model_name = pw.CharField(null=False)
    batch_size = pw.IntegerField(null=True)
    max_new_tokens = pw.IntegerField(null=True)
    max_attempts = pw.IntegerField(null=True)
    persist_buffer_size = pw.IntegerField(null=True)
    template_version = pw.CharField(null=False, default="v1")
    system_prompt = pw.TextField(null=True)
    persist_kind = pw.CharField(null=True)

class BenchmarkResult(BaseModel):
    id = pw.AutoField()
    persona_uuid = pw.ForeignKeyField(Persona, field=Persona.uuid, backref="benchmark_results", on_delete="CASCADE")
    question_uuid = pw.CharField(null=False)
    model_name = pw.CharField(null=False)
    template_version = pw.CharField(null=False)
    # Link to a concrete benchmark run/configuration (nullable for backwards-compat)
    benchmark_run = pw.ForeignKeyField(BenchmarkRun, backref="results", on_delete="CASCADE", null=True)
    gen_time_ms = pw.IntegerField(null=False)
    attempt = pw.IntegerField(null=False, default=1)
    answer_raw = pw.TextField(null=False)
    rating = pw.IntegerField(null=True)  # Likert 1-7 when parsed
    created_at = pw.DateTimeField(default=utcnow, null=False)

    class Meta:
        indexes = (
            # Uniqueness is now per (persona, question, run)
            (("persona_uuid", "question_uuid", "benchmark_run"), True),
        )



# ================================
# == Lookup / statistics tables ==
# ================================

class ForeignersPerCountry(BaseModel):
    id = pw.AutoField()
    country = pw.ForeignKeyField(Country, backref="foreigner_stats", on_delete="CASCADE")
    total = pw.IntegerField(null=True)
    # If you guarantee one row per country, uncomment:
    class Meta:
        constraints = [pw.SQL("UNIQUE(country_id)")]

class ReligionPerCountry(BaseModel):
    id = pw.AutoField()
    country = pw.ForeignKeyField(Country, backref="religion_stats", on_delete="CASCADE")
    religion = pw.CharField(null=True)
    total = pw.IntegerField(null=True)
    class Meta:
        constraints = [pw.SQL("UNIQUE(country_id, religion)")]

class Age(BaseModel):
    id = pw.AutoField()
    age = pw.IntegerField(unique=True, null=False)
    male = pw.IntegerField(null=True)
    female = pw.IntegerField(null=True)
    diverse = pw.IntegerField(null=True)
    total = pw.IntegerField(null=True)

class MarriageStatus(BaseModel):
    id = pw.AutoField()
    age_from = pw.IntegerField(null=True)
    age_to = pw.IntegerField(null=True)
    single = pw.IntegerField(null=True)
    married = pw.IntegerField(null=True)
    widowed = pw.IntegerField(null=True)
    divorced = pw.IntegerField(null=True)

    class Meta:
        indexes = (
            (("age_from", "age_to"), True),
        )

class MigrationStatus(BaseModel):
    id = pw.AutoField()
    age_from = pw.IntegerField(null=True)
    age_to = pw.IntegerField(null=True)
    gender = pw.CharField(null=True)  # values: 'male' | 'female' | 'all'
    with_migration = pw.IntegerField(null=True)
    without_migration = pw.IntegerField(null=True)

    class Meta:
        indexes = (
            (("age_from", "age_to", "gender"), True),
        )

class Education(BaseModel):
    id = pw.AutoField()
    age_from = pw.IntegerField(null=True)
    age_to = pw.IntegerField(null=True)
    gender = pw.CharField(null=True)  # 'male' | 'female' | 'all'
    education_level = pw.CharField(null=True)
    value = pw.IntegerField(null=True)
    
    class Meta:
        indexes = (
            (("age_from", "age_to", "gender"), True),
        )
        constraints = [
            pw.SQL("UNIQUE(age_from, age_to, gender)")
        ]

class Occupation(BaseModel):
    id = pw.AutoField()
    age_from = pw.IntegerField(null=True)
    age_to = pw.IntegerField(null=True)
    category = pw.CharField(null=True)
    job_de = pw.CharField(null=True)
    job_en = pw.CharField(null=True)
    
    class Meta:
        indexes = (
            (("age_from", "age_to"), True),
        )
        constraints = [
            pw.SQL("UNIQUE(age_from, age_to, job_en)")
        ]

# ---------- Table creation helper ----------
ALL_MODELS = [
    PersonaGeneratorRun,
    Country,
    Persona,
    AdditionalPersonaAttributes,
    BenchmarkRun,
    BenchmarkResult,
    AttrGenerationRun,
    ForeignersPerCountry,
    ReligionPerCountry,
    Age,
    MarriageStatus,
    MigrationStatus,
    Education,
    Occupation,
    FailLog,
]

def create_tables():
    """Create tables if they do not yet exist."""
    with db_proxy:
        db_proxy.create_tables(ALL_MODELS, safe=True)
