"""CSV export functionality for personas."""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, Iterable, List

from peewee import JOIN

from backend.infrastructure.storage.models import (
    AdditionalPersonaAttributes,
    Country,
    DatasetPersona,
    Persona,
)


class PersonaCSVExporter:
    """Handles CSV export of personas with streaming support."""

    BASE_COLUMNS = [
        "uuid",
        "created_at",
        "age",
        "gender",
        "education",
        "occupation",
        "marriage_status",
        "migration_status",
        "religion",
        "sexuality",
        "origin_country",
        "origin_region",
        "origin_subregion",
    ]

    def __init__(
        self,
        dataset_id: int,
        attrgen_run_id: int | None = None,
        chunk_size: int = 1000,
    ):
        """Initialize the exporter.

        Args:
            dataset_id: Dataset to export
            attrgen_run_id: Optional attribute generation run ID for enrichment
            chunk_size: Number of personas to fetch per chunk
        """
        self.dataset_id = dataset_id
        self.attrgen_run_id = attrgen_run_id
        self.chunk_size = chunk_size

    def get_attribute_keys(self) -> List[str]:
        """Get distinct attribute keys for the attrgen run.

        Returns:
            Sorted list of attribute keys
        """
        if self.attrgen_run_id is None:
            return []

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
                (DatasetPersona.dataset_id == self.dataset_id)
                & (
                    AdditionalPersonaAttributes.attr_generation_run_id
                    == self.attrgen_run_id
                )
            )
            .distinct()
        )
        return sorted({str(r.attribute_key) for r in query})

    def get_header(self) -> List[str]:
        """Get CSV header row.

        Returns:
            List of column names
        """
        attribute_keys = self.get_attribute_keys()
        return self.BASE_COLUMNS + attribute_keys

    def stream_rows(self) -> Iterable[bytes]:
        """Stream CSV rows as bytes.

        Yields:
            CSV data as bytes (UTF-8 encoded)
        """
        attribute_keys = self.get_attribute_keys()
        header = self.get_header()

        buf = io.StringIO()
        writer = csv.writer(buf)

        # Write header
        writer.writerow(header)
        yield buf.getvalue().encode("utf-8")
        buf.seek(0)
        buf.truncate(0)

        # Stream personas in chunks
        base_query = (
            Persona.select(Persona, Country)
            .join(DatasetPersona, on=(DatasetPersona.persona_id == Persona.uuid))
            .switch(Persona)
            .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))
            .where(DatasetPersona.dataset_id == self.dataset_id)
            .order_by(Persona.created_at.asc())
        )

        total = base_query.count()
        fetched = 0

        while fetched < total:
            batch = list(base_query.limit(self.chunk_size).offset(fetched))
            fetched += len(batch)
            if not batch:
                break

            # Fetch additional attributes for this batch
            add_map: Dict[str, Dict[str, Any]] = {}
            if self.attrgen_run_id is not None and attribute_keys:
                uuids = [r.uuid for r in batch]
                sub = (
                    AdditionalPersonaAttributes.select(AdditionalPersonaAttributes)
                    .where(
                        (AdditionalPersonaAttributes.persona_uuid_id.in_(uuids))
                        & (
                            AdditionalPersonaAttributes.attr_generation_run_id
                            == self.attrgen_run_id
                        )
                    )
                    .order_by(
                        AdditionalPersonaAttributes.persona_uuid_id,
                        AdditionalPersonaAttributes.attribute_key,
                        AdditionalPersonaAttributes.id.desc(),
                    )
                )
                for attr in sub:
                    pid = str(attr.persona_uuid_id)
                    d = add_map.setdefault(pid, {})
                    # Keep first occurrence per key (latest by id desc)
                    if attr.attribute_key not in d:
                        d[str(attr.attribute_key)] = str(attr.value)

            # Write rows
            for persona in batch:
                row = [
                    str(persona.uuid),
                    str(persona.created_at) if persona.created_at else "",
                    str(int(persona.age)) if persona.age is not None else "",
                    persona.gender or "",
                    persona.education or "",
                    persona.occupation or "",
                    persona.marriage_status or "",
                    persona.migration_status or "",
                    persona.religion or "",
                    persona.sexuality or "",
                    getattr(persona.origin_id, "country_en", "") or "",
                    getattr(persona.origin_id, "region", "") or "",
                    getattr(persona.origin_id, "subregion", "") or "",
                ]

                if attribute_keys:
                    vals = add_map.get(str(persona.uuid), {})
                    row.extend([str(vals.get(k, "")) for k in attribute_keys])

                writer.writerow(row)
                # Flush row
                yield buf.getvalue().encode("utf-8")
                buf.seek(0)
                buf.truncate(0)

    def get_filename(self) -> str:
        """Get suggested filename for the CSV.

        Returns:
            Filename string
        """
        filename = f"dataset_{self.dataset_id}"
        if self.attrgen_run_id is not None:
            filename += f"_attrrun_{self.attrgen_run_id}"
        filename += ".csv"
        return filename
