import argparse
import csv
import json
import uuid
from typing import Iterable, Mapping, Any, Callable, Optional

import peewee as pw

from persona_generator.sampler.age_sampler import AgeSampler
from persona_generator.sampler.education_sampler import EducationSampler
from persona_generator.sampler.gender_sampler import GenderSampler
from persona_generator.sampler.marriage_status_sampler import MarriageStatusSampler
from persona_generator.sampler.migration_status_sampler import MigrationStatusSampler
from persona_generator.sampler.occupation_sampler import OccupationSampler
from persona_generator.sampler.origin_sampler import OriginSampler
from persona_generator.sampler.religion_sampler import ReligionSampler
from persona_generator.sampler.sexuality_sampler import SexualitySampler

from shared.core_types import MigrationStatusEnum
from shared.paths import PATH_PERSONAS_CSV

from shared.storage.db import init_database, create_tables, transaction, get_db
from shared.storage.models import (
    Persona,
    Dataset,
    DatasetPersona,
    Country,
)
from functools import lru_cache
import unicodedata as ud


# --------- helpers ---------
def _json_or_none(x: Any) -> str | None:
    """Serialize lists/values to JSON; return None if x is falsy."""
    if x is None:
        return None
    return json.dumps(x, ensure_ascii=False)

def _nfc(s: str) -> str:
    return ud.normalize("NFC", s)

def _normkey(s: str) -> str:
    # Unicode-safe, sprachunabhängig
    return ud.normalize("NFC", s).casefold().strip()

@lru_cache(maxsize=1)
def _country_lookup_maps():
    """Build normalized lookup dicts once per process."""
    de_map, en_map, a2_map, id_map = {}, {}, {}, {}
    for c in Country.select(Country.id, Country.country_de, Country.country_en, Country.country_code_alpha2):
        if c.country_de:
            de_map[_normkey(c.country_de)] = c.id
        if c.country_en:
            en_map[_normkey(c.country_en)] = c.id
        if c.country_code_alpha2:
            a2_map[_normkey(c.country_code_alpha2)] = c.id
        id_map[c.id] = c.id
    return {"de": de_map, "en": en_map, "a2": a2_map, "id": id_map}

def _resolve_country_id(origin) -> int | None:
    """
    Resolve origin to Country.id:
    - int (PK)
    - str alpha2 ('DE')
    - str english name (country_en)
    - str german name (country_de)
    """
    if origin is None:
        return None

    maps = _country_lookup_maps()

    # direct int PK
    if isinstance(origin, int):
        return maps["id"].get(origin)

    # accept numpy.str_ etc. → cast to str
    s = str(origin).strip()
    if not s:
        return None

    # 1) alpha2 case-insensitive (avoid LOWER in SQL)
    if len(s) == 2:
        cid = maps["a2"].get(_normkey(s))
        if cid:
            return cid

    # 2) Unicode-insensitive fallback via in-memory maps
    key = _normkey(s)
    return maps["de"].get(key) or maps["en"].get(key)


def _resolve_origin_ids_bulk(origins: list) -> dict:
    """Resolve a list of origin tokens to Country.id using in-memory maps only.

    Returns a dict token->country_id (or None if unresolved). Tokens are used as-is.
    """
    maps = _country_lookup_maps()
    out: dict = {}
    for o in set(origins):
        if o is None:
            out[o] = None
            continue
        s = str(o).strip()
        if not s:
            out[o] = None
            continue
        # alpha2
        if len(s) == 2:
            cid = maps["a2"].get(_normkey(s))
            if cid:
                out[o] = cid
                continue
        key = _normkey(s)
        out[o] = maps["de"].get(key) or maps["en"].get(key)
    return out


