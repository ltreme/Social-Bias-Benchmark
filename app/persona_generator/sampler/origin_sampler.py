import numpy as np
from .sampler import Sampler
from models.db import ForeignCountry

GERMANY = "Deutschland"

class OriginSampler(Sampler):
    def __init__(self, temperature: float = 0.0):
        super().__init__(temperature)

    def _prepare(self):
        self.countries = []
        self.values = []
        for row in ForeignCountry.select():
            self.countries.append(row.country)
            self.values.append(row.value)
        self.values = np.array(self.values, dtype=float)
        if self.values.sum() > 0:
            self.values = self.values / self.values.sum()
        self.values = self.power_scaling_with_temperature(self.values, self.temperature)

    def sample(self, has_migration: bool) -> str:
        if not has_migration:
            return GERMANY
        return np.random.choice(self.countries, p=self.values)

    def sample_n(self, has_migrations: list[bool]) -> list[str]:
        return [self.sample(hm) for hm in has_migrations]
