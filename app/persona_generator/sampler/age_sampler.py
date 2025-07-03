from persona_generator.sampler.sampler import Sampler
import pandas as pd
import numpy as np

class AgeSampler(Sampler):
    required_columns = ["age", "total"]

    def __init__(self, df: pd.DataFrame, age_min: int = None, age_max: int = None, temperature: float = 0.0):
        self.age_min = age_min
        self.age_max = age_max
        super().__init__(df, temperature)

    def _prepare(self):
        # Filter by age range if given
        df = self.df
        if self.age_min is not None:
            df = df[df["age"] >= self.age_min]
        if self.age_max is not None:
            df = df[df["age"] <= self.age_max]
        # Prepare distributions
        weights = df["total"].values.astype(float)
        weights = self.power_scaling_with_temperature(weights, self.temperature)
        self.ages = df["age"].values
        self.weights = weights

    def sample(self) -> int:
        """Sample one age."""
        return np.random.choice(self.ages, p=self.weights)

    def sample_n(self, n: int) -> list[int]:
        """Sample n ages."""
        return np.random.choice(self.ages, size=n, p=self.weights).tolist()