# --------- core sampling ---------
def sample_personas(
    n: int,
    *,
    age_min: int,
    age_max: int,
    age_temperature: float,
    education_temperature: float,
    education_exclude: list | None,
    gender_temperature: float,
    gender_exclude: list | None,
    occupation_exclude: list | None,
    marriage_status_temperature: float,
    marriage_status_exclude: list | None,
    migration_status_temperature: float,
    migration_status_exclude: list | None,
    origin_temperature: float,
    origin_exclude: list | None,
    religion_temperature: float,
    religion_exclude: list | None,
    sexuality_temperature: float,
    sexuality_exclude: list | None,
) -> dict[str, list]:
    """Run all sampler components and return aligned lists for each attribute."""
    age_sampler = AgeSampler(age_min=age_min, age_max=age_max, temperature=age_temperature)
    education_sampler = EducationSampler(temperature=education_temperature, exclude=education_exclude)
    gender_sampler = GenderSampler(temperature=gender_temperature, exclude=gender_exclude)
    occupation_sampler = OccupationSampler(exclude=occupation_exclude)
    marriage_status_sampler = MarriageStatusSampler(temperature=marriage_status_temperature, exclude=marriage_status_exclude)
    migration_status_sampler = MigrationStatusSampler(temperature=migration_status_temperature, exclude=migration_status_exclude)
    origin_sampler = OriginSampler(temperature=origin_temperature, exclude=origin_exclude)
    religion_sampler = ReligionSampler(temperature=religion_temperature, exclude=religion_exclude)
    sexuality_sampler = SexualitySampler(temperature=sexuality_temperature, exclude=sexuality_exclude)

    ages = age_sampler.sample_n(n)
    genders = gender_sampler.sample_n(ages)
    educations = education_sampler.sample_n(ages, genders)
    occupations = occupation_sampler.sample_n(ages)
    marriage_statuses = marriage_status_sampler.sample_n(ages)
    migration_statuses = migration_status_sampler.sample_n(ages, genders)
    with_migrations = [ms == MigrationStatusEnum.WITH_MIGRATION.value for ms in migration_statuses]
    origins = origin_sampler.sample_n(with_migrations)
    religions = religion_sampler.sample_n(origins)
    sexualities = sexuality_sampler.sample_n(n)

    # Sanity checks keep data aligned (fail fast if a sampler breaks)
    exp = {
        "ages": ages, "genders": genders, "educations": educations, "occupations": occupations,
        "marriage_statuses": marriage_statuses, "migration_statuses": migration_statuses,
        "origins": origins, "religions": religions, "sexualities": sexualities,
    }
    for k, v in exp.items():
        if len(v) != n:
            raise ValueError(f"Sampler '{k}' returned {len(v)} != expected {n}")

    return exp


