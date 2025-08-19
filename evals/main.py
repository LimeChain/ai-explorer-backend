from langsmith import Client

from app.config import settings
from app.services.llm_orchestrator import LLMOrchestrator
from app.db.session import get_db_session
from app.schemas.chat import ChatMessage
from app.exceptions import ChatServiceError, ValidationError, LLMServiceError
from evals.evaluator import correctness_evaluator
from evals.dataset import get_or_create_dataset, DATASET_NAME

import asyncio
import logging
import os
import re
import uuid
from typing import List, Optional

EXPERIMENT_PREFIX = "gpt-4.1"

NETWORK = "testnet"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_PROVIDER_ALIASES = {
    "openai": "OPENAI_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",

}

key_name = _PROVIDER_ALIASES.get(settings.judge_llm_provider.lower())
if not key_name:
    raise ValueError(
        f"Invalid judge_llm_provider '{settings.judge_llm_provider}'. "
        f"Supported providers: {', '.join(sorted(_PROVIDER_ALIASES.keys()))}"
    )
    
# Set the API key for openevals to use
os.environ[key_name] = settings.judge_llm_api_key.get_secret_value()

client = Client(api_key=settings.langsmith_api_key.get_secret_value())
dataset = get_or_create_dataset(client)

async def get_orchestrator_response(
    query: str, 
    account_id: Optional[str] = None, 
    session_id: Optional[uuid.UUID] = None, 
) -> str:
    """
    Helper function to collect the full response from the streaming LLM orchestrator.
    This mirrors the flow used in the chat endpoint.
    """
    response_parts = []
    
    try:
        llm_orchestrator = LLMOrchestrator(enable_persistence=False)
        # Use context manager for safe database session handling
        with get_db_session() as db:
            if account_id:
                logger.info("Processing evaluation request with account_id=%s", account_id)
            
            async for token in llm_orchestrator.stream_llm_response(
                query=query,
                network=NETWORK,
                account_id=account_id,
                session_id=session_id,
                db=db
            ):
                response_parts.append(token)
            
            # Explicit commit for any remaining uncommitted changes
            db.commit()
                
    except (ValidationError, ChatServiceError) as e:
        logger.error("Service error for session %s: %s", session_id, e)
        return f"Service error: {str(e)}"
    except LLMServiceError as e:
        logger.error("LLM service error for session %s: %s", session_id, e)
        return f"AI service temporarily unavailable. Please try again. Error: {str(e)}"
    except Exception as e:
        logger.error("Unexpected error processing evaluation for session %s: %s", session_id, e)
        if response_parts:
            return "".join(response_parts)
        else:
            return "Internal server error"
            
    return "".join(response_parts)

# Define the logic you want to evaluate inside a target function. 
# The SDK will automatically send the inputs from the dataset to your target function
def get_account_id(inputs: dict) -> Optional[str]:
    """Extract account_id from inputs, supporting both direct and regex extraction methods."""
    # First try direct account_id field (production style)
    if "account_id" in inputs and inputs["account_id"]:
        return inputs["account_id"]
    
    # Fall back to regex extraction for backward compatibility
    question = inputs.get("question", "")
    wallet_pattern = r'0\.0\.\d+'
    match = re.search(wallet_pattern, question)
    return match.group(0) if match else None


def target(inputs: dict) -> dict:
    """
    Target function that mimics the exact flow of the chat endpoint.
    This ensures evaluations measure the agent's performance accurately.
    Supports both direct account_id and regex extraction for flexibility.
    """
    question = inputs["question"]
    account_id = get_account_id(inputs)
    session_id = uuid.uuid4()
    
    response = asyncio.run(get_orchestrator_response(
        query=question,
        account_id=account_id,
        session_id=session_id,
    ))
    return {"answer": response}

experiment_results = client.evaluate(
    target,
    data=DATASET_NAME,
    evaluators=[
        correctness_evaluator(),
        # multiple evaluators can be added here
    ],
    experiment_prefix=EXPERIMENT_PREFIX,
    max_concurrency=1,
    num_repetitions=1,
    blocking=True
)

# link will be provided to view the results in langsmith
print(experiment_results) 