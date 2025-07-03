from persona_generator.sampler.sampler import Sampler
import pandas as pd
import numpy as np

class GenderSampler(Sampler):
    required_columns = ["age", "male_adjusted", "female_adjusted", "diverse"]

    def __init__(self, df: pd.DataFrame, temperature: float = 0.0, exclude: list = None):
        self.exclude = set(exclude) if exclude else set()
        super().__init__(df, temperature)

    def _prepare(self):
        self.gender_probs = {}
        for _, row in self.df.iterrows():
            age = int(row["age"])
            counts = {
                "male": row["male_adjusted"],
                "female": row["female_adjusted"],
                "diverse": row["diverse"]
            }
            # Remove excluded genders
            for gender in self.exclude:
                counts.pop(gender, None)
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

