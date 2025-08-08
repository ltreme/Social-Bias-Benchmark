from abc import ABC, abstractmethod
from typing import Optional


class AbstractLLM(ABC):

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the model."""
        pass

    @abstractmethod
    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_new_tokens: int = 150,
    ) -> str:
        pass
