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
from typing import List, Optional

EXPERIMENT_PREFIX = "ai-explorer-eval"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
    
# Set the API key for openevals to use
os.environ["OPENAI_API_KEY"] = settings.llm_api_key.get_secret_value()

client = Client(api_key=settings.langsmith_api_key.get_secret_value())
dataset = get_or_create_dataset(client)

llm_orchestrator = LLMOrchestrator()

async def get_orchestrator_response(
    query: str, 
    account_id: Optional[str] = None, 
    session_id: Optional[str] = None, 
) -> str:
    """
    Helper function to collect the full response from the streaming LLM orchestrator.
    This mirrors the flow used in the chat endpoint.
    """
    response_parts = []
    
    try:
        # Use context manager for safe database session handling
        with get_db_session() as db:
            if account_id:
                logger.info(f"Processing evaluation request with account_id={account_id}")
            
            async for token in llm_orchestrator.stream_llm_response(
                query=query,
                account_id=account_id,
                session_id=session_id,
                db=db
            ):
                response_parts.append(token)
            
            # Explicit commit for any remaining uncommitted changes
            db.commit()
                
    except (ValidationError, ChatServiceError) as e:
        logger.error(f"Service error for session {session_id}: {e}")
        return f"Service error: {str(e)}"
    except LLMServiceError as e:
        logger.error(f"LLM service error for session {session_id}: {e}")
        return f"AI service temporarily unavailable. Please try again. Error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error processing evaluation for session {session_id}: {e}")
        if response_parts:
            return "".join(response_parts)
        else:
            return "Internal server error"
            
    return "".join(response_parts)

# Define the logic you want to evaluate inside a target function. 
# The SDK will automatically send the inputs from the dataset to your target function
def target(inputs: dict) -> dict:
    """
    Target function that mimics the exact flow of the chat endpoint.
    This ensures evaluations measure the agent's performance accurately.
    """
    question = inputs["question"]
    
    # Extract account_id from the question if it contains a wallet address
    account_id = None
    wallet_pattern = r'0\.0\.\d+'
    match = re.search(wallet_pattern, question)
    if match:
        account_id = match.group(0)
    
    # Generate a unique session_id for each evaluation
    session_id = f"eval_session_{hash(question) % 10000}"
    
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
)

# link will be provided to view the results in langsmith
print(experiment_results) 