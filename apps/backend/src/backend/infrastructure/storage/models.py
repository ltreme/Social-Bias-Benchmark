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


class Model(BaseModel):
    id = pw.AutoField()
    name = pw.CharField(unique=True, null=False)
    min_vram = pw.IntegerField(
        null=True, constraints=[pw.Check("min_vram IS NULL OR min_vram >= 0")]
    )
    vllm_serve_cmd = pw.TextField(null=True)
    created_at = pw.DateTimeField(default=utcnow, null=False)


class Trait(BaseModel):
    id = pw.CharField(primary_key=True)
    adjective = pw.CharField(null=False)
    case_template = pw.TextField(null=True)
    category = pw.CharField(null=True)
    valence = pw.IntegerField(
        null=True,
        constraints=[pw.Check("valence IS NULL OR (valence >= -1 AND valence <= 1)")],
    )
    is_active = pw.BooleanField(null=False, default=True)

    class Meta:
        table_name = "case"


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
    created_at = pw.DateTimeField(default=utcnow, null=False)

    # RawPersonaDto-like attributes
    age = pw.IntegerField(null=True)
    gender = pw.CharField(null=True)
    origin_id = pw.ForeignKeyField(
        Country, field=Country.id, backref="personas", null=True, on_delete="SET NULL"
    )
    education = pw.CharField(null=True)
    occupation = pw.CharField(null=True)
    marriage_status = pw.CharField(null=True)
    migration_status = pw.CharField(null=True)
    religion = pw.CharField(null=True)
    sexuality = pw.CharField(null=True)

    class Meta:
        # Optional: index a few frequent filters
        indexes = ((("age", "gender"), False),)


class FailLog(BaseModel):
    id = pw.AutoField()
    persona_uuid_id = pw.ForeignKeyField(
        Persona, field=Persona.uuid, on_delete="CASCADE", null=True
    )
    model_id = pw.ForeignKeyField(Model, on_delete="SET NULL", null=True)
    attempt = pw.IntegerField(null=True)
    error_kind = pw.CharField(null=False)
    raw_text_snippet = pw.TextField(null=True)
    prompt_snippet = pw.TextField(null=True)
    created_at = pw.DateTimeField(default=utcnow, null=False)


# ==============================
# == Dataset registry         ==
# ==============================


class Dataset(BaseModel):
    id = pw.AutoField()
    name = pw.CharField(unique=True, null=False)
    kind = pw.CharField(
        null=False
    )  # 'pool' | 'balanced' | 'counterfactual' | 'reality'
    created_at = pw.DateTimeField(default=utcnow, null=False)

    # Optional seed + config json for reproducibility
    seed = pw.IntegerField(null=True)
    config_json = pw.TextField(null=True)

    # Optional source linkage (e.g. balanced from pool, cf from balanced)
    source_dataset_id = pw.ForeignKeyField(
        "self", null=True, backref="derived", on_delete="SET NULL"
    )


# ==============================
# == Run tracking (new)       ==
# ==============================


class BenchmarkRun(BaseModel):
    id = pw.AutoField()
    created_at = pw.DateTimeField(default=utcnow, null=False)

    # Link to the dataset the run used
    dataset_id = pw.ForeignKeyField(
        Dataset, backref="benchmark_runs", on_delete="CASCADE"
    )

    # Link to the model
    model_id = pw.ForeignKeyField(Model, backref="benchmark_runs", on_delete="RESTRICT")

    # Core parameters captured from CLI
    batch_size = pw.IntegerField(null=True)
    max_attempts = pw.IntegerField(null=True)
    include_rationale = pw.BooleanField(null=False, default=True)
    system_prompt = pw.TextField(null=True)
    # Likert scale order mode: 'in' | 'rev' | 'random50' (optional for legacy rows)
    scale_mode = pw.CharField(null=True)
    # Fraction (0..1) of pairs asked in both directions
    dual_fraction = pw.FloatField(null=True)

    class Meta:
        indexes = ((("dataset_id", "created_at"), False),)


class BenchCache(BaseModel):
    id = pw.AutoField()
    run_id = pw.ForeignKeyField(BenchmarkRun, backref="caches", on_delete="CASCADE")
    kind = pw.CharField(
        null=False
    )  # e.g. 'metrics' | 'deltas' | 'forest' | 'means' | 'order'
    key = pw.TextField(
        null=False
    )  # canonicalized JSON key incl. params and current result count
    data = pw.TextField(null=False)  # JSON payload returned by API
    created_at = pw.DateTimeField(default=utcnow, null=False)
    updated_at = pw.DateTimeField(default=utcnow, null=False)

    class Meta:
        indexes = (
            (("run_id", "kind", "key"), True),  # unique per run + endpoint + param-key
        )


class AttrGenerationRun(BaseModel):
    id = pw.AutoField()
    created_at = pw.DateTimeField(default=utcnow, null=False)

    dataset_id = pw.ForeignKeyField(
        Dataset, backref="attrgen_runs", on_delete="CASCADE", null=True
    )

    # Parameters for attribute generation CLI
    model_id = pw.ForeignKeyField(Model, backref="attrgen_runs", on_delete="RESTRICT")
    batch_size = pw.IntegerField(null=True)
    max_new_tokens = pw.IntegerField(null=True)
    max_attempts = pw.IntegerField(null=True)
    system_prompt = pw.TextField(null=True)


