import unittest
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from persona_generator.sampler.origin_sampler import OriginSampler

GERMANY = "Deutschland"

class TestOriginSampler(unittest.TestCase):
    def test_exclude_countries(self):
        # Wähle ein Land aus der Liste, das ausgeschlossen werden soll
        if len(self.countries) > 0:
            exclude_country = self.countries[0]
            sampler_exclude = OriginSampler(exclude=[exclude_country])
            # Die Länder-Liste sollte das ausgeschlossene Land nicht enthalten
            self.assertNotIn(exclude_country, sampler_exclude.countries)
            # Es sollte niemals gesampelt werden
            samples = [sampler_exclude.sample(True) for _ in range(100)]
            self.assertNotIn(exclude_country, samples)
    def setUp(self):
        self.sampler = OriginSampler()
        self.sampler_T1 = OriginSampler(temperature=1.0)
        self.countries = self.sampler.countries

    def test_sample_returns_germany_without_migration(self):
        self.assertEqual(self.sampler.sample(False), GERMANY)

    def test_sample_returns_country_with_migration(self):
        country = self.sampler.sample(True)
        self.assertIn(country, self.countries)

    def test_sample_n_mixed(self):
        has_migrations = [False, True, False, True]
        results = self.sampler.sample_n(has_migrations)
        self.assertEqual(results[0], GERMANY)
        self.assertIn(results[1], self.countries)
        self.assertEqual(results[2], GERMANY)
        self.assertIn(results[3], self.countries)

    def test_temperature_one_is_uniform(self):
        # At T=1, the selection of countries should be approximately uniform
        sampler_T1 = OriginSampler(temperature=1.0)
        samples = [sampler_T1.sample(True) for _ in range(10000)]
        counts = {c: samples.count(c) for c in self.countries}
        expected = 10000 / len(self.countries)
        for c in self.countries:
            self.assertAlmostEqual(counts[c], expected, delta=500)

if __name__ == '__main__':
    unittest.main()
