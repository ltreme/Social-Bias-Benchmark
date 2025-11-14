import numpy as np

from backend.infrastructure.storage.models import MarriageStatus

from .sampler import Sampler


class MarriageStatusSampler(Sampler):

    def __init__(self, temperature: float = 0.0, exclude: list = None):
        self.exclude = set(exclude) if exclude else set()
        all_statuses = ["single", "married", "widowed", "divorced"]
        self.categories = [s for s in all_statuses if s not in self.exclude]
        super().__init__(temperature)

    def _prepare(self):
        # Mapping: age -> dict of status: probability
        self.age2probs = {}

        for row in MarriageStatus.select():
            age_from = row.age_from
            age_to = row.age_to
            # Filter categories is now handled in __init__
            probs = np.array([getattr(row, s) for s in self.categories], dtype=float)
            if probs.sum() == 0:
                continue  # skip if nothing left
            probs = probs / probs.sum()  # Normalize to 1
            probs = self.power_scaling_with_temperature(probs, self.temperature)
            for age in range(age_from, age_to + 1):
                self.age2probs[age] = dict(zip(self.categories, probs))

    def sample(self, age: int) -> str:
        if age not in self.age2probs:
            raise ValueError(f"No data for age {age}")
        probs_dict = self.age2probs[age]
        categories = list(probs_dict.keys())
        weights = np.array(list(probs_dict.values()))
        return np.random.choice(categories, p=weights)

    def sample_n(self, ages: list[int]) -> list[str]:
        results = []
        for age in ages:
            if age not in self.age2probs:
                raise ValueError(f"No data for age {age}")
            probs_dict = self.age2probs[age]
            categories = list(probs_dict.keys())
            weights = np.array(list(probs_dict.values()))
            results.append(np.random.choice(categories, p=weights))
        return results
