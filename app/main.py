"""
Main script to run the LikertBench evaluation using a specified LLM model.
"""

from llm_handler.model import LLMModel
from utils.prompt_loader import LikertPrompt, load_prompts_from_file
from datetime import datetime


def main() -> None:
    # 1. Modell-Wrapper initialisieren
    model_name = "mistralai/Mistral-7B-Instruct-v0.1"
    llm = LLMModel(model_identifier=model_name, mixed_precision="fp16")


    prompts = load_prompts_from_file("data/likertBench/likert_5.csv")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"data/likertBench/likert_5_results_{timestamp}.csv", "w") as f:
        f.write("pretest_id,scenario,question,adjective,response_in_order,response_reverse\n")
        for prompt in prompts:
            res_dir_in_order = llm.call(prompt.generate_prompt())
            res_dir_reverse = llm.call(prompt.generate_prompt(likert_reverse=True))

            # save results to csv:
            f.write(f"{prompt.pretest_id},{prompt.scenario},{prompt.question},{prompt.adjective},{res_dir_in_order},{res_dir_reverse}\n")
            print(f"Processed: {prompt.pretest_id} - {prompt.scenario}")
            print(f"Response (in order): {res_dir_in_order}")
            print(f"Response (reverse): {res_dir_reverse}")
            print("-" * 40)


if __name__ == "__main__":
    main()
