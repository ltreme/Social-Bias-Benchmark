import os
import sys
import unittest

# Add the app directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from persona_generator.sampler.education_sampler import EducationSampler
from tests.test_sampler_base import TestSamplerBase


class TestEducationSampler(TestSamplerBase):
    def setUp(self):
        self.sampler = EducationSampler()
        self.sampler_T1 = EducationSampler(temperature=1.0)
        # Use a typical age/gender combination to get categories
        try:
            self.categories = list(self.sampler.age_gender2levels[(18, "male")].keys())
        except Exception:
            self.categories = []

    def test_sample_n_returns_valid_categories(self):
        if not self.sampler:
            self.skipTest("Sampler not implemented.")
        ages = [18, 20, 22, 24, 26, 28, 30, 32, 34, 36]
        genders = [
            "male",
            "female",
            "all",
            "diverse",
            "male",
            "female",
            "all",
            "diverse",
            "male",
            "female",
        ]
        samples = self.sampler.sample_n(ages=ages, genders=genders)
        self.assertIsInstance(samples, list)
        for sample in samples:
            self.assertIn(sample, self.categories)

    def test_temperature_one_is_uniform(self):
        if not self.sampler_T1:
            self.skipTest("Sampler with T=1 not implemented.")
        ages = [18] * 10000
        genders = ["male"] * 10000
        samples = self.sampler_T1.sample_n(ages=ages, genders=genders)
        counts = {cat: samples.count(cat) for cat in self.categories}
        expected_count = 10000 / len(self.categories)
        for cat in self.categories:
            self.assertAlmostEqual(counts.get(cat, 0), expected_count, delta=500)

    def test_sample_returns_valid_category(self):
        if not self.sampler:
            self.skipTest("Sampler not implemented.")
        sample = self.sampler.sample(age=18, gender="male")
        self.assertIn(sample, self.categories)


if __name__ == "__main__":
    unittest.main()
