import enum

import numpy as np

from persona_generator.sampler.sampler import Sampler

# Prozentuale Verteilung laut Studie (Summe = 100%)
HETEROSEXUAL = 98.1
HOMOSEXUAL = 1.2
BISEXUAL = 0.7


class SexualityEnum(str, enum.Enum):
    HETEROSEXUAL = "heterosexual"
    HOMOSEXUAL = "homosexual"
    BISEXUAL = "bisexual"

    @classmethod
    def as_array(cls):
        return np.array(
            [cls.HETEROSEXUAL.value, cls.HOMOSEXUAL.value, cls.BISEXUAL.value]
        )


SEXUALITY_LABELS = SexualityEnum.as_array()
SEXUALITY_PROBS = np.array([HETEROSEXUAL, HOMOSEXUAL, BISEXUAL]) / 100


class SexualitySampler(Sampler):
    def __init__(self, temperature: float = 0.0, exclude: list = None):
        self.exclude = set(exclude) if exclude else set()
        super().__init__(temperature)

    def _prepare(self):
        # Filtere ausgeschlossene Sexualitäten
        self.labels = [s for s in SEXUALITY_LABELS if s not in self.exclude]
        idxs = [i for i, s in enumerate(SEXUALITY_LABELS) if s not in self.exclude]
        self.probs = SEXUALITY_PROBS[idxs]
        self.probs = (
            self.probs / self.probs.sum()
        )  # Normiere falls etwas ausgeschlossen wurde
        self.probs = self.power_scaling_with_temperature(self.probs, self.temperature)

    def sample(self) -> str:
        return np.random.choice(self.labels, p=self.probs)

    def sample_n(self, n: int) -> list[str]:
        return list(np.random.choice(self.labels, size=n, p=self.probs))
