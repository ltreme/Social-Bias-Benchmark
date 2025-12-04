"""Extended persona repository with filtering, pagination, and composition stats."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

import peewee as pw
from peewee import JOIN

from backend.infrastructure.storage.models import (
    AdditionalPersonaAttributes,
    Country,
    DatasetPersona,
    Persona,
)


class PersonaFilter:
    """Filter criteria for persona queries."""

    def __init__(
        self,
        gender: str | None = None,
        religion: str | None = None,
        sexuality: str | None = None,
        education: str | None = None,
        marriage_status: str | None = None,
        migration_status: str | None = None,
        origin_subregion: str | None = None,
        min_age: int | None = None,
        max_age: int | None = None,
    ):
        """Initialize filter criteria."""
        self.gender = gender
        self.religion = religion
        self.sexuality = sexuality
        self.education = education
        self.marriage_status = marriage_status
        self.migration_status = migration_status
        self.origin_subregion = origin_subregion
        self.min_age = min_age
        self.max_age = max_age

    def apply_to_query(self, query: pw.ModelSelect) -> pw.ModelSelect:
        """Apply filters to a Peewee query.

        Args:
            query: Base query to filter

        Returns:
            Filtered query
        """
        if self.gender:
            query = query.where(Persona.gender == self.gender)
        if self.religion:
            query = query.where(Persona.religion == self.religion)
        if self.sexuality:
            query = query.where(Persona.sexuality == self.sexuality)
        if self.education:
            query = query.where(Persona.education == self.education)
        if self.marriage_status:
            query = query.where(Persona.marriage_status == self.marriage_status)
        if self.migration_status:
            query = query.where(Persona.migration_status == self.migration_status)
        if self.origin_subregion:
            query = query.where(Country.subregion == self.origin_subregion)
        if self.min_age is not None:
            query = query.where(
                (Persona.age.is_null(True)) | (Persona.age >= self.min_age)
            )
        if self.max_age is not None:
            query = query.where(
                (Persona.age.is_null(True)) | (Persona.age <= self.max_age)
            )
        return query


class PersonaRepositoryExtended:
    """Extended repository for persona queries with filtering and stats."""

    def list_personas_in_dataset(
        self,
        dataset_id: int,
        filter_criteria: PersonaFilter | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Persona], int]:
        """List personas in a dataset with filtering, sorting, and pagination.

        Args:
            dataset_id: The dataset ID
            filter_criteria: Optional filter criteria
            sort_by: Field to sort by
            order: 'asc' or 'desc'
            limit: Number of results per page
            offset: Offset for pagination

        Returns:
            Tuple of (persona list, total count)
        """
        query = (
            Persona.select(Persona, Country)
            .join(DatasetPersona, on=(DatasetPersona.persona_id == Persona.uuid))
            .switch(Persona)
            .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))
            .where(DatasetPersona.dataset_id == dataset_id)
        )

        # Apply filters
        if filter_criteria:
            query = filter_criteria.apply_to_query(query)

        total = query.count()

        # Sorting
        sort_map = {
            "created_at": Persona.created_at,
            "age": Persona.age,
            "gender": Persona.gender,
            "education": Persona.education,
            "religion": Persona.religion,
            "sexuality": Persona.sexuality,
            "marriage_status": Persona.marriage_status,
            "migration_status": Persona.migration_status,
            "origin_subregion": Country.subregion,
        }
        col = sort_map.get(sort_by, Persona.created_at)
        col = col.desc() if order.lower() == "desc" else col.asc()
        query = query.order_by(col).limit(max(1, limit)).offset(max(0, offset))

        return list(query), total

    def get_additional_attributes_for_personas(
        self, persona_uuids: List[str], attrgen_run_id: int
    ) -> Dict[str, Dict[str, Any]]:
        """Get additional attributes for a list of personas.

        Args:
            persona_uuids: List of persona UUIDs
            attrgen_run_id: Attribute generation run ID

        Returns:
            Dictionary mapping persona_uuid -> {attribute_key: value}
        """
        if not persona_uuids:
            return {}

        query = (
            AdditionalPersonaAttributes.select(AdditionalPersonaAttributes)
            .where(
                (AdditionalPersonaAttributes.persona_uuid_id.in_(persona_uuids))
                & (AdditionalPersonaAttributes.attr_generation_run_id == attrgen_run_id)
            )
            .order_by(
                AdditionalPersonaAttributes.persona_uuid_id,
                AdditionalPersonaAttributes.attribute_key,
                AdditionalPersonaAttributes.id.desc(),
            )
        )

        result: Dict[str, Dict[str, Any]] = {}
        for attr in query:
            pid = str(attr.persona_uuid_id)
            result.setdefault(pid, {})
            # Keep first occurrence per key (latest by id desc)
            if attr.attribute_key not in result[pid]:
                result[pid][attr.attribute_key] = attr.value

        return result

    def get_composition_stats(self, dataset_id: int) -> Dict[str, Any]:
        """Get composition statistics for a dataset.

        Args:
            dataset_id: The dataset ID

        Returns:
            Dictionary with composition stats and age pyramid
        """
        personas = list(
            Persona.select(Persona, Country)
            .join(DatasetPersona, on=(DatasetPersona.persona_id == Persona.uuid))
            .switch(Persona)
            .join(
                Country, on=(Persona.origin_id == Country.id), join_type=JOIN.LEFT_OUTER
            )
            .where(DatasetPersona.dataset_id == dataset_id)
        )

        n = len(personas)
        if n == 0:
            return {
                "n": 0,
                "attributes": {},
                "age": {"bins": [], "male": [], "female": [], "other": []},
            }

        def normalize(value: str | None) -> str:
            s = (value or "").strip()
            return s if s else "Unknown"

        # Collect buckets
        buckets: Dict[str, Counter] = {
            "gender": Counter(),
            "religion": Counter(),
            "sexuality": Counter(),
            "education": Counter(),
            "marriage_status": Counter(),
            "migration_status": Counter(),
            "origin_country": Counter(),
            "origin_region": Counter(),
            "origin_subregion": Counter(),
        }

        def age_bin(age: int | None) -> str:
            if age is None or age < 0:
                return "Unknown"
            if age >= 90:
                return "90+"
            lo = (age // 5) * 5
            return f"{lo}-{lo+4}"

        age_by_gender: Dict[str, Counter] = {
            "male": Counter(),
            "female": Counter(),
            "other": Counter(),
        }

        for persona in personas:
            buckets["gender"][normalize(persona.gender)] += 1
            buckets["religion"][normalize(persona.religion)] += 1
            buckets["sexuality"][normalize(persona.sexuality)] += 1
            buckets["education"][normalize(persona.education)] += 1
            buckets["marriage_status"][normalize(persona.marriage_status)] += 1
            buckets["migration_status"][normalize(persona.migration_status)] += 1

            country = getattr(persona, "origin_id", None)
            buckets["origin_country"][
                normalize(getattr(country, "country_en", None))
            ] += 1
            buckets["origin_region"][normalize(getattr(country, "region", None))] += 1
            buckets["origin_subregion"][
                normalize(getattr(country, "subregion", None))
            ] += 1

            # Age pyramid by gender
            gender_normalized = (persona.gender or "").strip().lower()
            gender_key = "other"
            if gender_normalized in ("male", "m", "man"):
                gender_key = "male"
            elif gender_normalized in ("female", "f", "woman"):
                gender_key = "female"

            age_bucket = age_bin(getattr(persona, "age", None))
            age_by_gender[gender_key][age_bucket] += 1

        def pack(counter: Counter, limit: int | None = None) -> List[Dict[str, Any]]:
            items = counter.most_common()
            if limit is not None:
                items = items[:limit]
            total = sum(counter.values()) or 1
            return [
                {"value": k, "count": int(v), "share": float(v) / float(total)}
                for k, v in items
            ]

        # Build age pyramid
        bin_labels = [*(f"{b}-{b+4}" for b in range(0, 90, 5)), "90+", "Unknown"]
        age = {
            "bins": bin_labels,
            "male": [int(age_by_gender["male"].get(b, 0)) for b in bin_labels],
            "female": [int(age_by_gender["female"].get(b, 0)) for b in bin_labels],
            "other": [int(age_by_gender["other"].get(b, 0)) for b in bin_labels],
        }

        attributes: Dict[str, Any] = {
            key: pack(cnt, 30 if key == "origin_country" else None)
            for key, cnt in buckets.items()
        }

        return {"n": n, "attributes": attributes, "age": age}

    def get_distinct_attribute_keys_for_run(
        self, dataset_id: int, attrgen_run_id: int
    ) -> List[str]:
        """Get distinct attribute keys for a dataset and attrgen run.

        Args:
            dataset_id: The dataset ID
            attrgen_run_id: Attribute generation run ID

        Returns:
            Sorted list of attribute keys
        """
        query = (
            AdditionalPersonaAttributes.select(
                AdditionalPersonaAttributes.attribute_key
            )
            .join(
                DatasetPersona,
                on=(
                    DatasetPersona.persona_id
                    == AdditionalPersonaAttributes.persona_uuid_id
                ),
            )
            .where(
                (DatasetPersona.dataset_id == dataset_id)
                & (AdditionalPersonaAttributes.attr_generation_run_id == attrgen_run_id)
            )
            .distinct()
        )
        return sorted({str(r.attribute_key) for r in query})
