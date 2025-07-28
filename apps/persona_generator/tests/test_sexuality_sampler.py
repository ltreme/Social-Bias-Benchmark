import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import numpy as np

from persona_generator.sampler.sexuality_sampler import SexualityEnum, SexualitySampler
from tests.test_sampler_base import TestSamplerBase


class TestSexualitySampler(TestSamplerBase):
    def setUp(self):
        self.sampler = SexualitySampler(temperature=0.0)
        self.sampler_T1 = SexualitySampler(temperature=1.0)
        self.categories = [e.value for e in SexualityEnum]

    def test_distribution_at_T0(self):
        # Testet, ob die Verteilung bei T=0 ungefähr den Konstanten entspricht
        sampler = SexualitySampler(temperature=0.0)
        n = 10000
        samples = sampler.sample_n(n)
        counts = {cat: samples.count(cat) for cat in self.categories}
        probs = np.array([98.1, 1.2, 0.7]) / 100
        for i, cat in enumerate(self.categories):
            self.assertAlmostEqual(counts[cat] / n, probs[i], delta=0.02)

    def test_exclude(self):
        # Testet, ob ausgeschlossene Sexualitäten nicht gezogen werden
        exclude = [SexualityEnum.BISEXUAL.value]
        sampler = SexualitySampler(exclude=exclude)
        samples = sampler.sample_n(100)
        for s in samples:
            self.assertNotEqual(s, SexualityEnum.BISEXUAL.value)
        self.assertTrue(
            set(samples).issubset(
                {SexualityEnum.HETEROSEXUAL.value, SexualityEnum.HOMOSEXUAL.value}
            )
        )


if __name__ == "__main__":
    unittest.main()
