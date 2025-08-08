import argparse

from benchmark.benchmarks.bias_benchmark import BiasBenchmark
from benchmark.llm.model import LLMModel

# from benchmark.llm.dummy_llm import DummyLLM


def main(model_identifier: str, mixed_precision: str):
    llm = LLMModel(
        model_identifier=model_identifier,
        mixed_precision=mixed_precision,
    )
    # llm = DummyLLM(
    #     model_identifier=model_identifier,
    #     mixed_precision=mixed_precision,
    #     max_new_tokens=30
    # )
    benchmark = BiasBenchmark(model=llm)
    benchmark.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate personas using LLM.")
    parser.add_argument(
        "--model_name",
        type=str,
        default="mistralai/Mistral-Small-24B-Instruct-2501",
        help="Identifier of the LLM model to use for persona generation.",
    )
    parser.add_argument(
        "--mixed_precision",
        type=str,
        default="fp16",
        help="Mixed precision to use for the LLM model (e.g. 'fp16', 'bf16', 'no')",
    )
    args = parser.parse_args()
    main(model_identifier=args.model_name, mixed_precision=args.mixed_precision)
