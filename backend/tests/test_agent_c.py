"""
Tests for the gene values Agent C is given. They must say which transcript
they describe, and sums over all transcripts (what a graph built before
canonical_source existed holds) must be labelled as sums. No Claude calls.
"""

from app.agents import agent_c_explainer
from app.agents.agent_c_explainer import describe_gene_values, format_results_for_llm

BRCA2 = {
    "gene_id": "ENSG00000139618", "name": "BRCA2",
    "cds_length": 10254, "exon_count": 27, "utr_cds_ratio": 0.4,
    "canonical_transcript_id": "ENST00000380152",
    "canonical_source": "Ensembl_canonical",
}
# TTN as the graph before canonical_source stored it: sums over its isoforms
OLD_TTN = {
    "gene_id": "ENSG00000155657", "name": "TTN",
    "cds_length": 577563, "exon_count": 1700, "utr_cds_ratio": 0.0127,
}
# E. coli genes have no transcripts in the graph
THRA = {"gene_id": "b0002", "name": "thrA", "cds_length": 0, "exon_count": 0,
        "utr_cds_ratio": None}


def test_canonical_values_name_their_transcript_and_protein_length():
    text = describe_gene_values(BRCA2)
    assert "CDS length: 10254 bp (about 3418 amino acids)" in text
    assert "Exon count: 27" in text
    assert "ENST00000380152, its canonical transcript" in text
    assert "summed" not in text


def test_a_fallback_transcript_says_how_it_was_chosen():
    text = describe_gene_values({**BRCA2, "canonical_source": "longest_cds"})
    assert "the transcript with the longest coding sequence" in text


def test_sums_from_an_older_graph_are_labelled_as_sums():
    text = describe_gene_values(OLD_TTN)
    assert "summed over all of the gene's transcripts: 577563 bp" in text
    assert "Do not convert the CDS total into a protein length" in text
    assert "amino acids" not in text


def test_a_gene_without_transcripts_has_no_values():
    text = describe_gene_values(THRA)
    assert "not available" in text
    assert "0 bp" not in text


def test_the_results_summary_labels_every_gene():
    summary = format_results_for_llm([
        {**BRCA2, "species": "9606", "domains": []},
        {**OLD_TTN, "species": "9606", "domains": []},
        {**THRA, "species": "511145", "domains": []},
    ])
    lines = summary.splitlines()
    assert "CDS: 10254 bp (canonical transcript)" in lines[0]
    assert "CDS: 577563 bp (summed over all transcripts)" in lines[1]
    assert "CDS: not available" in lines[2]
    assert "do not convert them into protein lengths" in summary


def test_a_summary_without_sums_has_no_warning():
    summary = format_results_for_llm([{**BRCA2, "species": "9606", "domains": []}])
    assert "summed" not in summary


def test_the_single_gene_prompt_carries_the_described_values(monkeypatch):
    sent = {}

    class FakeMessages:
        def create(self, **kwargs):
            sent.update(kwargs)
            return object()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(agent_c_explainer, "client", FakeClient())
    monkeypatch.setattr(agent_c_explainer, "reply_text", lambda response: "explanation")

    assert agent_c_explainer.explain_single_gene(dict(BRCA2)) == "explanation"
    assert describe_gene_values(BRCA2) in sent["messages"][0]["content"]
