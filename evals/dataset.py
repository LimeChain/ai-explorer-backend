from langsmith import Client
from typing import List, Dict, Any
import csv
import os


DATASET_NAME = "Dataset - V1"


def load_examples_from_csv(csv_file: str = "examples.csv") -> List[Dict]:
    """
    Load examples from a CSV file with 'Question' and 'Example answer' columns.
    """
    # Get the directory where this module is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(current_dir, csv_file)
    
    examples = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter=';')
            for row in reader:
                # Skip rows with empty questions
                if not row.get("Question", "").strip():
                    continue
                    
                example = {
                    "inputs": {"question": row["Question"]},
                    "outputs": {"answer": row["Answer"]}
                }
                examples.append(example)
        
        print(f"Loaded {len(examples)} examples from {csv_file}")
        
    except FileNotFoundError:
        print(f"Warning: CSV file {csv_path} not found. Using empty examples list.")
        return []
    except Exception as e:
        print(f"Error loading examples from CSV: {e}")
        return []
    
    return examples

_EXAMPLES = None
def get_examples() -> List[Dict[str, Any]]:
    global _EXAMPLES
    if _EXAMPLES is None:
        _EXAMPLES = load_examples_from_csv()
    return _EXAMPLES

def get_or_create_dataset(client: Client, dataset_name: str = DATASET_NAME, examples: List[Dict] = get_examples()) -> Any:
    """
    Get an existing dataset by name or create a new one if it doesn't exist.
    If creating a new dataset, it will be populated with examples.
    """
    if not client.has_dataset(dataset_name=dataset_name):
        print(f"Creating new dataset: {dataset_name}")
        dataset = client.create_dataset(
            dataset_name=dataset_name, 
            description="A dataset for AI explorer in LangSmith."
        )
        client.create_examples(
            dataset_id=dataset.id,
            examples=examples
        )
        print(f"Added {len(examples)} examples to new dataset")
    else:
        print(f"Using existing dataset: {dataset_name}")
        datasets = list(client.list_datasets(dataset_name=dataset_name))
        if not datasets:
            raise ValueError(f"Dataset {dataset_name} not found")
        if len(datasets) > 1:
            # Filter for exact match
            exact_matches = [d for d in datasets if d.name == dataset_name]
            if len(exact_matches) != 1:
                raise ValueError(f"Multiple datasets found for name '{dataset_name}'")
            dataset = exact_matches[0]
        else:
            dataset = datasets[0]
        
        existing_examples = list(client.list_examples(dataset_id=dataset.id))
        if not existing_examples:
            client.create_examples(dataset_id=dataset.id, examples=examples)
            print(f"Added {len(examples)} examples to existing dataset")
        else:
            print(f"Dataset already has {len(existing_examples)} examples")
    
    return dataset
