import unittest

import numpy as np


class TestSamplerBase(unittest.TestCase):
    def setUp(self):
        # This will be overridden by the derived test classes
        self.sampler = None
        self.sampler_T1 = None
        self.categories = []

    def test_sample_returns_valid_category(self):
        """Tests that sample() returns a valid category."""
        if not self.sampler:
            self.skipTest("Sampler not implemented.")

        # For samplers that require arguments for sampling
        try:
            sample = self.sampler.sample(age=25)  # Example age
        except TypeError:
            sample = self.sampler.sample()

        self.assertIn(sample, self.categories)

    def test_sample_n_returns_valid_categories(self):
        """Tests that sample_n() returns valid categories."""
        if not self.sampler:
            self.skipTest("Sampler not implemented.")

        # For samplers that require arguments for sampling
        try:
            samples = self.sampler.sample_n(ages=[25, 30])  # Example ages
        except TypeError:
            samples = self.sampler.sample_n(n=10)

        self.assertIsInstance(samples, list)
        for sample in samples:
            self.assertIn(sample, self.categories)

    def test_temperature_one_is_uniform(self):
        """Tests that T=1 results in a uniform distribution."""
        if not self.sampler_T1:
            self.skipTest("Sampler with T=1 not implemented.")

        # For samplers that require arguments for sampling
        try:
            samples = self.sampler_T1.sample_n(ages=[25] * 10000)  # Example age
        except TypeError:
            samples = self.sampler_T1.sample_n(n=10000)

        counts = {cat: samples.count(cat) for cat in self.categories}

        expected_count = 10000 / len(self.categories)

        for cat in self.categories:
            self.assertAlmostEqual(counts.get(cat, 0), expected_count, delta=500)
