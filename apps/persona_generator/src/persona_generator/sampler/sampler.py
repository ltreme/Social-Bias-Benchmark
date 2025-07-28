from abc import ABC, abstractmethod

import numpy as np


class Sampler(ABC):

    def __init__(self, temperature: float = 0.0):
        self.temperature = temperature
        self._prepare()

    @abstractmethod
    def _prepare(self):
        """Subclasses prepare data (called in __init__)."""

    @abstractmethod
    def sample(self, *args, **kwargs):
        pass

    @abstractmethod
    def sample_n(self, *args, **kwargs):
        pass

    @staticmethod
    def power_scaling(weights: np.ndarray, alpha: float):
        scaled = weights**alpha
        return scaled / scaled.sum()

    def power_scaling_with_temperature(self, w: np.ndarray, T: float):
        return self.power_scaling(w, 1 - T)
