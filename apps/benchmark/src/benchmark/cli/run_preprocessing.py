import argparse

from tqdm import tqdm

from benchmark.llm.model import LLMModel
from benchmark.repository.persona_reader import PersonaReader
from benchmark.repository.persona_writer import PersonaWriter
from benchmark.services.llm_attribute_filler import AttributeFiller


def generate_personas(model_name: str, mixed_precision: str = "fp16") -> int:
    """
    Generates enriched personas using the LLM and saves them via PersonaWriter.
    Returns the number of processed personas.
    """
    llm = LLMModel(model_identifier=model_name, mixed_precision=mixed_precision)
    reader = PersonaReader()
    writer = PersonaWriter(model_name=llm.model_identifier)
    attribute_filler = AttributeFiller(llm=llm)
    personas = reader.find_all()
    count = 0
    for persona in tqdm(personas, desc="Generating personas"):
        try:
            enriched_persona = attribute_filler.fill_attributes(persona)
            writer.savePersona(enriched_persona)
            count += 1
        except Exception as e:
            print(
                f"Error enriching persona {getattr(persona, 'uuid', repr(persona))}: {e}"
            )
    return count


def main():
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
    n = generate_personas(
        model_name=args.model_name, mixed_precision=args.mixed_precision
    )
    print(f"{n} personas generated successfully.")


if __name__ == "__main__":
    main()
