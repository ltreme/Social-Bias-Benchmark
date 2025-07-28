import os
from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd

from benchmark.llm.model import LLMModel
from benchmark.utils.prompt_loader import LikertPrompt


class Benchmark(ABC):
    def __init__(self, model: LLMModel, **kwargs):
        self.model = model
        self.benchmark_name = kwargs.get("benchmark_name", "Unknown")
        snake_case_name = self.benchmark_name.lower().replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results_output_file = kwargs.get(
            "results_output_file",
            f"data/output/{snake_case_name}/results_{timestamp}.csv",
        )
        self.prompts = []  # Initialize prompts list
        self.header = kwargs.get("header", None)  # Accept header in constructor

    def run(self):
        print(f"Running {self.benchmark_name} benchmark on {self.model.model_name}")

        # Sicherstellen, dass das Ausgabeverzeichnis existiert
        os.makedirs(os.path.dirname(self.results_output_file), exist_ok=True)

        # Schreibe Header, falls vorhanden
        if self.header:
            pd.DataFrame(columns=self.header).to_csv(
                self.results_output_file, index=False, quoting=1
            )

        self.prompts = self.load_prompts()
        print(f"Loaded {len(self.prompts)} prompts for the benchmark.")

        for prompt in self.prompts:
            self.step(prompt)

    @abstractmethod
    def step(self, prompt: LikertPrompt):
        """
        Process a single prompt in the benchmark.
        This method should be overridden in subclasses to implement specific processing logic.
        :param prompt: The LikertPrompt to process.
        """
        pass

    @abstractmethod
    def report(self) -> dict:
        pass

    @abstractmethod
    def load_prompts(self) -> list:
        """
        Load prompts for the benchmark.
        This method should be overridden in subclasses to provide specific prompts.
        """
        pass
