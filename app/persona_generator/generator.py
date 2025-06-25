import os
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from dataclasses import fields
from models.persona import Persona
from .name_sampler import NameSampler
import logging

# In this file the PersonaGenerator and DistributionLoader will be implemented.

class DistributionLoader:
    """Loads attribute distributions from CSV files."""

    def __init__(self, distributions_path: str):
        self.distributions_path = distributions_path
        self.occupation_data = self._load_occupation_distribution()
        logging.info(f"DistributionLoader initialized with path: {distributions_path}")

    def _load_generic_distribution(self, attribute_name: str) -> Dict[str, float]:
        """Loads a simple key-weight distribution from a CSV file."""
        file_path = os.path.join(self.distributions_path, f"{attribute_name}.csv")
        if not os.path.exists(file_path):
            logging.error(f"Distribution file not found: {file_path}")
            raise FileNotFoundError(f"Distribution file not found: {file_path}")
        df = pd.read_csv(file_path)
        weights = df['weight'].values
        # Normalize weights to prevent sum errors
        normalized_weights = weights / np.sum(weights)
        return pd.Series(normalized_weights, index=df.iloc[:, 0]).to_dict()

    def _load_occupation_distribution(self) -> pd.DataFrame:
        """Loads the structured occupation distribution."""
        file_path = os.path.join(self.distributions_path, "occupation.csv")
        if not os.path.exists(file_path):
            logging.error(f"Distribution file not found: {file_path}")
            raise FileNotFoundError(f"Distribution file not found: {file_path}")
        df = pd.read_csv(file_path)
        # Normalize weights
        df['weight'] = df['weight'] / df['weight'].sum()
        return df

    def load_all_distributions(self) -> Dict[str, Any]:
        """Loads all available attribute distributions from the directory."""
        distributions = {'occupation': self.occupation_data}
        for filename in os.listdir(self.distributions_path):
            if filename.endswith(".csv") and filename != "occupation.csv":
                attribute_name = os.path.splitext(filename)[0]
                try:
                    distributions[attribute_name] = self._load_generic_distribution(attribute_name)
                except Exception as e:
                    logging.warning(f"Could not load distribution for {attribute_name}: {e}")
        return distributions

class PersonaGenerator:
    """Generates synthetic personas based on configured distributions."""

    MAX_AGE: int = 90  # Avoid magic number

    def __init__(self, distributions_path: str, name_sampler: NameSampler):
        self.dist_loader = DistributionLoader(distributions_path)
        self.distributions = self.dist_loader.load_all_distributions()
        self.name_sampler = name_sampler
        self.occupation_data = self.distributions.pop('occupation')
        logging.info("PersonaGenerator initialized.")

    def _sample_attribute(self, attribute_name: str) -> Any:
        """Samples a single independent attribute value based on its distribution."""
        distribution = self.distributions.get(attribute_name, None)
        if not distribution:
            logging.error(f"No distribution found for attribute: {attribute_name}")
            raise ValueError(f"No distribution found for attribute: {attribute_name}")
        options = list(distribution.keys())
        weights = list(distribution.values())
        return np.random.choice(options, p=weights)

    def _generate_single_persona(self) -> Persona:
        """Generates a single persona instance with attribute correlations."""
        attributes = {}
        # 1. Sample age_group and then a specific age
        attributes['age_group'] = self._sample_attribute('age_group')
        attributes['age'] = self._sample_age_from_group(attributes['age_group'])
        # 2. Filter and sample occupation based on age
        valid_occupations = self.occupation_data[
            (self.occupation_data['min_age'] <= attributes['age']) &
            (self.occupation_data['max_age'] >= attributes['age'])
        ].copy()
        if valid_occupations.empty:
            logging.error(f"No valid occupation found for age {attributes['age']}. Check distributions.")
            raise ValueError(f"No valid occupation found for age {attributes['age']}. Check distributions.")
        occ_weights = valid_occupations['weight'].values
        valid_occupations['weight'] = occ_weights / np.sum(occ_weights)
        sampled_occupation_row = valid_occupations.sample(weights=valid_occupations['weight']).iloc[0]
        attributes['occupation'] = sampled_occupation_row['occupation']
        # 3. Sample SES based on the occupation's SES profile
        ses_profile = [s.strip() for s in sampled_occupation_row['ses_profile'].split(',')]
        if 'ses' in self.distributions:
            ses_weights = [self.distributions['ses'].get(s, 0) for s in ses_profile]
            total_weight = sum(ses_weights)
            if total_weight > 0:
                normalized_ses_weights = [w / total_weight for w in ses_weights]
                attributes['ses'] = np.random.choice(ses_profile, p=normalized_ses_weights)
            else:
                attributes['ses'] = np.random.choice(ses_profile)
        else:
            attributes['ses'] = np.random.choice(ses_profile)
        # 4. Sample remaining independent attributes
        independent_attributes = ['gender', 'origin', 'religion', 'appearance']
        for attr in independent_attributes:
            if attr in self.distributions:
                attributes[attr] = self._sample_attribute(attr)
            else:
                logging.warning(f"No distribution for attribute: {attr}, setting to None.")
                attributes[attr] = None
        # 5. Get name from name sampler
        attributes['name'] = self.name_sampler.sample_name(
            gender=attributes.get('gender'),
            origin=attributes.get('origin'),
            age_group=attributes.get('age_group')
        )
        # Ensure all required fields for Persona constructor are present
        for f in fields(Persona):
            if f.init and f.name not in attributes:
                logging.warning(f"Missing attribute {f.name}, setting to None.")
                attributes[f.name] = None
        init_field_names = {f.name for f in fields(Persona) if f.init}
        constructor_attributes = {k: v for k, v in attributes.items() if k in init_field_names}
        return Persona(**constructor_attributes)

    def _sample_age_from_group(self, age_group: str) -> int:
        """Samples a specific age from a given age group string (e.g., '18-29')."""
        if age_group.endswith('+'):
            min_age = int(age_group[:-1])
            return np.random.randint(min_age, self.MAX_AGE + 1)
        try:
            min_age, max_age = map(int, age_group.split('-'))
            return np.random.randint(min_age, max_age + 1)
        except ValueError:
            logging.error(f"Invalid age group format: {age_group}")
            raise ValueError(f"Invalid age group format: {age_group}")

    def generate_personas(self, num_personas: int) -> List[Persona]:
        """Generates a specified number of personas."""
        np.random.seed(42)  # Für Testbarkeit, ggf. als Argument übergeben
        return [self._generate_single_persona() for _ in range(num_personas)]

    @staticmethod
    def to_dataframe(personas: List[Persona]) -> pd.DataFrame:
        """Converts a list of Persona objects to a pandas DataFrame."""
        return pd.DataFrame([p.__dict__ for p in personas])

# Logging-Konfiguration (kann auch in main.py erfolgen)
logging.basicConfig(level=logging.INFO)
