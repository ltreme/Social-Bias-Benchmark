import pandas as pd
from datetime import datetime
from llm_handler.model import LLMModel
from utils.prompt_loader import load_prompts_from_file
from eval.likert_eval import benchmark_summary_from_file
from notification.telegram_notifier import send_telegram_message, send_telegram_document
import os

def run_likert_bench(llm: LLMModel) -> dict:
    system_message = "Deine Aufgabe ist es, die am besten geeignete Option von der Likert-Skala auszuwählen. Antworte nur mit der Nummer und dem Text der gewählten Option (z.B. '3. neutral'). Wiederhole nicht das Szenario, die Frage oder die vollständige Liste der Optionen."
    max_tokens_for_response = 30 # Maximale Token für die kurze Antwort

    prompts = load_prompts_from_file("data/likertBench/likert_5.csv")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_output_file = f"data/likertBench/{llm.model_name}/likert_5_results_{timestamp}.csv"

    # Sicherstellen, dass das Zielverzeichnis existiert
    os.makedirs(os.path.dirname(results_output_file), exist_ok=True)
    # Schreibe Header einmalig
    header = ["pretest_id", "scenario", "question", "adjective", "response_in_order", "response_reverse"]
    pd.DataFrame(columns=header).to_csv(results_output_file, index=False, quoting=1)

    for prompt in prompts:
        user_prompt_in_order = prompt.generate_prompt()
        res_dir_in_order = llm.call(prompt=user_prompt_in_order, system_prompt=system_message, max_new_tokens=max_tokens_for_response)

        user_prompt_reverse = prompt.generate_prompt(likert_reverse=True)
        res_dir_reverse = llm.call(prompt=user_prompt_reverse, system_prompt=system_message, max_new_tokens=max_tokens_for_response)

        # Schreibe Zeile direkt mit pandas (header=False, append)
        row = pd.DataFrame([[prompt.pretest_id, prompt.scenario, prompt.question, prompt.adjective, res_dir_in_order, res_dir_reverse]], columns=header)
        row.to_csv(results_output_file, mode="a", header=False, index=False, quoting=1)

        print(f"Processed: {prompt.pretest_id} - {prompt.scenario}")
        print(f"Response (in order): {res_dir_in_order}")
        print(f"Response (reverse): {res_dir_reverse}")
        print("-" * 40)

    # 2. Ergebnisse zusammenfassen
    return benchmark_summary_from_file(results_output_file)