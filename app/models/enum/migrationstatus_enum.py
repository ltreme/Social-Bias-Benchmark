from enum import Enum

class MigrationStatusEnum(Enum):
    """Enumeration for migration statuses."""

    WITH_MIGRATION = "With_migration"
    WITHOUT_MIGRATION = "Without_migration"

    @classmethod
    def choices(cls):
        return [(tag, tag.value) for tag in cls]