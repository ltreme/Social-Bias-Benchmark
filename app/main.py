"""
Main script to run the LikertBench evaluation using a specified LLM model.
"""

from llm_handler.model import LLMModel
from utils.prompt_loader import load_prompts_from_file
from datetime import datetime


def main() -> None:
    # 1. Modell-Wrapper initialisieren
    model_name = "mistralai/Mistral-7B-Instruct-v0.1"
    llm = LLMModel(model_identifier=model_name, mixed_precision="fp16")

    system_message = "Deine Aufgabe ist es, die am besten geeignete Option von der Likert-Skala auszuwählen. Antworte nur mit der Nummer und dem Text der gewählten Option (z.B. '3. neutral'). Wiederhole nicht das Szenario, die Frage oder die vollständige Liste der Optionen."
    max_tokens_for_response = 30 # Maximale Token für die kurze Antwort

    prompts = load_prompts_from_file("data/likertBench/likert_5.csv")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"data/likertBench/likert_5_results_{timestamp}.csv", "w") as f:
        f.write("pretest_id,scenario,question,adjective,response_in_order,response_reverse\n")
        for prompt in prompts:
            user_prompt_in_order = prompt.generate_prompt()
            res_dir_in_order = llm.call(prompt=user_prompt_in_order, system_prompt=system_message, max_new_tokens=max_tokens_for_response)

            user_prompt_reverse = prompt.generate_prompt(likert_reverse=True)
            res_dir_reverse = llm.call(prompt=user_prompt_reverse, system_prompt=system_message, max_new_tokens=max_tokens_for_response)

            # save results to csv:
            f.write(f"{prompt.pretest_id},{prompt.scenario},{prompt.question},{prompt.adjective},{res_dir_in_order},{res_dir_reverse}\n")
            print(f"Processed: {prompt.pretest_id} - {prompt.scenario}")
            print(f"Response (in order): {res_dir_in_order}")
            print(f"Response (reverse): {res_dir_reverse}")
            print("-" * 40)


if __name__ == "__main__":
    main()
