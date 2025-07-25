from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT

# Use a prebuilt evaluator from openevals (https://github.com/langchain-ai/openevals)

def correctness_evaluator(model: str):
    """
    Returns an LLM judge evaluator that evaluates the correctness of the output.
    """
    
    evaluator = create_llm_as_judge(
        prompt=CORRECTNESS_PROMPT,
        model=f"openai:{model}",
        feedback_key="correctness",
    )
    
    def evaluate(inputs: dict, outputs: dict, reference_outputs: dict):
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