from enum import Enum

class ReligionEnum(Enum):
    """Enumeration for religions."""

    CHRISTIANS = "Christians"
    MUSLIMS = "Muslims"
    RELIGIOUSLY_UNAFFILIATED = "Religiously_unaffiliated"
    BUDDHISTS = "Buddhists"
    HINDUS = "Hindus"
    JEWS = "Jews"
    OTHER_RELIGIONS = "Other_religions"

    @classmethod
    def choices(cls):
        return [(tag, tag.value) for tag in cls]