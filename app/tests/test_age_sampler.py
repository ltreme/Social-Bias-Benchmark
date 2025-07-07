import unittest
import sys
import os
import numpy as np

# Add the app directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from persona_generator.sampler.age_sampler import AgeSampler
from tests.test_sampler_base import TestSamplerBase
from models.db import Age, db

class TestAgeSampler(TestSamplerBase):
    @classmethod
    def setUpClass(cls):
        # Connect to the database. Assumes it's populated.
        if db.is_closed():
            db.connect(reuse_if_open=True)

    @classmethod
    def tearDownClass(cls):
        if not db.is_closed():
            db.close()

    def setUp(self):
        """Set up the samplers for the tests."""
        self.sampler = AgeSampler(temperature=0.0)
        self.sampler_T1 = AgeSampler(temperature=1.0)
        self.categories = [age.age for age in Age.select()]

    def test_distribution_at_T0(self):
        """Tests that T=0 approximates the original distribution."""
        if not self.categories:
            self.skipTest("Database is not populated with age data.")

        samples = self.sampler.sample_n(10000)
        
        # Get original distribution from the database
        original_ages = list(Age.select())
        total_population = sum(a.total for a in original_ages)
        if total_population == 0:
            self.skipTest("Total population in age data is zero.")
            
        original_dist = {a.age: a.total / total_population for a in original_ages}

        # Calculate distribution of the samples
        sample_dist = {age: samples.count(age) / 10000 for age in self.categories}

        # Compare distributions
        for age in self.categories:
            self.assertAlmostEqual(sample_dist.get(age, 0), original_dist.get(age, 0), delta=0.05)

    def test_age_range_filter(self):
        """Tests the age_min and age_max filters."""
        min_age, max_age = 20, 40
        ranged_sampler = AgeSampler(age_min=min_age, age_max=max_age)
        samples = ranged_sampler.sample_n(100)
        
        for sample in samples:
            self.assertTrue(min_age <= sample <= max_age)

if __name__ == '__main__':
    unittest.main()
