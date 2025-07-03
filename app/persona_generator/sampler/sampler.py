from abc import ABC, abstractmethod
import pandas as pd

class Sampler(ABC):
    required_columns = []

    def __init__(self, df: pd.DataFrame, temperature: float = 0.0):
        self.df = df
        self.temperature = temperature
        self.validate_df()
        self._prepare()

    def validate_df(self):
        missing = set(self.required_columns) - set(self.df.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")

    @abstractmethod
    def _prepare(self):
        """Subclasses prepare data (called in __init__)."""
        pass

    @abstractmethod
    def sample(self, *args, **kwargs):
        pass

    @abstractmethod
    def sample_n(self, *args, **kwargs):
        pass

    @staticmethod
    def power_scaling(weights, alpha):
        scaled = weights ** alpha
        return scaled / scaled.sum()

    def power_scaling_with_temperature(self, w, T):
        return self.power_scaling(w, 1 - T)
