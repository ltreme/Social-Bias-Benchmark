class Persona:
    def __init__(self, id:str, name: str, gender:str, age: int, ethnicity:str, religion:str, occupation:str, appearance:str, social_status:str):
        self.id = id
        self.name = name
        self.age = age
        self.occupation = occupation
        self.gender = gender
        self.ethnicity = ethnicity
        self.religion = religion
        self.appearance = appearance
        self.social_status = social_status

    def __eq__(self, other):
        if not isinstance(other, Persona):
            return NotImplemented
        return (self.name == other.name and
                self.age == other.age and
                self.occupation == other.occupation and
                self.gender == other.gender and
                self.ethnicity == other.ethnicity and
                self.religion == other.religion and
                self.appearance == other.appearance and
                self.social_status == other.social_status)

    def __hash__(self):
        return hash((self.name, self.age, self.occupation, self.gender, self.ethnicity, self.religion, self.appearance, self.social_status))

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

    def __str__(self):
        return f"Persona(id={self.id}, name={self.name}, age={self.age}, occupation={self.occupation}, gender={self.gender}, ethnicity={self.ethnicity}, religion={self.religion}, appearance={self.appearance}, social_status={self.social_status})"

    def __repr__(self):
        return self.__str__()