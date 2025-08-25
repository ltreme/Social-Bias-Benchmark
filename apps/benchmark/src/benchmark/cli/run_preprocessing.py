import argparse

from tqdm import tqdm

from benchmark.llm.model import LLMModel
from benchmark.repository.enriched_persona import EnrichedPersonaRepository
from benchmark.repository.raw_persona import RawPersonaRepository
from benchmark.services.llm_attribute_filler import AttributeFiller


def generate_personas(
    model_name: str,
    mixed_precision: str = "fp16",
    load_in_4bit: bool = False,
    load_in_8bit: bool = False,
    no_quantization: bool = False,
) -> int:
    """
    Generates enriched personas using the LLM and saves them via PersonaWriter.
    Returns the number of processed personas.
    """
    llm = LLMModel(
        model_identifier=model_name,
        mixed_precision=mixed_precision,
        load_in_4bit=load_in_4bit,
        load_in_8bit=load_in_8bit,
        no_quantization=no_quantization,
    )
    raw_persona_repo = RawPersonaRepository()
    enriched_persona_repo = EnrichedPersonaRepository(model_name=model_name)
    attribute_filler = AttributeFiller(llm=llm)
    personas = raw_persona_repo.find_all()
    count = 0
    for persona in tqdm(personas, desc="Generating personas"):
        try:
            enriched_persona = attribute_filler.fill_attributes(persona)
            enriched_persona_repo.save(enriched_persona)
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
        help="Mixed precision (fp16, bf16, no).",
    )
    parser.add_argument(
        "--load_in_4bit",
        action="store_true",
        help="Aktiviere 4-bit Quantisierung (nf4).",
    )
    parser.add_argument(
        "--load_in_8bit",
        action="store_true",
        help="Aktiviere 8-bit Quantisierung.",
    )
    parser.add_argument(
        "--no_quantization",
        action="store_true",
        help="Erzwinge Laden ohne Quantisierung (überschreibt andere Quantisierungs-Flags).",
    )
    args = parser.parse_args()
    n = generate_personas(
        model_name=args.model_name,
        mixed_precision=args.mixed_precision,
        load_in_4bit=args.load_in_4bit,
        load_in_8bit=args.load_in_8bit,
        no_quantization=args.no_quantization,
    )
    print(f"{n} personas generated successfully.")


if __name__ == "__main__":
    main()
