import argparse

from benchmark.benchmarks.bias_benchmark import BiasBenchmark
from benchmark.llm.hf_model import HuggingFaceLLM

# from benchmark.llm.dummy_llm import DummyLLM


def main(model_identifier: str):
    llm = HuggingFaceLLM(
        model_identifier=model_identifier
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
    
    args = parser.parse_args()
    main(model_identifier=args.model_name)
