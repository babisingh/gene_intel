"""
Tests for app/agents/llm_reply.py: telling a declined reply apart from an
empty one. No Claude calls; the replies are stand-ins with the SDK's fields.
"""

from types import SimpleNamespace

import pytest

from app.agents.llm_reply import LLMRefusalError, reply_text

CYPHER = "MATCH (g:Gene) RETURN g AS gene LIMIT 1"


def reply(stop_reason, *texts):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text) for text in texts],
    )


def test_reply_text_returns_the_text():
    assert reply_text(reply("end_turn", CYPHER)) == CYPHER


@pytest.mark.parametrize("texts", [(), ("MATCH (g:Gene) WHERE",)])
def test_a_declined_reply_raises_even_with_part_of_an_answer(texts):
    with pytest.raises(LLMRefusalError):
        reply_text(reply("refusal", *texts))


def test_an_empty_reply_for_another_reason_raises_value_error():
    with pytest.raises(ValueError, match=r"stop_reason=max_tokens"):
        reply_text(reply("max_tokens"))
