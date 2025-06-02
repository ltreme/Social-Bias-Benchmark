from utils.prompt_loader import load_prompts_from_file, LikertPrompt

prompts = load_prompts_from_file("data/likertBench/likert_5.csv")

for prompt in prompts:
    print(prompt)
    print(prompt.generate_prompt())
    print(prompt.generate_prompt(likert_reverse=True))
    print("-" * 40)