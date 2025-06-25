import yaml
import pandas as pd
from persona_generator.generator import PersonaGenerator
from persona_generator.name_sampler import NameSampler
from llm_handler.model import LLMModel

def main():
    # Load configuration
    with open("app/persona_generator/config.yaml", 'r') as f:
        config = yaml.safe_load(f)

    # Initialize LLM model if needed
    llm_model = None
    if config['name_mode'] == 'llm':
        # This is a placeholder for your actual LLM model initialization
        # You will need to replace this with your actual LLM loading logic
        llm_model = LLMModel(model_name="<your-model-name>") 

    # Initialize NameSampler
    name_sampler = NameSampler(mode=config['name_mode'], llm_model=llm_model)

    # Initialize PersonaGenerator
    distributions_path = "data/biasBench/distributions"
    persona_generator = PersonaGenerator(distributions_path, name_sampler)

    # Generate personas
    num_personas = config.get('num_personas', 100)
    personas = persona_generator.generate_personas(num_personas)

    # Convert to DataFrame
    df = persona_generator.to_dataframe(personas)

    # Save to file
    output_path = config.get('output_path', 'data/biasBench/personas_generated.csv')
    if config['output_format'] == 'parquet':
        output_path = output_path.replace('.csv', '.parquet')
        df.to_parquet(output_path, index=False)
    else:
        df.to_csv(output_path, index=False)

    print(f"Successfully generated {len(df)} personas and saved to {output_path}")

if __name__ == '__main__':
    main()
