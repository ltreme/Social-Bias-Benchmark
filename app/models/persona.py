from dataclasses import dataclass, field
import uuid

@dataclass
class Persona:
    id: uuid.UUID = field(default_factory=uuid.uuid4, init=False)
    name: str
    gender: str
    age: int
    origin: str
    migration_status: str
    religion: str
    occupation: str
    appearance: str
    sexuality: str
    marriage_status: str
    education: str
    biography: str

    def get_possessive_pronoun(self):
        mapping = {
            "männlich": "sein",
            "weiblich": "ihr",
            "divers": "ihr"
        }
        return mapping.get(self.gender, "ihr")

    def get_subject_pronoun(self):
        mapping = {
            "männlich": "er",
            "weiblich": "sie",
            "divers": "sie"
        }
        return mapping.get(self.gender, "sie")

    def get_object_pronoun(self):
        mapping = {
            "männlich": "ihn",
            "weiblich": "sie",
            "divers": "sie"
        }
        return mapping.get(self.gender, "sie")
    
    def get_base_attributes(self)-> dict:
        return {
            "age": self.age,
            "gender": self.gender,
            "occupation": self.occupation,
            "marriage_status": self.marriage_status,
            "education": self.education,
            "migration_status": self.migration_status,
            "origin": self.origin,
            "religion": self.religion,
            "sexuality": self.sexuality,
        }


    def __str__(self):
        return f"Persona(id={self.id}, name={self.name}, age={self.age}, occupation={self.occupation}, gender={self.gender}, origin={self.origin}, religion={self.religion}, appearance={self.appearance}, sexuality={self.sexuality})"

    def __repr__(self):
        return self.__str__()