import numpy as np

from backend.infrastructure.storage.models import MigrationStatus

from .sampler import Sampler


class MigrationStatusSampler(Sampler):
    def __init__(self, temperature: float = 0.0, exclude: list = None):
        self.exclude = set(exclude) if exclude else set()
        all_statuses = ["with_migration", "without_migration"]
        self.categories = [s for s in all_statuses if s not in self.exclude]
        super().__init__(temperature)

    def _prepare(self):
        # Mapping: (age, gender_db) -> dict of status: probability
        self.age_gender2probs = {}
        for row in MigrationStatus.select():
            age_from = row.age_from
            age_to = row.age_to
            gender_db = row.gender  # "männlich", "weiblich", "Insgesamt"
            probs = np.array([getattr(row, s) for s in self.categories], dtype=float)
            if probs.sum() == 0:
                continue
            probs = probs / probs.sum()
            probs = self.power_scaling_with_temperature(probs, self.temperature)
            for age in range(age_from, age_to + 1):
                self.age_gender2probs[(age, gender_db)] = dict(
                    zip(self.categories, probs)
                )

    def _map_gender(self, gender: str) -> str:
        if gender not in ["male", "female"]:
            return "all"
        return gender

    def sample(self, age: int, gender: str) -> str:
        gender_db = self._map_gender(gender)
        key = (age, gender_db)
        if key not in self.age_gender2probs:
            raise ValueError(f"No data for age {age} and gender {gender_db}")
        probs_dict = self.age_gender2probs[key]
        categories = list(probs_dict.keys())
        weights = np.array(list(probs_dict.values()))
        return np.random.choice(categories, p=weights)

    def sample_n(self, ages: list[int], genders: list[str]) -> list[str]:
        if len(ages) != len(genders):
            raise ValueError("ages and genders must have the same length")
        results = []
        for age, gender in zip(ages, genders):
            results.append(self.sample(age, gender))
        return results
