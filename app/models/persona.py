from models.enum.gender_enum import GenderEnum

class PersonaDto:
    id: int
    gender: str
    age: int
    origin: str
    migration_status: str
    religion: str
    occupation: str
    sexuality: str
    marriage_status: str
    education: str
    name: str
    appearance: str
    biography: str


    def __init__(self, id: int, age: int, gender: str, origin: str, migration_status: str, religion: str, occupation: str, sexuality: str, marriage_status: str, education: str, name: str = None, appearance: str = None, biography: str = None):
        self.id = id
        self.age = age
        self.gender = gender
        self.origin = origin
        self.migration_status = migration_status
        self.religion = religion
        self.occupation = occupation
        self.sexuality = sexuality
        self.marriage_status = marriage_status
        self.education = education
        self.name = name
        self.appearance = appearance
        self.biography = biography

    def get_possessive_pronoun(self):
        mapping = {
            GenderEnum.MALE.value: "sein",
            GenderEnum.FEMALE.value: "ihr",
            GenderEnum.DIVERSE.value: "ihr"
        }
        return mapping.get(self.gender, "ihr")

    def get_subject_pronoun(self):
        mapping = {
            GenderEnum.MALE.value: "er",
            GenderEnum.FEMALE.value: "sie",
            GenderEnum.DIVERSE.value: "sie"
        }
        return mapping.get(self.gender, "sie")

    def get_object_pronoun(self):
        mapping = {
            GenderEnum.MALE.value: "ihn",
            GenderEnum.FEMALE.value: "sie",
            GenderEnum.DIVERSE.value: "sie"
        }
        return mapping.get(self.gender, "sie")
    
    def get_base_attributes(self)-> dict:
        attributes = {
            "age": self.age,
            "gender": self.gender,
            "occupation": self.occupation,
            "marriage_status": self.marriage_status,
            "education": self.education,
            "migration_status": self.migration_status,
            "origin": self.origin,
            "religion": self.religion,
            "sexuality": self.sexuality,
            "appearance": self.appearance,
            "biography": self.biography,
        }
        if self.name is not None:
            attributes["name"] = self.name
        if self.appearance is not None:
            attributes["appearance"] = self.appearance
        if self.biography is not None:
            attributes["biography"] = self.biography
        return attributes
    
    def set_name(self, name: str):
        self.name = name
    
    def set_appearance(self, appearance: str):
        self.appearance = appearance

    def set_biography(self, biography: str):
        self.biography = biography

    def save(self):
        # This method should implement the logic to save the persona to a database or any storage.
        # For now, it is just a placeholder.
        pass


    def __str__(self):
        return f"Persona(id={self.id}, name={self.name}, age={self.age}, occupation={self.occupation}, gender={self.gender}, origin={self.origin}, religion={self.religion}, appearance={self.appearance}, sexuality={self.sexuality})"

    def __repr__(self):
        return self.__str__()