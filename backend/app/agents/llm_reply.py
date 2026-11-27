"""
Reading Claude's replies.

Claude can decline a request. The reply then has stop_reason "refusal" and
holds no text, or only the start of an answer, so it must not be used as a
query or an explanation. reply_text raises LLMRefusalError for it, so callers
can tell a declined question apart from other failures.

Connected to:
  - agent_a_semantic.py, agent_c_explainer.py: read every reply through reply_text
  - graph_workflow.py: a declined question ends the search with a 422
  - api/gene.py: a declined explanation still returns the gene
"""


class LLMRefusalError(Exception):
    """Claude declined to answer (stop_reason "refusal")."""


def reply_text(response) -> str:
    """
    Return the text of a Claude reply.

    Raises LLMRefusalError when Claude declined, even if part of an answer
    came back, and ValueError when the reply holds no content for any other
    reason.
    """
    if response.stop_reason == "refusal":
        raise LLMRefusalError("Claude declined to answer (stop_reason=refusal)")
    if not response.content:
        raise ValueError(f"Empty response from LLM (stop_reason={response.stop_reason})")
    return response.content[0].text
