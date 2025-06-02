import pandas as pd

def generate_likert_5(adjective: str) -> list[str]:
    return [
        f"gar nicht {adjective}",
        f"eher nicht {adjective}",
        "neutral",
        f"eher {adjective}",
        f"sehr {adjective}"
    ]

class LikertPrompt:
    def __init__(self, pretest_id: str, scenario: str, question: str, adjective: str):
        self.pretest_id = pretest_id
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
        return f"LikertPrompt(pretest_id={self.pretest_id}, scenario={self.scenario}, question={self.question}, adjective={self.adjective})"
    
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