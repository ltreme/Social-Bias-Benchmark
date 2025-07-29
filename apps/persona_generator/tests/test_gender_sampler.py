import os
import sys
import unittest

import numpy as np

# Add the app directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from persona_generator.models.db import Age, db
from persona_generator.sampler.gender_sampler import GenderSampler
from tests.test_sampler_base import TestSamplerBase


class TestGenderSampler(TestSamplerBase):
    @classmethod
    def setUpClass(cls):
        if db.is_closed():
            db.connect(reuse_if_open=True)

    @classmethod
    def tearDownClass(cls):
        if not db.is_closed():
            db.close()

    def setUp(self):
        """Set up the samplers for the tests."""
        self.sampler = GenderSampler(temperature=0.0)
        self.sampler_T1 = GenderSampler(temperature=1.0)
        self.categories = ["male", "female", "diverse"]

    def test_distribution_at_T0_for_age(self):
        """Tests that T=0 approximates the original distribution for a given age."""
        test_age = 30  # An example age

        age_data = Age.get_or_none(Age.age == test_age)
        if not age_data:
            self.skipTest(f"No age data in DB for age {test_age}.")

        samples = self.sampler.sample_n(ages=[test_age] * 10000)

        total_for_age = age_data.male + age_data.female + age_data.diverse
        if total_for_age == 0:
            self.skipTest(f"Total population for age {test_age} is zero.")

        original_dist = {
            "male": age_data.male / total_for_age,
            "female": age_data.female / total_for_age,
            "diverse": age_data.diverse / total_for_age,
        }

        sample_dist = {
            gender: samples.count(gender) / 10000 for gender in self.categories
        }

        for gender in self.categories:
            self.assertAlmostEqual(
                sample_dist.get(gender, 0), original_dist.get(gender, 0), delta=0.05
            )

    def test_exclude_gender(self):
        """Tests the exclude parameter."""
        excluded_gender = "diverse"
        sampler_with_exclude = GenderSampler(exclude=[excluded_gender])

        samples = sampler_with_exclude.sample_n(ages=[30] * 100)

        for sample in samples:
            self.assertNotEqual(sample, excluded_gender)

        remaining_genders = set(self.categories) - {excluded_gender}
        self.assertTrue(remaining_genders.issubset(set(samples)))


if __name__ == "__main__":
    unittest.main()
