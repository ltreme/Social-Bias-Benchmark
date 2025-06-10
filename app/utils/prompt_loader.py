import pandas as pd
from typing import Callable, Any, List
import os
import sys
from models.case import Case
from models.persona import Persona

def generate_likert_5(adjective: str) -> list[str]:
    return [
        f"gar nicht {adjective}",
        f"eher nicht {adjective}",
        "neutral",
        f"eher {adjective}",
        f"sehr {adjective}"
    ]

class LikertPrompt:
    def __init__(self, id: str, scenario: str, question: str, adjective: str):
        self.id = id
        self.scenario = scenario
        self.question = question
        self.adjective = adjective
        self.likert_scale = generate_likert_5(adjective)

    def generate_prompt(self, likert_reverse: bool = False) -> str:
        """
        Generates a prompt for the Likert scale question.
        Returns:
            str: The formatted prompt.
        """
        if likert_reverse:
            self.likert_scale = self.likert_scale[::-1]
        return (
            f"{self.scenario}\n\n{self.question}\n\nBitte wähle eine Antwort aus der folgenden Skala:\n"
            + "\n".join(f"{i+1}. {option}" for i, option in enumerate(self.likert_scale))
            + "\n\n"
        )
    
    def __str__(self) -> str:
        """
        Returns a string representation of the LikertPrompt.
        Returns:
            str: The string representation.
        """
        return f"LikertPrompt(id={self.id}, scenario={self.scenario}, question={self.question}, adjective={self.adjective})"
    
def load_prompts_from_file(file_path: str) -> list[LikertPrompt]:
    df = pd.read_csv(file_path)
    prompts = []
    for _, row in df.iterrows():
        prompt = LikertPrompt(
            pretest_id=row["pretest_id"],
            scenario=row["scenario"],
            question=row["question"],
            adjective=row["adjective"]
        )
        prompts.append(prompt)
    return prompts

def load_objects_from_csv(path: str, object_factory: Callable[[Any], Any], id_col: int = 0) -> List[Any]:
    """
    General loader for objects from a CSV file.
    :param path: Path to the CSV file.
    :param object_factory: Function that converts a row to an object.
    :param id_col: Optional index column name.
    :return: List of instantiated objects.
    """
    if not os.path.exists(path):
        print(f"Error: The file {path} does not exist.")
        sys.exit(1)
    if not os.path.isfile(path):
        print(f"Error: The path {path} is not a file.")
        sys.exit(1)
    rows = pd.read_csv(path, index_col=id_col)
    return [object_factory(idx, row) for idx, row in rows.iterrows()]

# Beispiel-Factories:
def case_factory(id, row):
    return Case(id, row['case_template'], row['question'], row['adjective'])

def persona_factory(id, row):
    return Persona(id, row['name'], row['gender'], row['age'], row['ethnicity'], row['religion'],
                   row['occupation'], row['appearance'], row['socioeconomic_status'])
