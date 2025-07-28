import unittest

from persona_generator.models.db import Occupation, db
from persona_generator.sampler.occupation_sampler import OccupationSampler
from tests.test_sampler_base import TestSamplerBase


class TestOccupationSampler(TestSamplerBase):
    @classmethod
    def setUpClass(cls):
        if db.is_closed():
            db.connect(reuse_if_open=True)

    @classmethod
    def tearDownClass(cls):
        if not db.is_closed():
            db.close()

    def setUp(self):
        self.sampler = OccupationSampler()
        # T=1 ist für diesen Sampler nicht relevant, aber für Kompatibilität:
        self.sampler_T1 = self.sampler
        # Alle Berufe für ein Beispielalter (z.B. 30), plus "Rentner/in"
        age = 30
        jobs_for_age = [
            occ.job_de
            for occ in Occupation.select().where(
                (Occupation.age_from <= age) & (Occupation.age_to >= age)
            )
        ]
        self.categories = jobs_for_age + ["Rentner/in"]

    def test_sample_returns_rentner_for_old_age(self):
        age = 70
        job = self.sampler.sample(age)
        self.assertEqual(job, "Rentner/in")

    def test_exclude_categories(self):
        exclude = ["Gesundheit", "IT"]
        sampler = OccupationSampler(exclude=exclude)
        age = 30
        for _ in range(20):
            job = sampler.sample(age)
            occ = Occupation.select().where(Occupation.job_de == job).first()
            self.assertNotIn(occ.category, exclude)


if __name__ == "__main__":
    unittest.main()
