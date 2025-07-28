import unittest
from unittest.mock import mock_open, patch

from benchmark.repository.persona_reader import PersonaReader


class TestPersonaReader(unittest.TestCase):
    def setUp(self):
        self.csv_data = (
            "uuid,age,gender,education,occupation,marriage_status,migration_status,origin,religion,sexuality\n"
            "37bafb46-ae9a-4c08-a692-1916cc6df314,33,male,Fachhochschul- oder Hochschulreife,Friseur/in,single,with_migration,Afghanistan,Muslims,heterosexual\n"
            "2089c0c0-7308-44ef-996c-d11ef6041751,33,male,Fachhochschul- oder Hochschulreife,Erzieher/in,divorced,with_migration,Syrien,Muslims,heterosexual"
        )
        self.reader = PersonaReader(file_path="mock_personas.csv")

    def test_find_existing_persona(self):
        with patch("builtins.open", mock_open(read_data=self.csv_data)) as mock_file:
            persona = self.reader.find("37bafb46-ae9a-4c08-a692-1916cc6df314")
            self.assertIsNotNone(persona)
            self.assertEqual(persona.uuid, "37bafb46-ae9a-4c08-a692-1916cc6df314")
            self.assertEqual(persona.age, 33)

    def test_find_non_existing_persona(self):
        with patch("builtins.open", mock_open(read_data=self.csv_data)) as mock_file:
            persona = self.reader.find("non-existing-uuid")
            self.assertIsNone(persona)

    def test_find_all_personas(self):
        with patch("builtins.open", mock_open(read_data=self.csv_data)) as mock_file:
            personas = self.reader.find_all()
            self.assertEqual(len(personas), 2)
            self.assertEqual(personas[0].uuid, "37bafb46-ae9a-4c08-a692-1916cc6df314")
            self.assertEqual(personas[1].uuid, "2089c0c0-7308-44ef-996c-d11ef6041751")


if __name__ == "__main__":
    unittest.main()
