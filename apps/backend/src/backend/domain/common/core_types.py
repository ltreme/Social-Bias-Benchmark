from enum import Enum


class GenderEnum(Enum):
    """Enumeration for gender statuses."""

    MALE = "male"
    FEMALE = "female"
    DIVERSE = "diverse"

    @classmethod
    def choices(cls):
        return [(tag, tag.value) for tag in cls]

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"

    def __eq__(self, other):
        if isinstance(other, GenderEnum):
            return self.value == other.value
        return False

    def __hash__(self):
        return hash(self.value)


class MigrationStatusEnum(Enum):
    """Enumeration for migration statuses."""

    WITH_MIGRATION = "with_migration"
    WITHOUT_MIGRATION = "without_migration"

    @classmethod
    def choices(cls):
        return [(tag, tag.value) for tag in cls]

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"

    def __eq__(self, other):
        if isinstance(other, MigrationStatusEnum):
            return self.value == other.value
        return False

    def __hash__(self):
        return hash(self.value)


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

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"

    def __eq__(self, other):
        if isinstance(other, ReligionEnum):
            return self.value == other.value
        return False

    def __hash__(self):
        return hash(self.value)


class PersonaField(Enum):
    NAME = "name"
    AGE = "age"
    GENDER = "gender"
    EDUCATION = "education"
    OCCUPATION = "occupation"
    MARRIAGE_STATUS = "marriage_status"
    MIGRATION_STATUS = "migration_status"
    ORIGIN = "origin"
    RELIGION = "religion"
    SEXUALITY = "sexuality"
    APPEARANCE = "appearance"
    BIOGRAPHY = "biography"

    @classmethod
    def choices(cls):
        return [(tag, tag.value) for tag in cls]

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"

    def __eq__(self, other):
        if isinstance(other, PersonaField):
            return self.value == other.value
        return False
