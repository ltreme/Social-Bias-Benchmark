from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "apps" / "backend" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

TEST_DIR = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.append(str(TEST_DIR))

from test_sampler_base import TestSamplerBase  # noqa: E402

from backend.domain.persona.persona_generator.sampler.sexuality_sampler import (  # noqa: E402
    SexualityEnum,
    SexualitySampler,
)


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
