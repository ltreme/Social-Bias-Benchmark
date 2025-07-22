from enum import Enum

class GenderEnum(Enum):
    """Enumeration for gender statuses."""

    MALE = "male"
    FEMALE = "female"
    DIVERSE = "diverse"

    @classmethod
    def choices(cls):
        return [(tag, tag.value) for tag in cls]