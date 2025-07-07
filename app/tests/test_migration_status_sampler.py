import unittest
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from persona_generator.sampler.migration_status_sampler import MigrationStatusSampler
from tests.test_sampler_base import TestSamplerBase

class TestMigrationStatusSampler(TestSamplerBase):
    def setUp(self):
        self.sampler = MigrationStatusSampler()
        self.sampler_T1 = MigrationStatusSampler(temperature=1.0)
        self.categories = self.sampler.categories

    def test_sample_n_returns_valid_categories(self):
        """Tests that sample_n() returns valid categories."""
        if not self.sampler:
            self.skipTest("Sampler not implemented.")
        ages = [25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
        genders = ["male", "female", "all", "diverse", "male", "female", "all", "diverse", "male", "female"]
        samples = self.sampler.sample_n(ages=ages, genders=genders)
        self.assertIsInstance(samples, list)
        for sample in samples:
            self.assertIn(sample, self.categories)

    def test_temperature_one_is_uniform(self):
        """Tests that T=1 results in a uniform distribution."""
        if not self.sampler_T1:
            self.skipTest("Sampler with T=1 not implemented.")
        ages = [25]*10000
        genders = ["male"]*10000
        samples = self.sampler_T1.sample_n(ages=ages, genders=genders)
        counts = {cat: samples.count(cat) for cat in self.categories}
        expected_count = 10000 / len(self.categories)
        for cat in self.categories:
            self.assertAlmostEqual(counts.get(cat, 0), expected_count, delta=500)

    def test_sample_returns_valid_category(self):
        """Tests that sample() returns a valid category for given age and gender."""
        if not self.sampler:
            self.skipTest("Sampler not implemented.")
        sample = self.sampler.sample(age=25, gender="male")
        self.assertIn(sample, self.categories)

if __name__ == '__main__':
    unittest.main()
