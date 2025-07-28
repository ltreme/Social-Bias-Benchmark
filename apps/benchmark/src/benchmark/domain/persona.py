from dataclasses import dataclass


@dataclass(frozen=True)
class RawPersonaDto:
    uuid: str
    age: int
    gender: str
    education: str
    occupation: str
    marriage_status: str
    migration_status: str
    origin: str
    religion: str
    sexuality: str


@dataclass(frozen=True)
class EnrichedPersonaDto(RawPersonaDto):
    name: str
    appearance: str
    biography: str
