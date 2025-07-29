from benchmark.domain.persona import EnrichedPersonaDto, RawPersonaDto
from benchmark.llm.model import LLMModel

from .llm_attribute_generator import LLMAttributeGenerator


class AttributeFiller:
    def __init__(self, llm: LLMModel):
        self.llm = llm
        self.llm_attribute_generator = LLMAttributeGenerator(llm)

    def fill_attributes(self, persona: RawPersonaDto) -> EnrichedPersonaDto:
        """
        Fills the attributes of a persona using the LLM.
        """
        name = self.llm_attribute_generator.gen_name(persona)
        appearance = self.llm_attribute_generator.gen_appearance(persona)
        biography = self.llm_attribute_generator.gen_biography(persona)

        return EnrichedPersonaDto(
            **vars(persona), name=name, appearance=appearance, biography=biography
        )
