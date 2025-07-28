import numpy as np
from models.db import Education

from .sampler import Sampler


class EducationSampler(Sampler):
    def __init__(self, temperature: float = 0.0, exclude: list = None):
        self.exclude = set(exclude) if exclude else set()
        super().__init__(temperature)

    def _map_gender(self, gender: str) -> str:
        if gender not in ["male", "female"]:
            return "all"
        return gender

    def _prepare(self):
        # Build mapping: (age, gender) -> {education_level: value}
        self.age_gender2levels = {}
        for row in Education.select():
            for age in range(row.age_from, row.age_to + 1):
                gender = row.gender
                if (age, gender) not in self.age_gender2levels:
                    self.age_gender2levels[(age, gender)] = {}
                self.age_gender2levels[(age, gender)][row.education_level] = row.value

    def sample(self, age: int, gender: str) -> str:
        gender_db = self._map_gender(gender)
        key = (age, gender_db)
        if key not in self.age_gender2levels:
            return "Unknown"  # Default value if no data is available
        levels = {
            k: v
            for k, v in self.age_gender2levels[key].items()
            if k not in self.exclude
        }
        if not levels:
            return "Unknown"  # Default value if no data is available
        values = np.array(list(levels.values()), dtype=float)
        values = values / values.sum()
        values = self.power_scaling_with_temperature(values, self.temperature)
        return np.random.choice(list(levels.keys()), p=values)

    def sample_n(self, ages: list[int], genders: list[str]) -> list[str]:
        if len(ages) != len(genders):
            raise ValueError("ages and genders must have the same length")
        return [self.sample(age, gender) for age, gender in zip(ages, genders)]
