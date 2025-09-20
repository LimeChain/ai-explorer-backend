from openevals.llm import create_llm_as_judge
# from openevals.prompts import CORRECTNESS_PROMPT
from typing import Callable, Dict, Any

CORRECTNESS_PROMPT = """
You are an expert data labeler evaluating model outputs for correctness. 
Your task is to assign a score based on the following criteria:

<Rubric>
  A correct answer:
  - Provides accurate information
  - Contains no factual errors
  - Addresses all parts of the question

  When scoring, you should penalize:
  - Factual errors or inaccuracies
  - Incomplete or partial answers
  - Misleading or ambiguous statements
  - Logical inconsistencies
  - Missing key information
</Rubric>

<Evaluation Criteria>
  1. Factual Accuracy - Are the core facts correct?
  2. Question Answering - Does it answer what was asked?
  3. Key Information - Are the essential details present and correct?

  IMPORTANT NOTES:
  - Additional detail beyond the reference is GOOD, not bad
  - Focus on whether core facts match, not exact wording
  - Simple questions may have simple reference answers and that's fine
  - Extra context and explanation should not be penalized
</Evaluation Criteria>

<Scoring Scale>
  Return a score between 0.0 and 1.0:
  - 1.0: Perfect - Correct, accurate, and addresses the core question
  - 0.8-0.9: Very Good - Correct with minor issues
  - 0.6-0.7: Good - Mostly correct but missing some important information
  - 0.4-0.5: Fair - Partially correct but has some errors
  - 0.2-0.3: Poor - Major errors or misunderstandings
  - 0.0-0.1: Incorrect - Fundamentally wrong or completely off-topic
</Scoring Scale>

<Instructions>
  - Carefully read the input, the reference output, and the output
  - Check for factual accuracy and whether it answers the question
  - Focus on correctness of information rather than style or verbosity
  - Additional detail is valuable, not a penalty
</Instructions>

<Reminder>
  The goal is to evaluate factual correctness of the response,
  The actual response may include more information that the expected output which is fine.
</Reminder>

<input>
{inputs}
</input>

<output>
{outputs}
</output>

Use the reference outputs below to help you evaluate the correctness of the response:

<reference_outputs>
{reference_outputs}
</reference_outputs>
"""

from app.settings import settings

# Use a prebuilt evaluator from openevals (https://github.com/langchain-ai/openevals)

def correctness_evaluator() -> Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any]], Any]:
    """
    Returns an LLM judge evaluator that evaluates the correctness of the output.
    """
    
    evaluator = create_llm_as_judge(
        prompt=CORRECTNESS_PROMPT,
        model=f"{settings.judge_llm_provider}:{settings.judge_llm_model}",
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