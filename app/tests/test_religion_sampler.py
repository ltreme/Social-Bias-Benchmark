import unittest
import sys
import os
import numpy as np

# Add the app directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from persona_generator.sampler.religion_sampler import ReligionSampler
from models.db import ReligionPerCountry, Country

class TestReligionSampler(unittest.TestCase):
    def setUp(self):
        self.sampler = ReligionSampler()
        self.sampler_T1 = ReligionSampler(temperature=1.0)

    def _get_religions_for_country(self, country_de: str) -> list[str]:
        """Helper to get all valid religions for a country from the DB."""
        query = (ReligionPerCountry
                 .select(ReligionPerCountry.religion)
                 .join(Country)
                 .where((Country.country_de == country_de) & (ReligionPerCountry.total > 0)))
        return [row.religion for row in query]

    def test_sample_returns_valid_religion(self):
        """Tests that sample() returns a valid religion for a known country."""
        country = "Deutschland"
        valid_religions = self._get_religions_for_country(country)
        religion = self.sampler.sample(country)
        self.assertIn(religion, valid_religions)

    def test_sample_n_returns_valid_religions(self):
        """Tests that sample_n() returns a list of valid religions."""
        countries = ["Deutschland", "Frankreich"]
        results = self.sampler.sample_n(countries)
        self.assertEqual(len(results), len(countries))
        for i, religion in enumerate(results):
            valid_religions = self._get_religions_for_country(countries[i])
            self.assertIn(religion, valid_religions)

    def test_fallback_for_unknown_country(self):
        """Tests that the sampler returns a fallback for an unknown country."""
        country = "Fantasiland"
        religion = self.sampler.sample(country)
        self.assertEqual(religion, "Religiously_unaffiliated")

    def test_temperature_one_is_uniform(self):
        """Tests that T=1 results in a uniform distribution for a given country."""
        country = "Deutschland"
        country_religions = self._get_religions_for_country(country)
        num_religions = len(country_religions)
        
        if num_religions == 0:
            self.skipTest(f"No religion data for {country} to test uniform distribution.")

        num_samples = 10000
        samples = [self.sampler_T1.sample(country) for _ in range(num_samples)]
        
        counts = {religion: samples.count(religion) for religion in country_religions}
        expected_count = num_samples / num_religions
        
        # Check if the distribution is approximately uniform
        for religion in country_religions:
            self.assertAlmostEqual(counts.get(religion, 0), expected_count, delta=num_samples*0.05) # 5% delta

if __name__ == '__main__':
    unittest.main()
