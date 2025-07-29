from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT
from typing import Callable, Dict, Any

# Use a prebuilt evaluator from openevals (https://github.com/langchain-ai/openevals)

def correctness_evaluator(model: str) -> Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any]], Any]:
    """
    Returns an LLM judge evaluator that evaluates the correctness of the output.
    """
    
    evaluator = create_llm_as_judge(
        prompt=CORRECTNESS_PROMPT,
        model=f"openai:{model}",
        feedback_key="correctness",
    )
    
    def evaluate(inputs: Dict[str, Any], outputs: Dict[str, Any], reference_outputs: Dict[str, Any]) -> Any:
        """
        The actual evaluation function that gets called by LangSmith.
        """
        eval_result = evaluator(
            inputs=inputs,
            outputs=outputs,
            reference_outputs=reference_outputs
        )
        return eval_result
    
    return evaluate