class AdditionalPersonaAttributes(BaseModel):
    id = pw.AutoField()
    persona_uuid_id = pw.ForeignKeyField(
        Persona, field=Persona.uuid, backref="extra_attributes", on_delete="CASCADE"
    )
    # Note: We intend attributes to be unique per (run, persona, key). Keep nullable for
    # legacy DBs, but writers should always provide a run id.
    attr_generation_run_id = pw.ForeignKeyField(
        AttrGenerationRun, backref="extra_attributes", on_delete="SET NULL", null=True
    )
    attempt = pw.IntegerField(
        null=False, default=1, constraints=[pw.Check("attempt >= 1")]
    )
    attribute_key = pw.CharField(null=False)
    value = pw.TextField(null=False)
    created_at = pw.DateTimeField(default=utcnow, null=False)

    class Meta:
        indexes = (
            # Unique per (run, persona, key). This enables enriching the same dataset
            # with multiple models/runs without overwriting existing attributes.
            (("attr_generation_run_id", "persona_uuid_id", "attribute_key"), True),
        )


class BenchmarkResult(BaseModel):
    id = pw.AutoField()
    persona_uuid_id = pw.ForeignKeyField(
        Persona, field=Persona.uuid, backref="benchmark_results", on_delete="CASCADE"
    )
    case_id = pw.ForeignKeyField(
        Trait, field=Trait.id, backref="benchmark_results", on_delete="RESTRICT"
    )
    benchmark_run_id = pw.ForeignKeyField(
        BenchmarkRun, backref="results", on_delete="CASCADE"
    )
    attempt = pw.IntegerField(
        null=False, default=1, constraints=[pw.Check("attempt >= 1")]
    )
    answer_raw = pw.TextField(null=False)
    rating = pw.IntegerField(
        null=True, constraints=[pw.Check("rating BETWEEN 1 AND 5")]
    )
    # Record order used when asking Likert scale: 'in' or 'rev'
    scale_order = pw.CharField(null=True)
    created_at = pw.DateTimeField(default=utcnow, null=False)

    class Meta:
        indexes = (
            # Uniqueness per (benchmark_run, persona, case, scale_order)
            (("benchmark_run_id", "persona_uuid_id", "case_id", "scale_order"), True),
        )


# ================================
# == Lookup / statistics tables ==
# ================================


class ForeignersPerCountry(BaseModel):
    id = pw.AutoField()
    country = pw.ForeignKeyField(
        Country, backref="foreigner_stats", on_delete="CASCADE"
    )
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
        indexes = ((("age_from", "age_to"), True),)


class MigrationStatus(BaseModel):
    id = pw.AutoField()
    age_from = pw.IntegerField(null=True)
    age_to = pw.IntegerField(null=True)
    gender = pw.CharField(null=True)  # values: 'male' | 'female' | 'all'
    with_migration = pw.IntegerField(null=True)
    without_migration = pw.IntegerField(null=True)

    class Meta:
        indexes = ((("age_from", "age_to", "gender"), True),)


class Education(BaseModel):
    id = pw.AutoField()
    age_from = pw.IntegerField(null=True)
    age_to = pw.IntegerField(null=True)
    gender = pw.CharField(null=True)  # 'male' | 'female' | 'all'
    education_level = pw.CharField(null=True)
    value = pw.IntegerField(null=True)

    class Meta:
        # One row per (age interval, gender, education level)
        indexes = ((("age_from", "age_to", "gender", "education_level"), True),)


class Occupation(BaseModel):
    id = pw.AutoField()
    age_from = pw.IntegerField(null=True)
    age_to = pw.IntegerField(null=True)
    category = pw.CharField(null=True)
    job_de = pw.CharField(null=True)
    job_en = pw.CharField(null=True)

    class Meta:
        indexes = ((("age_from", "age_to"), True),)
        constraints = [pw.SQL("UNIQUE(age_from, age_to, job_en)")]


# ==============================
# == Dataset registry         ==
# ==============================


class DatasetPersona(BaseModel):
    id = pw.AutoField()
    dataset_id = pw.ForeignKeyField(Dataset, backref="members", on_delete="CASCADE")
    persona_id = pw.ForeignKeyField(
        Persona, field=Persona.uuid, backref="datasets", on_delete="CASCADE"
    )
    role = pw.CharField(null=True)  # optional: 'source' | 'counterfactual'
    created_at = pw.DateTimeField(default=utcnow, null=False)

    class Meta:
        indexes = ((("dataset_id", "persona_id"), True),)  # unique membership


class CounterfactualLink(BaseModel):
    id = pw.AutoField()
    dataset_id = pw.ForeignKeyField(
        Dataset, backref="counterfactual_links", on_delete="CASCADE"
    )
    source_persona_id = pw.ForeignKeyField(
        Persona,
        field=Persona.uuid,
        backref="counterfactual_sources",
        on_delete="CASCADE",
    )
    cf_persona_id = pw.ForeignKeyField(
        Persona, field=Persona.uuid, backref="counterfactuals", on_delete="CASCADE"
    )
    changed_attribute = pw.CharField(
        null=False
    )  # e.g., 'gender' | 'age' | 'origin' | 'religion' | 'sexuality'
    from_value = pw.CharField(null=True)
    to_value = pw.CharField(null=True)
    rule_tag = pw.CharField(null=True)  # e.g., 'far_age_bin', 'different_subregion'
    created_at = pw.DateTimeField(default=utcnow, null=False)

    class Meta:
        indexes = ((("dataset_id", "cf_persona_id"), True),)


# ---------- Table creation helper ----------
ALL_MODELS = [
    Model,
    Trait,
    Country,
    Persona,
    Dataset,
    DatasetPersona,
    CounterfactualLink,
    BenchmarkRun,
    BenchCache,
    AttrGenerationRun,
    AdditionalPersonaAttributes,
    BenchmarkResult,
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
