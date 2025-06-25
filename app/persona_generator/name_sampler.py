# In this file the NameSampler will be implemented.

from typing import Optional
from llm_handler.model import LLMModel
from faker import Faker

class NameSampler:
    """Samples names based on different modes."""

    def __init__(self, mode: str, llm_model: Optional[LLMModel] = None):
        if mode not in ['neutral', 'stereotypical', 'llm']:
            raise ValueError(f"Invalid name sampler mode: {mode}")
        
        self.mode = mode
        self.llm_model = llm_model
        self.faker = Faker('de_DE') # For neutral names

        if self.mode == 'llm' and not self.llm_model:
            raise ValueError("LLM model must be provided for 'llm' mode.")

    def sample_name(self, gender: Optional[str] = None, origin: Optional[str] = None, age_group: Optional[str] = None) -> str:
        """
        Samples a name based on the configured mode and provided attributes.
        """
        if self.mode == 'llm':
            return self._sample_llm_name(gender, origin, age_group)
        elif self.mode == 'stereotypical':
            # Placeholder for stereotypical name generation
            return self._sample_stereotypical_name(gender, origin, age_group)
        else: # neutral mode
            return self._sample_neutral_name(gender)

    def _sample_llm_name(self, gender: str, origin: str, age_group: str) -> str:
        """Generates a name using the provided LLM."""
        prompt = f"Bitte generiere einen einzelnen, typischen Vornamen und Nachnamen für eine Person mit den folgenden Merkmalen: Geschlecht: {gender}, Herkunft: {origin}, Altersgruppe: {age_group}. Antworte nur mit dem Namen."
        
        # Assuming the LLM model has a 'call' method
        name = self.llm_model.call(prompt)
        return name.strip()

    def _sample_neutral_name(self, gender: Optional[str]) -> str:
        """Generates a neutral name using Faker."""
        if gender == 'männlich':
            return self.faker.name_male()
        elif gender == 'weiblich':
            return self.faker.name_female()
        else:
            return self.faker.name()

    def _sample_stereotypical_name(self, gender: str, origin: str, age_group: str) -> str:
        """Placeholder for generating a stereotypical name from curated lists."""
        # This would involve loading lists and sampling based on attributes.
        # For now, we can return a placeholder or fall back to neutral.
        print("Warning: 'stereotypical' name mode is not fully implemented. Falling back to neutral.")
        return self._sample_neutral_name(gender)
