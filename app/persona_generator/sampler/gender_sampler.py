from persona_generator.sampler.sampler import Sampler
import numpy as np
from models.db import Age

class GenderSampler(Sampler):

    def __init__(self, temperature: float = 0.0, exclude: list = None):
        self.exclude = set(exclude) if exclude else set()
        super().__init__(temperature)

    def _prepare(self):
        self.gender_probs = {}
        # Bestimme, welche Geschlechter verwendet werden sollen
        all_genders = {"male", "female", "diverse"}
        used_genders = list(all_genders - self.exclude)
        used_genders.sort()  # Für konsistente Reihenfolge
        # Hole alle Altersdatensätze
        for age_row in Age.select():
            age = age_row.age
            counts = {g: getattr(age_row, g) for g in used_genders}
            total = sum(counts.values())
            if total > 0:
                probs = np.array(list(counts.values()), dtype=float)
                probs = probs / probs.sum()
                probs = self.power_scaling_with_temperature(probs, self.temperature)
                self.gender_probs[age] = dict(zip(counts.keys(), probs))

    def sample(self, age: int) -> str:
        """Sample a gender for a given age."""
        if age not in self.gender_probs:
            raise ValueError(f"No gender data for age {age}.")
        probs_dict = self.gender_probs[age]
        genders = list(probs_dict.keys())
        weights = np.array(list(probs_dict.values()))
        return np.random.choice(genders, p=weights)

    def sample_n(self, ages: list[int]) -> list[str]:
        """
        Efficiently sample genders for a list of ages using numpy.
        Returns a list of sampled genders in the same order as ages.
        """
        ages = np.array(ages)
        unique_ages, inverse_indices = np.unique(ages, return_inverse=True)

        # Pre-sample for each unique age
        sampled_map = {}
        for age in unique_ages:
            if age not in self.gender_probs:
                raise ValueError(f"No gender data for age {age}.")
            probs_dict = self.gender_probs[age]
            genders = np.array(list(probs_dict.keys()))
            weights = np.array(list(probs_dict.values()))
            count = np.sum(ages == age)
            sampled_map[age] = np.random.choice(genders, size=count, p=weights)

        # Map samples back to input order
        pointers = {age: 0 for age in unique_ages}
        result = []
        for age in ages:
            idx = pointers[age]
            result.append(sampled_map[age][idx])
            pointers[age] += 1
        return result

