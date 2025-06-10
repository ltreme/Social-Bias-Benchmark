from models.persona import Persona

class Case:
    def __init__(self, id: str, case_template: str, question: str, adjective: str):
        self.id = id
        self.case_template = case_template
        self.question = question
        self.adjective = adjective

    def render_case_by(self, persona: Persona):
        return self._render(self.case_template, persona)
    
    def render_question_by(self, persona: Persona):
        return self._render(self.question, persona)
    
    def _render(self, template: str, persona: Persona):
        possessive_pronoun = persona.get_possessive_pronoun()
        subject_pronoun = persona.get_subject_pronoun()
        return template.format(
            name=persona.name,
            age=persona.age,
            occupation=persona.occupation,
            possessive_pronoun=possessive_pronoun,
            possessive_pronoun_capitalized=possessive_pronoun.capitalize(),
            subject_pronoun=subject_pronoun,
            subject_pronoun_capitalized=subject_pronoun.capitalize(),
        )
    
    def __str__(self):
        return f"Case(id={self.id}, template={self.case_template}, question={self.question}, adjective={self.adjective})"

    def __repr__(self):
        return self.__str__()
    