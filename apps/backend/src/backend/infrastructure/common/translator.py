import csv
import os
from pathlib import Path


class TranslatorService:
    def __init__(self, csv_path: str = None):
        if csv_path is None:
            # Get the repository root by going up from this file's location
            repo_root = Path(__file__).parent.parent.parent.parent.parent.parent
            csv_path = repo_root / "lang" / "de.csv"
        self.translations = {}
        self._load_translations(csv_path)

    def _load_translations(self, csv_path):
        with open(csv_path, encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                self.translations[row["key"]] = row["value"]

    def translate(self, key: str) -> str:
        return self.translations.get(key, key)  # fallback: original value
