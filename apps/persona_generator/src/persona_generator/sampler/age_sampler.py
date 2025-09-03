import numpy as np

from shared.storage.models import Age

from .sampler import Sampler


class AgeSampler(Sampler):

    def __init__(
        self, age_min: int = None, age_max: int = None, temperature: float = 0.0
    ):
        self.age_min = age_min
        self.age_max = age_max
        super().__init__(temperature)

    def _prepare(self):
        # Filter by age range if given
        ages = Age.select()
        if self.age_min is not None:
            ages = ages.where(Age.age >= self.age_min)
        if self.age_max is not None:
            ages = ages.where(Age.age <= self.age_max)
        # Prepare distributions
        ages = list(ages)
        weights = np.array([a.total for a in ages], dtype=float)
        weights = self.power_scaling_with_temperature(weights, self.temperature)
        self.ages = np.array([a.age for a in ages])
        self.weights = weights

    def sample(self) -> int:
        """Sample one age."""
        return np.random.choice(self.ages, p=self.weights)

    def sample_n(self, n: int) -> list[int]:
        """Sample n ages."""
        return np.random.choice(self.ages, size=n, p=self.weights).tolist()
