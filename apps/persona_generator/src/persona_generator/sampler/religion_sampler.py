import numpy as np

from shared.storage.models import Country, ReligionPerCountry

from .sampler import Sampler


class ReligionSampler(Sampler):
    def __init__(self, temperature: float = 0.0, exclude: list = None):
        self.exclude = exclude
        super().__init__(temperature)

    def _prepare(self):
        """
        This method is intentionally left empty.
        Data is fetched on-the-fly in the sample() method.
        """

    def sample(self, country_de: str) -> str:
        query = (
            ReligionPerCountry.select(
                ReligionPerCountry.religion, ReligionPerCountry.total
            )
            .join(Country)
            .where(Country.country_de == country_de)
        )

        if not query.exists():
            return "Religiously_unaffiliated"

        religions = []
        totals = []
        exclude_set = set(self.exclude) if self.exclude else set()
        for row in query:
            if row.religion in exclude_set:
                continue
            religions.append(row.religion)
            totals.append(row.total)

        probabilities = np.array(totals, dtype=float)

        # Filter out religions with zero probability
        non_zero_mask = probabilities > 0
        if not np.any(non_zero_mask):
            return "Religiously_unaffiliated"

        religions = np.array(religions)[non_zero_mask]
        probabilities = probabilities[non_zero_mask]

        # Normalize to a probability distribution
        if probabilities.sum() > 0:
            probabilities = probabilities / probabilities.sum()
        else:
            # This case should not be reached due to the non_zero_mask check, but as a safeguard:
            return "Religiously_unaffiliated"

        # Apply temperature scaling
        if self.temperature > 0 and len(probabilities) > 1:
            probabilities = self.power_scaling_with_temperature(
                probabilities, self.temperature
            )

        return np.random.choice(religions, p=probabilities)

    def sample_n(self, country_des: list[str]) -> list[str]:
        return [self.sample(country) for country in country_des]
