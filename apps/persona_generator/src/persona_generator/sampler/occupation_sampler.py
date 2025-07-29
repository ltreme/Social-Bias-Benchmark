import numpy as np

from persona_generator.models.db import Occupation
from persona_generator.sampler.sampler import Sampler


class OccupationSampler(Sampler):
    def __init__(self, exclude=None):
        self.exclude_categories = set(exclude) if exclude else set()
        super().__init__(temperature=0.0)

    def _prepare(self):
        # Map: age -> list of occupation rows (dicts)
        self.occupation_by_age = {}
        for occ in Occupation.select():
            if occ.category in self.exclude_categories:
                continue
            for age in range(occ.age_from, occ.age_to + 1):
                self.occupation_by_age.setdefault(age, []).append(occ)

    def sample(self, age: int) -> str:
        if age > 67:
            return "Rentner/in"
        jobs = self.occupation_by_age.get(age, [])
        if not jobs:
            return "Arbeitslos"
        occ = np.random.choice(jobs)
        return occ.job_de

    def sample_n(self, ages: list[int]) -> list[str]:
        result = []
        for age in ages:
            result.append(self.sample(age))
        return result
