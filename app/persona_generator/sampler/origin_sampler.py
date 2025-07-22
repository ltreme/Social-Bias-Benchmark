import numpy as np
from .sampler import Sampler
from models.db import ForeignersPerCountry, Country

GERMANY = "Deutschland"

class OriginSampler(Sampler):
    def __init__(self, temperature: float = 0.0, exclude: list = None):
        self.exclude = exclude
        super().__init__(temperature)

    def _prepare(self):
        self.countries = []
        self.values = []
        result = (ForeignersPerCountry
            .select(ForeignersPerCountry, Country)
            .join(Country))
        exclude_set = set(self.exclude) if self.exclude else set()
        for row in result:
            country_name = row.country.country_de
            if country_name in exclude_set:
                continue
            self.countries.append(country_name)
            self.values.append(row.total)
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
