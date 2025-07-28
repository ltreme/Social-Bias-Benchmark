import os
import sys
import unittest

# Add the app directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from persona_generator.sampler.marriage_status_sampler import MarriageStatusSampler
from tests.test_sampler_base import TestSamplerBase


class TestMarriageStatusSampler(TestSamplerBase):
    def setUp(self):
        self.sampler = MarriageStatusSampler()
        self.sampler_T1 = MarriageStatusSampler(temperature=1.0)
        self.categories = self.sampler.categories


if __name__ == "__main__":
    unittest.main()
