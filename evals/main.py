from langsmith import Client

from app.config import settings
from app.services.llm_orchestrator import LLMOrchestrator
from evals.evaluator import correctness_evaluator
from evals.dataset import get_or_create_dataset, DATASET_NAME

import asyncio
import os
import re

EXPERIMENT_PREFIX = "ai-explorer-eval"

# Set the API key for openevals based on provider
if settings.llm_provider == "openai":
    os.environ["OPENAI_API_KEY"] = settings.llm_api_key.get_secret_value()
elif settings.llm_provider == "google_genai":
    os.environ["GOOGLE_API_KEY"] = settings.llm_api_key.get_secret_value()

client = Client(api_key=settings.langsmith_api_key.get_secret_value())
dataset = get_or_create_dataset(client)
llm_orchestrator = LLMOrchestrator()

async def get_orchestrator_response(query: str, account_id: str = None) -> str:
    """
    Helper function to collect the full response from the streaming LLM orchestrator.
    """
    response_parts = []
    try:
        async for token in llm_orchestrator.stream_llm_response(
            query=query,
            account_id=account_id,
            conversation_history=None,
            session_id=None
        ):
            response_parts.append(token)
    except Exception as e:
        print(f"Warning: Error during orchestrator response: {e}")
        if response_parts:
            return "".join(response_parts)
        else:
            return "Error: Unable to get response from orchestrator"
    return "".join(response_parts)

# Define the logic you want to evaluate inside a target function. 
# The SDK will automatically send the inputs from the dataset to your target function
def target(inputs: dict) -> dict:
    # Extract account_id from the question if it contains a wallet address
    question = inputs["question"]
    account_id = None
    wallet_pattern = r'0\.0\.\d+'
    match = re.search(wallet_pattern, question)
    if match:
        account_id = match.group(0)
    
    # Use asyncio to run the async orchestrator
    response = asyncio.run(get_orchestrator_response(question, account_id))
    
    return { "answer": response }

experiment_results = client.evaluate(
    target,
    data=DATASET_NAME,
    evaluators=[
                    correctness_evaluator(model=settings.llm_model),
        # multiple evaluators can be added here
    ],
    experiment_prefix=EXPERIMENT_PREFIX,
    max_concurrency=2,
)

# link will be provided to view the results in langsmith
print(experiment_results) 