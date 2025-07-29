from benchmark.domain.persona import RawPersonaDto
from shared.core_types import GenderEnum


def get_possessive_pronoun(persona: RawPersonaDto) -> str:
    mapping = {
        GenderEnum.MALE.value: "sein",
        GenderEnum.FEMALE.value: "ihr",
        GenderEnum.DIVERSE.value: "ihr",
    }
    return mapping.get(persona.gender, "ihr")


def get_subject_pronoun(persona: RawPersonaDto) -> str:
    mapping = {
        GenderEnum.MALE.value: "er",
        GenderEnum.FEMALE.value: "sie",
        GenderEnum.DIVERSE.value: "sie",
    }
    return mapping.get(persona.gender, "sie")


def get_object_pronoun(persona: RawPersonaDto) -> str:
    mapping = {
        GenderEnum.MALE.value: "ihn",
        GenderEnum.FEMALE.value: "sie",
        GenderEnum.DIVERSE.value: "sie",
    }
    return mapping.get(persona.gender, "sie")


def persona_to_dict(persona: RawPersonaDto) -> dict:
    attributes = {
        "age": persona.age,
        "gender": persona.gender,
        "occupation": persona.occupation,
        "marriage_status": persona.marriage_status,
        "education": persona.education,
        "migration_status": persona.migration_status,
        "origin": persona.origin,
        "religion": persona.religion,
        "sexuality": persona.sexuality,
        "appearance": persona.appearance,
        "biography": persona.biography,
    }
    if persona.name is not None:
        attributes["name"] = persona.name
    if persona.appearance is not None:
        attributes["appearance"] = persona.appearance
    if persona.biography is not None:
        attributes["biography"] = persona.biography
    return attributes