def persist_run_and_personas(
    n: int,
    params: Mapping[str, Any],
    sampled: Mapping[str, list],
    *,
    export_csv_path: str | None = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> int:
    """
    Create a Dataset and insert n Personas + DatasetPersona links in a single transaction.
    Returns the created dataset id.
    """
    # Create dataset row
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_name = f"Generated {n} personas {timestamp}"
    dataset_row = dict(
        name=dataset_name,
        kind="generated",
    )

    with transaction():
        # For PostgreSQL, speed up bulk insert by relaxing sync commit within tx
        try:
            db = get_db()
            if isinstance(db, pw.PostgresqlDatabase):  # type: ignore[attr-defined]
                db.execute_sql("SET LOCAL synchronous_commit = OFF")
        except Exception:
            pass
        dataset = Dataset.create(**dataset_row)

        # Build persona rows
        persona_rows = []
        origin_tokens = sampled["origins"]
        origin_id_map = _resolve_origin_ids_bulk(origin_tokens)
        for i in range(n):
            origin_pk = origin_id_map.get(origin_tokens[i])
            if origin_pk is None:
                raise ValueError(f"Unresolvable origin: {origin_tokens[i]!r}")
            persona_rows.append({
                "uuid": uuid.uuid4(),
                "age": sampled["ages"][i],
                "gender": sampled["genders"][i],
                "education": sampled["educations"][i],
                "occupation": sampled["occupations"][i],
                "marriage_status": sampled["marriage_statuses"][i],
                "migration_status": sampled["migration_statuses"][i],
                "origin_id": origin_pk,
                "religion": sampled["religions"][i],
                "sexuality": sampled["sexualities"][i],
            })

        # Helper: chunked insert to respect SQLite variable limit (~999 params)
        def _chunked(seq, size):
            for i in range(0, len(seq), size):
                yield seq[i:i+size]

        # Bulk insert personas in chunks (SQLite limit aware; use larger batches on Postgres)
        inserted = 0
        if persona_rows:
            cols = len(persona_rows[0])
            # Keep a safety margin under 999 to account for SQLite limits
            max_rows = 1000
            try:
                if isinstance(db, pw.PostgresqlDatabase):  # type: ignore[attr-defined]
                    max_rows = 5000
            except Exception:
                pass
            for chunk in _chunked(persona_rows, max_rows):
                Persona.insert_many(chunk).execute()
                inserted += len(chunk)
                if progress_cb:
                    try:
                        progress_cb(inserted, n, 'personas')
                    except Exception:
                        pass

        # Build DatasetPersona links using the UUIDs we just inserted (avoid huge IN())
        persona_uuids = [r['uuid'] for r in persona_rows]
        dataset_persona_rows = [
            dict(dataset_id=dataset.id, persona_id=u)
            for u in persona_uuids
        ]

        # Insert links in safe chunks (2 columns each)
        if dataset_persona_rows:
            max_rows = 2000
            try:
                if isinstance(db, pw.PostgresqlDatabase):  # type: ignore[attr-defined]
                    max_rows = 10000
            except Exception:
                pass
            for chunk in _chunked(dataset_persona_rows, max_rows):
                DatasetPersona.insert_many(chunk).execute()
                # Optional: report link progress too (same total n for simplicity)
                if progress_cb:
                    try:
                        progress_cb(min(n, inserted), n, 'links')
                    except Exception:
                        pass

        # Optional CSV export for debugging/backups
        if export_csv_path:
            fieldnames = [
                "uuid", "age", "gender", "education", "occupation",
                "marriage_status", "migration_status", "origin_id", "religion", "sexuality",
            ]
            with open(export_csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                for r in persona_rows:
                    # serialize UUID for CSV
                    r_csv = {**r, "uuid": str(r["uuid"])}
                    w.writerow(r_csv)

        return dataset.id


# --------- CLI ---------
def main():
    parser = argparse.ArgumentParser(description="Persona Generator (DB-backed)")
    parser.add_argument("--n", type=int, default=1000, help="Number of personas to generate")
    parser.add_argument("--export_csv", type=str, default=None,
                        help="Optional CSV export path (in addition to DB inserts)")

    parser.add_argument("--age_from", type=int, default=0, help="Minimum age")
    parser.add_argument("--age_to", type=int, default=100, help="Maximum age")
    parser.add_argument("--age_temperature", type=float, default=0.0, help="Sampling temperature for age")

    parser.add_argument("--education_temperature", type=float, default=0.0, help="Sampling temperature for education")
    parser.add_argument("--education_exclude", nargs="*", default=None, help="List of education levels to exclude")

    parser.add_argument("--gender_temperature", type=float, default=0.0, help="Sampling temperature for gender")
    parser.add_argument("--gender_exclude", nargs="*", default=None, help="List of genders to exclude")

    parser.add_argument("--occupation_exclude", nargs="*", default=None, help="List of occupations to exclude")

    parser.add_argument("--marriage_status_temperature", type=float, default=0.0, help="Sampling temperature for marriage status")
    parser.add_argument("--marriage_status_exclude", nargs="*", default=None, help="List of marriage statuses to exclude")

    parser.add_argument("--migration_status_temperature", type=float, default=0.0, help="Sampling temperature for migration status")
    parser.add_argument("--migration_status_exclude", nargs="*", default=None, help="List of migration statuses to exclude")

    parser.add_argument("--origin_temperature", type=float, default=0.0, help="Sampling temperature for origin")
    parser.add_argument("--origin_exclude", nargs="*", default=None, help="List of origins to exclude")

    parser.add_argument("--religion_temperature", type=float, default=0.0, help="Sampling temperature for religion")
    parser.add_argument("--religion_exclude", nargs="*", default=None, help="List of religions to exclude")

    parser.add_argument("--sexuality_temperature", type=float, default=0.0, help="Sampling temperature for sexuality")
    parser.add_argument("--sexuality_exclude", nargs="*", default=None, help="List of sexualities to exclude")

    args = parser.parse_args()

    # Initialize DB once (SQLite default: data/benchmark.db)
    init_database()
    create_tables()

    params = dict(
        age_min=args.age_from,
        age_max=args.age_to,
        age_temperature=args.age_temperature,
        education_temperature=args.education_temperature,
        education_exclude=args.education_exclude,
        gender_temperature=args.gender_temperature,
        gender_exclude=args.gender_exclude,
        occupation_exclude=args.occupation_exclude,
        marriage_status_temperature=args.marriage_status_temperature,
        marriage_status_exclude=args.marriage_status_exclude,
        migration_status_temperature=args.migration_status_temperature,
        migration_status_exclude=args.migration_status_exclude,
        origin_temperature=args.origin_temperature,
        origin_exclude=args.origin_exclude,
        religion_temperature=args.religion_temperature,
        religion_exclude=args.religion_exclude,
        sexuality_temperature=args.sexuality_temperature,
        sexuality_exclude=args.sexuality_exclude,
    )

    sampled = sample_personas(n=args.n, **params)
    dataset_id = persist_run_and_personas(
        n=args.n,
        params=params,
        sampled=sampled,
        export_csv_path=args.export_csv or None,
    )

    print(f"OK: stored {args.n} personas under dataset dataset_id={dataset_id}")


if __name__ == "__main__":
    main()
