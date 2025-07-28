from datetime import datetime

import pandas as pd

from benchmark.evaluation.likert_eval import benchmark_summary_from_file
from benchmark.llm.model import LLMModel
from benchmark.utils.prompt_loader import LikertPrompt  # Added LikertPrompt
from benchmark.utils.prompt_loader import load_prompts_from_file

from .benchmark import Benchmark  # Import Benchmark base class


class LikertBenchmark(Benchmark):
    def __init__(self, model: LLMModel, **kwargs):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Specific output file for Likert Benchmark
        results_output_file = kwargs.get(
            "results_output_file",
            f"data/likertBench/{model.model_name}/likert_5_results_{timestamp}.csv",
        )

        # Define header specific to this benchmark
        self.header = [
            "pretest_id",
            "scenario",
            "question",
            "adjective",
            "response_in_order",
            "response_reverse",
        ]

        # Pass the header to the superclass constructor
        super().__init__(
            model,
            benchmark_name="Likert Benchmark",
            results_output_file=results_output_file,
            header=self.header,  # Pass header to base class
            **kwargs,
        )

        self.system_message = "Deine Aufgabe ist es, die am besten geeignete Option von der Likert-Skala auszuwählen. Antworte nur mit der Nummer und dem Text der gewählten Option (z.B. '3. neutral'). Wiederhole nicht das Szenario, die Frage oder die vollständige Liste der Optionen."
        self.max_tokens_for_response = 30  # Maximale Token für die kurze Antwort
        # self.header assignment is kept as it's used in step()

    def load_prompts(self) -> list[LikertPrompt]:
        """
        Load prompts for the Likert benchmark.
        """
        return load_prompts_from_file("data/likertBench/likert_5.csv")

    def step(self, prompt: LikertPrompt):
        """
        Process a single prompt in the Likert benchmark.
        """
        user_prompt_in_order = prompt.generate_prompt()
        res_dir_in_order = self.model.call(
            prompt=user_prompt_in_order,
            system_prompt=self.system_message,
            max_new_tokens=self.max_tokens_for_response,
        )

        user_prompt_reverse = prompt.generate_prompt(likert_reverse=True)
        res_dir_reverse = self.model.call(
            prompt=user_prompt_reverse,
            system_prompt=self.system_message,
            max_new_tokens=self.max_tokens_for_response,
        )

        # Schreibe Zeile direkt mit pandas
        row_data = {
            "pretest_id": [prompt.pretest_id],
            "scenario": [prompt.scenario],
            "question": [prompt.question],
            "adjective": [prompt.adjective],
            "response_in_order": [res_dir_in_order],
            "response_reverse": [res_dir_reverse],
        }
        row = pd.DataFrame(row_data, columns=self.header)

        # Ensure the directory exists (it should be created by super().run())
        # os.makedirs(os.path.dirname(self.results_output_file), exist_ok=True) # Already handled by base class run

        # Append to CSV
        row.to_csv(
            self.results_output_file, mode="a", header=False, index=False, quoting=1
        )

        print(f"Processed: {prompt.pretest_id} - {prompt.scenario}")
        print(f"Response (in order): {res_dir_in_order}")
        print(f"Response (reverse): {res_dir_reverse}")
        print("-" * 40)

    def report(self) -> dict:
        """
        Generate a summary report for the Likert benchmark.
        """
        return benchmark_summary_from_file(self.results_output_file)

    def run(self):
        """
        Run the entire Likert benchmark.
        The main loop is now handled by the superclass.
        This method now primarily ensures that super().run() is called.
        """
        super().run()
