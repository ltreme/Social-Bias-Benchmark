import csv
import os
from pathlib import Path


class TranslatorService:
    def __init__(self, csv_path: str = None):
        if csv_path is None:
            # Determine repository root relative to this file
            repo_root = Path(__file__).resolve().parents[6]
            csv_path = repo_root / "lang" / "de.csv"
        self.translations = {}
        try:
            self._load_translations(csv_path)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Translations file not found at {csv_path}. "
                "Ensure 'lang/de.csv' exists in the repository root."
            )

    def _load_translations(self, csv_path):
        with open(csv_path, encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                self.translations[row["key"]] = row["value"]

    def translate(self, key: str) -> str:
        return self.translations.get(key, key)  # fallback: original value
